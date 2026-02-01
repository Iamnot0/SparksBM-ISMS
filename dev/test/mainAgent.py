"""Main Agent - Handles ISMS operations"""
from typing import Dict, Any, Optional, List
import re
import json
from pathlib import Path
from .baseAgent import BaseAgent
from .ismsHandler import ISMSHandler
from .instructions import (
    VERINICE_OBJECT_TYPES,
    VERINICE_CREATE_KEYWORDS,
    VERINICE_LIST_KEYWORDS,
    VERINICE_GET_KEYWORDS,
    VERINICE_UPDATE_KEYWORDS,
    VERINICE_DELETE_KEYWORDS,
    VERINICE_ANALYZE_KEYWORDS,
    VERINICE_QUESTION_STARTERS,
    VERINICE_QUESTION_WORDS,
    VERINICE_TYPO_CORRECTIONS,
    VERINICE_SUBTYPE_MAPPINGS,
    VERINICE_REPORT_KEYWORDS,
    VERINICE_REPORT_TYPES,
    VERINICE_REPORT_TYPE_MAPPINGS,
    KNOWLEDGE_QUESTION_STARTERS,
    KNOWLEDGE_QUESTION_PHRASES,
    KNOWLEDGE_WHAT_PATTERNS,
    KNOWLEDGE_HOW_TO_CREATE_PATTERNS,
    TYPO_VARIATIONS,
    get_error_message,
)
from .helpers import (
    parseSubtypeSelection,
    checkGreeting,
    formatTextResponse,
    successResponse,
    errorResponse,
)


