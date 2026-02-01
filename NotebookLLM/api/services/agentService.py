"""Agent service - main service layer for agent operations"""
from typing import Dict, Any, List
import sys
import os
import logging

logger = logging.getLogger(__name__)

_currentDir = os.path.dirname(os.path.abspath(__file__))
_projectRoot = os.path.join(_currentDir, '..', '..')
if _projectRoot not in sys.path:
    sys.path.insert(0, _projectRoot)

from integration.agentBridge import AgentBridge
from integration.contextMapper import ContextMapper
from api.services.sessionService import SessionService
from api.services.eventQueue import get_event_queue


class AgentService:
    """Main service for agent operations"""
    
    def __init__(self):
        self.sessionService = SessionService()
        self.contextMapper = ContextMapper()
        self.agentBridge = None  # Lazy initialization - don't initialize at startup
        # AgentBridge will be initialized on first use (in chat method)
        # This ensures session creation works even if AgentBridge fails to initialize
    
    def chat(self, message: str, sources: List[Dict[str, Any]], sessionId: str) -> Dict[str, Any]:
        """Process chat message"""
        session = self.sessionService.getSession(sessionId)
        if not session:
            return {
                'status': 'error',
                'result': None,
                'error': 'Invalid session'
            }
        
        # Lazy initialize AgentBridge if not already initialized
        if self.agentBridge is None:
            try:
                self.agentBridge = AgentBridge()
                if not self.agentBridge.initialize():
                    logger.error("AgentBridge initialization returned False")
                    return {
                        'status': 'error',
                        'result': None,
                        'error': 'Agent initialization failed'
                    }
            except Exception as e:
                logger.error(f"Failed to initialize AgentBridge: {e}")
                return {
                    'status': 'error',
                    'result': None,
                    'error': f'Agent initialization failed: {str(e)}'
                }
        
        # CRITICAL: Only update session context if sources have actual data
        # Frontend may send empty sources with data: {}, which would overwrite real data
        if sources:
            hasRealData = any(
                source.get('data') and 
                (isinstance(source.get('data'), dict) and (
                    'sheets' in source.get('data', {}) or 
                    'text' in source.get('data', {}) or 
                    'pages' in source.get('data', {}) or
                    'paragraphs' in source.get('data', {}) or
                    len([k for k in source.get('data', {}).keys() if k not in ['fileName', 'fileType']]) > 0
                )) or
                (not isinstance(source.get('data'), dict) and source.get('data') is not None)
                for source in sources
            )
            if hasRealData:
                self.sessionService.setContext(sessionId, sources)
            # If sources are empty/placeholder, keep existing session context (don't overwrite)
        
        activeSources = session.get('activeContext', [])
        contextDict = self.contextMapper.buildContext(activeSources)
        # Extract context string and metadata - contextDict is now a dict with metadata
        context = contextDict.get('context', '')
        # Use contextDict directly as context (it has all metadata)
        context = contextDict
        
        agent = self.agentBridge.agent
        
        # CRITICAL FIX: Implement per-session state management
        # Load agent state from session (isolates state per session)
        if 'agentState' not in session:
            session['agentState'] = {}
        
        # Restore agent state from this specific session (deep copy to avoid reference issues)
        if agent:
            agent.state = dict(session.get('agentState', {}))
            # Store sessionId in agent state for event emission
            agent.state['_currentSessionId'] = sessionId
            
            # CRITICAL: Set up event callback to push events to SSE queue
            event_queue = get_event_queue()
            
            def create_event_callback(sid: str):
                """Create event callback that pushes to event queue"""
                def event_callback(event_type: str, data: Dict[str, Any]):
                    """Callback function that agents call to emit events
                    
                    Args:
                        event_type: Event type (thought, tool_call, tool_result, etc.)
                        data: Event data dictionary
                    """
                    # Map event types to match frontend expectations
                    # ISMSAgent uses 'tool_call' and 'tool_result', frontend expects 'tool_start' and 'tool_complete'
                    mapped_type = event_type
                    if event_type == 'tool_call':
                        mapped_type = 'tool_start'
                    elif event_type == 'tool_result':
                        mapped_type = 'tool_complete'
                    
                    # Format event for SSE (matches frontend expectations)
                    event = {
                        'type': mapped_type,
                        'data': data if isinstance(data, dict) else {'content': str(data)},
                        'timestamp': __import__('time').time()
                    }
                    # Push to event queue for SSE streaming
                    event_queue.push_event(sid, event)
                    logger.debug(f"Event pushed to queue: {mapped_type} (from {event_type}) for session {sid}")
                return event_callback
            
            agent.state['_event_callback'] = create_event_callback(sessionId)
            
            # Also store event callback in agent for ISMSController access
            agent._event_callback = agent.state['_event_callback']
        
        # CRITICAL: Always try to restore data from session context, even if activeSources is empty
        # This ensures data is available when user responds to prompts
        if agent:
            if not activeSources:
                # Try to get from session directly
                activeSources = session.get('activeContext', [])
            
            latestSource = activeSources[-1] if activeSources else None
            
            if latestSource:
                sourceData = latestSource.get('data')
                
                # SINGLE SOURCE OF TRUTH: session.activeContext
                # Restore data from session context to agent.state['lastProcessed'] for quick access
                # This is a cache - the real data is in session.activeContext
                if sourceData is not None:
                    # Ensure sourceData is a dict before assigning
                    if isinstance(sourceData, dict):
                        # Store ISMS object data
                        agent.state['lastProcessed'] = sourceData.copy()
        
        result = self.agentBridge.process(message, context)
        
        self.sessionService.addMessage(sessionId, 'user', message)
        if result.get('status') == 'success':
            response = result.get('result', '')
            # For structured data (tables), store a simple text summary
            if isinstance(response, dict) and response.get('type') == 'table':
                responseText = response.get('title', 'Listed items')
            elif isinstance(response, dict):
                responseText = response.get('result', str(response))
            else:
                responseText = str(response)
            self.sessionService.addMessage(sessionId, 'assistant', responseText)
        
        # Save agent state back to session (for persistence across requests)
        if agent:
            # Clean up temporary keys before saving
            state_to_save = agent.state.copy()
            if '_event_callback' in state_to_save:
                del state_to_save['_event_callback']
            session['agentState'] = state_to_save
        
        return self._formatResponse(result)
    
    def createSession(self, userId: str) -> Dict[str, Any]:
        """Create new session"""
        sessionId = self.sessionService.createSession(userId)
        return {
            'status': 'success',
            'sessionId': sessionId
        }
    
    def getContext(self, sessionId: str) -> Dict[str, Any]:
        """Get active context for session"""
        session = self.sessionService.getSession(sessionId)
        if not session:
            return {
                'status': 'error',
                'sources': [],
                'error': 'Invalid session'
            }
        
        response = {
            'status': 'success',
            'sources': session.get('activeContext', [])
        }
        
        return response
    
    def addContext(self, sessionId: str, source: Dict[str, Any]) -> Dict[str, Any]:
        """Add source to context"""
        session = self.sessionService.getSession(sessionId)
        if not session:
            return {
                'status': 'error',
                'error': 'Invalid session'
            }
        
        sources = session.get('activeContext', [])
        
        sourceId = source.get('id')
        if any(s.get('id') == sourceId for s in sources):
            return {
                'status': 'error',
                'error': 'Source already in context'
            }
        
        sources.append(source)
        self.sessionService.setContext(sessionId, sources)
        
        return {
            'status': 'success',
            'sources': sources
        }
    
    def removeContext(self, sessionId: str, sourceId: str) -> Dict[str, Any]:
        """Remove source from context"""
        session = self.sessionService.getSession(sessionId)
        if not session:
            return {
                'status': 'error',
                'error': 'Invalid session'
            }
        
        sources = session.get('activeContext', [])
        sources = [s for s in sources if s.get('id') != sourceId]
        self.sessionService.setContext(sessionId, sources)
        
        return {
            'status': 'success',
            'sources': sources
        }
    
    def getAvailableTools(self) -> List[Dict[str, Any]]:
        """Get available agent tools"""
        # Ensure agent is initialized
        if not self.agentBridge.isInitialized():
            self.agentBridge.initialize()
        
        tools = []
        agent = self.agentBridge.agent
        
        if agent and hasattr(agent, 'tools'):
            # Filter out LLM tools (internal only, not shown in UI)
            internalTools = ['generate', 'analyze', 'extractEntities']
            
            query_tools_found = []
            for toolName, toolInfo in agent.tools.items():
                # Skip internal LLM tools
                if toolName in internalTools:
                    continue
                
                # Track query tools
                if any(x in toolName.lower() for x in ['row', 'column', 'filter', 'query', 'search', 'summary']):
                    query_tools_found.append(toolName)
                
                description = toolInfo.get('description', '') if isinstance(toolInfo, dict) else ''
                tools.append({
                    'name': toolName,
                    'description': description
                })
        
        return tools
    
    
    def _formatResponse(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Format agent response for web"""
        if result.get('status') == 'error':
            return {
                'status': 'error',
                'result': None,
                'error': result.get('error', 'Unknown error')
            }
        
        responseData = result.get('result', {})
        
        if isinstance(responseData, dict) and responseData.get('type') in ['table', 'object_detail']:
            response = {
                'status': 'success',
                'result': responseData,  # Preserve structured data as dict
                'type': 'tool_result',
                'dataType': responseData.get('type')  # Add dataType for Pydantic model
            }
        elif isinstance(responseData, dict):
            responseText = responseData.get('content', responseData.get('result', str(responseData)))
            responseType = responseData.get('type', 'chat_response')
            response = {
                'status': 'success',
                'result': responseText,
                'type': responseType
            }
        else:
            responseText = str(responseData)
            response = {
                'status': 'success',
                'result': responseText,
                'type': 'chat_response'
            }
        
        if 'report' in result:
            response['report'] = result.get('report')
        # Legacy individual fields (for backward compatibility)
        if 'reportData' in result:
            response['reportData'] = result.get('reportData')
        if 'reportId' in result:
            response['reportId'] = result.get('reportId')
        if 'reportName' in result:
            response['reportName'] = result.get('reportName')
        if 'format' in result:
            response['format'] = result.get('format')
        if 'size' in result:
            response['size'] = result.get('size')
        
        
        return response

