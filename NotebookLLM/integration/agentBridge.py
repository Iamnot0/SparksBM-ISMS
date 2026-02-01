"""Agent bridge - wraps MainAgent for web integration"""
import sys
import os
from typing import Dict, Any, Optional

_currentDir = os.path.dirname(os.path.abspath(__file__))
_agenticFrameworkPath = os.path.join(_currentDir, '..', '..', 'Agentic Framework')
if os.path.exists(_agenticFrameworkPath) and _agenticFrameworkPath not in sys.path:
    sys.path.insert(0, _agenticFrameworkPath)

from agents.mainAgent import MainAgent
from orchestrator.executor import AgentExecutor
from integration.responseFormatter import ResponseFormatter
from typing import Any


class AgentBridge:
    """Bridge between web API and MainAgent"""
    
    def __init__(self):
        self.agent = None
        self.executor = None
        self._initialized = False
    
    def initialize(self) -> bool:
        """Initialize agent and register tools"""
        try:
            # Force reload of ALL agent modules to pick up latest changes
            import sys
            import importlib
            
            modules_to_reload = [
                'agents.ismsHandler',
                'mcp.tools.linking',
                'orchestrator.chatRouter',
                'agents.coordinators.ismsCoordinator',
                'agents.mainAgent'
            ]
            
            for module_name in modules_to_reload:
                if module_name in sys.modules:
                    print(f"[AgentBridge] Reloading module: {module_name}")
                    importlib.reload(sys.modules[module_name])
            
            self.agent = MainAgent("SparksBM ISMS Assistant")
            
            # Register Reasoning Engine (Gemini API) - INTERNAL ONLY, not shown in UI
            try:
                from orchestrator.reasoningEngine import createReasoningEngine
                reasoningEngine = createReasoningEngine("gemini")
                
                # Store reasoning engine reference for document handlers and knowledge questions
                self.agent._reasoningEngine = reasoningEngine
                
                # These components still expect LLMTool interface, so we create a simple adapter
                class ReasoningEngineAdapter:
                    """Adapter to make ReasoningEngine compatible with old LLMTool interface"""
                    def __init__(self, engine):
                        self.engine = engine
                        self.provider = 'gemini'
                    
                    def generate(self, prompt: str, systemPrompt: str = "", maxTokens: int = 512, **kwargs) -> str:
                        """Generate text using ReasoningEngine"""
                        context = {"system": systemPrompt} if systemPrompt else None
                        return self.engine.reason(prompt, context=context)
                    
                    def analyze(self, data: Any, analysisType: str = "summary", **kwargs) -> str:
                        """Analyze data using ReasoningEngine"""
                        prompt = f"Analyze the following data ({analysisType}):\n\n{data}"
                        return self.engine.reason(prompt)
                    
                    def extractEntities(self, text: str, entityTypes: list, **kwargs) -> dict:
                        """Extract entities using ReasoningEngine"""
                        prompt = f"Extract the following entity types from the text: {', '.join(entityTypes)}\n\nText:\n{text}\n\nReturn as JSON."
                        response = self.engine.reason(prompt)
                        # Try to parse JSON from response
                        import json
                        try:
                            if '```json' in response:
                                json_str = response.split('```json')[1].split('```')[0].strip()
                            elif '```' in response:
                                json_str = response.split('```')[1].split('```')[0].strip()
                            else:
                                json_str = response.strip()
                            return json.loads(json_str)
                        except (json.JSONDecodeError, ValueError, KeyError, IndexError):
                            return {'raw': response, 'entities': []}
                
                llmAdapter = ReasoningEngineAdapter(reasoningEngine) if reasoningEngine.isAvailable() else None
                
                if llmAdapter:
                    # Register LLM tools (via adapter) but mark them as internal (not for UI display)
                    self.agent.registerTool('generate', llmAdapter.generate, 'Generate text using LLM')
                    self.agent.registerTool('analyze', llmAdapter.analyze, 'Analyze data using LLM')
                    self.agent.registerTool('extractEntities', llmAdapter.extractEntities, 'Extract entities from text')
                    # Store adapter reference for backward compatibility
                    self.agent.llmTool = llmAdapter
                    print("[+] Reasoning Engine (Gemini) registered in AgentBridge")
                else:
                    print("[!] Reasoning Engine not available, some features may be limited")
                    self.agent.llmTool = None
            except Exception as e:
                print(f"[!] Failed to initialize Reasoning Engine: {e}")
                self.agent.llmTool = None
                # Continue without LLM - agent can still process ISMS operations
            
            # Register ISMS tool (lazy initialization - will initialize on first use)
            # Don't initialize at startup to avoid timing issues with Keycloak
            # VeriniceTool will be initialized when first ISMS operation is requested
            self.agent._veriniceTool = None
            
            self.executor = AgentExecutor([self.agent])
            self.agent.executor = self.executor
            
            self._initialized = True
            return True
            
        except Exception as e:
            return False
    
    def process(self, message: str, context: Optional[Any] = None) -> Dict[str, Any]:
        """Process message with optional context"""
        if not self._initialized:
            if not self.initialize():
                return {
                    'status': 'error',
                    'result': None,
                    'error': 'Failed to initialize agent'
                }
        
        try:
            if isinstance(context, dict):
                # Store context dict in agent state for access during processing
                if self.agent:
                    # Store activeSources and metadata in agent state
                    self.agent.state['_sessionContext'] = context
                    # Build context string for message
                    contextStr = context.get('context', '')
                    fullMessage = f"{contextStr}\n\nUser: {message}" if contextStr else message
                else:
                    fullMessage = message
            else:
                # Context is a string (legacy format)
                fullMessage = f"{context}\n\nUser: {message}" if context else message
            
            print(f"🌉 AgentBridge.process() called with message: '{message[:50]}...'")
            print(f"🌉 fullMessage: '{fullMessage[:80]}...'")
            
            result = self.executor.execute(
                task="Chat message",
                inputData=fullMessage
            )
            print(f"🌉 Executor returned: status={result.get('success')}, keys={list(result.keys())}")
            
            if result.get('success'):
                # Extract response from result
                # Executor returns: {'success': True, 'result': {'status': 'success', 'result': {...}}}
                resultData = result.get('result', {})
                
                innerResult = resultData.get('result', {}) if isinstance(resultData, dict) else {}
                
                # Determine result type from inner result
                if isinstance(innerResult, dict) and innerResult.get('type'):
                    resultType = innerResult.get('type')
                elif isinstance(resultData, dict) and resultData.get('type'):
                    resultType = resultData.get('type')
                else:
                    resultType = 'chat_response'
                
                # CRITICAL: Preserve structured LLM responses (with reasoning steps) as-is
                if isinstance(innerResult, dict) and 'reasoning_steps' in innerResult:
                    return {
                        'status': 'success',
                        'result': innerResult,
                        'type': 'chat_response'
                    }
                
                # Use presenter layer if result is structured, otherwise use formatter
                elif isinstance(innerResult, dict) and innerResult.get('type') in ['table', 'object_detail', 'report']:
                    # Already formatted by presenter layer - use as-is
                    formattedResponse = innerResult
                    # Extract content if formattedResponse is a text type dictionary
                    if isinstance(formattedResponse, dict) and formattedResponse.get('type') == 'text':
                        formattedResponse = formattedResponse.get('content', str(formattedResponse))
                    response = {
                        'status': 'success',
                        'result': formattedResponse,
                        'type': resultType
                    }
                else:
                    # Use smart formatter for other types
                    # Use innerResult if available, otherwise use resultData
                    dataToFormat = innerResult if isinstance(innerResult, dict) and innerResult else resultData
                    formattedResponse = ResponseFormatter.format(
                        dataToFormat,
                        resultType=resultType,
                        context={'message': message, 'context': context}
                    )
                
                # Extract content if formattedResponse is a text type dictionary
                if isinstance(formattedResponse, dict) and formattedResponse.get('type') == 'text':
                    formattedResponse = formattedResponse.get('content', str(formattedResponse))
                
                response = {
                    'status': 'success',
                    'result': formattedResponse,
                    'type': resultType
                }
                
                # If result is structured data, add type indicator
                if isinstance(formattedResponse, dict) and formattedResponse.get('type') in ['table', 'object_detail']:
                    response['dataType'] = formattedResponse.get('type')
                
                if isinstance(resultData, dict):
                    if 'report' in resultData:
                        response['report'] = resultData.get('report')
                    # Legacy individual fields (for backward compatibility)
                    if 'reportData' in resultData:
                        response['reportData'] = resultData.get('reportData')
                    if 'reportId' in resultData:
                        response['reportId'] = resultData.get('reportId')
                    if 'reportName' in resultData:
                        response['reportName'] = resultData.get('reportName')
                    if 'format' in resultData:
                        response['format'] = resultData.get('format')
                    if 'size' in resultData:
                        response['size'] = resultData.get('size')
                
                return response
            else:
                resultData = result.get('result', {})
                errorMsg = None
                
                if isinstance(resultData, dict):
                    errorMsg = resultData.get('error') or resultData.get('result') or 'Unknown error'
                else:
                    errorMsg = result.get('error') or str(resultData) or 'Unknown error'
                
                # Format error intelligently
                formattedError = ResponseFormatter.format(errorMsg, resultType='error', context={'message': message})
                
                return {
                    'status': 'error',
                    'result': formattedError,
                    'error': formattedError
                }
                
        except Exception as e:
            import traceback
            # Format exception intelligently
            errorMsg = ResponseFormatter.format(
                str(e),
                resultType='error',
                context={'message': message, 'exception': True}
            )
            return {
                'status': 'error',
                'result': errorMsg,
                'error': errorMsg
            }
    
    def isInitialized(self) -> bool:
        """Check if agent is initialized"""
        return self._initialized