class MainAgent(BaseAgent):
    """Main agent for ISMS operations"""
    
    def __init__(self, name: str = "SparksBM ISMS Agent", executor=None):
        goals = [
            "Manage ISMS operations in Verinice",
            "Handle ISMS object CRUD operations",
            "Support ISMS compliance workflows"
        ]
        instructions = """You are SparksBM Intelligent, a professional ISMS compliance assistant integrated with Verinice.

Your expertise:
- ISO 27001, ISO 22301, NIS-2 compliance standards
- Verinice ISMS platform operations
- Risk management, asset management, control implementation

Communication style:
- Professional but friendly and approachable
- Clear, concise, and actionable
- Use ISMS terminology correctly
- Provide context and examples when helpful

CRITICAL RULES:
- NEVER expose tool names, tool calls, or execution steps to users
- ALWAYS narrate actions as if performed by you, not by tools
- Errors must be rewritten as calm, user-facing explanations with next steps
- One action per message, one question max
- No system wording ("service issue", "tool", "operation")
- End with guidance or a choice when appropriate"""
        
        super().__init__(name, "DataProcessor", goals, instructions)
        self.executor = executor
        self.conversationHistory = []
        self.lastUserMessage = None
        
        # Context management
        try:
            from memory.enhancedContextManager import EnhancedContextManager
            self.contextManager = EnhancedContextManager()
        except ImportError:
            self.contextManager = None
        
        # Intent classifier (lazy initialization)
        self._intentClassifier = None
        
        # Load knowledge base from JSON
        self._knowledgeBase = self._loadKnowledgeBase()
    
        # ISMS handler (initialized when veriniceTool is set)
        self._ismsHandler = None
        
        # PHASE 3: Chat Router (shadow testing mode)
        self._chatRouter = None
        self._useChatRouter = True  # Feature flag: False = shadow mode, True = active mode - DEPLOYED 2026-01-03
        self._routingLog = []  # Log routing decisions for comparison
    
    def process(self, inputData: Any) -> Dict:
        """Main entry point - route to appropriate handler"""
        try:
            if isinstance(inputData, str):
                # Extract the actual message if it contains "User: " prefix (from agentBridge)
                actualMessage = inputData
                if '\n\nUser: ' in inputData:
                    actualMessage = inputData.split('\n\nUser: ')[-1]
                elif '\nUser: ' in inputData:
                    actualMessage = inputData.split('\nUser: ')[-1]
                
                # Strip trailing punctuation first to avoid false positives (e.g., "list process.")
                cleaned = actualMessage.rstrip('.,!?;:').strip()
                
                return self._processChatMessage(actualMessage)
            elif isinstance(inputData, dict):
                return self._processChatMessage(str(inputData))
            else:
                return {'status': 'error', 'result': None, 'error': get_error_message('validation', 'invalid_input_type')}
        except Exception as e:
            return {'status': 'error', 'result': None, 'error': str(e)}
    
    # ==================== CHAT MESSAGE PROCESSING ====================
    
    def _processChatMessage(self, message: str) -> Dict:
        """Process chat message - AI-driven natural routing"""
        try:
            # CRITICAL: Sync state BEFORE routing to ensure context is available for bulk delete
            # This ensures _last_list_result is available when _detectBulkDelete is called
            if self._ismsHandler and hasattr(self._ismsHandler, 'state'):
                # Sync handler state to MainAgent state (bidirectional)
                if '_last_list_result' in self._ismsHandler.state:
                    self.state['_last_list_result'] = self._ismsHandler.state['_last_list_result']
                # Also sync MainAgent state to handler state
                self._ismsHandler.state = self.state
            
            # PHASE 3: Shadow testing - run new router in parallel
            # CRITICAL: Always ensure router is initialized if using new router
            if self._useChatRouter:
                self._ensureChatRouter()
                # Force router initialization - if it's None, create it
                if not self._chatRouter:
                    from orchestrator.chatRouter import ChatRouter
                    from .instructions import VERINICE_OBJECT_TYPES
                    self._chatRouter = ChatRouter(VERINICE_OBJECT_TYPES)
            
            newRouterDecision = None
            # CRITICAL: Always try to get router decision if router exists or if we're using it
            if self._chatRouter:
                try:
                    newRouterDecision = self._shadowTestNewRouter(message)
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"[MainAgent] Error in shadowTestNewRouter: {e}")
                    newRouterDecision = None
            
            # If using new router (feature flag enabled), execute its decision
            if self._useChatRouter and newRouterDecision:
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"[MainAgent] Using new router, decision: route={newRouterDecision.get('route')}, handler={newRouterDecision.get('handler')}, data={newRouterDecision.get('data')}")
                result = self._executeRoutingDecision(newRouterDecision, message)
                # ALWAYS return the result from router - don't fall through to old routing
                # Even if it's an error, the router made a decision and we should respect it
                if result:
                    logger.info(f"[MainAgent] Router decision executed, status: {result.get('status')}")
                    return result
                else:
                    logger.error(f"[MainAgent] Router handler returned None - this should not happen")
                    return self._error(f"Router handler returned None for: {message[:80]}")
            elif self._useChatRouter:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"[MainAgent] New router enabled but no decision returned for: {message[:80]}")
                # Router didn't return a decision - fall through to old routing logic
            elif newRouterDecision:
                import logging
                logger = logging.getLogger(__name__)
                logger.debug(f"[MainAgent] New router decision available but router disabled: {newRouterDecision.get('route')}")
            # CRITICAL: Sync state BEFORE routing to ensure context is available
            # This ensures bulk delete operations can access _last_list_result
            if self._ismsHandler and hasattr(self._ismsHandler, 'state'):
                # Sync handler state to MainAgent state (bidirectional)
                if '_last_list_result' in self._ismsHandler.state:
                    self.state['_last_list_result'] = self._ismsHandler.state['_last_list_result']
                # Also sync MainAgent state to handler state
                self._ismsHandler.state = self.state
                # CRITICAL: Also sync back to router state if router exists
                if self._chatRouter and hasattr(self._chatRouter, 'state'):
                    self._chatRouter.state = self.state
            
            # 0. PRIORITY: Check for follow-up responses FIRST (before any other processing)
            # This ensures follow-up handlers get priority over intent classification
            
            if self.state.get('pendingReportGeneration'):
                followUpResult = self._handleReportGenerationFollowUp(message)
                if followUpResult:
                    if newRouterDecision:
                        self._logRoutingComparison(message, "follow_up_report", newRouterDecision, followUpResult)
                    return followUpResult
            
            followUpResult = self._handleSubtypeFollowUp(message)
            if followUpResult:
                if newRouterDecision:
                    self._logRoutingComparison(message, "follow_up_subtype", newRouterDecision, followUpResult)
                return followUpResult
            
            # Store message (only if not a follow-up)
            self.lastUserMessage = message
            self.conversationHistory.append({'user': message, 'timestamp': None})
            if len(self.conversationHistory) > 50:
                self.conversationHistory.pop(0)
            
            if self.contextManager:
                self.contextManager.addToConversation('user', message)
            
            # 1. Quick greeting check (fast response)
            greeting = self._checkGreeting(message)
            if greeting:
                greetingResult = self._success(greeting)
                if newRouterDecision:
                    self._logRoutingComparison(message, "greeting", newRouterDecision, greetingResult)
                return greetingResult
            
            # 2. Get context from state if available (set by agentBridge with activeSources)
            sessionContext = self.state.get('_sessionContext', {})
            if sessionContext and isinstance(sessionContext, dict):
                # Use session context which has activeSources and metadata from session
                context = sessionContext.copy()
            else:
                # Build basic context if no session context available
                context = {
                    'conversationHistory': self.conversationHistory[-3:] if self.conversationHistory else [],
                    'activeSources': []
                }
            
            # 3. CRITICAL: Check for Verinice operations FIRST (before IntentClassifier)
            # This ensures ISMS commands work even if IntentClassifier fails or misclassifies
            veriniceOp = self._detectVeriniceOp(message)
            if veriniceOp:
                veriniceResult = self._handleVeriniceOp(veriniceOp, message)
                if newRouterDecision:
                    self._logRoutingComparison(message, "verinice_operation", newRouterDecision, veriniceResult)
                return veriniceResult
            
            # 4. Check for report generation (before IntentClassifier to avoid misclassification)
            reportGen = self._detectReportGeneration(message)
            if reportGen:
                reportResult = self._handleReportGeneration(reportGen, message)
                if newRouterDecision:
                    self._logRoutingComparison(message, "report_generation", newRouterDecision, reportResult)
                return reportResult
            
            # 5. Initialize IntentClassifier if not already initialized (lazy init)
            if not hasattr(self, '_intentClassifier') or not self._intentClassifier:
                try:
                    from orchestrator.intentClassifier import IntentClassifier
                    llmTool = getattr(self, '_llmTool', None)
                    if llmTool:
                        self._intentClassifier = IntentClassifier(llmTool)
                except Exception:
                    self._intentClassifier = None
            
            # 6. Use IntentClassifier to understand what user wants (AI-driven)
            # Only use if pattern-based detection didn't catch it
            if hasattr(self, '_intentClassifier') and self._intentClassifier:
                try:
                    classification = self._intentClassifier.classify(message, context)
                    intent = classification.get('intent', 'unknown')
                    confidence = classification.get('confidence', 0)
                    
                    # Route based on classified intent
                    if confidence >= 0.6:  # Only use if confident enough
                        if intent == 'verinice_create':
                            # Extract operation details and handle
                            veriniceOp = self._detectVeriniceOp(message)
                            if veriniceOp:
                                return self._handleVeriniceOp(veriniceOp, message)
                        
                        elif intent == 'verinice_list':
                            veriniceOp = self._detectVeriniceOp(message)
                            if veriniceOp:
                                return self._handleVeriniceOp(veriniceOp, message)
                        
                        elif intent == 'verinice_get':
                            veriniceOp = self._detectVeriniceOp(message)
                            if veriniceOp:
                                return self._handleVeriniceOp(veriniceOp, message)
                        
                        elif intent == 'verinice_update':
                            veriniceOp = self._detectVeriniceOp(message)
                            if veriniceOp:
                                return self._handleVeriniceOp(veriniceOp, message)
                        
                        elif intent == 'verinice_delete':
                            veriniceOp = self._detectVeriniceOp(message)
                            if veriniceOp:
                                return self._handleVeriniceOp(veriniceOp, message)
                        
                except Exception:
                    # Intent classification failed - continue to next handler
                    pass
            
            
            # 7. Check fallback knowledge base (pattern-based, for backward compatibility)
            fallbackAnswer = self._getFallbackAnswer(message)
            if fallbackAnswer:
                return self._success(fallbackAnswer)
            
            # 7.5 Check for contextual questions ("what are those", "what is this")
            contextualAnswer = self._handleContextualQuestion(message)
            if contextualAnswer:
                return self._success(contextualAnswer)
            
            # 8. Route ALL knowledge questions to ReasoningEngine (not just pattern-based)
            reasoningEngine = getattr(self, '_reasoningEngine', None)
            if reasoningEngine and reasoningEngine.isAvailable():
                try:
                    messageLower = message.lower().strip()
                    isKnowledgeQuestion = any(
                        starter in messageLower 
                        for starter in KNOWLEDGE_QUESTION_STARTERS
                    ) or messageLower.endswith('?')
                    
                    # Route to ReasoningEngine if it's a knowledge question OR not an ISMS operation
                    isISMSOp = any([
                        'create' in messageLower and any(obj in messageLower for obj in VERINICE_OBJECT_TYPES),
                        'list' in messageLower and any(obj in messageLower for obj in VERINICE_OBJECT_TYPES),
                        'get' in messageLower and any(obj in messageLower for obj in VERINICE_OBJECT_TYPES),
                        'update' in messageLower and any(obj in messageLower for obj in VERINICE_OBJECT_TYPES),
                        'delete' in messageLower and any(obj in messageLower for obj in VERINICE_OBJECT_TYPES),
                    ])
                    
                    if isKnowledgeQuestion or not isISMSOp:
                        # This is a knowledge question or general query - use ReasoningEngine
                        # IMPORTANT: Don't override the concise mode - let ReasoningEngine use its default
                        # The system_prompt will be enhanced by ReasoningEngine with concise constraints
                        system_prompt = f"{self.instructions}\n\nYou are an expert ISMS compliance assistant. Answer questions about ISO 27001, ISMS, Verinice, and related topics clearly and helpfully."
                        context = {
                            "system": "You are an ISMS expert assistant helping users understand ISMS concepts, ISO 27001 compliance, and Verinice operations."
                        }
                        # Explicitly pass response_mode='concise' to ensure concise mode is used
                        response = reasoningEngine.reason(message, context=context, system_prompt=system_prompt, response_mode='concise')
                        return self._success(response)
                except Exception:
                    # Fallback to tool-based generation if ReasoningEngine fails
                    pass
            
            # 9. Fallback: Use generate tool if available (for backward compatibility)
            if 'generate' in self.tools:
                try:
                    response = self.executeTool('generate', prompt=message, systemPrompt=self.instructions)
                    formattedResponse = self._formatTextResponse(response)
                    return self._success(formattedResponse)
                except Exception:
                    pass
            
            # 9. Final fallback - use reasoning engine if available
            try:
                from orchestrator.reasoningEngine import ReasoningEngine
                reasoningEngine = ReasoningEngine()
                system_prompt = f"{self.instructions}\n\nYou are an expert ISMS compliance assistant. Answer questions clearly and helpfully."
                context = {
                    "system": "You are an ISMS expert assistant helping users understand ISMS concepts, ISO 27001 compliance, and Verinice operations."
                }
                response = reasoningEngine.reason(message, context=context, system_prompt=system_prompt, response_mode='concise')
                oldResult = self._success(response)
            except Exception:
                # Last resort: return error instead of generic message
                oldResult = self._error("I couldn't process your request. Please try rephrasing or use specific ISMS commands like 'list scopes' or 'create scope MyScope'.")
            
            # PHASE 3: Log old routing decision for comparison
            if newRouterDecision:
                self._logRoutingComparison(message, "final_fallback", newRouterDecision, oldResult)
            
            return oldResult
        except Exception as e:
            # Never return None - always provide actionable feedback
            return {
                'status': 'error', 
                'result': f"I encountered an error: {str(e)}\n\nYou can try:\n  • list scopes\n  • create scope MyScope MS Description\n  • ask 'help'", 
                'error': str(e)
            }
    
    # ==================== VERINICE OPERATIONS ====================
    
    def _detectVeriniceOp(self, message: str) -> Optional[Dict]:
        """Detect Verinice operation from message - ignore questions"""
        try:
            messageLower = message.lower().strip()
            
            # Skip questions - these should go to LLM for knowledge answers
            # BUT: subtype queries should be handled separately (checked before this)
            if any(messageLower.startswith(phrase) for phrase in KNOWLEDGE_QUESTION_PHRASES):
                subtype_patterns = [
                    r'how\s+many\s+subtypes?',
                    r'what\s+subtypes?',
                    r'list\s+subtypes?',
                    r'show\s+subtypes?',
                    r'get\s+subtypes?',
                ]
                if not any(re.search(pattern, messageLower) for pattern in subtype_patterns):
                    return None
    
            # Normalize typos - only replace whole words to avoid substring issues
            # Build typo map from JSON (reverse lookup: typo -> correct)
            typoMap = {}
            for correct, typos in TYPO_VARIATIONS.items():
                for typo in typos:
                    typoMap[typo] = correct
            typoMap.update(VERINICE_TYPO_CORRECTIONS)
            for typo, correct in typoMap.items():
                # Use word boundaries to only replace whole words, not substrings
                pattern = r'\b' + re.escape(typo) + r'\b'
                messageLower = re.sub(pattern, correct, messageLower)
            
            # CRITICAL: Check if word after "create" is a subtype name, not an object type
            # This MUST happen BEFORE object type matching to avoid false matches
            # Pattern: "create Controllers named X" or "create 'Controllers' named X" or "Create a 'Controllers' named 'MFA for VPN'"
            createSubtypePatterns = [
                r'create\s+(?:a\s+)?["\']([A-Z][^"\']+)["\']\s+(?:named|called)',  # "create 'Controllers' named"
                r'create\s+(?:a\s+)?([A-Z][a-z]+(?:s|es)?)\s+(?:named|called)',  # "create Controllers named"
            ]
            
            for createSubtypePattern in createSubtypePatterns:
                createSubtypeMatch = re.search(createSubtypePattern, message)
                if createSubtypeMatch:
                    potentialSubtype = createSubtypeMatch.group(1).strip()
                    potentialSubtypeLower = potentialSubtype.lower()
                    
                    isKnownObjectType = any(objType.lower() == potentialSubtypeLower or 
                                           objType.lower() == potentialSubtypeLower.rstrip('s') or
                                           objType.lower() == potentialSubtypeLower.rstrip('es')
                                           for objType in VERINICE_OBJECT_TYPES)
                    
                    # Use subtype mappings from JSON (ismsInstructions.json)
                    if not isKnownObjectType and potentialSubtypeLower in VERINICE_SUBTYPE_MAPPINGS:
                        objectType = VERINICE_SUBTYPE_MAPPINGS[potentialSubtypeLower]
                        detectedSubtype = potentialSubtype
                        
                        # Detect operation using keywords from JSON
                        if any(re.search(r'\b' + re.escape(word) + r'\b', messageLower) for word in VERINICE_CREATE_KEYWORDS):
                            return {
                                'operation': 'create',
                                'objectType': objectType,
                                'subType': detectedSubtype,
                                'isSubtypeFirst': True
                            }
                    break
            
            # Extract object type (normal flow)
            objectType = None
            # Sort to check plurals first (longer strings first), then check for whole word matches
            sortedTypes = sorted(VERINICE_OBJECT_TYPES, key=len, reverse=True)
            for objType in sortedTypes:
                # Use word boundary matching to avoid substring issues
                pattern = r'\b' + re.escape(objType) + r'\b'
                if re.search(pattern, messageLower):
                    # Convert to singular: remove trailing "s" but handle special cases correctly
                    if objType.endswith("es"):
                        if objType == "processes":
                            objectType = "process"
                        elif objType == "scopes":
                            objectType = "scope"
                        else:
                            objectType = objType[:-2]  # Remove "es" for other words
                    elif objType.endswith("s") and objType != "process":  # Don't modify "process" itself
                        objectType = objType[:-1]  # Remove single "s" (e.g., "assets" -> "asset")
                    else:
                        objectType = objType  # Already singular
                    break
            
            if not objectType:
                return None
        
            # Detect operation - use word boundaries to avoid false matches (e.g., "NEW" triggering "new")
            # Use keywords from JSON (ismsInstructions.json)
            if any(re.search(r'\b' + re.escape(word) + r'\b', messageLower) for word in VERINICE_UPDATE_KEYWORDS):
                return {'operation': 'update', 'objectType': objectType}
            elif any(re.search(r'\b' + re.escape(word) + r'\b', messageLower) for word in VERINICE_DELETE_KEYWORDS):
                return {'operation': 'delete', 'objectType': objectType}
            # Then CREATE
            elif any(re.search(r'\b' + re.escape(word) + r'\b', messageLower) for word in VERINICE_CREATE_KEYWORDS) and not any(q in messageLower for q in VERINICE_QUESTION_WORDS):
                return {'operation': 'create', 'objectType': objectType}
            # Then LIST/GET
            elif any(re.search(r'\b' + re.escape(word) + r'\b', messageLower) for word in VERINICE_LIST_KEYWORDS) and not any(q in messageLower for q in VERINICE_QUESTION_WORDS):
                return {'operation': 'list', 'objectType': objectType}
            elif any(re.search(r'\b' + re.escape(word) + r'\b', messageLower) for word in VERINICE_GET_KEYWORDS) and not any(q in messageLower for q in VERINICE_QUESTION_WORDS):
                return {'operation': 'get', 'objectType': objectType}
            # Then ANALYZE
            elif any(re.search(r'\b' + re.escape(word) + r'\b', messageLower) for word in VERINICE_ANALYZE_KEYWORDS):
                return {'operation': 'analyze', 'objectType': objectType}
            
            return None
        except Exception:
            # If detection fails, return None (don't break the flow)
            return None
    
    def _detectReportGeneration(self, message: str) -> Optional[Dict]:
        """Detect report generation requests"""
        messageLower = message.lower().strip()
        
        hasReportKeyword = any(keyword in messageLower for keyword in VERINICE_REPORT_KEYWORDS)
        hasReportType = any(reportType in messageLower for reportType in VERINICE_REPORT_TYPES)
        
        if hasReportKeyword and hasReportType:
            # Extract report type using mappings from JSON
            reportType = None
            for reportTypeKey, keywords in VERINICE_REPORT_TYPE_MAPPINGS.items():
                if all(keyword in messageLower for keyword in keywords):
                    reportType = reportTypeKey
                    break
            
            # Fallback to individual type detection
            if not reportType:
                if 'inventory' in messageLower and 'asset' in messageLower:
                    reportType = 'inventory-of-assets'
                elif 'risk' in messageLower and 'assessment' in messageLower:
                    reportType = 'risk-assessment'
                elif 'statement' in messageLower and 'applicability' in messageLower:
                    reportType = 'statement-of-applicability'
                elif 'inventory' in messageLower:
                    reportType = 'inventory-of-assets'
                elif 'risk' in messageLower:
                    reportType = 'risk-assessment'
                elif 'statement' in messageLower:
                    reportType = 'statement-of-applicability'
            
            if reportType:
                return {'operation': 'generate_report', 'reportType': reportType}
        
        return None
    
    def _handleReportGeneration(self, command: Dict, message: str) -> Dict:
        """Handle report generation - list scopes and ask user to select"""
        reportType = command.get('reportType')
        if not reportType:
            return self._error(get_error_message('user_guidance', 'what_report'))
        
        if not self._ismsHandler:
            veriniceTool = getattr(self, "_veriniceTool", None)
            if not veriniceTool:
                return self._error(get_error_message('connection', 'isms_client_not_available'))
            llmTool = getattr(self, '_llmTool', None)
            self._ismsHandler = ISMSHandler(veriniceTool, self._formatVeriniceResult, llmTool)
        
        domainId, unitId = self._ismsHandler._getDefaults()
        if not domainId:
            return self._error(get_error_message('not_found', 'domain'))
        
        # List scopes
        scopesResult = self._ismsHandler.veriniceTool.listObjects('scope', domainId)
        if not scopesResult.get('success'):
            return self._error(get_error_message('operation_failed', 'list_scopes', error=scopesResult.get('error', 'Unknown error')))
        
        # Extract scopes
        objects = scopesResult.get('objects', {})
        items = objects.get('items', []) if isinstance(objects, dict) else (objects if isinstance(objects, list) else [])
        
        if not items:
            return self._error(get_error_message('not_found', 'scopes'))
        
        # Format report type name
        reportNames = {
            'inventory-of-assets': 'Inventory of Assets',
            'risk-assessment': 'Risk Assessment',
            'statement-of-applicability': 'Statement of Applicability'
        }
        
        # Store pending report generation state
        self.state['pendingReportGeneration'] = {
            'reportType': reportType,
            'reportName': reportNames.get(reportType, reportType.replace('-', ' ').title()),
            'scopes': items,
            'domainId': domainId
        }
        
        # Format scopes list
        from presenters.table import TablePresenter
        presenter = TablePresenter()
        formatted = presenter.present({
            'items': items,
            'columns': ['Name', 'Description'],
            'title': f'Which scope do you want to generate the "{reportNames.get(reportType, reportType.replace("-", " ").title())}" report for?',
            'total': len(items)
        })
        
        if isinstance(formatted, dict) and formatted.get('type') == 'text':
            content = formatted.get('content', str(formatted))
            content += "\n\nPlease specify which scope (by name or number) to generate the report for."
            return self._success(content)
        
        return self._success(formatted)
    
    def _handleReportGenerationFollowUp(self, message: str) -> Dict:
        """Handle follow-up response for report generation (scope selection)"""
        pending = self.state.get('pendingReportGeneration')
        if not pending:
            return self._error(get_error_message('not_found', 'pending_report'))
        
        reportType = pending['reportType']
        scopes = pending['scopes']
        domainId = pending['domainId']
        
        # Clear pending state
        del self.state['pendingReportGeneration']
        
        # Parse user input - could be number or scope name
        messageLower = message.strip().lower()
        selectedScope = None
        
        # Try to parse as number
        try:
            scopeIndex = int(messageLower) - 1
            if 0 <= scopeIndex < len(scopes):
                selectedScope = scopes[scopeIndex]
        except ValueError:
            # Not a number, try to find by name
            for scope in scopes:
                scopeName = scope.get('name', '').lower()
                if messageLower in scopeName or scopeName in messageLower:
                    selectedScope = scope
                    break
                            
        if not selectedScope:
            return self._error(get_error_message('not_found', 'scope', name=message))
        
        scopeId = selectedScope.get('id') or selectedScope.get('value')
        if not scopeId:
            return self._error(get_error_message('operation_failed', 'list_scopes', error='Could not determine scope ID.'))
        
        # Generate report
        if not self._ismsHandler:
            veriniceTool = getattr(self, '_veriniceTool', None)
            if not veriniceTool:
                return self._error(get_error_message('connection', 'isms_client_not_available'))
            llmTool = getattr(self, '_llmTool', None)
            self._ismsHandler = ISMSHandler(veriniceTool, self._formatVeriniceResult, llmTool)
        
        # Generate report with scope as target
        params = {
            'outputType': 'application/pdf',
            'language': 'en',
            'targets': [{'id': scopeId, 'modelType': 'scope'}],
            'timeZone': 'UTC'
        }
        
        result = self._ismsHandler.veriniceTool.generateReport(reportType, domainId, params)
        
        if result.get('success'):
            scopeName = selectedScope.get('name', 'Unknown')
            reportId = result.get('reportId', reportType)
            reportSize = result.get('size', 0)
            reportFormat = result.get('format', 'pdf')
            
            # Build success message with report details
            message = f"✅ Report '{pending['reportName']}' generated successfully for scope '{scopeName}'.\n\n"
            message += "Report Details:\n"
            message += f"• Report ID: {reportId}\n"
            message += f"• Format: {reportFormat.upper()}\n"
            message += f"• Size: {reportSize:,} bytes\n"
            message += f"• Scope: {scopeName}\n"
            
            # Include report data in response if available (for verification)
            response_data = {
                'status': 'success',
                'result': message,
                'type': 'chat_response',
                'report': {
                    'id': reportId,
                    'type': reportType,
                    'format': reportFormat,
                    'size': reportSize,
                    'scope': scopeName,
                    'data': result.get('data'),
                    'generated_at': result.get('generated_at')
                }
            }
            return response_data
        else:
            return self._error(get_error_message('operation_failed', 'generate_report', error=result.get('error', 'Unknown error')))
    
    def _handleSubtypeFollowUp(self, message: str) -> Optional[Dict]:
        """Handle follow-up response for subtype selection (e.g., user replies "2" or "PER_DataProtectionOfficer")"""
        pending = self.state.get('_pendingSubtypeSelection')
        if not pending and self._ismsHandler and hasattr(self._ismsHandler, 'state'):
            pending = self._ismsHandler.state.get('_pendingSubtypeSelection')
        
        if not pending:
            return None
        
        message_clean = message.strip()
        
        # Try to parse as number
        try:
            selection_num = int(message_clean)
            availableSubTypes = pending.get('availableSubTypes', [])
            if 1 <= selection_num <= len(availableSubTypes):
                selectedSubType = availableSubTypes[selection_num - 1]
            else:
                return self._error(get_error_message('validation', 'invalid_selection', max=len(availableSubTypes)))
        except ValueError:
            # Not a number, try to match as subtype name
            availableSubTypes = pending.get('availableSubTypes', [])
            selectedSubType = None
            
            # Exact match
            for subType in availableSubTypes:
                if message_clean.lower() == subType.lower():
                    selectedSubType = subType
                    break
            
            # Partial match
            if not selectedSubType:
                for subType in availableSubTypes:
                    if message_clean.lower() in subType.lower() or subType.lower() in message_clean.lower():
                        selectedSubType = subType
                        break
            
            if not selectedSubType:
                # Clear pending and show error
                self.state.pop('_pendingSubtypeSelection', None)
                if self._ismsHandler and hasattr(self._ismsHandler, 'state'):
                    self._ismsHandler.state.pop('_pendingSubtypeSelection', None)
                subtype_list = '\n'.join([f"{idx + 1}. {subType}" for idx, subType in enumerate(availableSubTypes)])
                return self._error(get_error_message('validation', 'invalid_subtype_selection', subtype=message_clean, options=subtype_list, max=len(availableSubTypes)))
        
        # Clear pending state
        self.state.pop('_pendingSubtypeSelection', None)
        if self._ismsHandler and hasattr(self._ismsHandler, 'state'):
            self._ismsHandler.state.pop('_pendingSubtypeSelection', None)
        
        # Complete the creation with selected subtype
        if not self._ismsHandler:
            veriniceTool = getattr(self, "_veriniceTool", None)
            if not veriniceTool:
                return self._error(get_error_message('connection', 'isms_client_not_available'))
            llmTool = getattr(self, '_llmTool', None)
            self._ismsHandler = ISMSHandler(veriniceTool, self._formatVeriniceResult, llmTool)
        
        result = self._ismsHandler.veriniceTool.createObject(
            pending['objectType'],
            pending['domainId'],
            pending['unitId'],
            pending['name'],
            subType=selectedSubType,
            description=pending.get('description', ''),
            abbreviation=pending.get('abbreviation')
        )
        
        if result.get('success'):
            info = f"Created {pending['objectType']} '{pending['name']}'"
            if pending.get('abbreviation'):
                info += f" (abbreviation: {pending['abbreviation']})"
            info += f" (type: {selectedSubType})"
            return self._success(info)
        
        return self._error(get_error_message('operation_failed', 'create', objectType=pending['objectType'], error=result.get('error', 'Unknown error')))
    
    def _handleSubtypeQuery(self, data: Dict, message: str) -> Dict:
        """
        Handle queries about available subtypes for an object type.
        
        Examples:
        - "how many subtypes assets to create assets"
        - "what subtypes are available for scopes"
        - "list subtypes for asset"
        """
        objectType = data.get('objectType')
        if not objectType:
            return self._error("Could not determine object type from your question.")
        
        if not self._ismsHandler:
            veriniceTool = getattr(self, "_veriniceTool", None)
            if not veriniceTool:
                return self._error(get_error_message('connection', 'isms_client_not_available'))
            llmTool = getattr(self, '_llmTool', None)
            self._ismsHandler = ISMSHandler(veriniceTool, self._formatVeriniceResult, llmTool)
        
        domainId, unitId = self._ismsHandler._getDefaults()
        if not domainId:
            return self._error("No domain found. Please ensure you have access to a domain.")
        
        subTypesInfo = self._ismsHandler._getSubTypesInfo(domainId, objectType)
        availableSubTypes = subTypesInfo.get('subTypes', [])
        count = subTypesInfo.get('count', 0)
        
        if not availableSubTypes:
            return self._success(f"No subtypes are available for {objectType} in this domain.")
        
        # Convert technical subtypes to dashboard-friendly names
        dashboard_names = [self._convertToDashboardName(subType, objectType) for subType in availableSubTypes]
        
        # Format response with dashboard-friendly names
        subtype_list = '\n'.join([f"{idx + 1}. {name}" for idx, name in enumerate(dashboard_names)])
        response = f"Available subtypes for {objectType}:\nTotal: {count}\n\n{subtype_list}"
        
        if dashboard_names:
            response += f"\n\nTo create a {objectType} with a specific subtype, use:\n"
            response += f"  create {objectType} MyName subType {dashboard_names[0]}"
            if len(dashboard_names) > 1:
                response += f"\n  or: create {objectType} MyName subType {dashboard_names[1]}"
        
        return self._success(response)
    
    def _convertToDashboardName(self, technicalSubType: str, objectType: str) -> str:
        """
        Convert technical subtype (e.g., SCP_Controller) to dashboard-friendly name (e.g., Controllers).
        
        Args:
            technicalSubType: Technical subtype from API (e.g., SCP_Controller, AST_Datatype)
            objectType: Main object type (scope, asset, person, etc.)
        
        Returns:
            Dashboard-friendly name (e.g., Controllers, Datatypes, Data protection officers)
        """
        # Mapping of technical subtypes to dashboard-friendly names
        # Based on actual dashboard structure
        subtype_mapping = {
            # Scope subtypes
            'SCP_Scope': 'Scopes',
            'SCP_Processor': 'Processors',
            'SCP_Controller': 'Controllers',
            'SCP_JointController': 'Joint controllerships',
            'SCP_ResponsibleBody': 'Responsible body',
            
            # Asset subtypes
            'AST_Datatype': 'Datatypes',
            'AST_IT-System': 'IT-systems',
            'AST_Application': 'Applications',
            
            # Person subtypes
            'PER_Person': 'Persons',
            'PER_DataProtectionOfficer': 'Data protection officers',
            
            # Control subtypes
            'CTL_TOM': 'TOMs',
            
            'PRO_DPIA': 'Data protection impact assessment',
            'PRO_DataTransfer': 'Data transfers',
            'PRO_DataProcessing': 'Data processings',
            
            # Incident subtypes
            'INC_Incident': 'Data privacy incidents',
            
            # Scenario subtypes
            'SCN_Scenario': 'Scenarios',
        }
        
        if technicalSubType in subtype_mapping:
            return subtype_mapping[technicalSubType]
        
        # Fallback: Try to convert by removing prefix and formatting
        name = technicalSubType
        prefixes = ['SCP_', 'AST_', 'PER_', 'CTL_', 'PRO_', 'INC_', 'DOC_', 'SCN_']
        for prefix in prefixes:
            if name.startswith(prefix):
                name = name[len(prefix):]
                break
        
        # Convert to dashboard-friendly format
        # SCP_Controller -> Controllers, AST_Datatype -> Datatypes
        if name.endswith('s') or name.endswith('es'):
            # Already plural
            return name.replace('_', ' ').replace('-', ' ').title()
        else:
            # Make plural for dashboard display
            if name.lower() in ['controller', 'processor', 'application', 'datatype', 'it-system']:
                if name.lower() == 'it-system':
                    return 'IT-systems'
                elif name.lower() == 'datatype':
                    return 'Datatypes'
                elif name.lower() == 'application':
                    return 'Applications'
                else:
                    return name.replace('_', ' ').replace('-', ' ').title() + 's'
            else:
                    return name.replace('_', ' ').replace('-', ' ').title()
    
    def _handleMultipleCreates(self, data: Dict, message: str) -> Dict:
        """
        Handle multiple create operations in one message.
        
        Example: "create a new scope 'SCOPE-1' and also create a new Data protection officer 'John'"
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[_handleMultipleCreates] Received data: {data}")
        
        operations = data.get('operations', [])
        if not operations or len(operations) == 0:
            logger.error(f"[_handleMultipleCreates] No operations found in data")
            return self._error("No create operations found in request.")
        
        logger.info(f"[_handleMultipleCreates] Processing {len(operations)} create operations")
        
        # Ensure ISMSHandler is initialized
        if not self._ismsHandler:
            # Lazy initialization of VeriniceTool
            veriniceTool = getattr(self, '_veriniceTool', None)
            if not veriniceTool:
                try:
                    from tools.veriniceTool import VeriniceTool
                    veriniceTool = VeriniceTool()
                    self._veriniceTool = veriniceTool
                except Exception as e:
                    return self._error(f"Failed to initialize ISMS client: {str(e)}")
            
            if not veriniceTool._ensureAuthenticated():
                return self._error("ISMS client not available")
            
            llmTool = getattr(self, '_llmTool', None)
            event_callback = self.state.get('_event_callback') or getattr(self, '_event_callback', None)
            self._ismsHandler = ISMSHandler(veriniceTool, self._formatVeriniceResult, llmTool, event_callback)
            # Share state between MainAgent and ISMSHandler for context tracking
            self._ismsHandler.state = self.state
        
        results = []
        errors = []
        
        for i, op in enumerate(operations, 1):
            operation_type = op.get('operation', 'create')
            object_type = op.get('objectType')
            object_name = op.get('objectName')
            subtype = op.get('subType')
            is_bulk = op.get('isBulk', False)
            count = op.get('count', 0)
            
            logger.info(f"[_handleMultipleCreates] Operation {i}: op={operation_type}, type={object_type}, isBulk={is_bulk}, count={count}")
            
            # Handle bulk updates (Pattern 0: Add N items to subtype)
            if operation_type == 'update' and is_bulk:
                logger.info(f"[_handleMultipleCreates] Handling bulk update: {count} {object_type}(s) to subtype {subtype}")
                
                # Logic for bulk update from context
                # 1. Get recently created objects
                created_objects = self.state.get('_created_objects', {})
                if not created_objects:
                    # Also check ISMSHandler state
                    if self._ismsHandler and hasattr(self._ismsHandler, 'state'):
                        created_objects = self._ismsHandler.state.get('_created_objects', {})
                
                # Filter for objects of this type
                relevant_objects = []
                # Sort by key to ensure deterministic order
                for key in sorted(created_objects.keys()):
                    obj_info = created_objects[key]
                    if obj_info.get('objectType', '').lower() == object_type.lower():
                        relevant_objects.append(obj_info)
                
                # Use a pointer in state to track which objects have been assigned
                start_index = self.state.get('_bulk_update_pointer', 0)
                objects_to_update = relevant_objects[start_index : start_index + count]
                self.state['_bulk_update_pointer'] = start_index + count
                
                if objects_to_update:
                    success_count = 0
                    updated_names = []
                    for obj in objects_to_update:
                        obj_name = obj.get('name')
                        
                        # Execute update
                        update_msg = f"update {object_type} {obj_name} subType {subtype}"
                        result = self._ismsHandler.execute('update', object_type, update_msg, subtype)
                        if result.get('status') == 'success':
                            success_count += 1
                            updated_names.append(obj_name)
                        else:
                            errors.append(f"Failed to update {obj_name}: {result.get('error')}")
                    
                    if success_count > 0:
                        results.append(f"✅ Assigned {success_count} {object_type}(s) ({', '.join(updated_names)}) to subtype '{subtype}'")
                else:
                    errors.append(f"No {object_type}s found to update (context missing or exhausted)")
                
                continue

            # Handle bulk operations (Pattern 0 creates bulk operations without names)
            if is_bulk and count > 0:
                logger.info(f"[_handleMultipleCreates] Operation {i} is bulk create: {count} {object_type}(s) with subtype {subtype}")
                bulk_result = self._handleBulkCreate(op, message)
                logger.info(f"[_handleMultipleCreates] Bulk create result: status={bulk_result.get('status')}, error={bulk_result.get('error', 'None')}, result={str(bulk_result.get('result', 'None'))[:100]}")
                if bulk_result.get('status') == 'success':
                    results.append(bulk_result.get('result', f"✅ Created {count} {object_type}(s)"))
                else:
                    error_msg = bulk_result.get('error', 'Bulk create failed')
                    if not error_msg or error_msg == 'Bulk create failed':
                        # Try to get more details from result
                        result_str = str(bulk_result.get('result', ''))
                        if result_str:
                            error_msg = result_str[:200]
                    errors.append(f"Operation {i}: {error_msg}")
                continue
            
            if not object_type or not object_name:
                errors.append(f"Operation {i}: Missing object type or name")
                continue
            
            # Emit thought for each operation
            self._emit_thought('thought', f"Creating {object_type} '{object_name}' ({i}/{len(operations)})...")
            
            # Build create message with subtype in the message itself
            # This allows the normal extraction flow to handle subtype matching
            create_message = f"create {object_type} {object_name}"
            if subtype:
                create_message += f" subType {subtype}"
            
            logger.info(f"[_handleMultipleCreates] Executing: {create_message} with subtype: {subtype}")
            
            # Pass None for preDetectedSubType - let normal flow extract subtype from message
            # This ensures proper subtype matching via _matchSubType
            result = self._ismsHandler.execute('create', object_type, create_message, None)
            
            logger.info(f"[_handleMultipleCreates] Result for operation {i}: status={result.get('status')}, error={result.get('error', 'None')}")
            
            if result.get('status') == 'success':
                results.append(f"✅ Created {object_type} '{object_name}'" + (f" (subtype: {subtype})" if subtype else ""))
                
                # Store created object in state for contextual linking
                # Extract object ID from result if available
                result_data = result.get('result', {})
                if isinstance(result_data, dict):
                    object_id = result_data.get('objectId') or result_data.get('id') or result_data.get('resourceId')
                else:
                    # Try to extract from ISMSHandler state if it was stored there
                    if self._ismsHandler and hasattr(self._ismsHandler, 'state'):
                        created_objs = self._ismsHandler.state.get('_created_objects', {})
                        key = f"{object_type}:{object_name.lower().replace('_', ' ').replace('-', ' ').strip()}"
                        if key in created_objs:
                            object_id = created_objs[key].get('objectId')
                        else:
                            object_id = None
                    else:
                        object_id = None
                
                # Store in MainAgent state for contextual operations
                if '_created_objects' not in self.state:
                    self.state['_created_objects'] = {}
                key = f"{object_type}:{object_name.lower().replace('_', ' ').replace('-', ' ').strip()}"
                self.state['_created_objects'][key] = {
                    'objectId': object_id,
                    'objectType': object_type,
                    'name': object_name,
                    'domainId': None  # Will be resolved when needed
                }
                logger.info(f"[_handleMultipleCreates] Stored created object in state: {key}")
            else:
                error_msg = result.get('error', 'Unknown error')
                errors.append(f"❌ Failed to create {object_type} '{object_name}': {error_msg}")
        
        # Build combined response
        if results and not errors:
            # All succeeded
            response = f"✅ All operations completed:\n" + "\n".join(f"  {r}" for r in results)
            return self._success(response)
        elif results and errors:
            # Some succeeded, some failed
            response = f"⚠️ Partial success:\n" + "\n".join(f"  {r}" for r in results) + "\n" + "\n".join(f"  {e}" for e in errors)
            return self._success(response)  # Still return success since at least one worked
        else:
            # All failed
            response = f"❌ All operations failed:\n" + "\n".join(f"  {e}" for e in errors)
            return self._error(response)
    
    def _handleCreateAndLink(self, data: Dict, message: str) -> Dict:
        """
        Handle create-and-link operations as a two-step process:
        1. Create the source object
        2. Link it to the target object
        
        This method acknowledges the multi-step nature of the operation and provides
        clear feedback about each step, even if the linking step fails.
        """
        source_type = data.get('source_type')
        source_name = data.get('source_name')
        target_type = data.get('target_type')
        target_name = data.get('target_name')
        
        if not source_type or not source_name or not target_name:
            return self._error("Missing required parameters for create and link operation")
        
        # Lazy initialization of VeriniceTool (fixes timing issue with Keycloak)
        veriniceTool = getattr(self, '_veriniceTool', None)
        if not veriniceTool:
            try:
                from tools.veriniceTool import VeriniceTool
                veriniceTool = VeriniceTool()
                self._veriniceTool = veriniceTool
            except Exception as e:
                self._emit_thought('error', f"Failed to initialize ISMS client: {str(e)}")
                return self._error(get_error_message('connection', 'isms_init_failed', error=str(e)))
        
        # Ensure authentication and ObjectManager are ready
        if not veriniceTool._ensureAuthenticated():
            self._emit_thought('error', "ISMS client not available")
            return self._error(get_error_message('connection', 'isms_init_failed', error='ISMS client not available'))
        
        # Ensure ObjectManager is initialized (may have failed at startup)
        if not veriniceTool.objectManager:
            # Try to ensure authentication again (this will create ObjectManager)
            if not veriniceTool._ensureAuthenticated():
                self._emit_thought('error', "Authentication failed")
                return self._error(get_error_message('connection', 'isms_auth_failed'))
            # If still no ObjectManager after authentication, return error
            if not veriniceTool.objectManager:
                self._emit_thought('error', "Object manager unavailable")
                return self._error(get_error_message('connection', 'isms_object_manager_unavailable'))
        
        if not self._ismsHandler:
            llmTool = getattr(self, '_llmTool', None)
            event_callback = self.state.get('_event_callback') or getattr(self, '_event_callback', None)
            self._ismsHandler = ISMSHandler(veriniceTool, self._formatVeriniceResult, llmTool, event_callback)
            # Share state between MainAgent and ISMSHandler for context tracking
            self._ismsHandler.state = self.state
        
        domainId, unitId = self._ismsHandler._getDefaults()
        if not domainId:
            return self._error("No domain found. Please ensure you have access to a domain.")
        
        # Step 1: Create the source object
        import re
        clean_source_name = re.sub(r'["\']', '', source_name).strip()
        
        create_result = self._ismsHandler.execute('create', source_type, f"create {source_type} {source_name}", None)
        if create_result.get('status') != 'success':
            return self._error(f"Step 1 (Create) failed: Could not create {source_type} '{source_name}': {create_result.get('error', 'Unknown error')}")
        
        # Small delay to ensure state is updated
        import time
        time.sleep(0.2)
        
        # Extract created object ID - SIMPLIFIED: Search state by name match
        created_id = None
        created_name = clean_source_name
        
        if self._ismsHandler and hasattr(self._ismsHandler, 'state'):
            created_objects = self._ismsHandler.state.get('_created_objects', {})
            # Search all objects of this type and match by name (case-insensitive)
            # Prefer exact matches, but also try partial matches
            best_match = None
            for key, obj_data in created_objects.items():
                if key.startswith(f"{source_type}:"):
                    stored_name = obj_data.get('name', '')
                    stored_name_normalized = stored_name.lower().strip()
                    clean_name_normalized = clean_source_name.lower().strip()
                    
                    # Exact match (preferred)
                    if stored_name_normalized == clean_name_normalized:
                        created_id = obj_data.get('objectId')
                        created_name = stored_name
                        break
                    # Partial match (fallback - in case name was modified during extraction)
                    elif clean_name_normalized in stored_name_normalized or stored_name_normalized in clean_name_normalized:
                        if not best_match or len(stored_name) > len(best_match.get('name', '')):
                            best_match = obj_data
            
            # Use best match if no exact match found
            if not created_id and best_match:
                created_id = best_match.get('objectId')
                created_name = best_match.get('name', clean_source_name)
        
        # If not found in handler state, check coordinator state
        if not created_id and self._ismsHandler and hasattr(self._ismsHandler, 'coordinator'):
            coordinator = self._ismsHandler.coordinator
            if coordinator and hasattr(coordinator, 'state'):
                created_objects = coordinator.state.get('_created_objects', {})
                for key, obj_data in created_objects.items():
                    if key.startswith(f"{source_type}:"):
                        stored_name = obj_data.get('name', '')
                        if stored_name.lower().strip() == clean_source_name.lower().strip():
                            created_id = obj_data.get('objectId') or obj_data.get('id')
                            created_name = stored_name
                            break
        
        # Step 2: Link the created object to the target
        # Acknowledge this is a multi-step operation
        veriniceTool = getattr(self, "_veriniceTool", None)
        if not veriniceTool:
            return self._success(f"✅ Step 1 completed: Created {source_type} '{source_name}'\n⚠️  Step 2 (Link) skipped: VeriniceTool not available")
        
        domainId, unitId = self._ismsHandler._getDefaults()
        
        # Try to use linking tool from MCP server pattern
        try:
            from mcp.tools.linking import link_objects
            import re
            
            # Use created_id if available, otherwise use the actual stored name (not the original source_name)
            # The linking tool will handle UUIDs directly or resolve by name with retry
            link_params = {
                'source_type': source_type,
                'source_name': created_id if created_id else created_name,  # Use ID if available, else use actual stored name
                'target_name': target_name,
                'target_type': target_type,
                'domain_id': domainId,
            }
            
            # Try single object linking first (let the system work naturally)
            link_result = link_objects(
                verinice_tool=veriniceTool,
                state=self.state,
                **link_params
            )
            
            # If linking failed and the error suggests it's a subtype, automatically retry as bulk linking
            if not link_result.get('success'):
                error_msg = link_result.get('error', '')
                # The error message contains: "'IT-System assets' appears to be a subtype"
                if 'appears to be a subtype' in error_msg.lower() or ('subtype' in error_msg.lower() and 'try:' in error_msg.lower()):
                    # Extract subtype from target_name - try to parse "IT-System assets" -> "IT-System"
                    clean_target = re.sub(r'["\']', '', target_name).strip()
                    # Pattern: "subtype assets" or "subtype assets assets" or "the subtype assets"
                    patterns = [
                        r'^([A-Za-z0-9_\s-]+?)\s+assets?\s*(?:assets?)?$',  # "IT-System assets" or "IT-System assets assets"
                        r'^the\s+([A-Za-z0-9_\s-]+?)\s+assets?\s*(?:assets?)?$',  # "the IT-System assets"
                    ]
                    detected_subtype = None
                    for pattern in patterns:
                        subtype_match = re.match(pattern, clean_target, re.IGNORECASE)
                        if subtype_match:
                            detected_subtype = subtype_match.group(1).strip()
                            break
                    
                    if detected_subtype:
                        # Normalize common variations
                        detected_subtype_normalized = detected_subtype.replace('-', ' ').replace('_', ' ').strip()
                        
                        # Try to match with known subtypes
                        common_subtypes = ['IT-System', 'IT System', 'Datatype', 'Data Type', 'Application', 'Process', 'Service']
                        for common_subtype in common_subtypes:
                            common_normalized = common_subtype.replace('-', ' ').replace('_', ' ').strip().lower()
                            if detected_subtype_normalized.lower() == common_normalized or detected_subtype_normalized.lower() in common_normalized:
                                detected_subtype = common_subtype
                                break
                        
                        # Retry as bulk linking with detected subtype
                        # CRITICAL: Use the same domainId that was used for creation
                        bulk_link_params = {
                            'source_type': source_type,
                            'source_name': created_id if created_id else created_name,
                            'target_type': target_type,
                            'subtype': detected_subtype,  # No target_name for bulk linking
                            'domain_id': domainId,  # Same domain as creation
                        }
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.info(f"[_handleCreateAndLink] Retrying as bulk link: subtype='{detected_subtype}', domain='{domainId}', source='{created_id or created_name}'")
                        link_result = link_objects(
                            verinice_tool=veriniceTool,
                            state=self.state,
                            **bulk_link_params
                        )
            
            if link_result.get('success'):
                link_message = link_result.get('message', f"Linked to {target_type} '{target_name}'")
                return self._success(f"✅ Multi-step operation completed:\n  Step 1: Created {source_type} '{source_name}'\n  Step 2: {link_message}")
            else:
                # Provide clear feedback about multi-step operation
                link_error = link_result.get('error', 'Unknown error')
                return self._success(f"✅ Step 1 completed: Created {source_type} '{source_name}'\n⚠️  Step 2 (Link) failed: {link_error}\n\nNote: The {source_type} was created successfully. The linking step encountered an issue.")
        except ImportError:
            # If linking tool not available, acknowledge multi-step nature
            return self._success(f"✅ Step 1 completed: Created {source_type} '{source_name}'\n⚠️  Step 2 (Link) skipped: Linking tool not available")
        except Exception as e:
            # If linking fails, still acknowledge multi-step operation
            return self._success(f"✅ Step 1 completed: Created {source_type} '{source_name}'\n⚠️  Step 2 (Link) failed: {str(e)}\n\nNote: The {source_type} was created successfully. The linking step encountered an issue.")
    
    def _emit_thought(self, step_type: str, content: str, metadata: Dict = None):
        """Emit a reasoning step to the frontend via event callback"""
        event_callback = self.state.get('_event_callback') or getattr(self, '_event_callback', None)
        if event_callback:
            event_callback(step_type, {
                'content': content,
                **(metadata or {})
            })
    
    def _handleVeriniceOp(self, command: Dict, message: str) -> Dict:
        """Handle ISMS operation using ISMSHandler"""
        # Emit thought event: Starting operation
        self._emit_thought('thought', f"Processing {command.get('operation', 'operation')} for {command.get('objectType', 'object')}")
        
        # Lazy initialization of VeriniceTool (fixes timing issue with Keycloak)
        veriniceTool = getattr(self, '_veriniceTool', None)
        if not veriniceTool:
            try:
                from tools.veriniceTool import VeriniceTool
                veriniceTool = VeriniceTool()
                self._veriniceTool = veriniceTool
            except Exception as e:
                self._emit_thought('error', f"Failed to initialize ISMS client: {str(e)}")
                return self._error(get_error_message('connection', 'isms_init_failed', error=str(e)))
        
        # Ensure authentication and ObjectManager are ready
        if not veriniceTool._ensureAuthenticated():
            self._emit_thought('error', "ISMS client not available")
            return self._error(get_error_message('connection', 'isms_init_failed', error='ISMS client not available'))
        
        # Ensure ObjectManager is initialized (may have failed at startup)
        # _ensureAuthenticated should create it, but double-check
        if not veriniceTool.objectManager:
            # Try to ensure authentication again (this will create ObjectManager)
            if not veriniceTool._ensureAuthenticated():
                self._emit_thought('error', "Authentication failed")
                return self._error(get_error_message('connection', 'isms_auth_failed'))
            # If still no ObjectManager after authentication, return error
            if not veriniceTool.objectManager:
                self._emit_thought('error', "Object manager unavailable")
                return self._error(get_error_message('connection', 'isms_object_manager_unavailable'))
        
        if not self._ismsHandler:
            # Pass LLM tool if available for intelligent parsing
            llmTool = getattr(self, '_llmTool', None)
            event_callback = self.state.get('_event_callback') or getattr(self, '_event_callback', None)
            self._ismsHandler = ISMSHandler(veriniceTool, self._formatVeriniceResult, llmTool, event_callback)
            # Share state between MainAgent and ISMSHandler for context tracking
            self._ismsHandler.state = self.state
        else:
            # CRITICAL: Always ensure state is shared (state reference might change)
            self._ismsHandler.state = self.state
        
        # CRITICAL: Handle role/subtype assignment FIRST (before other operations)
        if command.get('isRoleAssignment'):
            # This could be:
            # 1. Update existing object: "set role for the DPO for the person Ruby"
            # 2. Create with subtype: "set role for the Data protection officer and create person Ruby"
            # 3. Bulk update: "add John,Anna,Eddie to DPO"
            objectType = command.get('objectType')
            objectName = command.get('objectName')
            names = command.get('names', [])  # For bulk operations
            subtype = command.get('subtype')
            isMultiStep = command.get('isMultiStep', False)
            isBulk = command.get('isBulk', False)
            
            # Handle bulk role assignment
            if isBulk and names:
                if not objectType or not subtype:
                    return self._error("Missing required parameters for bulk role assignment")
                
                domainId, unitId = self._ismsHandler._getDefaults()
                if not domainId:
                    return self._error("No domain found. Please ensure you have access to a domain.")
                
                subTypesInfo = self._ismsHandler._getSubTypesInfo(domainId, objectType)
                availableSubTypes = subTypesInfo.get('subTypes', [])
                if availableSubTypes:
                    matchedSubtype = self._ismsHandler._matchSubType(subtype, availableSubTypes)
                    if not matchedSubtype:
                        return self._error(f"Subtype '{subtype}' not found for {objectType}. Available subtypes: {', '.join(availableSubTypes)}")
                    
                    # Update each person
                    results = []
                    for name in names:
                        result = self._ismsHandler.execute('update', objectType, f"update {objectType} {name} subtype {matchedSubtype}", matchedSubtype)
                        if result.get('status') == 'success':
                            results.append(name)
                    
                    if results:
                        return self._success(f"Updated {len(results)} {objectType}(s) to subtype '{matchedSubtype}': {', '.join(results)}")
                    else:
                        return self._error(f"Failed to update any {objectType}(s)")
                else:
                    return self._error(f"No subtypes available for {objectType}")
            
            # Single role assignment
            if not objectType or not objectName or not subtype:
                return self._error("Missing required parameters for role/subtype assignment")
            
            domainId, unitId = self._ismsHandler._getDefaults()
            if not domainId:
                return self._error("No domain found. Please ensure you have access to a domain.")
            
            subTypesInfo = self._ismsHandler._getSubTypesInfo(domainId, objectType)
            availableSubTypes = subTypesInfo.get('subTypes', [])
            if availableSubTypes:
                # Map common abbreviations before matching
                subtype_mapping = {
                    'dpo': 'Data protection officer',
                    'data protection officer': 'Data protection officer',
                }
                subtype_lower = subtype.lower()
                if subtype_lower in subtype_mapping:
                    subtype = subtype_mapping[subtype_lower]
                
                # Try to match the provided subtype
                if subtype in availableSubTypes:
                    matchedSubtype = subtype
                else:
                    # Use _matchSubType from ISMSHandler (takes providedSubType, availableSubTypes)
                    matchedSubtype = self._ismsHandler._matchSubType(subtype, availableSubTypes)
                    if not matchedSubtype:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.error(f"[_handleVeriniceOp] Subtype matching failed: provided='{subtype}', available={availableSubTypes[:5]}")
                        return self._error(get_error_message('validation', 'invalid_subtype', subType=subtype, available=', '.join(availableSubTypes[:5])))
                subtype = matchedSubtype
            
            # CRITICAL: If this is a multi-step create operation, create the person with the subtype
            if isMultiStep and command.get('operation') == 'create':
                # Use the matched subtype (already matched above)
                create_message = f"create {objectType} {objectName} subType {subtype}"
                # Pass the subtype as preDetectedSubType to ensure it's used
                result = self._ismsHandler.execute('create', objectType, create_message, subtype)
                if result.get('status') == 'success':
                    return self._success(f"Created {objectType} '{objectName}' with role/subtype '{subtype}'")
                else:
                    error_msg = result.get('error', 'Unknown error')
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"[_handleVeriniceOp] Failed to create {objectType} '{objectName}' with subtype '{subtype}': {error_msg}")
                    # Extract specific error details
                    error_detail = error_msg if error_msg else (result.get('error') or result.get('message') or 'Unknown error')
                    return self._error(f"Failed to create {objectType} '{objectName}': {error_detail}")
            
            # Otherwise, this is an update operation - resolve existing object
            # CRITICAL: If person doesn't exist, create them with the subtype instead of erroring
            # This handles: "set role for the Data protection officer for the person Ruby"
            # If Ruby doesn't exist, create Ruby with DPO subtype
            resolve_message = f'get {objectType} "{objectName}"'
            objectId = self._ismsHandler._resolveToId(objectType, resolve_message, domainId)
            if not objectId:
                # Fallback: try without quotes
                resolve_message = f'get {objectType} {objectName}'
                objectId = self._ismsHandler._resolveToId(objectType, resolve_message, domainId)
            if not objectId:
                # Try with original message (contains role assignment pattern)
                objectId = self._ismsHandler._resolveToId(objectType, message, domainId)
            
            # If object doesn't exist and this is a person with role assignment, create them with the subtype
            # CRITICAL: "set role for the Data protection officer for the person Ruby" 
            # should create Ruby with DPO subtype if Ruby doesn't exist
            if not objectId and objectType == 'person':
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"[_handleVeriniceOp] Person '{objectName}' not found, creating with subtype '{subtype}'")
                create_message = f"create {objectType} {objectName} subType {subtype}"
                result = self._ismsHandler.execute('create', objectType, create_message, subtype)
                if result.get('status') == 'success':
                    return self._success(f"Created {objectType} '{objectName}' with role/subtype '{subtype}' (person didn't exist, so created with the role)")
                else:
                    # Extract specific error from result
                    error_detail = result.get('error') or result.get('message') or 'Failed to create person'
                    return self._error(f"Person '{objectName}' doesn't exist and failed to create: {error_detail}")
            
            if not objectId:
                return self._error(get_error_message('validation', 'object_not_found_with_name', objectType=objectType, name=objectName))
            
            # Use the domain where object was found
            actualDomainId = domainId
            
            updateData = {'subType': subtype}
            result = veriniceTool.updateObject(objectType, actualDomainId, objectId, updateData)
            
            if result.get('success'):
                return self._success(f"Updated {objectType} '{objectName}' with role/subtype '{subtype}'")
            else:
                error_msg = result.get('error', 'Unknown error')
                if 'Cannot change a sub type' in str(error_msg) or 'sub type' in str(error_msg).lower():
                    current_obj = veriniceTool.getObject(objectType, actualDomainId, objectId)
                    current_subtype = 'unknown'
                    if current_obj.get('success') and current_obj.get('object'):
                        current_subtype = current_obj['object'].get('subType', 'unknown')
                    return self._error(f"Cannot change subtype of existing {objectType} '{objectName}'. Verinice does not allow changing subtypes after creation. Current subtype: {current_subtype}. To assign a role, create the person with the desired subtype from the start.")
                return self._error(f"Failed to update {objectType} '{objectName}': {error_msg}")
        
        # CRITICAL: Handle list operations - sync state before and after
        if command.get('operation') == 'list':
            # Ensure state is synced before list operation
            self._ismsHandler.state = self.state
        
        if command.get('operation') == 'create' and command.get('isBulk'):
            return self._handleBulkCreate(command, message)
        
        # Handle delete operations (both bulk and single from context)
        if command.get('operation') == 'delete' and (command.get('isBulk') or command.get('items')):
            # If objectType is None, try to get from state
            if not command.get('objectType') and command.get('needsContext'):
                last_list = self.state.get('_last_list_result') or {}
                if not last_list and self._ismsHandler and hasattr(self._ismsHandler, 'state'):
                    last_list = self._ismsHandler.state.get('_last_list_result', {})
                if last_list.get('objectType'):
                    command['objectType'] = last_list.get('objectType')
                    command['items'] = last_list.get('items', [])
                    command['count'] = last_list.get('count', 0)
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.info(f"[_handleVeriniceOp] Retrieved context from state: objectType={command.get('objectType')}, count={command.get('count')}")
            
            if command.get('objectType'):
                return self._handleBulkDelete(command, message)
            else:
                return self._error("I need to know what to delete. Please specify the object type (e.g., 'delete all persons') or list objects first.")
        
        if command.get('operation') == 'link' and command.get('isContextual'):
            return self._handleContextualLink(command, message)
        
        # Handle multi-link operations
        if command.get('operation') == 'link' and command.get('isMultiLink'):
            return self._handleMultiLink(command, message)
        
        # Handle standalone link operations (support both naming conventions)
        if command.get('operation') == 'link':
            source_name = command.get('sourceName') or command.get('source_name')
            source_type = command.get('sourceType') or command.get('source_type') or command.get('objectType')
            target_name = command.get('targetName') or command.get('target_name')
            target_type = command.get('targetType') or command.get('target_type')
            subtype = command.get('subtype')
            
            # For bulk linking (subtype-based), source_name or target_name can be None
            if source_type:
                if not source_type:
                    return self._error("Missing source type for link operation")
                
                domainId, unitId = self._ismsHandler._getDefaults() if self._ismsHandler else (None, None)
                if not domainId:
                    return self._error("No domain found. Please ensure you have access to a domain.")
                
                # Use linking tool
                from mcp.tools.linking import link_objects
                
                # Handle bulk linking (subtype-based) - if source_name is None, link all objects of subtype
                if source_name is None and subtype:
                    # Bulk link: link all persons with DPO subtype to target
                    if source_type == 'person' and subtype == 'Data protection officer':
                        # List all DPO persons first
                        list_result = self._ismsHandler.execute('list', 'person', 'list all persons', None, 'Data protection officer')
                        if list_result.get('status') == 'success':
                            persons_data = list_result.get('result', {})
                            if isinstance(persons_data, dict):
                                persons = persons_data.get('objects', {}).get('items', [])
                            elif isinstance(persons_data, list):
                                persons = persons_data
                            else:
                                persons = []
                            
                            if persons:
                                results = []
                                errors = []
                                for person in persons:
                                    person_name = person.get('name') if isinstance(person, dict) else str(person)
                                    link_result = link_objects(
                                        verinice_tool=veriniceTool,
                                        state=self.state,
                                        source_type=source_type,
                                        source_name=person_name,
                                        target_type=target_type or 'scope',
                                        target_name=target_name,
                                        domain_id=domainId
                                    )
                                    if link_result.get('success'):
                                        results.append(person_name)
                                    else:
                                        errors.append(f"{person_name}: {link_result.get('error', 'Unknown error')}")
                                
                                if results:
                                    return self._success(f"✅ Linked {len(results)} DPO person(s) to {target_type} '{target_name}': {', '.join(results[:5])}")
                                else:
                                    return self._error(f"Failed to link DPO persons: {', '.join(errors[:3])}")
                            else:
                                return self._error("No DPO persons found to link")
                        else:
                            return self._error(f"Failed to list DPO persons: {list_result.get('error', 'Unknown error')}")
                
                link_result = link_objects(
                    verinice_tool=veriniceTool,
                    state=self.state,
                    source_type=source_type,
                    source_name=source_name,
                    target_type=target_type or 'asset',  # Default to asset if not specified
                    target_name=target_name,
                    subtype=subtype,
                    domain_id=domainId
                )
                
                if link_result.get('success'):
                    if subtype and source_name is None:
                        return self._success(f"✅ Linked {subtype} {source_type}s to {target_type} '{target_name}'")
                    elif subtype:
                        return self._success(f"✅ Linked {source_type} '{source_name}' to {subtype} {target_type or 'assets'}")
                    elif target_name:
                        return self._success(f"✅ Linked {source_type} '{source_name}' to {target_type} '{target_name}'")
                    else:
                        return self._success(f"✅ Linked {source_type} '{source_name}'")
                else:
                    error_msg = link_result.get('error', 'Unknown error')
                    return self._error(f"Failed to link {source_type} '{source_name or subtype}': {error_msg}")
        
        if command.get('operation') == 'get' and command.get('returnSubtype'):
            # CRITICAL: Ensure handler is initialized and state is shared
            if not self._ismsHandler:
                llmTool = getattr(self, '_llmTool', None)
                event_callback = self.state.get('_event_callback') or getattr(self, '_event_callback', None)
                self._ismsHandler = ISMSHandler(veriniceTool, self._formatVeriniceResult, llmTool, event_callback)
            # CRITICAL: Always sync state before setting flag
            self._ismsHandler.state = self.state
            self.state['_returnSubtype'] = True
            # If objectName is provided, use it to construct a simpler message for _handleGet
            if command.get('objectName'):
                objectName = command.get('objectName')
                objectType = command.get('objectType', 'asset')
                # Construct a simple message that _resolveToId can parse
                message = f"get {objectType} {objectName}"
        
        # Pass pre-detected subtype if available (from router detection)
        preDetectedSubType = command.get('subType') if command.get('isSubtypeFirst') else None
        
        # Debug logging for conversational list operations
        if command.get('operation') == 'list':
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"[_handleVeriniceOp] Executing list operation for {command.get('objectType')} from message: {message[:80]}")
            subtypeFilter = command.get('subtypeFilter')
            if subtypeFilter:
                logger.info(f"[_handleVeriniceOp] Subtype filter detected: {subtypeFilter}")
                result = self._ismsHandler.execute(
                    command.get('operation'),
                    command.get('objectType'),
                    message,
                    preDetectedSubType=None,
                    subtypeFilter=subtypeFilter
                )
                return result if result.get('status') == 'success' else self._error(result.get('result', 'Unknown error'))
        
        # CRITICAL: Ensure state is synced before execute (for returnSubtype flag)
        if self._ismsHandler:
            self._ismsHandler.state = self.state
        
        try:
            result = self._ismsHandler.execute(
                command['operation'],
                command['objectType'],
                message,
                preDetectedSubType=preDetectedSubType
            )
            
            # Debug logging
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"[_handleVeriniceOp] Handler execute returned: status={result.get('status') if result else 'None'}, has_result={bool(result)}")
            
            # Ensure result is valid
            if not result:
                logger.error(f"[_handleVeriniceOp] Handler returned None for {command.get('operation')} {command.get('objectType')}")
                return self._error(f"Handler returned None for {command.get('operation')} operation")
            
            # CRITICAL: After list operations, sync state back to ensure _last_list_result is available for bulk operations
            if command.get('operation') == 'list' and self._ismsHandler and hasattr(self._ismsHandler, 'state'):
                # Sync handler state back to MainAgent state (they should be same reference, but ensure it)
                if '_last_list_result' in self._ismsHandler.state:
                    self.state['_last_list_result'] = self._ismsHandler.state['_last_list_result']
                    logger.info(f"[_handleVeriniceOp] Synced _last_list_result after list operation: {self.state.get('_last_list_result', {}).get('objectType')}")
            
            # This happens when agent asks user to select subtype
            # Can be in either success or error response
            if '_pendingSubtypeSelection' in result:
                # Store pending create operation in agent state for follow-up handling
                self.state['_pendingSubtypeSelection'] = result['_pendingSubtypeSelection']
                # Return the message as success (not error) so it doesn't get formatted with error prefix
                # Preserve the metadata for agentBridge to pass through
                response = {'status': 'success', 'result': result.get('result'), 'type': 'tool_result'}
                response['_pendingSubtypeSelection'] = result['_pendingSubtypeSelection']
                return response
            
            # Ensure result has status
            if 'status' not in result:
                logger.warning(f"[_handleVeriniceOp] Result missing status, adding default: {result}")
                result['status'] = 'success' if result.get('result') else 'error'
            
            return result
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"[_handleVeriniceOp] Error executing {command.get('operation')} for {command.get('objectType')}: {e}", exc_info=True)
            return self._error(f"Error executing {command.get('operation')} operation: {str(e)}")
    
    # ==================== BULK OPERATIONS ====================
    
    def _handleContextualLink(self, command: Dict, message: str) -> Dict:
        """
        Handle contextual linking like "link these person/persons to SCOPE-A"
        Uses state context to find recently created objects
        """
        import logging
        logger = logging.getLogger(__name__)
        
        target_name = command.get('targetName')
        if not target_name:
            # Try to extract target from message
            import re
            match = re.search(r'(?:to|with)\s+([A-Za-z0-9_\s-]+)', message, re.IGNORECASE)
            if match:
                target_name = match.group(1).strip()
        
        if not target_name:
            return self._error("I need to know what to link to. Please specify the target (e.g., 'link these person to SCOPE-A').")
        
        created_objects = self.state.get('_created_objects', {})
        if not created_objects:
            # Also check ISMSHandler state
            if self._ismsHandler and hasattr(self._ismsHandler, 'state'):
                created_objects = self._ismsHandler.state.get('_created_objects', {})
        
        # Filter for persons (or the object type mentioned)
        object_type = command.get('objectType', 'person')
        persons_to_link = []
        
        for key, obj_info in created_objects.items():
            if obj_info.get('objectType', '').lower() == object_type.lower():
                persons_to_link.append(obj_info)
        
        if not persons_to_link:
            return self._error(f"I couldn't find any recently created {object_type}s to link. Please create them first or specify the names explicitly.")
        
        logger.info(f"[_handleContextualLink] Found {len(persons_to_link)} {object_type}(s) to link to '{target_name}'")
        
        # Ensure VeriniceTool is available
        veriniceTool = getattr(self, '_veriniceTool', None)
        if not veriniceTool:
            try:
                from tools.veriniceTool import VeriniceTool
                veriniceTool = VeriniceTool()
                self._veriniceTool = veriniceTool
            except Exception as e:
                return self._error(f"Failed to initialize ISMS client: {str(e)}")
        
        if not veriniceTool._ensureAuthenticated():
            return self._error("ISMS client not available")
        
        domainId, unitId = self._ismsHandler._getDefaults() if self._ismsHandler else (None, None)
        if not domainId:
            return self._error("No domain found. Please ensure you have access to a domain.")
        
        # Link each person to the target scope
        from mcp.tools.linking import link_objects
        
        results = []
        errors = []
        
        for i, person_info in enumerate(persons_to_link, 1):
            person_name = person_info.get('name')
            person_id = person_info.get('objectId')
            
            self._emit_thought('thought', f"Linking {object_type} '{person_name}' to '{target_name}' ({i}/{len(persons_to_link)})...")
            
            # Use linking tool
            link_result = link_objects(
                verinice_tool=veriniceTool,
                state=self.state,
                source_type='scope',
                source_name=target_name,
                target_type=object_type,
                target_name=person_id or person_name,
                domain_id=domainId
            )
            
            if link_result.get('success'):
                results.append(f"✅ Linked {object_type} '{person_name}' to '{target_name}'")
            else:
                error_msg = link_result.get('error', 'Unknown error')
                errors.append(f"❌ Failed to link {object_type} '{person_name}': {error_msg}")
        
        # Build response
        if results and not errors:
            response = f"✅ All {object_type}s linked successfully:\n" + "\n".join(f"  {r}" for r in results)
            return self._success(response)
        elif results and errors:
            response = f"⚠️ Partial success:\n" + "\n".join(f"  {r}" for r in results) + "\n" + "\n".join(f"  {e}" for e in errors)
            return self._success(response)
        else:
            response = f"❌ All linking operations failed:\n" + "\n".join(f"  {e}" for e in errors)
            return self._error(response)
    
    def _handleMultiLink(self, command: Dict, message: str) -> Dict:
        """
        Handle multi-link operations like "link SCOPE-B with IT-System assets, and SCOPE-D link with Datatypes assets"
        """
        import logging
        logger = logging.getLogger(__name__)
        
        links = command.get('links', [])
        if not links:
            return self._error("No links specified in multi-link operation")
        
        veriniceTool = getattr(self, '_veriniceTool', None)
        if not veriniceTool:
            try:
                from tools.veriniceTool import VeriniceTool
                veriniceTool = VeriniceTool()
                self._veriniceTool = veriniceTool
            except Exception as e:
                return self._error(f"Failed to initialize ISMS client: {str(e)}")
        
        if not veriniceTool._ensureAuthenticated():
            return self._error("ISMS client not available")
        
        domainId, unitId = self._ismsHandler._getDefaults() if self._ismsHandler else (None, None)
        if not domainId:
            return self._error("No domain found. Please ensure you have access to a domain.")
        
        from mcp.tools.linking import link_objects
        
        results = []
        errors = []
        
        for link in links:
            source = link.get('source', '').strip()
            target = link.get('target', '').strip()
            
            # Infer types and extract subtypes
            source_type = 'scope'  # Default
            if source.upper().startswith('SCOPE-'):
                source_type = 'scope'
            
            target_type = 'asset'  # Default
            subtype = None
            
            # Check if target is a subtype
            if 'it-system' in target.lower():
                subtype = 'IT-System'
                target_name = None
            elif 'datatype' in target.lower():
                subtype = 'Datatype'
                target_name = None
            else:
                target_name = target
            
            logger.info(f"[_handleMultiLink] Linking: {source_type} '{source}' -> {target_type} '{target_name}' (subtype: {subtype})")
            
            link_result = link_objects(
                verinice_tool=veriniceTool,
                state=self.state,
                source_type=source_type,
                source_name=source,
                target_type=target_type,
                target_name=target_name,
                subtype=subtype,
                domain_id=domainId
            )
            
            if link_result.get('success'):
                if subtype:
                    results.append(f"✅ Linked {source} to {subtype} assets")
                else:
                    results.append(f"✅ Linked {source} to {target_name}")
            else:
                errors.append(f"❌ Failed to link {source}: {link_result.get('error', 'Unknown error')}")
        
        if results and not errors:
            return self._success("\n".join(results))
        elif results and errors:
            return self._success("\n".join(results) + "\n" + "\n".join(errors))
        else:
            return self._error("\n".join(errors))
    
    def _handleBulkCreate(self, command: Dict, message: str) -> Dict:
        """
        Handle bulk create operations (e.g., "create 5 persons in DPO now")
        
        Args:
            command: Command dict with operation='create', isBulk=True, objectType, count, subType, namePattern, names
            message: Original user message
        """
        object_type = command.get('objectType')
        count = command.get('count', 1)
        subtype = command.get('subType')
        name_pattern = command.get('namePattern')
        names = command.get('names', [])
        
        if not object_type:
            return self._error("I need to know what to create. Please specify the object type.")
        
        # Ensure VeriniceTool is initialized
        veriniceTool = getattr(self, '_veriniceTool', None)
        if not veriniceTool:
            try:
                from tools.veriniceTool import VeriniceTool
                veriniceTool = VeriniceTool()
                self._veriniceTool = veriniceTool
            except Exception as e:
                return self._error(f"Failed to initialize ISMS client: {str(e)}")
        
        if not veriniceTool._ensureAuthenticated():
            return self._error("ISMS client not available")
        
        if not self._ismsHandler:
            llmTool = getattr(self, '_llmTool', None)
            event_callback = self.state.get('_event_callback') or getattr(self, '_event_callback', None)
            self._ismsHandler = ISMSHandler(veriniceTool, self._formatVeriniceResult, llmTool, event_callback)
            self._ismsHandler.state = self.state
        
        domainId, unitId = self._ismsHandler._getDefaults()
        if not domainId:
            return self._error("No domain found. Please ensure you have access to a domain.")
        
        # Get available subtypes if subtype is provided
        if subtype:
            subTypesInfo = self._ismsHandler._getSubTypesInfo(domainId, object_type)
            availableSubTypes = subTypesInfo.get('subTypes', [])
            if availableSubTypes:
                # Map common abbreviations
                subtype_mapping = {
                    'dpo': 'Data protection officer',
                    'data protection officer': 'Data protection officer',
                }
                subtype_lower = subtype.lower()
                if subtype_lower in subtype_mapping:
                    subtype = subtype_mapping[subtype_lower]
                
                # Match subtype
                if subtype in availableSubTypes:
                    matched_subtype = subtype
                else:
                    matched_subtype = self._ismsHandler._matchSubType(subtype, availableSubTypes)
                    if not matched_subtype:
                        return self._error(f"Invalid subtype '{subtype}'. Available subtypes: {', '.join(availableSubTypes[:5])}")
                    subtype = matched_subtype
        
        created_count = 0
        failed_count = 0
        failed_names = []
        
        # Generate names based on pattern or provided names
        if names:
            # Handle name ranges (e.g. Asset-A,E -> Asset-A, Asset-B, ..., Asset-E)
            # Check if we have 2 names and they look like start/end points
            if len(names) == 2 and count > 2:
                import re
                # Check for "Name-A", "Name-E" pattern (single char suffix)
                # Pattern: something + separator + char
                match1 = re.search(r'^(.*?)[\-_]?([A-Z])$', names[0])
                match2 = re.search(r'^(.*?)[\-_]?([A-Z])$', names[1])
                
                # Also handle just single letters "A", "E"
                if not match1 and len(names[0]) == 1 and names[0].isupper():
                    match1 = re.search(r'^()([A-Z])$', names[0])
                if not match2 and len(names[1]) == 1 and names[1].isupper():
                    match2 = re.search(r'^()([A-Z])$', names[1])
                
                if match1 and match2:
                    prefix1, char1 = match1.groups()
                    prefix2, char2 = match2.groups()
                    
                    # Same prefix (or empty) or second is just suffix
                    if prefix1 == prefix2 or (prefix1 and not prefix2):
                        start_ord = ord(char1)
                        end_ord = ord(char2)
                        
                        # Use prefix1
                        prefix = prefix1
                        
                        # Check if range length matches count
                        if end_ord > start_ord and (end_ord - start_ord + 1) == count:
                            # Generate range
                            separator = '-' if prefix and not prefix.endswith('-') and len(prefix) > 0 else ''
                            name_list = [f"{prefix}{separator}{chr(c)}" for c in range(start_ord, end_ord + 1)]
                        else:
                            name_list = names[:]
                            for i in range(len(names), count):
                                name_list.append(f"{object_type.title()}-{i+1:02d}")
                    else:
                        name_list = names[:]
                        for i in range(len(names), count):
                            name_list.append(f"{object_type.title()}-{i+1:02d}")
                else:
                    name_list = names[:]
                    for i in range(len(names), count):
                        name_list.append(f"{object_type.title()}-{i+1:02d}")
            else:
                # Use provided names, fill rest with defaults if needed
                name_list = names[:]
                for i in range(len(names), count):
                    name_list.append(f"{object_type.title()}-{i+1:02d}")
        elif name_pattern:
            # Parse name pattern like "SCOPE1 TO 5" or "SCOPE1 TO SCOPE5"
            import re
            # Pattern: "PREFIX1 TO 5" or "PREFIX1 TO PREFIX5"
            pattern_match = re.search(r'([A-Za-z]+)(\d+)\s+TO\s+(\d+)', name_pattern, re.IGNORECASE)
            if pattern_match:
                prefix = pattern_match.group(1)
                start_num = int(pattern_match.group(2))
                end_num = int(pattern_match.group(3))
                # Generate names from start to end, but limit to count
                generated = [f"{prefix}{i}" for i in range(start_num, min(start_num + count, end_num + 1))]
                name_list = generated[:count]
            else:
                # Fallback: use pattern as prefix and generate numbers
                name_list = [f"{name_pattern}-{i:02d}" for i in range(1, count + 1)]
        else:
            # Generate default names
            if object_type == 'person' and subtype and 'data protection' in subtype.lower():
                name_list = [f"DPO-{i:02d}" for i in range(1, count + 1)]
            else:
                name_list = [f"{object_type.title()}-{i:02d}" for i in range(1, count + 1)]
        
        # Create each object
        for i, name in enumerate(name_list[:count], 1):
            self._emit_thought('thought', f"Creating {object_type} '{name}' ({i}/{count})...")
            
            create_message = f"create {object_type} {name}"
            if subtype:
                create_message += f" subType {subtype}"
            
            result = self._ismsHandler.execute('create', object_type, create_message, subtype)
            
            if result.get('status') == 'success':
                created_count += 1
            else:
                failed_count += 1
                failed_names.append(name)
                error_msg = result.get('error', 'Unknown error')
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"[_handleBulkCreate] Failed to create {object_type} '{name}': {error_msg}")
        
        # Build response
        if created_count > 0:
            success_msg = f"✅ Successfully created {created_count} {object_type}(s)"
            if subtype:
                success_msg += f" with subtype '{subtype}'"
            if failed_count > 0:
                success_msg += f". {failed_count} failed to create"
                if failed_names:
                    success_msg += f": {', '.join(failed_names[:5])}"
            self._emit_thought('complete', f"Bulk create completed: {created_count} created")
            return self._success(success_msg)
        else:
            return self._error(f"Failed to create any {object_type}s. Please check the error messages above.")
    
    def _handleBulkDelete(self, command: Dict, message: str) -> Dict:
        """
        Handle bulk delete operations (e.g., "remove them all")
        
        Args:
            command: Command dict with operation='delete', isBulk=True, objectType, and optionally items
            message: Original user message
        """
        object_type = command.get('objectType')
        items = command.get('items', [])
        count = command.get('count', 0)
        
        if not object_type:
            return self._error("I need to know what to delete. Please specify the object type (e.g., 'delete all persons').")
        
        # Emit thought: Starting bulk delete
        self._emit_thought('thought', f"Preparing to delete {count} {object_type}(s)...")
        
        # Lazy initialization of VeriniceTool
        veriniceTool = getattr(self, '_veriniceTool', None)
        if not veriniceTool:
            try:
                from tools.veriniceTool import VeriniceTool
                veriniceTool = VeriniceTool()
                self._veriniceTool = veriniceTool
            except Exception as e:
                self._emit_thought('error', f"Failed to initialize ISMS client: {str(e)}")
                return self._error(get_error_message('connection', 'isms_init_failed', error=str(e)))
        
        if not veriniceTool._ensureAuthenticated():
            self._emit_thought('error', "ISMS client not available")
            return self._error(get_error_message('connection', 'isms_init_failed', error='ISMS client not available'))
        
        if not self._ismsHandler:
            llmTool = getattr(self, '_llmTool', None)
            event_callback = self.state.get('_event_callback') or getattr(self, '_event_callback', None)
            self._ismsHandler = ISMSHandler(veriniceTool, self._formatVeriniceResult, llmTool, event_callback)
            # Share state between MainAgent and ISMSHandler for context tracking
            self._ismsHandler.state = self.state
        
        domainId, unitId = self._ismsHandler._getDefaults()
        if not domainId:
            return self._error("No domain found. Please ensure you have access to a domain.")
        
        if not items or len(items) == 0:
            # CRITICAL: Sync state BEFORE checking for last list result
            if self._ismsHandler:
                self._ismsHandler.state = self.state
            
            # Try to get from state (shared between MainAgent and ISMSHandler)
            last_list = self.state.get('_last_list_result') or {}
            if not last_list and self._ismsHandler and hasattr(self._ismsHandler, 'state'):
                last_list = self._ismsHandler.state.get('_last_list_result', {})
                # Sync back to MainAgent state if found in handler
                if last_list:
                    self.state['_last_list_result'] = last_list
            
            items = last_list.get('items', [])
            if not object_type:
                object_type = last_list.get('objectType')
            
            # Debug logging
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"[_handleBulkDelete] State check: objectType={object_type}, items_count={len(items) if items else 0}")
            logger.info(f"[_handleBulkDelete] State keys: {list(self.state.keys())}")
            if self._ismsHandler and hasattr(self._ismsHandler, 'state'):
                logger.info(f"[_handleBulkDelete] Handler state keys: {list(self._ismsHandler.state.keys())}")
        
        # If items are provided from last list, use them
        if items and len(items) > 0:
            deleted_count = 0
            failed_count = 0
            failed_names = []
            
            for item in items:
                if isinstance(item, dict):
                    item_id = item.get('id') or item.get('resourceId')
                    item_name = item.get('name', 'Unknown')
                    
                    if item_id:
                        self._emit_thought('thought', f"Deleting {object_type} '{item_name}'...")
                        result = veriniceTool.deleteObject(object_type, domainId, item_id)
                        if result.get('success'):
                            deleted_count += 1
                        else:
                            failed_count += 1
                            failed_names.append(item_name)
            
            # Clear last list result after bulk delete
            if self._ismsHandler and hasattr(self._ismsHandler, 'state'):
                self._ismsHandler.state.pop('_last_list_result', None)
            
            # Build success message
            if deleted_count > 0:
                success_msg = f"✅ Successfully deleted {deleted_count} {object_type}(s)"
                if failed_count > 0:
                    success_msg += f". {failed_count} failed to delete"
                    if failed_names:
                        success_msg += f": {', '.join(failed_names[:5])}"
                        if len(failed_names) > 5:
                            success_msg += f" and {len(failed_names) - 5} more"
                self._emit_thought('complete', f"Bulk delete completed: {deleted_count} deleted")
                return self._success(success_msg)
            else:
                return self._error(f"Failed to delete any {object_type}s. Please check permissions and try again.")
        else:
            # No items in context - list all objects of this type and delete them
            self._emit_thought('thought', f"Listing all {object_type}s to delete...")
            list_result = veriniceTool.listObjects(object_type, domainId)
            if not list_result.get('success'):
                error_detail = self._ismsHandler._extract_error_details(list_result)
                return self._error(f"Could not list {object_type}s: {error_detail}")
            
            objects = list_result.get('objects', {})
            items_to_delete = objects.get('items', []) if isinstance(objects, dict) else (objects if isinstance(objects, list) else [])
            
            if not items_to_delete:
                return self._success(f"No {object_type}s found to delete.")
            
            deleted_count = 0
            failed_count = 0
            failed_names = []
            
            for item in items_to_delete:
                if isinstance(item, dict):
                    item_id = item.get('id') or item.get('resourceId')
                    item_name = item.get('name', 'Unknown')
                    
                    if item_id:
                        self._emit_thought('thought', f"Deleting {object_type} '{item_name}'...")
                        result = veriniceTool.deleteObject(object_type, domainId, item_id)
                        if result.get('success'):
                            deleted_count += 1
                        else:
                            failed_count += 1
                            failed_names.append(item_name)
            
            # Clear last list result after bulk delete
            if self._ismsHandler and hasattr(self._ismsHandler, 'state'):
                self._ismsHandler.state.pop('_last_list_result', None)
            
            # Build success message
            if deleted_count > 0:
                success_msg = f"✅ Successfully deleted {deleted_count} {object_type}(s)"
                if failed_count > 0:
                    success_msg += f". {failed_count} failed to delete"
                    if failed_names:
                        success_msg += f": {', '.join(failed_names[:5])}"
                        if len(failed_names) > 5:
                            success_msg += f" and {len(failed_names) - 5} more"
                self._emit_thought('complete', f"Bulk delete completed: {deleted_count} deleted")
                return self._success(success_msg)
            else:
                return self._error(f"Failed to delete any {object_type}s. Please check permissions and try again.")
    
    # ==================== FORMATTING ====================
    
    def _formatVeriniceResult(self, toolName: str, result: dict):
        """Format Verinice results using presenter layer"""
        from presenters import TablePresenter
        
        if not isinstance(result, dict):
            return "No data returned."
        
        # List domains
        if 'domains' in result:
            domains = result.get('domains', [])
            count = len(domains)
            if count == 0:
                return "You can't list the domains in your ISMS.If you want to know why read documentation."
            
            presenter = TablePresenter()
            formatted = presenter.present({
                'items': domains,
                'columns': ['Name', 'Description'],
                'title': f"Here are your Domains in your ISMS:",
                'total': count
            })
            if isinstance(formatted, dict) and formatted.get('type') == 'text':
                return formatted.get('content', str(formatted))
            return formatted
        
        # List units
        if 'units' in result:
            units = result.get('units', [])
            count = len(units)
            if count == 0:
                return "I couldn't find any units in your ISMS."
            
            presenter = TablePresenter()
            formatted = presenter.present({
                'items': units,
                'columns': ['Name', 'Description'],
                'title': f"Here are your Units in your ISMS:",
                'total': count
            })
            if isinstance(formatted, dict) and formatted.get('type') == 'text':
                return formatted.get('content', str(formatted))
            return formatted
        
        # Object details (getVeriniceObject) - check BEFORE list/creation
        # This must come BEFORE checking for 'objects' to avoid confusion
        if toolName == 'getVeriniceObject' and result.get('success'):
            data = result.get('data')
            # Ensure data is a single object dict, not a list
            if isinstance(data, dict) and not isinstance(data, list):
                # Format object details - single object
                name = data.get('name', 'Unknown')
                description = data.get('description', '')
                objType = result.get('objectType', 'object')
                lines = [f"**{objType.capitalize()}: {name}**"]
                if description:
                    lines.append(f"Description: {description}")
                # Add other important fields
                for key in ['status', 'subType', 'createdAt', 'updatedAt', 'abbreviation', 'designator']:
                    if key in data and data[key]:
                        lines.append(f"{key.capitalize()}: {data[key]}")
                return "\n".join(lines)
            elif isinstance(data, list) and len(data) == 1:
                singleObj = data[0]
                if isinstance(singleObj, dict):
                    name = singleObj.get('name', 'Unknown')
                    description = singleObj.get('description', '')
                    objType = result.get('objectType', 'object')
                    lines = [f"**{objType.capitalize()}: {name}**"]
                    if description:
                        lines.append(f"Description: {description}")
                    for key in ['status', 'subType', 'createdAt', 'updatedAt', 'abbreviation', 'designator']:
                        if key in singleObj and singleObj[key]:
                            lines.append(f"{key.capitalize()}: {singleObj[key]}")
                    return "\n".join(lines)
        
        # List objects
        if 'objects' in result:
            objects = result.get('objects', {})
            items = objects.get('items', []) if isinstance(objects, dict) else (objects if isinstance(objects, list) else [])
            count = len(items)
            objectType = result.get('objectType', 'object')
            if count == 0:
                # Conversational empty state messages
                if objectType == 'process':
                    return "I couldn't find any processes in your ISMS."
                elif objectType == 'scope':
                    return "I couldn't find any scopes in your ISMS."
                elif objectType == 'asset':
                    return "I couldn't find any assets in your ISMS."
                elif objectType == 'person':
                    return "I couldn't find any people in your ISMS."
                elif objectType == 'control':
                    return "I couldn't find any controls in your ISMS."
                elif objectType == 'scenario':
                    return "I couldn't find any scenarios in your ISMS."
                elif objectType == 'incident':
                    return "I couldn't find any incidents in your ISMS."
                elif objectType == 'document':
                    return "I couldn't find any documents in your ISMS."
                elif objectType.endswith('s'):
                    return f"I couldn't find any {objectType} in your ISMS."
                else:
                    return f"I couldn't find any {objectType}s in your ISMS."
            # Fix pluralization for title
            if objectType == 'process':
                objectTypePlural = 'processes'
                objectTypeCapitalized = 'Processes'
            elif objectType.endswith('s'):
                objectTypePlural = objectType
                objectTypeCapitalized = objectType.capitalize()
            else:
                objectTypePlural = f"{objectType}s"
                objectTypeCapitalized = objectType.capitalize() + 's'
            
            # Determine columns based on object type
            # Essential columns (shown by default) and all columns (for expansion)
            if objectType == 'asset':
                # For assets: essential = Name, SubType; all = Name, SubType, Abbreviation, Description
                essential_columns = ['Name', 'SubType']
                all_columns = ['Name', 'SubType', 'Abbreviation', 'Description']
            elif objectType == 'scope':
                essential_columns = ['Name']
                all_columns = ['Name', 'Description']
            elif objectType == 'person':
                essential_columns = ['Name']
                all_columns = ['Name', 'Abbreviation', 'Description']
            else:
                essential_columns = ['Name']
                all_columns = ['Name', 'Description']
            
            # Conversational title based on object type - include count
            if objectType == 'scope':
                conversational_title = f"I found {count} Scope{'s' if count != 1 else ''} in our ISMS:"
            elif objectType == 'asset':
                conversational_title = f"Here are your {count} Asset{'s' if count != 1 else ''} in your ISMS:"
            elif objectType == 'person':
                conversational_title = f"Here are the {count} Person{'s' if count != 1 else ''} in your ISMS:"
            elif objectType == 'control':
                conversational_title = f"Here are your {count} Control{'s' if count != 1 else ''} in your ISMS:"
            elif objectType == 'process':
                conversational_title = f"Here are your {count} Process{'es' if count != 1 else ''} in your ISMS:"
            elif objectType == 'scenario':
                conversational_title = f"Here are your {count} Scenario{'s' if count != 1 else ''} in your ISMS:"
            elif objectType == 'incident':
                conversational_title = f"Here are your {count} Incident{'s' if count != 1 else ''} in your ISMS:"
            elif objectType == 'document':
                conversational_title = f"Here are your {count} Document{'s' if count != 1 else ''} in your ISMS:"
            else:
                conversational_title = f"I found {count} {objectTypeCapitalized} in our ISMS:"
            
            presenter = TablePresenter()
            formatted = presenter.present({
                'items': items,
                'columns': all_columns,  # All available columns
                'essential_columns': essential_columns,  # Columns to show by default
                'use_essential_columns': True,  # Enable column prioritization
                'title': conversational_title,
                'total': count,
                'objectType': objectType,
                'page': 1,  # Default to first page
                'page_size': 15  # Show 15 items per page when paginated
            })
            # TablePresenter now returns structured table data
            return formatted
        
        # Object creation
        if result.get('success') and 'objectId' in result and toolName == 'createVeriniceObject':
            objName = result.get('objectName', result.get('name', 'Object'))
            objType = result.get('objectType', 'object')
            return f"Created {objType} '{objName}'"
        
        # Object details (getVeriniceObject) - check AFTER creation
        if 'data' in result and result.get('success') and toolName == 'getVeriniceObject':
            data = result.get('data', {})
            if isinstance(data, dict):
                # Format object details
                name = data.get('name', 'Unknown')
                description = data.get('description', '')
                objType = result.get('objectType', 'object')
                lines = [f"**{objType.capitalize()}: {name}**"]
                if description:
                    lines.append(f"Description: {description}")
                # Add other important fields
                for key in ['status', 'subType', 'createdAt', 'updatedAt']:
                    if key in data and data[key]:
                        lines.append(f"{key.capitalize()}: {data[key]}")
                return "\n".join(lines)
        
        if result.get('success'):
            return result.get('message', 'Operation completed successfully')
        
        if result.get('success') is False:
            return f"Error: {result.get('error', 'Unknown error')}"
        
        return "No data to display."
    
    # ==================== HELPERS ====================
    
    def _parseSubtypeSelection(self, message: str, availableSubTypes: List[str]) -> Optional[str]:
        """Parse subtype selection - delegates to helper function"""
        return parseSubtypeSelection(message, availableSubTypes)
    
    def _checkGreeting(self, message: str) -> Optional[str]:
        """Check for greeting - delegates to helper function"""
        processedCount = self.state.get('processedCount', 0)
        return checkGreeting(message, processedCount)
    
    def _loadKnowledgeBase(self) -> Dict:
        """Load knowledge base from JSON file"""
        try:
            # knowledgeBase.json is in utils directory
            kbPath = Path(__file__).parent.parent / 'utils' / 'knowledgeBase.json'
            with open(kbPath, 'r') as f:
                return json.load(f)
        except Exception:
            # Fallback to empty knowledge base if file missing
            return {'topics': {}, 'how_to_create': {}}
    
    def _formatKnowledgeTopic(self, topic: str, data: Dict) -> str:
        """Format a knowledge topic from JSON into readable text"""
        lines = [f"**What is {topic.replace('_', ' ').title()}?**\n"]
        
        if 'definition' in data:
            lines.append("**Definition**")
            lines.append(f"  {data['definition']}\n")
        
        # Types (for assets)
        if 'types' in data:
            lines.append("**Types**")
            for t in data['types']:
                lines.append(f"  • {t}")
            lines.append("")
        
        if 'context' in data:
            ctx = data['context']
            lines.append(f"**{ctx.get('title', 'Context')}**")
            for point in ctx.get('points', []):
                lines.append(f"  • {point}")
            lines.append("")
        
        # Elements (for ISMS)
        if 'elements' in data:
            elem = data['elements']
            lines.append(f"**{elem.get('title', 'Elements')}**")
            for point in elem.get('points', []):
                lines.append(f"  • {point}")
            lines.append("")
        
        # Benefits (for ISMS)
        if 'benefits' in data:
            ben = data['benefits']
            lines.append(f"**{ben.get('title', 'Benefits')}**")
            for point in ben.get('points', []):
                lines.append(f"  • {point}")
            lines.append("")
        
        if 'examples' in data:
            lines.append("**Examples**")
            for ex in data['examples']:
                lines.append(f"  • {ex}")
            lines.append("")
        
        if 'relationship' in data:
            lines.append("**Relationship**")
            lines.append(f"  {data['relationship']}\n")
        
        if 'commands' in data:
            lines.append("**Commands**")
            for cmd in data['commands']:
                lines.append(f"  • `{cmd}`")
        
        return "\n".join(lines)
    
    def _formatComparison(self, data: Dict) -> str:
        """Format a comparison topic (e.g., scope vs asset)"""
        from presenters.text import TextPresenter
        presenter = TextPresenter()
        
        sections = {}
        if 'comparison' in data:
            sections.update(data['comparison'])
        if 'relationship' in data:
            sections['Relationship'] = data['relationship']
        if 'commands' in data:
            sections['Commands'] = data['commands']
        
            formatted = presenter.present({
            'title': 'Scope vs Asset in ISO 27001',
            'sections': sections
            })
            return formatted.get('content', str(formatted)) if isinstance(formatted, dict) else formatted
        
    def _formatHowToCreate(self, objectType: str, data: Dict) -> str:
        """Format 'how to create' instructions from JSON"""
        lines = [f"**How to Create {objectType.title()}**\n"]
        
        # If detailed steps exist
        if 'steps' in data:
            for step in data['steps']:
                lines.append(f"**{step['title']}**")
                lines.append(f"  {step['content']}\n")
        else:
            # Simple format (for smaller object types)
            if 'format' in data:
                lines.append("**Command Format**")
                lines.append(f"  `{data['format']}`\n")
            if 'example' in data:
                lines.append("**Example**")
                lines.append(f"  `{data['example']}`\n")
            if 'optional' in data:
                lines.append("**Optional Details**")
                lines.append(f"  {data['optional']}\n")
            if 'view' in data:
                lines.append("**View All**")
                lines.append(f"  `{data['view']}`\n")
        
        # Note
        if 'note' in data:
            lines.append("**Note**")
            lines.append(f"  {data['note']}")
        
        return "\n".join(lines)
    
    def _getFallbackAnswer(self, message: str) -> Optional[str]:
        """Provide fallback answers for common knowledge questions using JSON knowledge base"""
        messageLower = message.lower().strip()
        topics = self._knowledgeBase.get('topics', {})
        howToCreate = self._knowledgeBase.get('how_to_create', {})
        
        # 1. Scope vs Asset comparison (most specific)
        if 'scope' in messageLower and 'asset' in messageLower and ('difference' in messageLower or 'vs' in messageLower or 'versus' in messageLower):
            if 'scope_vs_asset' in topics:
                return self._formatComparison(topics['scope_vs_asset'])
        
        # 2. "What is X?" questions - check specific before general
        if any(q in messageLower for q in KNOWLEDGE_WHAT_PATTERNS):
            # Asset (check before ISMS to avoid conflicts)
            if 'asset' in messageLower and 'scope' not in messageLower and 'asset' in topics:
                return self._formatKnowledgeTopic('asset', topics['asset'])
            
            # Scope (exclude if asset mentioned)
            if 'scope' in messageLower and 'asset' not in messageLower and 'scope' in topics:
                return self._formatKnowledgeTopic('scope', topics['scope'])
            
            # ISMS (general - check last, exclude if asset/scope mentioned)
            if 'isms' in messageLower and 'asset' not in messageLower and 'scope' not in messageLower and 'isms' in topics:
                return self._formatKnowledgeTopic('isms', topics['isms'])
        
        # 3. "How to create X?" questions - dynamic for all object types
        if any(pattern in messageLower for pattern in KNOWLEDGE_HOW_TO_CREATE_PATTERNS) and 'create' in messageLower:
            for objType in VERINICE_OBJECT_TYPES:
                if objType in messageLower and objType in howToCreate:
                    return self._formatHowToCreate(objType, howToCreate[objType])
        
        return None
    
    def _handleContextualQuestion(self, message: str) -> Optional[str]:
        """
        Handle contextual questions like "what are those", "what is this", "explain that".
        Checks recent state/history to provide relevant answer.
        """
        messageLower = message.lower().strip()
        context_patterns = [
            r'what\s+(?:are|is)\s+(?:those|these|that|this)',
            r'explain\s+(?:those|these|that|this)',
            r'tell\s+me\s+more\s+about\s+(?:those|these|that|this)',
        ]
        
        if any(re.search(pattern, messageLower) for pattern in context_patterns):
            # Check for last comparison result
            last_comparison = self.state.get('_last_comparison')
            if last_comparison:
                return f"Those are the differences between {last_comparison.get('obj1')} and {last_comparison.get('obj2')}. " \
                       f"The comparison identified {last_comparison.get('diff_count')} key differences."
            
            # Check for last list result
            last_list = self.state.get('_last_list_result')
            if last_list:
                obj_type = last_list.get('objectType', 'object')
                count = last_list.get('count', 0)
                return f"Those are the {count} {obj_type}s found in your ISMS."
            
            # Check for last created objects
            created = self.state.get('_created_objects')
            if created:
                count = len(created)
                return f"Those are the {count} objects you just created."
                
        return None

    def _formatTextResponse(self, text: str) -> str:
        """Format text responses - delegates to helper function"""
        return formatTextResponse(text)
    
    def _success(self, result: Any) -> Dict:
        """Success response - delegates to helper function"""
        return successResponse(result)
    
    def _error(self, message: str) -> Dict:
        """Error response - delegates to helper function"""
        return errorResponse(message)
    
    # ==================== PHASE 3: SHADOW TESTING ====================
    
    def _ensureChatRouter(self):
        """Initialize ChatRouter if not already initialized (Phase 3)"""
        if not self._chatRouter:
            from orchestrator.chatRouter import ChatRouter
            from .instructions import VERINICE_OBJECT_TYPES
            self._chatRouter = ChatRouter(VERINICE_OBJECT_TYPES)
    
    def _shadowTestNewRouter(self, message: str) -> Optional[Dict]:
        """
        Run new ChatRouter in shadow mode (doesn't affect execution)
        
        This allows us to compare old vs new routing decisions without
        affecting live users. Logs are written for later analysis.
        """
        try:
            self._ensureChatRouter()
            
            # Build context for router
            sessionContext = self.state.get('_sessionContext', {})
            if sessionContext and isinstance(sessionContext, dict):
                context = sessionContext.copy()
            else:
                context = {
                    'conversationHistory': self.conversationHistory[-3:] if self.conversationHistory else [],
                    'activeSources': []
                }
            
            if not hasattr(self, '_intentClassifier') or not self._intentClassifier:
                try:
                    from orchestrator.intentClassifier import IntentClassifier
                    llmTool = getattr(self, '_llmTool', None)
                    if llmTool:
                        self._intentClassifier = IntentClassifier(llmTool)
                except Exception:
                    self._intentClassifier = None
            
            # Route using new router (pass state by reference)
            intentClassifier = getattr(self, '_intentClassifier', None)
            print(f"[DEBUG _shadowTestNewRouter] Routing message: {message[:80]}")
            decision = self._chatRouter.route(message, self.state, context, intentClassifier)
            print(f"[DEBUG _shadowTestNewRouter] Router returned: route={decision.get('route')}, handler={decision.get('handler')}")
            return decision
        except Exception as e:
            # If new router fails, log error but don't break execution
            self._routingLog.append({
                'message': message,
                'newRouter': 'ERROR',
                'error': str(e)
            })
            return None
    
    def _logRoutingComparison(self, message: str, oldRoute: str, newDecision: Dict, oldResult: Dict):
        """
        Log routing decision comparison for analysis
        
        Args:
            message: User message
            oldRoute: Old routing decision (string identifier)
            newDecision: New router decision dict
            oldResult: Result from old routing
        """
        logEntry = {
            'message': message[:100],  # Truncate long messages
            'oldRoute': oldRoute,
            'newRoute': newDecision.get('route'),
            'newHandler': newDecision.get('handler'),
            'newConfidence': newDecision.get('confidence'),
            'match': oldRoute == newDecision.get('route')
        }
        
        self._routingLog.append(logEntry)
        
        # Keep log size reasonable (last 100 entries)
        if len(self._routingLog) > 100:
            self._routingLog.pop(0)
    
    def _executeRoutingDecision(self, decision: Dict, message: str) -> Dict:
        """
        Execute a routing decision from ChatRouter
        
        This method maps router decisions to actual handler calls.
        Used when feature flag is enabled (active mode).
        """
        handler = decision.get('handler')
        data = decision.get('data', {})
        
        # Map handler names to actual methods
        if handler == '_handleVeriniceOp':
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"[_executeRoutingDecision] Calling _handleVeriniceOp with data: {data}")
            result = self._handleVeriniceOp(data, message)
            logger.info(f"[_executeRoutingDecision] _handleVeriniceOp returned: status={result.get('status') if result else 'None'}, has_result={bool(result)}")
            # Ensure we return a valid result (not None or empty)
            if result and result.get('status'):
                return result
            # ALWAYS return result - even if it's an error, the router made a decision
            if result:
                # Ensure result has status
                if 'status' not in result:
                    result['status'] = 'error' if result.get('error') else 'success'
                return result
            # If result is None, return error
            logger.error(f"[_executeRoutingDecision] _handleVeriniceOp returned None")
            return self._error(f"Handler returned None for operation: {data.get('operation', 'unknown')}")
        elif handler == '_handleReportGeneration':
            return self._handleReportGeneration(data, message)
        elif handler == '_handleReportGenerationFollowUp':
            return self._handleReportGenerationFollowUp(message)
        elif handler == '_handleSubtypeFollowUp':
            return self._handleSubtypeFollowUp(message)
        elif handler == '_handleSubtypeQuery':
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"[MainAgent] Handling subtype query with data: {data}")
            result = self._handleSubtypeQuery(data, message)
            # ALWAYS return result - even if it's an error
            if result:
                if 'status' not in result:
                    result['status'] = 'error' if result.get('error') else 'success'
                return result
            logger.error(f"[_executeRoutingDecision] _handleSubtypeQuery returned None")
            return self._error(f"Subtype query handler returned None")
        elif handler == '_handleCreateAndLink':
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"[MainAgent] Handling create-and-link with data: {data}")
            return self._handleCreateAndLink(data, message)
        elif handler == '_handleMultipleCreates':
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"[MainAgent] Handling multiple creates with data: {data}")
            return self._handleMultipleCreates(data, message)
        elif handler == '_checkGreeting':
            greeting = self._checkGreeting(message)
            return self._success(greeting) if greeting else self._error(get_error_message('user_guidance', 'error_processing_greeting'))
        elif handler == '_getFallbackAnswer':
            answer = self._getFallbackAnswer(message)
            if answer:
                return self._success(answer)
            
            # Check for contextual questions ("what are those", "what is this")
            contextualAnswer = self._handleContextualQuestion(message)
            if contextualAnswer:
                return self._success(contextualAnswer)
                
            # Fallback to LLM/Reasoning if no answer found
            return self._executeRoutingDecision({'handler': 'llm_generate', 'data': {}}, message)
        elif handler == 'llm_generate':
            # Use LLM for general chat
            if 'generate' in self.tools:
                try:
                    response = self.executeTool('generate', prompt=message, systemPrompt=self.instructions)
                    formattedResponse = self._formatTextResponse(response)
                    return self._success(formattedResponse)
                except Exception:
                    # Try reasoning engine as fallback
                    try:
                        from orchestrator.reasoningEngine import ReasoningEngine
                        reasoningEngine = ReasoningEngine()
                        system_prompt = f"{self.instructions}\n\nYou are an expert ISMS compliance assistant."
                        response = reasoningEngine.reason(message, context={}, system_prompt=system_prompt, response_mode='concise')
                        return self._success(response)
                    except Exception:
                        return self._error("I couldn't process your request. Please try rephrasing or use specific ISMS commands.")
            # Try reasoning engine as fallback
            try:
                from orchestrator.reasoningEngine import ReasoningEngine
                reasoningEngine = ReasoningEngine()
                system_prompt = f"{self.instructions}\n\nYou are an expert ISMS compliance assistant."
                response = reasoningEngine.reason(message, context={}, system_prompt=system_prompt, response_mode='concise')
                return self._success(response)
            except Exception:
                return self._error("I couldn't process your request. Please try rephrasing or use specific ISMS commands.")
        else:
            # Unknown handler - try reasoning engine
            try:
                from orchestrator.reasoningEngine import ReasoningEngine
                reasoningEngine = ReasoningEngine()
                system_prompt = f"{self.instructions}\n\nYou are an expert ISMS compliance assistant."
                response = reasoningEngine.reason(message, context={}, system_prompt=system_prompt, response_mode='concise')
                return self._success(response)
            except Exception:
                return self._error("I couldn't process your request. Please try rephrasing or use specific ISMS commands.")
    
    def getRoutingLog(self) -> List[Dict]:
        """Get routing comparison log (for debugging and validation)"""
        return self._routingLog.copy()
    
    def clearRoutingLog(self):
        """Clear routing log"""
        self._routingLog = []
    
    def enableChatRouter(self):
        """Enable ChatRouter (switch from shadow to active mode)"""
        self._useChatRouter = True
    
    def disableChatRouter(self):
        """Disable ChatRouter (switch back to old routing)"""
        self._useChatRouter = False
    
    def validateContext(self) -> Dict[str, Any]:
        """
        Validate context health across all context managers.
        
        Returns:
            Dict with validation status, issues, and recommendations
        """
        results = {
            'mainAgent': {},
            'contextManager': {},
            'state': {}
        }
        
        # Validate MainAgent conversation history
        if len(self.conversationHistory) > 50:
            results['mainAgent']['warning'] = f"Conversation history exceeds limit: {len(self.conversationHistory)}/50"
        else:
            results['mainAgent']['status'] = 'ok'
            results['mainAgent']['messageCount'] = len(self.conversationHistory)
        
        # Validate EnhancedContextManager if available
        if self.contextManager:
            if hasattr(self.contextManager, 'validateContext'):
                results['contextManager'] = self.contextManager.validateContext()
            else:
                results['contextManager']['status'] = 'ok'
                results['contextManager']['documentCount'] = len(self.contextManager.documents) if hasattr(self.contextManager, 'documents') else 0
        
        # Validate state structure
        state_issues = []
        if not isinstance(self.state, dict):
            state_issues.append("State is not a dictionary")
        else:
            # Check for critical state keys
            critical_keys = ['_created_objects', '_last_list_result', '_sessionContext']
            missing_keys = [key for key in critical_keys if key not in self.state]
            if missing_keys:
                results['state']['missing_keys'] = missing_keys
                results['state']['status'] = 'partial'
            else:
                results['state']['status'] = 'ok'
            
            # Check state size
            state_size = len(str(self.state))
            if state_size > 100000:  # ~100KB
                state_issues.append(f"State size is large: {state_size} bytes")
        
        if state_issues:
            results['state']['issues'] = state_issues
        
        # Overall validation result
        all_valid = (
            results.get('mainAgent', {}).get('status') != 'error' and
            results.get('contextManager', {}).get('valid', True) and
            results.get('state', {}).get('status') != 'error'
        )
        
        results['overall'] = {
            'valid': all_valid,
            'status': 'healthy' if all_valid else 'degraded'
        }
        
        return results
    
    def summarizeContext(self, maxMessages: int = 20) -> str:
        """
        Create a concise summary of current context.
        
        Args:
            maxMessages: Maximum number of messages to include in summary
            
        Returns:
            Summarized context string
        """
        summary_parts = []
        
        # MainAgent conversation summary
        if self.conversationHistory:
            recent = self.conversationHistory[-maxMessages:] if len(self.conversationHistory) > maxMessages else self.conversationHistory
            summary_parts.append(f"MainAgent: {len(self.conversationHistory)} total messages ({len(recent)} recent)")
        
        # EnhancedContextManager summary
        if self.contextManager:
            if hasattr(self.contextManager, 'summarizeConversation'):
                context_summary = self.contextManager.summarizeConversation(maxMessages)
                summary_parts.append(f"ContextManager: {context_summary}")
            elif hasattr(self.contextManager, 'conversation'):
                conv_len = len(self.contextManager.conversation) if hasattr(self.contextManager, 'conversation') else 0
                summary_parts.append(f"ContextManager: {conv_len} conversation messages")
        
        # State summary
        if self.state:
            created_count = len(self.state.get('_created_objects', {}))
            has_list_result = '_last_list_result' in self.state
            has_session_context = '_sessionContext' in self.state
            
            state_info = []
            if created_count > 0:
                state_info.append(f"{created_count} created objects")
            if has_list_result:
                state_info.append("last list result cached")
            if has_session_context:
                state_info.append("session context active")
            
            if state_info:
                summary_parts.append(f"State: {', '.join(state_info)}")
        
        return "\n".join(summary_parts) if summary_parts else "No context available"
    
    def getContextHealth(self) -> Dict[str, Any]:
        """
        Get overall context health metrics.
        
        Returns:
            Dict with health metrics, status, and recommendations
        """
        validation = self.validateContext()
        
        # Calculate health score
        health_score = 100
        if not validation.get('overall', {}).get('valid', True):
            health_score -= 30
        if validation.get('mainAgent', {}).get('warning'):
            health_score -= 10
        if validation.get('state', {}).get('issues'):
            health_score -= len(validation.get('state', {}).get('issues', [])) * 5
        
        health_score = max(0, min(100, health_score))
        
        # Determine status
        if health_score >= 80:
            status = "healthy"
        elif health_score >= 60:
            status = "degraded"
        else:
            status = "unhealthy"
        
        # Recommendations
        recommendations = []
        if len(self.conversationHistory) > 40:
            recommendations.append("Consider summarizing conversation history")
        if self.contextManager and hasattr(self.contextManager, 'getContextHealth'):
            ctx_health = self.contextManager.getContextHealth()
            if ctx_health.get('status') != 'healthy':
                recommendations.append("Context manager needs attention")
        
        return {
            'status': status,
            'score': health_score,
            'validation': validation,
            'recommendations': recommendations,
            'metrics': {
                'conversation_messages': len(self.conversationHistory),
                'state_keys': len(self.state),
                'has_context_manager': self.contextManager is not None
            }
        }


