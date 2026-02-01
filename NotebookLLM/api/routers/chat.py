from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import sys
import os
import tempfile
import time
import logging
import json
import asyncio
from ..models.events import SSEEvent

logger = logging.getLogger(__name__)

_currentDir = os.path.dirname(os.path.abspath(__file__))
_projectRoot = os.path.join(_currentDir, '..', '..')
if _projectRoot not in sys.path:
    sys.path.insert(0, _projectRoot)

from api.models.chat import ChatRequest, ChatResponse, ContextRequest, ContextResponse
from api.services.agentService import AgentService
from api.services.eventQueue import get_event_queue

router = APIRouter(prefix="/api/agent", tags=["agent"])

agentService = AgentService()
event_queue = get_event_queue()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Process chat message"""
    try:
        result = agentService.chat(
            message=request.message,
            sources=[s.dict() for s in request.sources] if request.sources else [],
            sessionId=request.sessionId
        )
        return ChatResponse(**result)
    except Exception as e:
        return ChatResponse(
            status='error',
            result=None,
            error=str(e)
        )


@router.post("/session", response_model=Dict[str, Any])
async def createSession(userId: str = "default"):
    """Create new session"""
    try:
        result = agentService.createSession(userId)
        if result.get('status') == 'success':
            return result
        else:
            return {
                'status': 'error',
                'sessionId': None,
                'error': result.get('error', 'Failed to create session')
            }
    except Exception as e:
        import traceback
        logger.error(f"Session creation error: {e}\n{traceback.format_exc()}")
        return {
            'status': 'error',
            'sessionId': None,
            'error': f"Failed to create session: {str(e)}"
        }
@router.get("/tools", response_model=Dict[str, Any])
async def getAvailableTools():
    """Get available agent tools"""
    try:
        tools = agentService.getAvailableTools()
        return {
            'status': 'success',
            'tools': tools
        }
    except Exception as e:
        return {
            'status': 'error',
            'tools': [],
            'error': str(e)
        }


@router.get("/context/{sessionId}", response_model=ContextResponse)
async def getContext(sessionId: str):
    """Get active context"""
    result = agentService.getContext(sessionId)
    return ContextResponse(**result)


@router.post("/context", response_model=ContextResponse)
async def addContext(request: ContextRequest):
    """Add source to context"""
    result = agentService.addContext(
        sessionId=request.sessionId,
        source=request.source.dict()
    )
    return ContextResponse(**result)



@router.delete("/context/{sessionId}/{sourceId}", response_model=ContextResponse)
async def removeContext(sessionId: str, sourceId: str):
    """Remove source from context"""
    result = agentService.removeContext(sessionId, sourceId)
    return ContextResponse(**result)


@router.get("/stream/{sessionId}")
async def stream_agent_events(sessionId: str):
    """
    SSE endpoint for real-time agent reasoning events.
    
    Streams events as they happen:
    - thought: Agent's reasoning thoughts
    - tool_start: Tool execution started
    - tool_complete: Tool execution finished
    - complete: Task completed
    - error: Error occurred
    """
    async def event_generator():
        """Generate SSE events from queue"""
        try:
            # Send initial connection event
            yield f"data: {json.dumps({'type': 'connected', 'sessionId': sessionId})}\n\n"
            
            # Keep connection alive with periodic heartbeats
            last_heartbeat = time.time()
            heartbeat_interval = 30  # seconds
            
            while True:
                event = await event_queue.get_event(sessionId, timeout=1.0)
                
                if event:
                    # Send event as SSE
                    yield f"data: {json.dumps(event)}\n\n"
                    last_heartbeat = time.time()
                else:
                    # Timeout - send heartbeat if needed
                    now = time.time()
                    if now - last_heartbeat >= heartbeat_interval:
                        yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': now})}\n\n"
                        last_heartbeat = now
                        
        except asyncio.CancelledError:
            logger.info(f"SSE stream cancelled for session {sessionId}")
        except Exception as e:
            logger.error(f"Error in SSE stream for session {sessionId}: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@router.post("/isms", response_model=Dict[str, Any])
async def ismsOperation(request: Dict[str, Any]):
    """Direct ISMS operation - bypasses pattern matching for efficiency"""
    try:
        from api.services.agentService import AgentService
        agentService = AgentService()
        
        agent = agentService.agentBridge.agent
        if not agent:
            return {
                'status': 'error',
                'result': None,
                'error': 'Agent not initialized'
            }
        
        if not hasattr(agent, '_ismsController') or not agent._ismsController:
            # Import from Agentic Framework
            import sys
            agenticFrameworkPath = os.path.join(_projectRoot, '..', 'Agentic Framework')
            if agenticFrameworkPath not in sys.path:
                sys.path.insert(0, agenticFrameworkPath)
            
            from agents.ismsController import ISMSController
            from api.services.eventQueue import get_event_queue
            
            veriniceTool = getattr(agent, '_veriniceTool', None)
            if not veriniceTool:
                return {
                    'status': 'error',
                    'result': None,
                    'error': 'ISMS client not available. Please check your configuration.'
                }
            llmTool = getattr(agent, '_llmTool', None)
            
            sessionId = request.get('sessionId') or agent.state.get('_currentSessionId')
            
            event_callback = None
            if sessionId:
                event_queue = get_event_queue()
                def create_event_callback(sid: str):
                    """Create event callback that pushes to event queue"""
                    def callback(event_type: str, data: Dict[str, Any]):
                        """Callback function that agents call to emit events"""
                        # Map event types to match frontend expectations
                        mapped_type = event_type
                        if event_type == 'tool_call':
                            mapped_type = 'tool_start'
                        elif event_type == 'tool_result':
                            mapped_type = 'tool_complete'
                        
                        event = SSEEvent(
                            type=mapped_type,
                            data=data if isinstance(data, dict) else {'content': str(data)},
                            timestamp=time.time()
                        )
                        event_queue.push_event(sid, event)
                    return callback
                event_callback = create_event_callback(sessionId)
            
            agent._ismsController = ISMSController(veriniceTool, llmTool, event_callback)
        
        # Extract operation parameters
        operation = request.get('operation')
        objectType = request.get('objectType')
        name = request.get('name')
        objectId = request.get('id')
        field = request.get('field')
        value = request.get('value')
        
        # Build message for handler
        message = f"{operation} {objectType}"
        if name:
            message += f" {name}"
        elif objectId:
            message += f" {objectId}"
        if field and value:
            message += f" {field} {value}"
        
        result = agent._ismsController.execute(message)
        
        # Format response
        if result.get('status') == 'success':
            responseData = result.get('result', '')
            return {
                'status': 'success',
                'result': responseData,
                'type': 'isms_operation'
            }
        else:
            return {
                'status': 'error',
                'result': None,
                'error': result.get('error', 'Unknown error')
            }
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            'status': 'error',
            'result': None,
            'error': str(e)
        }


