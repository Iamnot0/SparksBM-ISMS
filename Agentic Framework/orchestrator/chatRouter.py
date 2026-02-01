"""
Chat Router - Extracts routing logic from MainAgent (Phase 3)

This module handles all chat message routing decisions:
- Follow-up detection (subtype selection, report generation)
- Greeting detection
- Verinice operation detection (ISMS commands)
- Report generation detection
- Intent classification (LLM-based fallback)
- Fallback routing

CRITICAL: This router MUST maintain the exact routing priority order:
1. Follow-ups (highest priority)
2. Greetings
3. Verinice operations (pattern-based)
4. Report generation (pattern-based)
5. Intent classifier (LLM-based)
6. Fallback knowledge base
7. LLM general chat
8. Final fallback

State Management:
- Router receives state by REFERENCE (not copy)
- All state mutations are preserved
- Prevents Bug #3 regression (context loss)
"""

from typing import Dict, Optional, Any, List
import re
import logging
from agents.instructions import (
    VERINICE_CREATE_KEYWORDS,
    VERINICE_LIST_KEYWORDS,
    VERINICE_GET_KEYWORDS,
    VERINICE_SUBTYPE_MAPPINGS,
    VERINICE_UPDATE_KEYWORDS,
    VERINICE_DELETE_KEYWORDS,
    VERINICE_ANALYZE_KEYWORDS,
    VERINICE_QUESTION_STARTERS,
    VERINICE_QUESTION_WORDS,
    VERINICE_CONVERSATIONAL_LIST,
    VERINICE_SUBTYPE_QUERIES,
    VERINICE_REPORT_KEYWORDS,
    VERINICE_REPORT_TYPES,
    VERINICE_REPORT_TYPE_MAPPINGS,
    VERINICE_TYPO_CORRECTIONS
)

logger = logging.getLogger(__name__)


class ChatRouter:
    """Routes chat messages to appropriate handlers based on intent and context"""
    
    # Routing decision types (for logging and debugging)
    ROUTE_FOLLOW_UP = "follow_up"
    ROUTE_GREETING = "greeting"
    ROUTE_SUBTYPE_QUERY = "subtype_query"
    ROUTE_CREATE_AND_LINK = "create_and_link"
    ROUTE_VERINICE = "verinice_operation"
    ROUTE_REPORT = "report_generation"
    ROUTE_INTENT_CLASSIFIER = "intent_classifier"
    ROUTE_FALLBACK_KB = "fallback_knowledge"
    ROUTE_LLM = "llm_chat"
    ROUTE_FINAL_FALLBACK = "final_fallback"
    
    def __init__(self, veriniceObjectTypes: List[str]):
        """
        Initialize ChatRouter
        
        Args:
            veriniceObjectTypes: List of valid Verinice object types for pattern matching
        """
        self.veriniceObjectTypes = veriniceObjectTypes
    
    def route(self, message: str, state: Dict, context: Dict, intentClassifier=None) -> Dict:
        """
        Route a chat message to the appropriate handler
        
        Args:
            message: User's chat message
            state: Agent state (passed by REFERENCE - mutations are preserved)
            context: Session context with document/file information
            intentClassifier: Optional IntentClassifier instance for LLM-based routing
        
        Returns:
            Dict with routing decision:
            {
                'route': str,  # Route type (ROUTE_* constants)
                'handler': str,  # Handler method name to call
                'data': dict,  # Handler-specific data (e.g., veriniceOp, reportGen)
                'confidence': float  # Confidence in routing decision (0-1)
            }
        """
        # Validate state (prevent Bug #3 regression)
        self._validateState(state)
        
        # 0. PRIORITY: Check for follow-up responses FIRST
        followUp = self._checkFollowUp(message, state)
        if followUp:
            return followUp
        
        # 1. Quick greeting check
        greeting = self._checkGreeting(message, state)
        if greeting:
            return greeting
        
        # 1.4.5. Check for subtype queries FIRST (BEFORE conversational list to avoid misrouting)
        # CRITICAL: Subtype queries like "show me all subtypes of Scopes" must be detected before
        # conversational list queries like "show all scopes" to avoid confusion
        subtypeQuery = self._detectSubtypeQuery(message)
        if subtypeQuery:
            logger.info(f"[ROUTER] Subtype query detected: {subtypeQuery} for message: {message[:80]}")
            return {
                'route': self.ROUTE_SUBTYPE_QUERY,
                'handler': '_handleSubtypeQuery',
                'data': subtypeQuery,
                'confidence': 0.9
            }
        else:
            logger.debug(f"[ROUTER] No subtype query detected for: {message[:80]}")
        
        # 1.4.5. Check for subtype-filtered list queries (e.g., "how many assets in our IT-System assets")
        subtypeListQuery = self._detectSubtypeListQuery(message)
        if subtypeListQuery:
            logger.info(f"[ROUTER] Subtype-filtered list query detected: {subtypeListQuery} for message: {message[:80]}")
            return {
                'route': self.ROUTE_VERINICE,
                'handler': '_handleVeriniceOp',
                'data': subtypeListQuery,
                'confidence': 0.95
            }
        
        # 1.4.6. Check for conversational list queries (AFTER subtype queries to avoid misrouting)
        # Patterns like "show all scopes", "show me all assets in our isms", "display all controls"
        # This MUST be checked before generic fallback to catch natural language queries
        conversationalList = self._detectConversationalList(message)
        if conversationalList:
            logger.info(f"[ROUTER] Conversational list query detected: {conversationalList} for message: {message[:80]}")
            return {
                'route': self.ROUTE_VERINICE,
                'handler': '_handleVeriniceOp',
                'data': conversationalList,
                'confidence': 0.95
            }
        
        # 1.6. Check for role/subtype assignment patterns (BEFORE VeriniceOp to avoid generic fallback)
        # BUT: Skip if this looks like a list query (check BEFORE role assignment)
        # Patterns: "set role for the Data protection officer for the person Ruby"
        #           "add in the DPO for the person Tommy"
        #           "set subtype Controller for the scope Project Phoenix"
        message_lower_check = message.lower().strip()
        # CRITICAL: Comprehensive list query detection - check multiple patterns
        list_query_starters = ['show', 'list', 'display', 'how many', 'what', 'do we have', 'are there', 'tell me']
        list_query_patterns = [
            r'^show\s+(?:me\s+)?(?:all\s+)?',  # "show me all", "show all"
            r'^list\s+(?:all\s+)?',  # "list all", "list"
            r'^display\s+(?:all\s+)?',  # "display all"
            r'^how\s+many\s+',  # "how many"
            r'^what\s+(?:are|is)\s+',  # "what are", "what is"
            r'^do\s+we\s+have\s+',  # "do we have"
            r'^are\s+there\s+',  # "are there"
            r'^tell\s+me\s+(?:all\s+)?',  # "tell me all", "tell me"
        ]
        
        # CRITICAL: Also check if conversational list or subtype list query would match
        # This is a safety net to ensure list queries are never treated as role assignments
        conversational_list_check = self._detectConversationalList(message)
        subtype_list_check = self._detectSubtypeListQuery(message)
        
        is_list_query = (
            any(message_lower_check.startswith(starter) for starter in list_query_starters) or
            any(re.match(pattern, message_lower_check) for pattern in list_query_patterns) or
            conversational_list_check is not None or
            subtype_list_check is not None
        )
        
        if not is_list_query:
            roleAssignment = self._detectRoleSubtypeAssignment(message)
            if roleAssignment:
                logger.info(f"[ROUTER] Role/subtype assignment detected: {roleAssignment} for message: {message[:80]}")
                return {
                    'route': self.ROUTE_VERINICE,
                    'handler': '_handleVeriniceOp',
                    'data': roleAssignment,
                    'confidence': 0.95
                }
        
        # 1.5. Check for multiple create operations (e.g., "create scope X and also create person Y")
        # CRITICAL: This must be checked BEFORE create-and-link and single create operations
        # to avoid matching only the first create operation
        multipleCreates = self._detectMultipleCreates(message)
        if multipleCreates:
            logger.info(f"[ROUTER] Multiple create operations detected: {len(multipleCreates.get('operations', []))} operations")
            return {
                'route': self.ROUTE_VERINICE,
                'handler': '_handleMultipleCreates',
                'data': multipleCreates,
                'confidence': 0.95
            }
        else:
            logger.debug(f"[ROUTER] No multiple creates detected for: {message[:80]}")
        
        # 1.7.5. Check for multi-link operations (BEFORE create-and-link)
        # Pattern: "link SCOPE-B with IT-System assets, and SCOPE-D link with Datatypes assets"
        multi_link_pattern = r'link\s+([A-Za-z0-9_\s-]+?)\s+(?:with|to)\s+([A-Za-z0-9_\s-]+?)\s+(?:assets?|scopes?|controls?|persons?|processes?|documents?|incidents?|scenarios?)\s*,\s*and\s+([A-Za-z0-9_\s-]+?)\s+link\s+(?:with|to)\s+([A-Za-z0-9_\s-]+?)\s+(?:assets?|scopes?|controls?|persons?|processes?|documents?|incidents?|scenarios?)'
        multi_link_match = re.search(multi_link_pattern, message, re.IGNORECASE)
        if multi_link_match:
            source1 = multi_link_match.group(1).strip()
            target1 = multi_link_match.group(2).strip()
            source2 = multi_link_match.group(3).strip()
            target2 = multi_link_match.group(4).strip()
            
            logger.info(f"[ROUTER] Multi-link detected: {source1}->{target1}, {source2}->{target2}")
            return {
                'route': self.ROUTE_VERINICE,
                'handler': '_handleVeriniceOp',
                'data': {
                    'operation': 'link',
                    'isMultiLink': True,
                    'links': [
                        {'source': source1, 'target': target1},
                        {'source': source2, 'target': target2}
                    ]
                },
                'confidence': 0.95
            }
        
        # 1.7.5. Check for multi-link operations (BEFORE create-and-link)
        # Pattern: "link SCOPE-B with IT-System assets, and SCOPE-D link with Datatypes assets"
        multi_link_pattern = r'link\s+([A-Za-z0-9_\s-]+?)\s+(?:with|to)\s+([A-Za-z0-9_\s-]+?)\s+(?:assets?|scopes?|controls?|persons?|processes?|documents?|incidents?|scenarios?)\s*,\s*and\s+([A-Za-z0-9_\s-]+?)\s+link\s+(?:with|to)\s+([A-Za-z0-9_\s-]+?)\s+(?:assets?|scopes?|controls?|persons?|processes?|documents?|incidents?|scenarios?)'
        multi_link_match = re.search(multi_link_pattern, message, re.IGNORECASE)
        if multi_link_match:
            source1 = multi_link_match.group(1).strip()
            target1 = multi_link_match.group(2).strip()
            source2 = multi_link_match.group(3).strip()
            target2 = multi_link_match.group(4).strip()
            
            logger.info(f"[ROUTER] Multi-link detected: {source1}->{target1}, {source2}->{target2}")
            return {
                'route': self.ROUTE_VERINICE,
                'handler': '_handleVeriniceOp',
                'data': {
                    'operation': 'link',
                    'isMultiLink': True,
                    'links': [
                        {'source': source1, 'target': target1},
                        {'source': source2, 'target': target2}
                    ]
                },
                'confidence': 0.95
            }
        
        # 1.7. Check for create-and-link operations (BEFORE general VeriniceOp)
        createAndLink = self._detectCreateAndLink(message)
        if createAndLink:
            logger.info(f"[ROUTER] Create-and-link detected: {createAndLink} for message: {message[:80]}")
            return {
                'route': self.ROUTE_CREATE_AND_LINK,
                'handler': '_handleCreateAndLink',
                'data': createAndLink,
                'confidence': 0.95
            }
        if multipleCreates:
            logger.info(f"[ROUTER] Multiple create operations detected: {len(multipleCreates.get('operations', []))} operations")
            return {
                'route': self.ROUTE_VERINICE,
                'handler': '_handleMultipleCreates',
                'data': multipleCreates,
                'confidence': 0.95
            }
        else:
            logger.debug(f"[ROUTER] No multiple creates detected for: {message[:80]}")
        
        # 2. CRITICAL: Check for Verinice operations FIRST (before IntentClassifier)
        veriniceOp = self._detectVeriniceOp(message)
        if veriniceOp:
            return {
                'route': self.ROUTE_VERINICE,
                'handler': '_handleVeriniceOp',
                'data': veriniceOp,
                'confidence': 0.95
            }
        
        # 3. Check for report generation
        reportGen = self._detectReportGeneration(message)
        if reportGen:
            return {
                'route': self.ROUTE_REPORT,
                'handler': '_handleReportGeneration',
                'data': reportGen,
                'confidence': 0.9
            }
        
        # 4. Use IntentClassifier (LLM-based) if available
        if intentClassifier:
            intentRoute = self._useIntentClassifier(message, context, intentClassifier)
            if intentRoute:
                return intentRoute
        
        # 5. Check fallback knowledge base
        if self._hasFallbackAnswer(message):
            return {
                'route': self.ROUTE_FALLBACK_KB,
                'handler': '_getFallbackAnswer',
                'data': {},
                'confidence': 0.7
            }
        
        # 7. Route to LLM for general chat
        return {
            'route': self.ROUTE_LLM,
            'handler': 'llm_generate',
            'data': {},
            'confidence': 0.5
        }
    
    # ==================== STATE VALIDATION ====================
    
    def _validateState(self, state: Dict) -> None:
        """
        Validate that state has required structure
        
        Prevents Bug #3 regression by ensuring state is passed by reference
        and has necessary keys for routing decisions
        """
        if not isinstance(state, dict):
            raise ValueError(f"State must be a dict, got {type(state)}")
        
        # State should have these keys (create if missing)
        if '_sessionContext' not in state:
            state['_sessionContext'] = {}
        if 'lastProcessed' not in state:
            state['lastProcessed'] = None
    
    # ==================== FOLLOW-UP DETECTION ====================
    
    def _checkFollowUp(self, message: str, state: Dict) -> Optional[Dict]:
        """Check for follow-up responses (subtype selection, report generation, bulk operations)"""
        # Report generation follow-up
        if state.get('pendingReportGeneration'):
            return {
                'route': self.ROUTE_FOLLOW_UP,
                'handler': '_handleReportGenerationFollowUp',
                'data': {},
                'confidence': 1.0
            }
        
        # Subtype selection follow-up
        pending = state.get('_pendingSubtypeSelection')
        if pending:
            return {
                'route': self.ROUTE_FOLLOW_UP,
                'handler': '_handleSubtypeFollowUp',
                'data': {},
                'confidence': 1.0
            }
        
        # Bulk delete/remove follow-up - check for "remove them all", "delete all", etc.
        bulk_delete = self._detectBulkDelete(message, state)
        if bulk_delete:
            return {
                'route': self.ROUTE_VERINICE,
                'handler': '_handleVeriniceOp',
                'data': bulk_delete,
                'confidence': 0.95
            }
        
        return None
    
    # ==================== BULK DELETE DETECTION ====================
    
    def _detectBulkDelete(self, message: str, state: Dict) -> Optional[Dict]:
        """
        Detect bulk delete/remove operations that reference the last list result.
        
        Examples:
        - "remove it" → delete single object from last result
        - "delete it" → delete single object from last result
        - "remove them" → delete all from last list
        - "remove them all" → delete all from last list
        - "delete all" → delete all from last list
        - "remove all of them" → delete all from last list
        - "delete all persons" → delete all persons
        - "remove all scopes" → delete all scopes
        - "remove assets" → delete all assets (without "all")
        - "delete scopes" → delete all scopes (without "all")
        
        Returns:
            Dict with operation='delete', objectType, and isBulk=True if detected
        """
        messageLower = message.lower().strip()
        
        # Patterns for contextual single object deletion ("remove it", "delete it")
        single_context_patterns = [
            r'^(?:remove|delete|clear|wipe)\s+it\s*$',
            r'^(?:remove|delete|clear|wipe)\s+that\s*$',
            r'^(?:remove|delete|clear|wipe)\s+this\s*$',
        ]
        
        # Patterns for contextual bulk deletion ("remove them", "delete them", "remove them all")
        bulk_context_patterns = [
            r'^(?:remove|delete|clear|wipe)\s+them\s*$',
            r'^(?:remove|delete|clear|wipe)\s+these\s*$',
            r'^(?:remove|delete|clear|wipe)\s+those\s*$',
            r'^(?:remove|delete|clear|wipe)\s+them\s+all\s*$',
            r'^(?:remove|delete|clear|wipe)\s+all\s+of\s+them\s*$',
        ]
        
        # Patterns for explicit bulk delete/remove (with or without object type)
        bulk_patterns = [
            r'remove\s+them\s+all',
            r'delete\s+them\s+all',
            r'remove\s+all\s+of\s+them',
            r'delete\s+all\s+of\s+them',
            r'remove\s+all',
            r'delete\s+all',
            r'clear\s+all',
            r'wipe\s+all',
        ]
        
        # Check for single object contextual deletion first
        is_single_context = any(re.search(pattern, messageLower) for pattern in single_context_patterns)
        # Check for bulk contextual deletion (including "remove them all")
        is_bulk_context = any(re.search(pattern, messageLower) for pattern in bulk_context_patterns)
        # Check for explicit bulk patterns
        is_bulk_reference = any(re.search(pattern, messageLower) for pattern in bulk_patterns)
        
        # Debug logging
        logger.info(f"[_detectBulkDelete] Pattern matching: is_single_context={is_single_context}, is_bulk_context={is_bulk_context}, is_bulk_reference={is_bulk_reference}, message='{message}'")
        
        # Check for "remove {objectType}" pattern (without "all")
        type_without_all_pattern = r'^(?:remove|delete|clear|wipe)\s+(scopes?|assets?|controls?|processes?|persons?|people|scenarios?|incidents?|documents?)\s*$'
        type_without_all_match = re.search(type_without_all_pattern, messageLower, re.IGNORECASE)
        
        # If matched "remove {objectType}" without "all", treat as bulk delete
        if type_without_all_match:
            obj_type = type_without_all_match.group(1).lower()
            # Normalize plural/singular
            if obj_type.endswith('s') and obj_type != 'scopes':
                obj_type = obj_type[:-1]
            elif obj_type == 'people':
                obj_type = 'person'
            logger.info(f"[_detectBulkDelete] ✅ Matched 'remove {obj_type}' pattern (without 'all') - treating as bulk delete")
            return {
                'operation': 'delete',
                'objectType': obj_type,
                'isBulk': True
            }
        
        # CRITICAL: Get context from state FIRST (before pattern checks)
        # This ensures we have the latest list result available
        last_list = state.get('_last_list_result') or {}
        object_type = last_list.get('objectType')
        items = last_list.get('items', [])
        
        # Try handler state if not found in main state
        if not object_type or not items:
            if '_ismsHandler' in state:
                handler = state.get('_ismsHandler')
                if handler and hasattr(handler, 'state'):
                    handler_last_list = handler.state.get('_last_list_result', {})
                    if handler_last_list:
                        if not object_type:
                            object_type = handler_last_list.get('objectType')
                        if not items:
                            items = handler_last_list.get('items', [])
                        # Sync back to main state
                        state['_last_list_result'] = handler_last_list
                        last_list = handler_last_list
        
        # If single context pattern matched, handle single object deletion
        if is_single_context:
            # If we have items, take the first one (single object deletion)
            if object_type and items and len(items) > 0:
                first_item = items[0] if isinstance(items, list) else items
                logger.info(f"[_detectBulkDelete] ✅ Single context deletion: objectType={object_type}, item={first_item.get('name', 'Unknown') if isinstance(first_item, dict) else 'Unknown'}")
                return {
                    'operation': 'delete',
                    'objectType': object_type,
                    'isBulk': False,
                    'items': [first_item],
                    'count': 1
                }
            elif object_type:
                # We have object type but no items - delete all of that type
                logger.info(f"[_detectBulkDelete] ✅ Single context deletion (no items): objectType={object_type}, will delete all")
                return {
                    'operation': 'delete',
                    'objectType': object_type,
                    'isBulk': True
                }
            else:
                logger.warning(f"[_detectBulkDelete] ⚠️ 'remove it' matched but no context found in state")
                return None
        
        # If bulk context pattern matched ("remove them", "remove them all"), treat as bulk delete
        if is_bulk_context:
            is_bulk_reference = True  # Treat as bulk reference
        
        if is_bulk_reference:
            # Use the context we already retrieved above (object_type and items from state)
            # Debug logging
            logger.info(f"[_detectBulkDelete] Bulk delete detected. Checking state: objectType={object_type}, items_count={len(items) if items else 0}")
            
            if object_type and items:
                # We have context - use it
                logger.info(f"[_detectBulkDelete] ✅ Found context: objectType={object_type}, count={len(items)}")
                return {
                    'operation': 'delete',
                    'objectType': object_type,
                    'isBulk': True,
                    'items': items,
                    'count': len(items)
                }
            elif object_type:
                # We have object type but no items - will list and delete all
                logger.info(f"[_detectBulkDelete] ✅ Found objectType={object_type} but no items, will list and delete all")
                return {
                    'operation': 'delete',
                    'objectType': object_type,
                    'isBulk': True
                }
            else:
                # No context found - log warning but still try to extract from message
                logger.warning(f"[_detectBulkDelete] ⚠️ No context found in state. State keys: {list(state.keys())}")
                # Try to extract object type from message
                # Pattern: "delete all persons", "remove all scopes"
                type_patterns = [
                    r'(?:remove|delete|clear|wipe)\s+all\s+(scopes?|assets?|controls?|processes?|persons?|people|scenarios?|incidents?|documents?)',
                ]
                for pattern in type_patterns:
                    match = re.search(pattern, messageLower, re.IGNORECASE)
                    if match:
                        obj_type = match.group(1).lower()
                        # Normalize plural/singular
                        if obj_type.endswith('s') and obj_type != 'scopes':
                            obj_type = obj_type[:-1]
                        elif obj_type == 'people':
                            obj_type = 'person'
                        logger.info(f"[_detectBulkDelete] ✅ Extracted objectType={obj_type} from message")
                        return {
                            'operation': 'delete',
                            'objectType': obj_type,
                            'isBulk': True
                        }
                # If we matched bulk pattern but couldn't extract type, still return bulk delete
                # The handler will need to figure out what to delete
                logger.warning(f"[_detectBulkDelete] ⚠️ Matched bulk pattern but couldn't extract type. Returning generic bulk delete.")
                return {
                    'operation': 'delete',
                    'objectType': None,  # Will need to be determined by handler
                    'isBulk': True,
                    'needsContext': True  # Flag to indicate handler should check state
                }
        
        return None
    
    # ==================== CONVERSATIONAL LIST DETECTION ====================
    
    def _detectConversationalList(self, message: str) -> Optional[Dict]:
        """
        Detect conversational list queries that should map to list operations.
        
        CRITICAL: This must NOT match subtype queries like "show me all subtypes of Scopes"
        - "show all scopes" → list scopes ✅
        - "show me all assets in our isms" → list assets ✅
        - "how many persons?" → list persons ✅
        - "show me all subtypes of Scopes" → subtype query (should NOT match here) ❌
        
        Examples:
        - "show all scopes" → list scopes
        - "show me all assets in our isms" → list assets
        - "display all controls" → list controls
        - "show all scopes in our domain" → list scopes
        - "what scopes do we have" → list scopes
        - "do we have any assets" → list assets
        - "ok so how about assets" → list assets
        - "how many person?" → list persons
        - "how many persons in our isms" → list persons
        - "how many scopes do we have" → list scopes
        
        Returns:
            Dict with operation='list' and objectType if detected, None otherwise
        """
        messageLower = message.lower().strip()
        
        # CRITICAL: First check if this is a subtype query - if so, skip it
        # Pattern: "show me all subtypes of X" or "show subtypes of X"
        subtype_query_pattern = r'show\s+(?:me\s+)?(?:all\s+)?subtypes?\s+(?:for|of)\s+(?:the\s+)?(\w+)'
        if re.search(subtype_query_pattern, messageLower, re.IGNORECASE):
            logger.debug(f"[_detectConversationalList] Skipping - this is a subtype query: {message[:80]}")
            return None
        
        # Comprehensive patterns for conversational list queries
        # Order matters - more specific patterns first
        # CRITICAL: Patterns must NOT match "subtypes" - only match object types
        list_patterns = [
            # "how many X?" or "how many X in our isms" patterns (most specific for count queries)
            r'how\s+many\s+(scopes?|assets?|controls?|processes?|persons?|people|scenarios?|incidents?|documents?)(?:\s+(?:do\s+we\s+have|in\s+(?:our\s+)?(?:isms|domain|system)))?\s*\??',
            # "show all X in our isms/domain/system" patterns (most specific)
            r'show\s+(?:me\s+)?all\s+(scopes?|assets?|controls?|processes?|persons?|people|scenarios?|incidents?|documents?)\s+in\s+(?:our\s+)?(?:isms|domain|system)',
            # "show all X" patterns (must come before "show X" to avoid false matches)
            r'show\s+(?:me\s+)?all\s+(scopes?|assets?|controls?|processes?|persons?|people|scenarios?|incidents?|documents?)(?:\s+in\s+(?:our\s+)?(?:isms|domain|system))?',
            # "show X" patterns (without "all") - must be after "show all" to avoid false matches
            r'show\s+(?:me\s+)?(scopes?|assets?|controls?|processes?|persons?|people|scenarios?|incidents?|documents?)(?:\s+in\s+(?:our\s+)?(?:isms|domain|system))?',
            # "display all X" patterns
            r'display\s+(?:all\s+)?(scopes?|assets?|controls?|processes?|persons?|people|scenarios?|incidents?|documents?)(?:\s+in\s+(?:our\s+)?(?:isms|domain|system))?',
            # "what X do we have" patterns
            r'what\s+(scopes?|assets?|controls?|processes?|persons?|people|scenarios?|incidents?|documents?)\s+(?:do\s+)?we\s+have',
            # "do we have any X" patterns
            r'do\s+we\s+have\s+(?:any\s+)?(scopes?|assets?|controls?|processes?|persons?|people|scenarios?|incidents?|documents?)',
            # "are there any X" patterns
            r'are\s+there\s+(?:any\s+)?(scopes?|assets?|controls?|processes?|persons?|people|scenarios?|incidents?|documents?)',
            # "how about X" patterns (from test cases) - must match "ok so how about assets? do we have any assets"
            r'(?:ok\s+so\s+)?how\s+about\s+(scopes?|assets?|controls?|processes?|persons?|people|scenarios?|incidents?|documents?)(?:\?)?(?:\s+do\s+we\s+have\s+(?:any\s+)?(?:scopes?|assets?|controls?|processes?|persons?|people|scenarios?|incidents?|documents?))?',
            # "what about X" patterns
            r'what\s+about\s+(scopes?|assets?|controls?|processes?|persons?|people|scenarios?|incidents?|documents?)(?:\?)?',
            # "list all X" patterns (explicit)
            r'list\s+(?:all\s+)?(scopes?|assets?|controls?|processes?|persons?|people|scenarios?|incidents?|documents?)(?:\s+in\s+(?:our\s+)?(?:isms|domain|system))?',
            # "tell me all X" patterns
            r'tell\s+me\s+(?:all\s+)?(scopes?|assets?|controls?|processes?|persons?|people|scenarios?|incidents?|documents?)(?:\s+in\s+(?:our\s+)?(?:isms|domain|system))?',
            # "tell me X" patterns (without "all")
            r'tell\s+me\s+(scopes?|assets?|controls?|processes?|persons?|people|scenarios?|incidents?|documents?)(?:\s+in\s+(?:our\s+)?(?:isms|domain|system))?',
        ]
        
        for pattern in list_patterns:
            match = re.search(pattern, messageLower, re.IGNORECASE)
            if match:
                objectType = match.group(1).strip().lower()
                
                # Normalize to singular form
                if objectType.endswith('s') and objectType != 'process':
                    objectType = objectType.rstrip('s')
                elif objectType.endswith('es'):
                    if objectType == 'processes':
                        objectType = 'process'
                    else:
                        objectType = objectType.rstrip('es')
                
                if objectType == 'people':
                    objectType = 'person'
                
                normalized_types = [ot.lower() for ot in self.veriniceObjectTypes]
                singular_types = []
                for ot in normalized_types:
                    if ot.endswith('s') and ot != 'process':
                        singular_types.append(ot.rstrip('s'))
                    elif ot.endswith('es'):
                        if ot == 'processes':
                            singular_types.append('process')
                        else:
                            singular_types.append(ot.rstrip('es'))
                    else:
                        singular_types.append(ot)
                
                if objectType in normalized_types or objectType in singular_types:
                    logger.info(f"[_detectConversationalList] ✅ Matched pattern '{pattern}' -> objectType: {objectType} for message: {message[:80]}")
                    return {
                        'operation': 'list',
                        'objectType': objectType
                    }
                else:
                    logger.debug(f"[_detectConversationalList] Pattern matched but objectType '{objectType}' not in valid types")
        
        logger.debug(f"[_detectConversationalList] ❌ No match for message: {message[:80]}")
        return None
    
    def _detectSubtypeListQuery(self, message: str) -> Optional[Dict]:
        """
        Detect list queries filtered by subtype.
        
        Examples:
        - "how many assets in our IT-System assets"
        - "list assets in our IT-System assets"
        - "show me all assets in our Datatype assets"
        - "how many scopes in our Controllers"
        
        Returns:
            Dict with operation='list', objectType, and subtypeFilter if detected, None otherwise
        """
        messageLower = message.lower().strip()
        
        # Patterns for subtype-filtered list queries
        # Pattern: "how many/list/show {objectType} in our {subtype} {objectType}"
        # Also handles: "how many asset do we have in our IT-System subtype asset"
        # Also handles: "show me all person in DPO" (without object type word at end)
        patterns = [
            # Pattern with object type word at end: "show me all person in DPO persons"
            r'how\s+many\s+(scopes?|assets?|controls?|processes?|persons?|people|scenarios?|incidents?|documents?)\s+(?:in|of)\s+(?:our|the)\s+([A-Za-z0-9_\s-]+?)\s+(?:scopes?|assets?|controls?|processes?|persons?|people|scenarios?|incidents?|documents?)',
            r'list\s+(?:all\s+)?(scopes?|assets?|controls?|processes?|persons?|people|scenarios?|incidents?|documents?)\s+(?:in|of)\s+(?:our|the)\s+([A-Za-z0-9_\s-]+?)\s+(?:scopes?|assets?|controls?|processes?|persons?|people|scenarios?|incidents?|documents?)',
            r'show\s+(?:me\s+)?(?:all\s+)?(scopes?|assets?|controls?|processes?|persons?|people|scenarios?|incidents?|documents?)\s+(?:in|of)\s+(?:our|the)\s+([A-Za-z0-9_\s-]+?)\s+(?:scopes?|assets?|controls?|processes?|persons?|people|scenarios?|incidents?|documents?)',
            r'count\s+(?:all\s+)?(scopes?|assets?|controls?|processes?|persons?|people|scenarios?|incidents?|documents?)\s+(?:in|of)\s+(?:our|the)\s+([A-Za-z0-9_\s-]+?)\s+(?:scopes?|assets?|controls?|processes?|persons?|people|scenarios?|incidents?|documents?)',
            # Pattern WITHOUT object type word at end: "show me all person in DPO"
            r'show\s+(?:me\s+)?(?:all\s+)?(scopes?|assets?|controls?|processes?|persons?|people|scenarios?|incidents?|documents?)\s+in\s+([A-Za-z0-9_\s-]+?)(?:\s|$)',
            r'list\s+(?:all\s+)?(scopes?|assets?|controls?|processes?|persons?|people|scenarios?|incidents?|documents?)\s+in\s+([A-Za-z0-9_\s-]+?)(?:\s|$)',
            r'how\s+many\s+(scopes?|assets?|controls?|processes?|persons?|people|scenarios?|incidents?|documents?)\s+in\s+([A-Za-z0-9_\s-]+?)(?:\s|$)',
            # Pattern for "how many asset do we have in our IT-System subtype asset"
            r'how\s+many\s+(scopes?|assets?|controls?|processes?|persons?|people|scenarios?|incidents?|documents?)\s+(?:do\s+we\s+have\s+)?(?:in|of)\s+(?:our|the)\s+([A-Za-z0-9_\s-]+?)\s+subtype\s+(?:scopes?|assets?|controls?|processes?|persons?|people|scenarios?|incidents?|documents?)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                objectType = match.group(1).strip().lower()
                subtype = match.group(2).strip()
                
                # Normalize object type to singular
                if objectType.endswith('s') and objectType != 'process':
                    objectType = objectType[:-1]
                elif objectType.endswith('es'):
                    if objectType == 'processes':
                        objectType = 'process'
                    else:
                        objectType = objectType.rstrip('es')
                
                if objectType == 'people':
                    objectType = 'person'
                
                normalized_types = [ot.lower() for ot in self.veriniceObjectTypes]
                singular_types = []
                for ot in normalized_types:
                    if ot.endswith('s') and ot != 'process':
                        singular_types.append(ot.rstrip('s'))
                    elif ot.endswith('es'):
                        if ot == 'processes':
                            singular_types.append('process')
                        else:
                            singular_types.append(ot.rstrip('es'))
                    else:
                        singular_types.append(ot)
                
                if objectType in normalized_types or objectType in singular_types:
                    # Normalize subtype filter (handle DPO -> Data protection officer, etc.)
                    subtype_normalized = subtype.strip()
                    subtype_lower = subtype_normalized.lower()
                    
                    # Map common abbreviations and variations
                    if 'dpo' in subtype_lower and len(subtype_normalized.strip()) <= 5:
                        subtype_normalized = 'Data protection officer'
                    elif 'data protection' in subtype_lower and 'offic' in subtype_lower:
                        # Handle "Data protection officer" and typos like "offiecer"
                        subtype_normalized = 'Data protection officer'
                    elif 'dataprotection' in subtype_lower.replace(' ', '').replace('-', '') and 'offic' in subtype_lower:
                        subtype_normalized = 'Data protection officer'
                    
                    logger.info(f"[_detectSubtypeListQuery] ✅ Matched: objectType={objectType}, subtype={subtype_normalized} (from: '{subtype}') for message: {message[:80]}")
                    return {
                        'operation': 'list',
                        'objectType': objectType,
                        'subtypeFilter': subtype_normalized  # Add normalized subtype filter
                    }
        
        return None
    
    # ==================== GREETING DETECTION ====================
    
    def _detectSubtypeQuery(self, message: str) -> Optional[Dict]:
        """
        Detect questions about subtypes for an object type.
        
        Examples:
        - "how many subtypes assets to create assets"
        - "how many subtypes scopes to create scope"
        - "what subtypes are available for assets"
        - "list subtypes for asset"
        - "show subtypes of scope"
        
        Returns:
            Dict with objectType if detected, None otherwise
        """
        messageLower = message.lower().strip()
        logger.debug(f"[_detectSubtypeQuery] Checking message: {message[:80]}")
        logger.debug(f"[_detectSubtypeQuery] Available object types: {self.veriniceObjectTypes}")
        
        # Patterns for subtype questions
        # Note: patterns must match before object type extraction to avoid misrouting
        # CRITICAL: Handle patterns like "how many subtypes assets to create assets"
        # where the object type appears twice (once after "subtypes" and once after "to create")
        # All patterns are case-insensitive
        # CRITICAL: These patterns MUST match "show me all subtypes of Scopes" correctly
        subtype_patterns = [
            # Most specific patterns first
            r'show\s+me\s+all\s+subtypes?\s+(?:for|of)\s+(?:the\s+)?(\w+)',  # "show me all subtypes of Scopes"
            r'show\s+(?:me\s+)?(?:all\s+)?subtypes?\s+(?:for|of)\s+(?:the\s+)?(\w+)',  # "show subtypes of scope" or "show all subtypes of Scopes"
            r'how\s+many\s+subtypes?\s+(\w+)\s+to\s+create\s+(\w+)',  # "how many subtypes assets to create assets"
            r'how\s+many\s+subtypes?\s+(\w+)\s+to\s+create',  # "how many subtypes assets to create"
            r'how\s+many\s+subtypes?\s+options?\s+(?:for|of)\s+(?:the\s+)?(\w+)',  # "how many subtypes options for the assets"
            r'how\s+many\s+subtypes?\s+(\w+)',  # "how many subtypes assets"
            r'what\s+subtypes?\s+(?:are\s+)?(?:available\s+)?(?:for|of)\s+(?:the\s+)?(\w+)',  # "what subtypes for assets"
            r'list\s+subtypes?\s+(?:for|of)\s+(?:the\s+)?(\w+)',  # "list subtypes for asset"
            r'get\s+subtypes?\s+(?:for|of)\s+(?:the\s+)?(\w+)',  # "get subtypes for asset"
            r'subtypes?\s+(?:for|of)\s+(?:the\s+)?(\w+)',  # "subtypes of asset"
        ]
        
        for pattern in subtype_patterns:
            match = re.search(pattern, messageLower, re.IGNORECASE)
            if match:
                # If pattern has 2 groups, prefer the second one (after "to create")
                # Otherwise use the first group
                if len(match.groups()) >= 2 and match.group(2):
                    objectType = match.group(2).strip().lower()
                else:
                    objectType = match.group(1).strip().lower()
                
                # Normalize to singular form
                if objectType.endswith('s') and objectType != 'process':
                    objectType = objectType.rstrip('s')
                elif objectType.endswith('es'):
                    if objectType == 'processes':
                        objectType = 'process'
                    else:
                        objectType = objectType.rstrip('es')
                
                normalized_types = [ot.lower() for ot in self.veriniceObjectTypes]
                singular_types = []
                for ot in normalized_types:
                    if ot.endswith('s') and ot != 'process':
                        singular_types.append(ot.rstrip('s'))
                    elif ot.endswith('es'):
                        if ot == 'processes':
                            singular_types.append('process')
                        else:
                            singular_types.append(ot.rstrip('es'))
                    else:
                        singular_types.append(ot)
                
                if objectType in normalized_types or objectType in singular_types:
                    logger.info(f"[_detectSubtypeQuery] ✅ Matched pattern '{pattern}' -> objectType: {objectType}")
                    return {'objectType': objectType}
                else:
                    logger.warning(f"[_detectSubtypeQuery] Pattern matched but objectType '{objectType}' not in valid types")
                    logger.debug(f"[_detectSubtypeQuery] normalized_types: {normalized_types[:5]}...")
                    logger.debug(f"[_detectSubtypeQuery] singular_types: {singular_types[:5]}...")
        
        # Also check for subtype queries from JSON config
        if any(query in messageLower for query in VERINICE_SUBTYPE_QUERIES):
            logger.debug(f"[_detectSubtypeQuery] Found subtype query keyword in message")
            # Try to extract object type from message (case-insensitive)
            for objType in self.veriniceObjectTypes:
                objTypeLower = objType.lower()
                # Try exact match first
                pattern = r'\b' + re.escape(objTypeLower) + r'\b'
                if re.search(pattern, messageLower, re.IGNORECASE):
                    # Convert to singular
                    if objTypeLower.endswith("es"):
                        if objTypeLower == "processes":
                            objectType = "process"
                        else:
                            objectType = objTypeLower[:-2]
                    elif objTypeLower.endswith("s") and objTypeLower != "process":
                        objectType = objTypeLower[:-1]
                    else:
                        objectType = objTypeLower
                    logger.info(f"[_detectSubtypeQuery] ✅ Found objectType via JSON config: {objectType}")
                    return {'objectType': objectType}
            
            # Fallback: Try to find any object type mentioned in the message
            # This handles cases where the object type might be mentioned in a different form
            for objType in self.veriniceObjectTypes:
                objTypeLower = objType.lower()
                if objTypeLower in messageLower:
                    # Convert to singular
                    if objTypeLower.endswith("es"):
                        if objTypeLower == "processes":
                            objectType = "process"
                        else:
                            objectType = objTypeLower[:-2]
                    elif objTypeLower.endswith("s") and objTypeLower != "process":
                        objectType = objTypeLower[:-1]
                    else:
                        objectType = objTypeLower
                    logger.info(f"[_detectSubtypeQuery] ✅ Found objectType via fallback: {objectType}")
                    return {'objectType': objectType}
        
        logger.debug(f"[_detectSubtypeQuery] ❌ No subtype query detected")
        return None
    
    def _detectRoleSubtypeAssignment(self, message: str) -> Optional[Dict]:
        """
        Detect role/subtype assignment patterns like:
        - "set role for the Data protection officer for the person Ruby"
        - "add in the DPO for the person Tommy"
        - "set subtype Controller for the scope Project Phoenix"
        - "assign role Data Protection Officer to person John"
        - "set role for the Data protection officer and create person Ruby" (multi-step: create with subtype)
        - "Create a new person 'John'.assign his role to 'DPO'" (with period separator)
        
        Returns:
            Dict with operation='update' or 'create', objectType, and subtype info if detected, None otherwise
        """
        messageLower = message.lower().strip()
        
        # CRITICAL: Skip list queries - these should NOT match role assignment patterns
        # Check if message starts with list query keywords or matches list query patterns
        list_starters = ['show', 'list', 'display', 'how many', 'what', 'do we have', 'are there', 'tell me']
        list_query_patterns = [
            r'^show\s+(?:me\s+)?(?:all\s+)?',  # "show me all", "show all"
            r'^list\s+(?:all\s+)?',  # "list all", "list"
            r'^display\s+(?:all\s+)?',  # "display all"
            r'^how\s+many\s+',  # "how many"
            r'^what\s+(?:are|is)\s+',  # "what are", "what is"
            r'^do\s+we\s+have\s+',  # "do we have"
            r'^are\s+there\s+',  # "are there"
            r'^tell\s+me\s+(?:all\s+)?',  # "tell me all", "tell me"
        ]
        
        # Check both simple startswith and regex patterns
        is_list_query = (
            any(messageLower.startswith(starter) for starter in list_starters) or
            any(re.match(pattern, messageLower) for pattern in list_query_patterns)
        )
        
        if is_list_query:
            logger.debug(f"[_detectRoleSubtypeAssignment] Skipping - this is a list query: {message[:80]}")
            return None
        
        # CRITICAL: Check for bulk role assignment FIRST: "add John,Anna,Eddie to DPO"
        # BUT: Skip if it matches multi-create pattern (e.g., "Add 3 assets to IT-System asset")
        # Check for multi-create indicator first - if it matches, skip bulk role assignment
        multi_create_indicator = r'add\s+\d+\s+\b(person|persons|people|asset|assets|control|controls|scope|scopes|process|processes|document|documents|incident|incidents|scenario|scenarios)\b\s+to'
        if not re.search(multi_create_indicator, message, re.IGNORECASE):
            bulk_role_pattern = r'add\s+([A-Za-z0-9_\s,]+?)\s+to\s+([A-Za-z0-9_\s-]+)'
            bulk_role_match = re.search(bulk_role_pattern, message, re.IGNORECASE)
            if bulk_role_match:
                names_str = bulk_role_match.group(1).strip()
                subtype = bulk_role_match.group(2).strip()
                
                # Additional validation: names should be actual names (not numbers or object types)
                # If names_str contains numbers or looks like "3 assets", skip this pattern
                if re.search(r'\d+', names_str) or any(obj_type in names_str.lower() for obj_type in ['asset', 'scope', 'control', 'person', 'process', 'document', 'incident', 'scenario']):
                    logger.debug(f"[_detectRoleSubtypeAssignment] Skipping bulk role - looks like multi-create: '{names_str}'")
                else:
                    # Parse comma-separated names
                    names = [name.strip() for name in names_str.split(',')]
                    
                    # Validate names are actual names (not generic terms)
                    valid_names = [n for n in names if n.lower() not in ['all', 'the', 'our', 'isms', 'in', 'is', 'dpo', 'it-system', 'it system', 'datatype', 'datatypes']]
                    if valid_names:
                        # Normalize subtype
                        subtype_normalized = self._normalizeSubtypeForObject(subtype, 'person')
                        
                        logger.info(f"[_detectRoleSubtypeAssignment] ✅ Bulk role assignment: {len(valid_names)} persons to {subtype_normalized}")
                        return {
                            'operation': 'update',
                            'objectType': 'person',
                            'names': valid_names,
                            'subtype': subtype_normalized,
                            'isRoleAssignment': True,
                            'isBulk': True
                        }
        
        # CRITICAL: Check for multi-step pattern FIRST: "set role for X and create person Y"
        # This should create the person with the subtype, not update an existing person
        multi_step_pattern = r'set\s+role\s+for\s+(?:the\s+)?([A-Za-z0-9_\s-]+?)\s+and\s+(?:create|creat|reate)\s+person\s+["\']?([^"\']+)["\']?'
        multi_step_match = re.search(multi_step_pattern, message, re.IGNORECASE)
        if multi_step_match:
            subtype = multi_step_match.group(1).strip()
            person_name = multi_step_match.group(2).strip().strip("'\"")
            logger.info(f"[_detectRoleSubtypeAssignment] ✅ Multi-step pattern matched: create person '{person_name}' with subtype '{subtype}'")
            return {
                'operation': 'create',
                'objectType': 'person',
                'objectName': person_name,
                'subtype': subtype,
                'isRoleAssignment': True,
                'isMultiStep': True  # Flag to indicate this is a create-with-subtype operation
            }
        
        # Pattern: "Create a new person 'John'.assign his role to 'DPO'" (with period separator)
        # Handles: create person 'name'.assign role to 'subtype' (no space between quote and period)
        # Also handles: create person 'name', assign role to 'subtype' (with space)
        period_separator_pattern = r'(?:create|creat|new|add)\s+(?:a\s+)?(?:new\s+)?person\s+["\']([^"\']+)["\']\s*[\.\,]\s*(?:assign|set)\s+(?:his|her|their|its)\s+role\s+to\s+["\']([^"\']+)["\']'
        period_match = re.search(period_separator_pattern, message, re.IGNORECASE)
        if period_match:
            person_name = period_match.group(1).strip()
            subtype = period_match.group(2).strip()
            
            # Map common abbreviations to full subtype names
            subtype_mapping = {
                'dpo': 'Data protection officer',
                'data protection officer': 'Data protection officer',
            }
            subtype_lower = subtype.lower()
            if subtype_lower in subtype_mapping:
                subtype = subtype_mapping[subtype_lower]
            
            logger.info(f"[_detectRoleSubtypeAssignment] ✅ Period separator pattern matched: create person '{person_name}' with role '{subtype}'")
            return {
                'operation': 'create',
                'objectType': 'person',
                'objectName': person_name,
                'subtype': subtype,
                'isRoleAssignment': True,
                'isMultiStep': True
            }
        
        # Pattern 1: "set role for the [subtype] for the person [name]"
        # Pattern 2: "set role for [subtype] for the person [name]"
        # Pattern 3: "add in the [subtype] for the person [name]"
        # Pattern 4: "add [subtype] for the person [name]"
        # Pattern 5: "assign role [subtype] to person [name]"
        # Pattern 6: "set subtype [subtype] for the [objectType] [name]"
        
        role_assignment_patterns = [
            # Person-specific patterns (highest priority)
            # "set role for the Data protection officer for the person Ruby"
            r'set\s+role\s+for\s+(?:the\s+)?([A-Za-z0-9_\s-]+?)\s+for\s+(?:the\s+)?person\s+["\']?([^"\']+)["\']?',
            # "add in the DPO for the person Tommy"
            r'add\s+(?:in\s+the\s+)?([A-Za-z0-9_\s-]+?)\s+for\s+(?:the\s+)?person\s+["\']?([^"\']+)["\']?',
            # "add DPO for person Tommy" (without "in the")
            r'add\s+([A-Za-z0-9_\s-]+?)\s+for\s+(?:the\s+)?person\s+["\']?([^"\']+)["\']?',
            # "assign role Data Protection Officer to person Ruby"
            r'assign\s+role\s+([A-Za-z0-9_\s-]+?)\s+to\s+(?:the\s+)?person\s+["\']?([^"\']+)["\']?',
            # "set the role to DPO for the person Ruby"
            r'set\s+(?:the\s+)?role\s+to\s+([A-Za-z0-9_\s-]+?)\s+for\s+(?:the\s+)?person\s+["\']?([^"\']+)["\']?',
            # "set role Data Protection Officer for person Ruby" (without "for the")
            r'set\s+role\s+([A-Za-z0-9_\s-]+?)\s+for\s+(?:the\s+)?person\s+["\']?([^"\']+)["\']?',
            # "assign DPO role to person Ruby" (role after subtype)
            r'assign\s+([A-Za-z0-9_\s-]+?)\s+role\s+to\s+(?:the\s+)?person\s+["\']?([^"\']+)["\']?',
            # "make person Ruby a DPO" (casual format)
            r'make\s+(?:the\s+)?person\s+["\']?([^"\']+)["\']?\s+(?:a|an)\s+([A-Za-z0-9_\s-]+)',
            # Generic patterns for all object types
            # "set subtype Controller for the scope Project Phoenix"
            # CRITICAL: Must require a name after object type to avoid matching "show all persons"
            r'set\s+subtype\s+([A-Za-z0-9_\s-]+?)\s+for\s+(?:the\s+)?(scope|scopes|asset|assets|control|controls|person|persons|people|process|processes|document|documents|incident|incidents|scenario|scenarios)\s+["\']?([A-Za-z0-9_\s-]+)["\']?',
            # "add subtype Datatype for the asset Main Firewall"
            # CRITICAL: Must require a name after object type to avoid matching "show all persons"
            r'add\s+(?:subtype\s+)?([A-Za-z0-9_\s-]+?)\s+for\s+(?:the\s+)?(scope|scopes|asset|assets|control|controls|person|persons|people|process|processes|document|documents|incident|incidents|scenario|scenarios)\s+["\']?([A-Za-z0-9_\s-]+)["\']?',
            # "assign subtype Controller to the scope Project Phoenix"
            r'assign\s+subtype\s+([A-Za-z0-9_\s-]+?)\s+to\s+(?:the\s+)?(scope|scopes|asset|assets|control|controls|person|persons|people|process|processes|document|documents|incident|incidents|scenario|scenarios)\s+["\']?([^"\']+)["\']?',
        ]
        
        for pattern in role_assignment_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                # CRITICAL: Double-check this is not a list query (safety net)
                matched_text = match.group(0).lower()
                list_query_indicators = ['show', 'list', 'display', 'how many', 'tell me', 'do we have', 'are there']
                if any(indicator in messageLower[:50] for indicator in list_query_indicators):
                    logger.debug(f"[_detectRoleSubtypeAssignment] Pattern matched but message is a list query: {message[:80]}")
                    continue
                
                # CRITICAL: Validate that this is actually a role assignment, not a list query
                # Check if the match contains actual role assignment keywords
                role_keywords = ['set', 'add', 'assign', 'role', 'subtype', 'make']
                if not any(keyword in matched_text for keyword in role_keywords):
                    # This doesn't look like a role assignment, skip it
                    logger.debug(f"[_detectRoleSubtypeAssignment] Pattern matched but missing role keywords: {matched_text}")
                    continue
                
                # Determine if this is a person-specific pattern or generic pattern
                # Person-specific patterns have 2 groups (subtype, name) or (name, subtype)
                # Generic patterns have 3 groups (subtype, objectType, name)
                num_groups = len(match.groups())
                
                # CRITICAL: Ensure objectName is not empty or just "all" - list queries often have "all" as the name
                if num_groups >= 2:
                    potential_name = match.group(num_groups).strip().strip("'\"")
                    if not potential_name or potential_name.lower() in ['all', 'the', 'our', 'isms', 'in', 'is', 'dpo', 'it-system', 'it system']:
                        logger.debug(f"[_detectRoleSubtypeAssignment] Pattern matched but objectName is invalid: '{potential_name}'")
                        continue
                
                if num_groups == 2:
                    if 'make' in messageLower and 'person' in messageLower:
                        objectType = 'person'
                        objectName = match.group(1).strip().strip("'\"")
                        subtype = match.group(2).strip()
                    else:
                        # Person-specific pattern: "set role for DPO for the person Ruby"
                        # Most patterns have (subtype, name) order
                        objectType = 'person'
                        subtype = match.group(1).strip()
                        objectName = match.group(2).strip().strip("'\"")
                elif num_groups == 3:
                    # Generic pattern: "set subtype Controller for the scope Project Phoenix"
                    objectType = match.group(2).strip().lower()
                    subtype = match.group(1).strip()
                    objectName = match.group(3).strip().strip("'\"")
                    # Normalize objectType
                    if objectType.endswith('s') and objectType != 'process':
                        objectType = objectType[:-1]
                else:
                    # Unexpected number of groups, skip this pattern
                    continue
                
                logger.info(f"[_detectRoleSubtypeAssignment] ✅ Matched: subtype='{subtype}', objectType='{objectType}', name='{objectName}'")
                
                return {
                    'operation': 'update',
                    'objectType': objectType,
                    'subtype': subtype,
                    'objectName': objectName,
                    'isRoleAssignment': True
                }
        
        return None
    
    def _detectCreateAndLink(self, message: str) -> Optional[Dict]:
        """
        Detect create-and-link operations like:
        - "Create a new Scope named 'Project Phoenix' and immediately link it with the 'IT-System assets' assets"
        - "Create a new Incident named 'Phishing Attempt Jan-24'. Then, find the 'Email Server' asset and link it to this incident"
        
        Returns:
            Dict with source_type, source_name, target_type, target_name if detected, None otherwise
        """
        messageLower = message.lower().strip()
        logger.debug(f"[_detectCreateAndLink] Checking message: {message[:100]}")
        
        # Pattern 1: create object X (named 'name') and immediately link it with target Y
        # CRITICAL: Must NOT match "and also create" - only match "and link" or "and immediately link"
        pattern1 = r'(?:create|creat|new|add)\s+(?:a\s+)?(?:new\s+)?(scope|scopes|asset|assets|control|controls|person|persons|people|process|processes|document|documents|incident|incidents|scenario|scenarios)\s+(?:named|called)\s+["\']([^"\']+)["\']\s+and\s+(?!also\s+create)(?:immediately\s+)?(?:link|connect|associate)\s+(?:it|them)\s+(?:with|to)\s+(?:the\s+)?["\']([^"\']+)["\']\s+(scope|scopes|asset|assets|control|controls|person|persons|people|process|processes|document|documents|incident|incidents|scenario|scenarios)'
        match1 = re.search(pattern1, message, re.IGNORECASE)
        if match1:
            source_type = match1.group(1).strip().lower()
            source_name = match1.group(2).strip()
            target_name = match1.group(3).strip()
            target_type = match1.group(4).strip().lower()
            
            # Normalize types
            if source_type.endswith('s') and source_type != 'process':
                source_type = source_type[:-1]
            if target_type.endswith('s') and target_type != 'process':
                target_type = target_type[:-1]
            
            return {
                'source_type': source_type,
                'source_name': source_name,
                'target_type': target_type,
                'target_name': target_name
            }
        
        # Pattern 2: create object X (named 'name'). Then, find object Y and link it to X
        pattern2 = r'(?:create|creat|new|add)\s+(?:a\s+)?(?:new\s+)?(scope|scopes|asset|assets|control|controls|person|persons|people|process|processes|document|documents|incident|incidents|scenario|scenarios)\s+(?:named|called)\s+["\']([^"\']+)["\']\s*[\.\,]\s*then[^\.]*["\']([^"\']+)["\']\s+(scope|scopes|asset|assets|control|controls|person|persons|people|process|processes|document|documents|incident|incidents|scenario|scenarios)'
        match2 = re.search(pattern2, message, re.IGNORECASE)
        if match2:
            source_type = match2.group(1).strip().lower()
            source_name = match2.group(2).strip()
            target_name = match2.group(3).strip()
            target_type = match2.group(4).strip().lower()
            
            # Normalize types
            if source_type.endswith('s') and source_type != 'process':
                source_type = source_type[:-1]
            if target_type.endswith('s') and target_type != 'process':
                target_type = target_type[:-1]
            
            return {
                'source_type': source_type,
                'source_name': source_name,
                'target_type': target_type,
                'target_name': target_name
            }
        
        # Pattern 3: create object X and link with target Y (simpler format, no quotes, no "named")
        # Also handles: "create SCOPE-C and link with 'DESKTOP' asset" (with quotes)
        # Also handles: "create SCOPE-C and link with 'DESKTOP" (incomplete quotes)
        # Also handles: "create SCOPE-C and link with 'DESKTOP'" (no type word at end)
        # Also handles: "create SCOPE-D and link with 'DESKTOP' assets" (with type word)
        # CRITICAL: Use separate patterns for quoted vs unquoted to avoid ambiguity
        # Pattern 3a: create object X and link with 'target Y' objects (with quotes and explicit type)
        pattern3a = r'(?:create|creat|new|add)\s+(?:a\s+)?(?:new\s+)?(scope|scopes|asset|assets|control|controls|person|persons|people|process|processes|document|documents|incident|incidents|scenario|scenarios)\s+([A-Za-z0-9_-]+(?:[A-Za-z0-9_\s-]*[A-Za-z0-9_-])?)\s+and\s+(?:link|connect|associate)\s+(?:it|them\s+)?(?:with|to)\s+(?:the\s+)?["\']([^"\']+?)["\'](?:\s+(scope|scopes|asset|assets|control|controls|person|persons|people|process|processes|document|documents|incident|incidents|scenario|scenarios))?'
        match3a = re.search(pattern3a, message, re.IGNORECASE)
        logger.debug(f"[_detectCreateAndLink] Pattern 3a match: {match3a is not None}, groups: {match3a.groups() if match3a else None}")
        if match3a:
            source_type = match3a.group(1).strip().lower()
            source_name = match3a.group(2).strip()
            target_name = match3a.group(3).strip()
            target_type = (match3a.group(4) or 'asset').strip().lower()
            
            # Normalize types
            if source_type.endswith('s') and source_type != 'process':
                source_type = source_type[:-1]
            if target_type.endswith('s') and target_type != 'process':
                target_type = target_type[:-1]
            
            logger.info(f"[_detectCreateAndLink] Pattern 3a (quoted) matched: source={source_type} '{source_name}', target={target_type} '{target_name}'")
            return {
                'source_type': source_type,
                'source_name': source_name,
                'target_type': target_type,
                'target_name': target_name
            }
        
        # Pattern 3a-alt: Without explicit type word - "create SCOPE-D and link with 'DESKTOP' assets"
        # Infer type from name pattern (SCOPE-* suggests scope, etc.) or default to scope
        pattern3a_alt = r'(?:create|creat|new|add)\s+(?:a\s+)?(?:new\s+)?([A-Za-z0-9_-]+(?:[A-Za-z0-9_\s-]*[A-Za-z0-9_-])?)\s+and\s+(?:link|connect|associate)\s+(?:it|them\s+)?(?:with|to)\s+(?:the\s+)?["\']([^"\']+?)["\'](?:\s+(scope|scopes|asset|assets|control|controls|person|persons|people|process|processes|document|documents|incident|incidents|scenario|scenarios))?'
        match3a_alt = re.search(pattern3a_alt, message, re.IGNORECASE)
        logger.debug(f"[_detectCreateAndLink] Pattern 3a-alt match: {match3a_alt is not None}, groups: {match3a_alt.groups() if match3a_alt else None}")
        if match3a_alt:
            source_name = match3a_alt.group(1).strip()
            target_name = match3a_alt.group(2).strip()
            target_type = (match3a_alt.group(3) or 'asset').strip().lower()
            
            # Infer source type from name pattern or default to scope
            source_type = 'scope'  # Default
            if source_name.upper().startswith('SCOPE-') or 'scope' in source_name.lower():
                source_type = 'scope'
            elif source_name.upper().startswith('ASSET-') or 'asset' in source_name.lower():
                source_type = 'asset'
            elif source_name.upper().startswith('CONTROL-') or 'control' in source_name.lower():
                source_type = 'control'
            
            # Normalize types
            if target_type.endswith('s') and target_type != 'process':
                target_type = target_type[:-1]
            
            logger.info(f"[_detectCreateAndLink] Pattern 3a-alt (quoted, inferred type) matched: source={source_type} '{source_name}', target={target_type} '{target_name}'")
            return {
                'source_type': source_type,
                'source_name': source_name,
                'target_type': target_type,
                'target_name': target_name
            }
        
        # Pattern 3b: create object X and link with target Y objects (without quotes, with explicit type)
        pattern3b = r'(?:create|creat|new|add)\s+(?:a\s+)?(?:new\s+)?(scope|scopes|asset|assets|control|controls|person|persons|people|process|processes|document|documents|incident|incidents|scenario|scenarios)\s+([A-Za-z0-9_-]+(?:[A-Za-z0-9_\s-]*[A-Za-z0-9_-])?)\s+and\s+(?:link|connect|associate)\s+(?:it|them\s+)?(?:with|to)\s+(?:the\s+)?([A-Za-z0-9_\s-]+?)(?:\s+(scope|scopes|asset|assets|control|controls|person|persons|people|process|processes|document|documents|incident|incidents|scenario|scenarios))?'
        match3b = re.search(pattern3b, message, re.IGNORECASE)
        logger.debug(f"[_detectCreateAndLink] Pattern 3b match: {match3b is not None}, groups: {match3b.groups() if match3b else None}")
        if match3b:
            source_type = match3a.group(1).strip().lower()
            source_name = match3a.group(2).strip()
            target_name = match3a.group(3).strip()
            target_type = (match3a.group(4) or 'asset').strip().lower()
            
            # Normalize types
            if source_type.endswith('s') and source_type != 'process':
                source_type = source_type[:-1]
            if target_type.endswith('s') and target_type != 'process':
                target_type = target_type[:-1]
            
            logger.info(f"[_detectCreateAndLink] Pattern 3a (quoted) matched: source={source_type} '{source_name}', target={target_type} '{target_name}'")
            return {
                'source_type': source_type,
                'source_name': source_name,
                'target_type': target_type,
                'target_name': target_name
            }
        
        # Pattern 3b: Without quotes - "create SCOPE-D and link with DESKTOP assets"
        pattern3b = r'(?:create|creat|new|add)\s+(?:a\s+)?(?:new\s+)?(scope|scopes|asset|assets|control|controls|person|persons|people|process|processes|document|documents|incident|incidents|scenario|scenarios)\s+([A-Za-z0-9_-]+(?:[A-Za-z0-9_\s-]*[A-Za-z0-9_-])?)\s+and\s+(?:link|connect|associate)\s+(?:it|them\s+)?(?:with|to)\s+(?:the\s+)?([A-Za-z0-9_\s-]+?)(?:\s+(scope|scopes|asset|assets|control|controls|person|persons|people|process|processes|document|documents|incident|incidents|scenario|scenarios))?'
        match3b = re.search(pattern3b, message, re.IGNORECASE)
        logger.debug(f"[_detectCreateAndLink] Pattern 3b match: {match3b is not None}, groups: {match3b.groups() if match3b else None}")
        if match3b:
            source_type = match3b.group(1).strip().lower()
            source_name = match3b.group(2).strip()
            target_name = match3b.group(3).strip()
            target_type = (match3b.group(4) or 'asset').strip().lower()
            
            # Normalize types
            if source_type.endswith('s') and source_type != 'process':
                source_type = source_type[:-1]
            if target_type.endswith('s') and target_type != 'process':
                target_type = target_type[:-1]
            
            logger.info(f"[_detectCreateAndLink] Pattern 3b (unquoted) matched: source={source_type} '{source_name}', target={target_type} '{target_name}'")
            return {
                'source_type': source_type,
                'source_name': source_name,
                'target_type': target_type,
                'target_name': target_name
            }
        
        # Pattern 3b-alt: create object X and link with target Y objects (without quotes, type inferred)
        pattern3b_alt = r'(?:create|creat|new|add)\s+(?:a\s+)?(?:new\s+)?([A-Za-z0-9_-]+(?:[A-Za-z0-9_\s-]*[A-Za-z0-9_-])?)\s+and\s+(?:link|connect|associate)\s+(?:it|them\s+)?(?:with|to)\s+(?:the\s+)?([A-Za-z0-9_\s-]+?)(?:\s+(scope|scopes|asset|assets|control|controls|person|persons|people|process|processes|document|documents|incident|incidents|scenario|scenarios))?'
        match3b_alt = re.search(pattern3b_alt, message, re.IGNORECASE)
        logger.debug(f"[_detectCreateAndLink] Pattern 3b-alt match: {match3b_alt is not None}, groups: {match3b_alt.groups() if match3b_alt else None}")
        if match3b_alt:
            source_name = match3b_alt.group(1).strip()
            target_name = match3b_alt.group(2).strip()
            target_type = (match3b_alt.group(3) or 'asset').strip().lower()
            
            # Infer source type from name pattern or default to scope
            source_type = 'scope'  # Default
            if source_name.upper().startswith('SCOPE-') or 'scope' in source_name.lower():
                source_type = 'scope'
            elif source_name.upper().startswith('ASSET-') or 'asset' in source_name.lower():
                source_type = 'asset'
            elif source_name.upper().startswith('CONTROL-') or 'control' in source_name.lower():
                source_type = 'control'
            
            # Normalize types
            if target_type.endswith('s') and target_type != 'process':
                target_type = target_type[:-1]
            
            logger.info(f"[_detectCreateAndLink] Pattern 3b-alt (unquoted, inferred type) matched: source={source_type} '{source_name}', target={target_type} '{target_name}'")
            return {
                'source_type': source_type,
                'source_name': source_name,
                'target_type': target_type,
                'target_name': target_name
            }
        
        # Pattern 4: create object X and link it to target Y (with "it" pronoun)
        pattern4 = r'(?:create|creat|new|add)\s+(?:a\s+)?(?:new\s+)?(scope|scopes|asset|assets|control|controls|person|persons|people|process|processes|document|documents|incident|incidents|scenario|scenarios)\s+(?:named|called)?\s*["\']?([^"\']+)["\']?\s+and\s+(?:link|connect|associate)\s+it\s+(?:with|to)\s+(?:the\s+)?["\']?([^"\']+)["\']?\s+(scope|scopes|asset|assets|control|controls|person|persons|people|process|processes|document|documents|incident|incidents|scenario|scenarios)'
        match4 = re.search(pattern4, message, re.IGNORECASE)
        if match4:
            source_type = match4.group(1).strip().lower()
            source_name = match4.group(2).strip()
            target_name = match4.group(3).strip()
            target_type = match4.group(4).strip().lower()
            
            # Normalize types
            if source_type.endswith('s') and source_type != 'process':
                source_type = source_type[:-1]
            if target_type.endswith('s') and target_type != 'process':
                target_type = target_type[:-1]
            
            return {
                'source_type': source_type,
                'source_name': source_name,
                'target_type': target_type,
                'target_name': target_name
            }
        
        # Pattern 5: create object X, then link it to target Y (with comma separator)
        pattern5 = r'(?:create|creat|new|add)\s+(?:a\s+)?(?:new\s+)?(scope|scopes|asset|assets|control|controls|person|persons|people|process|processes|document|documents|incident|incidents|scenario|scenarios)\s+(?:named|called)?\s*["\']?([^"\']+)["\']?\s*[,\.]\s*then\s+(?:link|connect|associate)\s+(?:it|them)?\s+(?:with|to)\s+(?:the\s+)?["\']?([^"\']+)["\']?\s+(scope|scopes|asset|assets|control|controls|person|persons|people|process|processes|document|documents|incident|incidents|scenario|scenarios)'
        match5 = re.search(pattern5, message, re.IGNORECASE)
        if match5:
            source_type = match5.group(1).strip().lower()
            source_name = match5.group(2).strip()
            target_name = match5.group(3).strip()
            target_type = match5.group(4).strip().lower()
            
            # Normalize types
            if source_type.endswith('s') and source_type != 'process':
                source_type = source_type[:-1]
            if target_type.endswith('s') and target_type != 'process':
                target_type = target_type[:-1]
            
            return {
                'source_type': source_type,
                'source_name': source_name,
                'target_type': target_type,
                'target_name': target_name
            }
        
        logger.debug(f"[_detectCreateAndLink] No pattern matched for message: {message[:100]}")
        return None
    
    def _checkGreeting(self, message: str, state: Dict) -> Optional[Dict]:
        """Check if message is a greeting"""
        messageLower = message.lower().strip()
        greetings = ['hi', 'hello', 'hey', 'greetings', 'good morning', 
                    'good afternoon', 'good evening']
        
        # Only treat as greeting if message is ONLY greeting (no other words)
        if messageLower in greetings:
            return {
                'route': self.ROUTE_GREETING,
                'handler': '_checkGreeting',
                'data': {},
                'confidence': 1.0
            }
        
        return None
    
    # ==================== VERINICE OPERATION DETECTION ====================
    
    def _detectVeriniceOp(self, message: str) -> Optional[Dict]:
        """Detect Verinice operation from message - ignore questions"""
        try:
            messageLower = message.lower().strip()
            
            # CRITICAL: Check for standalone link operations FIRST (before question filtering)
            # Patterns: "link SCOPE-B with IT-System assets", "link DPO with SCOPE-A"
            link_patterns = [
                # Pattern 1: "link SOURCE with TARGET objects" or "link SOURCE to TARGET objects"
                r'link\s+([A-Za-z0-9_\s-]+?)\s+(?:with|to)\s+(?:the\s+)?([A-Za-z0-9_\s-]+?)\s+(scope|scopes|asset|assets|control|controls|person|persons|people|process|processes|document|documents|incident|incidents|scenario|scenarios)',
                # Pattern 2: "link SOURCE with TARGET" (without object type word)
                r'link\s+([A-Za-z0-9_\s-]+?)\s+(?:with|to)\s+(?:the\s+)?([A-Za-z0-9_\s-]+?)\s*$',
            ]
            
            for pattern in link_patterns:
                match = re.search(pattern, messageLower)
                if match:
                    source_name = match.group(1).strip()
                    target_name = match.group(2).strip()
                    target_type_raw = match.group(3).strip().lower() if len(match.groups()) >= 3 else None
                    
                    # Infer source type from name patterns
                    source_type = 'scope'  # Default
                    if source_name.upper().startswith('SCOPE-') or 'scope' in source_name.lower():
                        source_type = 'scope'
                    elif 'dpo' in source_name.lower() and len(source_name.strip()) <= 5:
                        # DPO is a subtype, not a person name - this is bulk linking
                        source_type = 'person'
                        # For "link DPO with SCOPE-A", we want to link all DPO persons to the scope
                        # So source_name should be None and subtype should be DPO
                        subtype = 'Data protection officer'
                        source_name = None  # Clear for bulk linking
                        # Also set target_type to scope if not already set
                        if not target_type_raw:
                            target_type = 'scope'
                    elif source_name.upper().startswith('ASSET-') or 'asset' in source_name.lower():
                        source_type = 'asset'
                    
                    # Infer target type
                    if target_type_raw:
                        if target_type_raw.endswith('s') and target_type_raw != 'process':
                            target_type = target_type_raw[:-1]
                        else:
                            target_type = target_type_raw
                    else:
                        # Try to infer from target name
                        if 'it-system' in target_name.lower() or 'datatype' in target_name.lower() or 'application' in target_name.lower():
                            target_type = 'asset'
                            # Extract subtype from target name
                            if 'it-system' in target_name.lower():
                                target_name = None  # Clear for bulk linking
                                subtype = 'IT-System'
                            elif 'datatype' in target_name.lower():
                                target_name = None
                                subtype = 'Datatype'
                            else:
                                subtype = None
                        else:
                            target_type = 'scope'  # Default
                            subtype = None
                    
                    # Check if target_name is a subtype (for bulk linking)
                    if target_name and not subtype:
                        common_subtypes = ['IT-System', 'IT System', 'Datatype', 'Data Type', 'DataType', 'Application', 'DPO', 'Data protection officer']
                        target_lower = target_name.lower().strip()
                        for st in common_subtypes:
                            st_lower = st.lower().replace('-', '').replace('_', '').replace(' ', '')
                            target_normalized = target_lower.replace('-', '').replace('_', '').replace(' ', '')
                            if st_lower == target_normalized or st_lower in target_normalized:
                                subtype = st
                                target_name = None  # Clear for bulk linking
                                break
                    
                    logger.info(f"[_detectVeriniceOp] ✅ Standalone link detected: source={source_type} '{source_name}', target={target_type} '{target_name}', subtype={subtype}")
                    result = {
                        'operation': 'link',
                        'source_type': source_type,
                        'source_name': source_name,
                        'target_type': target_type,
                        'target_name': target_name,
                        'subtype': subtype
                    }
                    # If source_name is None (bulk linking), ensure subtype is set
                    if source_name is None and subtype:
                        result['subtype'] = subtype
                    return result
            
            # Skip questions - these should go to LLM for knowledge answers
            # BUT: subtype queries and asset type queries should be handled separately (checked before this)
            # CRITICAL: Only skip if it's a pure knowledge question (not an ISMS operation)
            if any(messageLower.startswith(starter) for starter in VERINICE_QUESTION_STARTERS):
                subtype_patterns = [
                    r'how\s+many\s+subtypes?',
                    r'what\s+subtypes?',
                    r'list\s+subtypes?',
                    r'show\s+subtypes?',
                    r'get\s+subtypes?',
                ]
                asset_type_patterns = [
                    r'what\s+is\s+(?:this\s+)?.*?\s+asset\s+type',
                    r'tell\s+me\s+.*?\s+asset\s+is\s+in\s+which\s+asset\s+type',
                    r'what\s+type\s+(?:is|of)\s+.*?\s+asset',
                    r'.*?\s+asset\s+type\s+is',
                ]
                if not any(re.search(pattern, messageLower) for pattern in subtype_patterns):
                    if not any(re.search(pattern, messageLower) for pattern in asset_type_patterns):
                        # This allows "what is scope" to be handled as a question, but "compare X and Y" to be handled as operation
                        has_operation_keyword = any(
                            word in messageLower for word in 
                            ['compare', 'create', 'list', 'get', 'update', 'delete', 'analyze', 'link', 'unlink']
                        )
                        if not has_operation_keyword:
                            return None
        
            # Normalize typos - only replace whole words to avoid substring issues
            for typo, correct in VERINICE_TYPO_CORRECTIONS.items():
                # Use word boundaries to only replace whole words, not substrings
                pattern = r'\b' + re.escape(typo) + r'\b'
                messageLower = re.sub(pattern, correct, messageLower)
            
            # CRITICAL: Handle asset type queries FIRST (before object type extraction)
            # These should GET the asset and return its subtype
            asset_type_query_patterns = [
                r'what\s+is\s+(?:this\s+)?([A-Za-z0-9_\s-]+?)\s+asset\s+type',
                r'tell\s+me\s+([A-Za-z0-9_\s-]+?)\s+asset\s+is\s+in\s+which\s+asset\s+type',
                r'tell\s+me\s+([A-Za-z0-9_\s-]+?)\s+asset\s+is\s+in\s+which\s+asset',  # Without "type" at end
                r'what\s+type\s+(?:is|of)\s+([A-Za-z0-9_\s-]+?)\s+asset',
                r'([A-Za-z0-9_\s-]+?)\s+asset\s+type\s+is',
                # New patterns for additional variations
                r'tell\s+me\s+(?:the\s+)?asset\s+type\s+of\s+([A-Za-z0-9_\s-]+?)\s+asset',
                r'which\s+subtypes?\s+(?:is|are)\s+(?:the\s+)?([A-Za-z0-9_\s-]+?)\s+asset',
                r'show\s+me\s+(?:the\s+)?subtypes?\s+of\s+([A-Za-z0-9_\s-]+?)\s+asset',
            ]
            
            # Also handle "what is the DESKTOP asset" - should be a GET operation
            what_is_asset_pattern = r'what\s+is\s+(?:the\s+)?([A-Za-z0-9_\s-]+?)\s+asset(?:\s+type)?\s*$'
            what_is_match = re.search(what_is_asset_pattern, messageLower)
            if what_is_match:
                asset_name = what_is_match.group(1).strip()
                if 'type' in messageLower:
                    logger.info(f"[_detectVeriniceOp] ✅ Asset type query detected: asset={asset_name}")
                    return {
                        'operation': 'get',
                        'objectType': 'asset',
                        'objectName': asset_name,
                        'returnSubtype': True
                    }
                else:
                    # Just asking what the asset is - return full details
                    logger.info(f"[_detectVeriniceOp] ✅ Asset query detected: asset={asset_name}")
                    return {
                        'operation': 'get',
                        'objectType': 'asset',
                        'objectName': asset_name
                    }
            
            for pattern in asset_type_query_patterns:
                match = re.search(pattern, messageLower)
                if match:
                    asset_name = match.group(1).strip()
                    logger.info(f"[_detectVeriniceOp] ✅ Asset type query detected (early): asset={asset_name}")
                    return {
                        'operation': 'get',
                        'objectType': 'asset',
                        'objectName': asset_name,
                        'returnSubtype': True  # Flag to return subtype info
                    }
            
            # CRITICAL: Check if word after "create" is a subtype name, not an object type
            # This MUST happen BEFORE object type matching to avoid false matches
            # Pattern: create subtype X (named Y) - handles subtypes like Controllers, DPO, etc.
            # "Controllers" is a subtype of "Scopes", not a separate object type
            # Also handle: "Create a \"Controller\" named 'MFA for VPN'"
            # Also handle: "create person X as an Data protection officer"
            createSubtypePatterns = [
                r'create\s+(?:a\s+)?["\']([A-Z][^"\']+)["\']\s+(?:named|called)',  # "create 'Controllers' named"
                r'create\s+(?:a\s+)?["\']?([A-Z][a-z]+(?:s|es)?)["\']?\s+(?:named|called)',  # "create Controllers named" or "create \"Controller\" named"
                r'create\s+(?:a\s+)?["\']([A-Z][^"\']+)["\']',  # "create \"Controller\"" (without "named")
            ]
            
            # Pattern for "create person X as an Y" or "create person X as a Y"
            as_pattern = r'create\s+(?:a\s+)?(?:new\s+)?person\s+([A-Za-z0-9_\s-]+?)\s+as\s+(?:a|an)\s+([A-Za-z0-9_\s-]+)'
            as_match = re.search(as_pattern, message, re.IGNORECASE)
            if as_match:
                person_name = as_match.group(1).strip().strip("'\"")
                subtype = as_match.group(2).strip()
                
                # Map common abbreviations to full subtype names
                subtype_mapping = {
                    'dpo': 'Data protection officer',
                    'data protection officer': 'Data protection officer',
                }
                subtype_lower = subtype.lower()
                if subtype_lower in subtype_mapping:
                    subtype = subtype_mapping[subtype_lower]
                
                logger.info(f"[_detectVeriniceOp] ✅ 'as' pattern matched: create person '{person_name}' as '{subtype}'")
                return {
                    'operation': 'create',
                    'objectType': 'person',
                    'objectName': person_name,
                    'subType': subtype,
                    'isSubtypeFirst': False
                }
            
            for createSubtypePattern in createSubtypePatterns:
                createSubtypeMatch = re.search(createSubtypePattern, message, re.IGNORECASE)
                if createSubtypeMatch:
                    potentialSubtype = createSubtypeMatch.group(1).strip()
                    potentialSubtypeLower = potentialSubtype.lower()
                    
                    logger.debug(f"[_detectVeriniceOp] Found potential subtype: '{potentialSubtype}' (lowercase: '{potentialSubtypeLower}')")
                    logger.debug(f"[_detectVeriniceOp] VERINICE_SUBTYPE_MAPPINGS: {list(VERINICE_SUBTYPE_MAPPINGS.keys())}")
                    
                    # CRITICAL: Check subtype mappings FIRST - if it's in mappings, it's a subtype regardless
                    # This handles "Controller" which is a subtype of scope, not a control object
                    if potentialSubtypeLower in VERINICE_SUBTYPE_MAPPINGS:
                        objectType = VERINICE_SUBTYPE_MAPPINGS[potentialSubtypeLower]
                        # Extract the subtype name (preserve original case for matching)
                        detectedSubtype = potentialSubtype
                        
                        logger.info(f"[_detectVeriniceOp] ✅ Matched subtype '{potentialSubtype}' -> objectType: {objectType}")
                        
                        # Detect operation - check for create keywords
                        if any(word in messageLower for word in ['create', 'new', 'add', 'make']):
                            return {
                                'operation': 'create',
                                'objectType': objectType,
                                'subType': detectedSubtype,  # Pass subtype to handler
                                'isSubtypeFirst': True  # Flag to indicate subtype was detected first
                            }
                    
                    # This prevents "control" from matching when user says "create control"
                    # BUT: "Controller" (capitalized) is a subtype of scope, not the same as "control"
                    isKnownObjectType = any(objType.lower() == potentialSubtypeLower or 
                                           objType.lower() == potentialSubtypeLower.rstrip('s') or
                                           objType.lower() == potentialSubtypeLower.rstrip('es')
                                           for objType in self.veriniceObjectTypes)
                    
                    # Use subtype mappings from JSON (ismsInstructions.json) - fallback check
                    if not isKnownObjectType and potentialSubtypeLower in VERINICE_SUBTYPE_MAPPINGS:
                        objectType = VERINICE_SUBTYPE_MAPPINGS[potentialSubtypeLower]
                        # Extract the subtype name (preserve original case for matching)
                        detectedSubtype = potentialSubtype
                        
                        logger.info(f"[_detectVeriniceOp] ✅ Matched subtype via fallback '{potentialSubtype}' -> objectType: {objectType}")
                        
                        # Detect operation
                        if any(word in messageLower for word in ['create', 'new', 'add', 'make']):
                            return {
                                'operation': 'create',
                                'objectType': objectType,
                                'subType': detectedSubtype,  # Pass subtype to handler
                                'isSubtypeFirst': True  # Flag to indicate subtype was detected first
                            }
                    break  # Only check first matching pattern
            
            # CRITICAL: Check for bulk create patterns FIRST (before normal create detection)
            # Pattern: "create N objects in subtype" or "create N objects with subtype"
            # Examples: "create 5 persons in DPO now"
            #           "create 5 scopes named 'SCOPE1 TO 5' in our isms"
            #           "create 5 persons in DPO now and give thier names (John,Anna,Jame,David,Eddie)"
            bulk_create_patterns = [
                # Pattern 1: "create 5 persons in DPO now and give thier names (John,Anna,Jame,David,Eddie)"
                r'create\s+(\d+)\s+(person|persons|people|scope|scopes|asset|assets|control|controls|process|processes|document|documents|incident|incidents|scenario|scenarios)\s+in\s+([A-Za-z0-9_\s-]+?)(?:\s+now)?(?:\s+and\s+give\s+thier\s+names\s+\(([^)]+)\))',
                # Pattern 1b: "create 3 scopes in our isms and give the scopes name (SCOPE-A,SCOPE-B,and SCOPE-C)"
                # Also handles: "create 5 assets in our isms and give the asset name (Asset-A,E)"
                r'create\s+(\d+)\s+(person|persons|people|scope|scopes|asset|assets|control|controls|process|processes|document|documents|incident|incidents|scenario|scenarios)\s+in\s+(?:our|the)\s+isms(?:\s+and\s+give\s+(?:the\s+)?(?:scopes?|assets?|persons?|controls?|processes?|documents?|incidents?|scenarios?)\s+name\s+\(([^)]+)\))',
                # Pattern 1c: "create 5 persons now and give thier names (John,Anna,Jame,David,Eddie)" (without "in")
                r'create\s+(\d+)\s+(person|persons|people|scope|scopes|asset|assets|control|controls|process|processes|document|documents|incident|incidents|scenario|scenarios)\s+(?:now\s+)?and\s+give\s+(?:thier|their|the)\s+names\s+\(([^)]+)\)',
                # Pattern 2: "create 5 persons in DPO now" or "create 5 persons in DPO"
                r'create\s+(\d+)\s+(person|persons|people|scope|scopes|asset|assets|control|controls|process|processes|document|documents|incident|incidents|scenario|scenarios)\s+in\s+([A-Za-z0-9_\s-]+?)(?:\s+now)?\s*$',
                # Pattern 2b: "create 5 scopes in our isms" (without subtype)
                r'create\s+(\d+)\s+(person|persons|people|scope|scopes|asset|assets|control|controls|process|processes|document|documents|incident|incidents|scenario|scenarios)\s+in\s+(?:our|the)\s+isms\s*$',
                # Pattern 3: "create 5 scopes named 'SCOPE1 TO 5' in our isms"
                r'create\s+(\d+)\s+(person|persons|people|scope|scopes|asset|assets|control|controls|process|processes|document|documents|incident|incidents|scenario|scenarios)\s+(?:named|called)\s+["\']([^"\']+)["\']\s+in\s+(?:our|the)\s+isms',
            ]
            
            for pattern_idx, pattern in enumerate(bulk_create_patterns, 1):
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    count_str = match.group(1).strip()
                    object_type_raw = match.group(2).strip().lower()
                    
                    try:
                        count = int(count_str)
                    except ValueError:
                        continue
                    
                    # Normalize object type
                    if object_type_raw.endswith('s') and object_type_raw != 'process':
                        object_type = object_type_raw[:-1]
                    elif object_type_raw == 'people':
                        object_type = 'person'
                    else:
                        object_type = object_type_raw
                    
                    # Pattern 1: "in subtype and give names" - has subtype and names
                    if pattern_idx == 1:
                        subtype = match.group(3).strip() if len(match.groups()) >= 3 else None
                        names_list = match.group(4).strip() if len(match.groups()) >= 4 and match.group(4) else None
                        name_pattern = None
                        
                        # Map common abbreviations
                        subtype_mapping = {
                            'dpo': 'Data protection officer',
                            'data protection officer': 'Data protection officer',
                        }
                        if subtype:
                            subtype_lower = subtype.lower()
                            if subtype_lower in subtype_mapping:
                                subtype = subtype_mapping[subtype_lower]
                        
                        # Parse names list if provided: "(John,Anna,Jame,David,Eddie)" or "(SCOPE-A,SCOPE-B,and SCOPE-C)"
                        names = []
                        if names_list:
                            # Split by comma and clean up each name (remove "and" prefix if present)
                            raw_names = names_list.split(',')
                            for raw_name in raw_names:
                                name = raw_name.strip()
                                # Remove leading "and" if present
                                if name.lower().startswith('and '):
                                    name = name[4:].strip()
                                if name:
                                    names.append(name)
                    
                    # Pattern 1b: "in our isms and give names" - no subtype, has names
                    elif pattern_idx == 2:
                        subtype = None
                        names_list = match.group(3).strip() if len(match.groups()) >= 3 else None
                        name_pattern = None
                        names = []
                        if names_list:
                            # Split by comma and clean up each name (remove "and" prefix if present)
                            raw_names = names_list.split(',')
                            for raw_name in raw_names:
                                name = raw_name.strip()
                                # Remove leading "and" if present
                                if name.lower().startswith('and '):
                                    name = name[4:].strip()
                                if name:
                                    names.append(name)
                    
                    # Pattern 1c: "and give names" - no subtype, has names
                    elif pattern_idx == 3:
                        subtype = None
                        names_list = match.group(3).strip() if len(match.groups()) >= 3 else None
                        name_pattern = None
                        names = []
                        if names_list:
                            # Split by comma and clean up each name (remove "and" prefix if present)
                            raw_names = names_list.split(',')
                            for raw_name in raw_names:
                                name = raw_name.strip()
                                # Remove leading "and" if present
                                if name.lower().startswith('and '):
                                    name = name[4:].strip()
                                if name:
                                    names.append(name)
                    
                    # Pattern 2: "in subtype" - has subtype, no names
                    elif pattern_idx == 4:
                        subtype = match.group(3).strip() if len(match.groups()) >= 3 else None
                        name_pattern = None
                        names = []
                        
                        # Map common abbreviations
                        subtype_mapping = {
                            'dpo': 'Data protection officer',
                            'data protection officer': 'Data protection officer',
                        }
                        if subtype:
                            subtype_lower = subtype.lower()
                            if subtype_lower in subtype_mapping:
                                subtype = subtype_mapping[subtype_lower]
                    
                    # Pattern 2b: "in our isms" - no subtype, no names
                    elif pattern_idx == 5:
                        subtype = None
                        name_pattern = None
                        names = []
                    
                    # Pattern 3: "named 'SCOPE1 TO 5'" - name pattern
                    else:
                        name_pattern = match.group(3).strip() if len(match.groups()) >= 3 else None
                        subtype = None
                        names = []
                    
                    logger.info(f"[_detectVeriniceOp] ✅ Bulk create pattern {pattern_idx} matched: count={count}, objectType={object_type}, subtype={subtype}, name_pattern={name_pattern}, names={names}")
                    return {
                        'operation': 'create',
                        'objectType': object_type,
                        'count': count,
                        'subType': subtype,
                        'namePattern': name_pattern,
                        'names': names,
                        'isBulk': True
                    }
            
            # Extract object type (normal flow)
            # CRITICAL: Check for create-and-link patterns FIRST to avoid misrouting
            # Pattern: create object X (named 'name') and immediately link it with target Y
            # Also handle: "Create a new Incident named 'X'. Then, find the 'Y' asset and link it..."
            create_and_link_patterns = [
                r'(?:create|creat|new|add)\s+(?:a\s+)?(?:new\s+)?(scope|scopes|asset|assets|control|controls|person|persons|people|process|processes|document|documents|incident|incidents|scenario|scenarios)\s+(?:named|called)\s+["\']([^"\']+)["\']\s+and\s+(?:immediately\s+)?(?:link|connect|associate)',
                r'(?:create|creat|new|add)\s+(?:a\s+)?(?:new\s+)?(scope|scopes|asset|assets|control|controls|person|persons|people|process|processes|document|documents|incident|incidents|scenario|scenarios)\s+(?:named|called)\s+["\']([^"\']+)["\']\s*[\.\,]\s*then',
            ]
            
            create_link_match = None
            for pattern in create_and_link_patterns:
                create_link_match = re.search(pattern, messageLower)
                if create_link_match:
                    break
            
            if create_link_match:
                # If it's a create-and-link, prioritize the source object type
                detected_type = create_link_match.group(1).strip()
                if detected_type.endswith("es"):
                    if detected_type == "processes":
                        objectType = "process"
                    elif detected_type == "scopes":
                        objectType = "scope"
                    else:
                        objectType = detected_type[:-2]
                elif detected_type.endswith("s") and detected_type != "process":
                    objectType = detected_type[:-1]
                else:
                    objectType = detected_type
            else:
                objectType = None
                # Sort to check plurals first (longer strings first)
                sortedTypes = sorted(self.veriniceObjectTypes, key=len, reverse=True)
                for objType in sortedTypes:
                    # Use word boundary matching to avoid substring issues
                    pattern = r'\b' + re.escape(objType) + r'\b'
                    if re.search(pattern, messageLower):
                        # Convert to singular
                        if objType.endswith("es"):
                            if objType == "processes":
                                objectType = "process"
                            elif objType == "scopes":
                                objectType = "scope"
                            else:
                                objectType = objType[:-2]
                        elif objType.endswith("s") and objType != "process":
                            objectType = objType[:-1]
                        else:
                            objectType = objType
                        break
            
            # CRITICAL: Check for contextual linking BEFORE objectType check
            # This handles "link these person to SCOPE-A" even if objectType isn't explicitly detected
            if any(re.search(r'\b' + re.escape(word) + r'\b', messageLower) for word in ['link', 'connect', 'associate']):
                contextual_link_patterns = [
                    r'link\s+(?:these|those|the)\s+(?:person|persons|people)\s+(?:to|with)\s+([A-Za-z0-9_\s-]+)',
                    r'link\s+them\s+(?:to|with)\s+([A-Za-z0-9_\s-]+)',
                ]
                for pattern in contextual_link_patterns:
                    match = re.search(pattern, messageLower)
                    if match:
                        # Extract object type from pattern
                        inferred_type = 'person'  # Default for "these person/persons"
                        if 'person' in messageLower or 'people' in messageLower:
                            inferred_type = 'person'
                        elif 'asset' in messageLower:
                            inferred_type = 'asset'
                        elif 'control' in messageLower:
                            inferred_type = 'control'
                        
                        target_name = match.group(1).strip()
                        return {
                            'operation': 'link',
                            'objectType': inferred_type,
                            'isContextual': True,
                            'targetName': target_name
                        }
            
            if not objectType:
                return None
            
            # CRITICAL: Handle conversational prompts like "ok so how about assets? do we have any assets"
            # These should be routed to list operations
            conversational_list_patterns = [
                rf'ok\s+so\s+how\s+about\s+(?:the\s+)?{objectType}s?',  # "ok so how about assets"
                rf'ok\s+how\s+about\s+(?:the\s+)?{objectType}s?',  # "ok how about assets"
                rf'how\s+about\s+(?:the\s+)?{objectType}s?',  # "how about assets"
                rf'what\s+about\s+(?:the\s+)?{objectType}s?',  # "what about assets"
                rf'do\s+we\s+have\s+(?:any\s+)?(?:the\s+)?{objectType}s?',  # "do we have any assets"
                rf'are\s+there\s+(?:any\s+)?(?:the\s+)?{objectType}s?',  # "are there any assets"
            ]
            
            for pattern in conversational_list_patterns:
                if re.search(pattern, messageLower):
                    return {'operation': 'list', 'objectType': objectType}
            
            # CRITICAL: Handle delete patterns with typos like "Delete the Ruby form the person"
            # Pattern: delete/remove object X from object type Y (handles typo "form" instead of "from")
            delete_typo_patterns = [
                rf'(?:delete|remove)\s+([A-Za-z0-9_\s-]+?)\s+(?:form|from)\s+(?:the\s+)?{objectType}s?',  # "Delete Ruby form the person"
                rf'(?:delete|remove)\s+the\s+([A-Za-z0-9_\s-]+?)\s+(?:form|from)\s+(?:the\s+)?{objectType}s?',  # "Delete the Ruby form the person"
                rf'(?:delete|remove)\s+([A-Za-z0-9_\s-]+?)\s+(?:form|from)\s+(?:our\s+)?isms',  # "Delete Ruby form our isms"
            ]
            
            for pattern in delete_typo_patterns:
                match = re.search(pattern, messageLower)
                if match:
                    objectName = match.group(1).strip()
                    logger.info(f"[_detectVeriniceOp] ✅ Delete with typo pattern matched: objectType={objectType}, name={objectName}")
                    return {'operation': 'delete', 'objectType': objectType, 'objectName': objectName}
            
            # Also check for conversational patterns from JSON config
            for conv_pattern in VERINICE_CONVERSATIONAL_LIST:
                # Replace {objectType} placeholder with actual object type
                pattern = conv_pattern.replace('{objectType}', objectType)
                # Use word boundary matching for better accuracy
                if re.search(rf'\b{re.escape(pattern)}\b', messageLower, re.IGNORECASE):
                    return {'operation': 'list', 'objectType': objectType}
        
            # Detect operation - only for direct commands, not questions
            # Use word boundaries to avoid false matches
            # CRITICAL: Check for link operations FIRST (before other operations) to handle "link these person"
            if any(re.search(r'\b' + re.escape(word) + r'\b', messageLower) for word in ['link', 'connect', 'associate']):
                contextual_link_patterns = [
                    r'link\s+(?:these|those|the)\s+(?:person|persons|people)\s+(?:to|with)\s+([A-Za-z0-9_\s-]+)',
                    r'link\s+them\s+(?:to|with)\s+([A-Za-z0-9_\s-]+)',
                    r'link\s+(?:these|those|the)\s+(?:person|persons|people|asset|assets|control|controls|scope|scopes)\s+(?:to|with)\s+([A-Za-z0-9_\s-]+)',
                ]
                for pattern in contextual_link_patterns:
                    match = re.search(pattern, messageLower)
                    if match:
                        # Extract object type from pattern if present
                        inferred_type = None
                        if 'person' in messageLower or 'people' in messageLower:
                            inferred_type = 'person'
                        elif 'asset' in messageLower:
                            inferred_type = 'asset'
                        elif 'control' in messageLower:
                            inferred_type = 'control'
                        elif 'scope' in messageLower:
                            inferred_type = 'scope'
                        
                        # Use detected objectType or inferred type
                        final_object_type = objectType or inferred_type or 'person'  # Default to person
                        
                        # This is a contextual link - will be handled by handler
                        target_name = match.group(1).strip()
                        return {
                            'operation': 'link',
                            'objectType': final_object_type,
                            'isContextual': True,
                            'targetName': target_name
                        }
                
                # Standalone link operation: "link DESKTOP asset to the scope SCOPE-A"
                # Pattern: link object X (name, type) to target Y (target_type, target_name)
                # Also handles: "link DESKTOP asset to SCOPE-A scope"
                standalone_link_patterns = [
                    # Pattern 1: link object X (type) to the target Y (target_type)
                    r'link\s+["\']?([A-Za-z0-9_\s-]+)["\']?\s+(scope|scopes|asset|assets|control|controls|person|persons|people|process|processes|document|documents|incident|incidents|scenario|scenarios)\s+(?:to|with)\s+(?:the\s+)?(scope|scopes|asset|assets|control|controls|person|persons|people|process|processes|document|documents|incident|incidents|scenario|scenarios)\s+["\']?([A-Za-z0-9_\s-]+)["\']?',
                    # Pattern 2: link object X (type) to target Y (target_type)
                    r'link\s+["\']?([A-Za-z0-9_\s-]+)["\']?\s+(scope|scopes|asset|assets|control|controls|person|persons|people|process|processes|document|documents|incident|incidents|scenario|scenarios)\s+(?:to|with)\s+["\']?([A-Za-z0-9_\s-]+)["\']?\s+(scope|scopes|asset|assets|control|controls|person|persons|people|process|processes|document|documents|incident|incidents|scenario|scenarios)',
                ]
                for pattern in standalone_link_patterns:
                    match = re.search(pattern, messageLower)
                    if match:
                        source_name = match.group(1).strip()
                        source_type = match.group(2).strip().lower()
                        if len(match.groups()) == 4:
                            # Pattern 1: "link X asset to the scope Y"
                            target_type = match.group(3).strip().lower()
                            target_name = match.group(4).strip()
                        else:
                            # Pattern 2: link object X (type) to target Y (target_type)
                            target_name = match.group(3).strip()
                            target_type = match.group(4).strip().lower()
                        
                        # Normalize types
                        if source_type.endswith('s') and source_type != 'process':
                            source_type = source_type[:-1]
                        if target_type.endswith('s') and target_type != 'process':
                            target_type = target_type[:-1]
                        
                        return {
                            'operation': 'link',
                            'objectType': source_type,
                            'sourceName': source_name,
                            'sourceType': source_type,
                            'targetName': target_name,
                            'targetType': target_type
                        }
                
                # Regular link operation (fallback - minimal info)
                return {'operation': 'link', 'objectType': objectType}
            elif any(re.search(r'\b' + re.escape(word) + r'\b', messageLower) for word in VERINICE_DELETE_KEYWORDS + ['delete', 'remove', 'drop']):
                return {'operation': 'delete', 'objectType': objectType}
            elif any(re.search(r'\b' + re.escape(word) + r'\b', messageLower) for word in VERINICE_CREATE_KEYWORDS) and not any(q in messageLower for q in VERINICE_QUESTION_WORDS):
                return {'operation': 'create', 'objectType': objectType}
            elif any(re.search(r'\b' + re.escape(word) + r'\b', messageLower) for word in VERINICE_LIST_KEYWORDS) and not any(q in messageLower for q in VERINICE_QUESTION_WORDS):
                return {'operation': 'list', 'objectType': objectType}
            elif any(re.search(r'\b' + re.escape(word) + r'\b', messageLower) for word in VERINICE_GET_KEYWORDS) and not any(q in messageLower for q in VERINICE_QUESTION_WORDS):
                return {'operation': 'get', 'objectType': objectType}
            elif any(re.search(r'\b' + re.escape(word) + r'\b', messageLower) for word in VERINICE_UPDATE_KEYWORDS):
                return {'operation': 'update', 'objectType': objectType}
            # Compare operation - handle "compare X and Y"
            elif any(re.search(r'\b' + re.escape(word) + r'\b', messageLower) for word in ['compare', 'comparison', 'diff', 'difference', 'differences']):
                if not any(q in messageLower for q in VERINICE_QUESTION_WORDS):
                    return {'operation': 'compare', 'objectType': objectType}
            # Analyze operation - handle "analyze on", "analyze the", etc.
            elif any(re.search(r'\b' + re.escape(word) + r'\b', messageLower) for word in VERINICE_ANALYZE_KEYWORDS):
                if not any(q in messageLower for q in VERINICE_QUESTION_WORDS):
                    return {'operation': 'analyze', 'objectType': objectType}
            
            return None
        except Exception:
            return None
    
    # ==================== REPORT GENERATION DETECTION ====================
    
    def _detectReportGeneration(self, message: str) -> Optional[Dict]:
        """Detect report generation requests"""
        messageLower = message.lower().strip()
        
        hasReportKeyword = any(keyword in messageLower for keyword in VERINICE_REPORT_KEYWORDS)
        hasReportType = any(reportType in messageLower for reportType in VERINICE_REPORT_TYPES)
        
        # Also check for generic "report" (but only if it's not too ambiguous)
        hasGenericReport = 'report' in messageLower and not any(q in messageLower for q in VERINICE_QUESTION_WORDS + ['which'])
        
        if hasReportKeyword and (hasReportType or hasGenericReport):
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
                elif hasGenericReport:
                    # Generic "generate report" - default to inventory
                    reportType = 'inventory-of-assets'
            
            if reportType:
                return {'operation': 'generate_report', 'reportType': reportType}
        
        return None
    
    # ==================== INTENT CLASSIFIER ====================
    
    def _useIntentClassifier(self, message: str, context: Dict, intentClassifier) -> Optional[Dict]:
        """Use IntentClassifier (LLM-based) for routing"""
        try:
            classification = intentClassifier.classify(message, context)
            intent = classification.get('intent', 'unknown')
            confidence = classification.get('confidence', 0)
            
            # Only use if confident enough
            if confidence >= 0.6:
                # Map intent to handler
                if intent in ['verinice_create', 'verinice_list', 'verinice_get', 
                             'verinice_update', 'verinice_delete']:
                    # Re-detect to get operation details
                    veriniceOp = self._detectVeriniceOp(message)
                    if veriniceOp:
                        return {
                            'route': self.ROUTE_INTENT_CLASSIFIER,
                            'handler': '_handleVeriniceOp',
                            'data': veriniceOp,
                            'confidence': confidence
                        }
                
        except Exception:
            pass
        
        logger.debug(f"[_detectVeriniceOp] ❌ No operation detected")
        return None
    
    # ==================== MULTIPLE CREATE DETECTION ====================
    
    def _detectMultipleCreates(self, message: str) -> Optional[Dict]:
        """
        Detect multiple create operations in one message.
        
        Examples:
        - "create a new scope 'SCOPE-1' and also create a new Data protection officer 'John'"
        - "create scope X and create person Y"
        - "create asset A and also create control B"
        
        Returns:
            Dict with 'operations' list containing multiple create commands, or None
        """
        # Pattern to detect multiple creates with various connectors
        # Patterns: "create X 'name1' and create Y 'name2'", "create X 'name1', create Y 'name2'", etc.
        # First check if message contains indicators of multiple creates - quick check before regex
        multiple_create_indicators = [
            r'and\s+(?:also\s+)?(?:create|add)',
            r',\s+(?:create|add)',
            r'and\s+(?:create|add)',
            r'then\s+(?:create|add)',
            r'and\s+then\s+(?:create|add)',
            r'also\s+(?:create|add)',
            r'and\s+the\s+other\s+.*?\s+(?:add|create)',  # "and the other 2 add"
        ]
        if not any(re.search(pattern, message, re.IGNORECASE) for pattern in multiple_create_indicators):
            logger.debug(f"[_detectMultipleCreates] No multiple create indicators found in message")
            return None
        
        patterns = [
            # Pattern 0: Add N objects to subtype1, and the other M add to subtype2
            # Handles: Add 3 assets to IT-System asset, and the other 2 add to Datatypes assets
            # Examples: Add 3 assets to our IT-System asset, and the other 2 add to the Datatypes assets
            r'add\s+(\d+)\s+\b(person|persons|people|asset|assets|control|controls|scope|scopes|process|processes|document|documents|incident|incidents|scenario|scenarios)\b\s+to\s+(?:our|the)\s+([A-Za-z0-9_\s-]+?)\s+(?:asset|assets|person|persons|scope|scopes|control|controls|process|processes|document|documents|incident|incidents|scenario|scenarios)\s*,\s*and\s+the\s+other\s+(\d+)\s+(?:add|create)\s+to\s+(?:our|the)\s+([A-Za-z0-9_\s-]+?)\s+(?:asset|assets|person|persons|scope|scopes|control|controls|process|processes|document|documents|incident|incidents|scenario|scenarios)',
            
            # Pattern 1: create object X (named) 'name1' and also create/add N objects of type Y for subtype Z
            # Handles: create object X and create N objects of type Y for subtype Z
            # Examples: create scope X and create 3 assets for IT-System subtype
            #           create scope X and add 3 persons for Data protection officer subtype
            # CRITICAL: Use word boundary and specific object type matching to avoid capturing "for" as part of object type
            # This pattern must be FIRST to match before other patterns
            r'(?:create|add)\s+(?:a\s+)?(?:new\s+)?(.+?)\s+(?:named\s+)?([A-Za-z0-9_\s-]+?)\s+and\s+(?:also\s+)?(?:create|add)\s+(\d+)\s+\b(person|persons|people|asset|assets|control|controls|scope|scopes|process|processes|document|documents|incident|incidents|scenario|scenarios)\b\s+for\s+(?:the\s+)?([A-Za-z0-9_\s-]+?)(?:\s+(?:officer|officers|assets?|controls?|scopes?|persons?|processes?|documents?|incidents?|scenarios?))?',
            
            # Pattern 2a: create object X (name1) and create object Y ('name2') in our Z subtype objects
            # Handles: create object X and create object Y with subtype Z in our ISMS
            # Examples: create scope X and create asset 'Y' in our IT-System assets
            # Must come BEFORE Pattern 2 to match first
            r'create\s+(?:a\s+)?(?:new\s+)?(.+?)\s+([A-Za-z0-9_\s-]+?)\s+and\s+(?:also\s+)?create\s+(?:a\s+)?(?:new\s+)?(.+?)\s+["\']([^"\']+)["\']\s+in\s+(?:our|the)\s+([A-Za-z0-9_\s-]+?)\s+(?:assets?|scopes?|controls?|persons?|processes?|documents?|incidents?|scenarios?)',
            
            # Pattern 2: create object X ('name1') and (also) create object Y ('name2')
            # Handles: create object X and create object Y (both with quoted names)
            # Examples: create scope 'X' and create person 'Y'
            r'create\s+(?:a\s+)?(?:new\s+)?(.+?)\s+["\']([^"\']+)["\']\s+and\s+(?:also\s+)?create\s+(?:a\s+)?(?:new\s+)?(.+?)\s+["\']([^"\']+)["\']',
            
            # Pattern 3: create object X ('name1'), create object Y ('name2')
            # Handles: create object X and create object Y separated by comma
            # Examples: create scope 'X', create person 'Y'
            r'create\s+(?:a\s+)?(?:new\s+)?(.+?)\s+["\']([^"\']+)["\']\s*,\s*create\s+(?:a\s+)?(?:new\s+)?(.+?)\s+["\']([^"\']+)["\']',
            
            # Pattern 4: create object X ('name1') (and) then create object Y ('name2')
            # Handles: create object X and then create object Y (with "then" connector)
            # Examples: create scope 'X' then create person 'Y'
            r'create\s+(?:a\s+)?(?:new\s+)?(.+?)\s+["\']([^"\']+)["\']\s+(?:and\s+)?then\s+create\s+(?:a\s+)?(?:new\s+)?(.+?)\s+["\']([^"\']+)["\']',
            
            # Pattern 5: create object X ('name1') and object Y ('name2')
            # Handles: create object X and object Y (without second "create" keyword)
            # Examples: create scope 'X' and person 'Y'
            r'create\s+(?:a\s+)?(?:new\s+)?(.+?)\s+["\']([^"\']+)["\']\s+and\s+(?:a\s+)?(?:new\s+)?(.+?)\s+["\']([^"\']+)["\']',
            
            # Pattern 6: create object X ('name1') and also object Y ('name2')
            # Handles: create object X and also object Y (with "also" keyword, no second "create")
            # Examples: create scope 'X' and also person 'Y'
            r'create\s+(?:a\s+)?(?:new\s+)?(.+?)\s+["\']([^"\']+)["\']\s+and\s+also\s+(?:a\s+)?(?:new\s+)?(.+?)\s+["\']([^"\']+)["\']',
            
            # Pattern 7: add object X ('name1') and (also) add object Y ('name2')
            # Handles: add object X and add object Y (using "add" keyword instead of "create")
            # Examples: add scope 'X' and add person 'Y'
            r'add\s+(?:a\s+)?(?:new\s+)?(.+?)\s+["\']([^"\']+)["\']\s+and\s+(?:also\s+)?add\s+(?:a\s+)?(?:new\s+)?(.+?)\s+["\']([^"\']+)["\']',
            
            # Pattern 8: create object X ('name1'), and create object Y ('name2')
            # Handles: create object X and create object Y (with comma before "and")
            # Examples: create scope 'X', and create person 'Y'
            r'create\s+(?:a\s+)?(?:new\s+)?(.+?)\s+["\']([^"\']+)["\']\s*,\s*and\s+create\s+(?:a\s+)?(?:new\s+)?(.+?)\s+["\']([^"\']+)["\']',
        ]
        
        operations = []
        matched_pattern = None
        for i, pattern in enumerate(patterns, 1):
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                logger.info(f"[_detectMultipleCreates] Pattern {i} matched! Groups: {match.groups()}")
                matched_pattern = i
                
                # Special handling for Pattern 0: Add N objects to subtype1, and the other M add to subtype2
                if i == 1:
                    count1_str = match.group(1).strip()
                    obj_type_raw = match.group(2).strip()
                    subtype1 = match.group(3).strip()
                    count2_str = match.group(4).strip()
                    subtype2 = match.group(5).strip()
                    
                    try:
                        count1 = int(count1_str)
                        count2 = int(count2_str)
                    except ValueError:
                        logger.warning(f"[_detectMultipleCreates] Pattern 0 - Invalid counts: {count1_str}, {count2_str}")
                        continue
                    
                    # Normalize object type
                    if obj_type_raw.lower().endswith('s') and obj_type_raw.lower() != 'process':
                        obj_type = obj_type_raw[:-1]
                    elif obj_type_raw.lower() == 'people':
                        obj_type = 'person'
                    else:
                        obj_type = obj_type_raw
                    
                    obj_type_normalized = self._normalizeObjectType(obj_type)
                    if not obj_type_normalized:
                        continue
                    
                    # Normalize subtypes using existing logic
                    subtype1_normalized = self._normalizeSubtypeForObject(subtype1, obj_type_normalized)
                    subtype2_normalized = self._normalizeSubtypeForObject(subtype2, obj_type_normalized)
                    
                    # Create two bulk operations (UPDATE context)
                    operations.append({
                        'operation': 'update',
                        'objectType': obj_type_normalized,
                        'count': count1,
                        'subType': subtype1_normalized,
                        'isBulk': True
                    })
                    operations.append({
                        'operation': 'update',
                        'objectType': obj_type_normalized,
                        'count': count2,
                        'subType': subtype2_normalized,
                        'isBulk': True
                    })
                    
                    logger.info(f"[_detectMultipleCreates] ✅ Pattern 0: {count1} {obj_type_normalized} to {subtype1_normalized}, {count2} to {subtype2_normalized}")
                    return {'operations': operations}
                
                # Special handling for Pattern 1: create object X and create N objects of type Y for subtype Z
                elif i == 2:
                    # Pattern 1: groups are: obj_type1, name1, count, obj_type2, subtype_name
                    obj_type1_raw = match.group(1).strip()
                    name1 = match.group(2).strip()
                    count_str = match.group(3).strip()
                    obj_type2_raw = match.group(4).strip()
                    subtype_name = match.group(5).strip()
                    
                    try:
                        count = int(count_str)
                    except ValueError:
                        logger.warning(f"[_detectMultipleCreates] Pattern 1 - Invalid count: {count_str}")
                        continue
                    
                    logger.info(f"[_detectMultipleCreates] Pattern 1 - Extracted: obj_type1='{obj_type1_raw}', name1='{name1}', count={count}, obj_type2='{obj_type2_raw}', subtype='{subtype_name}'")
                    
                    # Extract object type (remove "a new" if present)
                    obj_type1 = re.sub(r'^(?:a\s+)?(?:new\s+)?', '', obj_type1_raw, flags=re.IGNORECASE).strip()
                    obj_type2 = re.sub(r'^(?:a\s+)?(?:new\s+)?', '', obj_type2_raw, flags=re.IGNORECASE).strip()
                    
                    # Normalize object types - handle singular/plural for obj_type2
                    # "person" or "persons" should become "person"
                    obj_type2 = re.sub(r'^\d+\s+', '', obj_type2, flags=re.IGNORECASE).strip()  # Remove leading number if any
                    if obj_type2.lower().endswith('s') and obj_type2.lower() not in ['process', 'processes']:
                        obj_type2 = obj_type2[:-1]  # Remove plural 's'
                    obj_type2 = re.sub(r'\s+for\s+.*$', '', obj_type2, flags=re.IGNORECASE).strip()
                    # Clean up any trailing words that shouldn't be there
                    obj_type2 = re.sub(r'\s+(for|to|with|the).*$', '', obj_type2, flags=re.IGNORECASE).strip()
                    
                    # Normalize object types
                    obj_type1_normalized = self._normalizeObjectType(obj_type1)
                    obj_type2_normalized = self._normalizeObjectType(obj_type2)
                    
                    logger.info(f"[_detectMultipleCreates] Pattern 1 - After normalization: obj_type1='{obj_type1_normalized}', obj_type2='{obj_type2_normalized}'")
                    
                    logger.info(f"[_detectMultipleCreates] Pattern 1 - Normalized: obj_type1='{obj_type1_normalized}', obj_type2='{obj_type2_normalized}'")
                    
                    if obj_type1_normalized:
                        # First operation: create the scope/object
                        operations.append({
                            'operation': 'create',
                            'objectType': obj_type1_normalized,
                            'objectName': name1,
                            'subType': None
                        })
                    
                    if obj_type2_normalized:
                        # Second operation: create N objects with subtype
                        # Normalize subtype name (e.g., "Datatypes" -> "Datatype", "Data protection officers" -> "Data protection officer")
                        subtype_normalized = subtype_name.strip()
                        
                        # CRITICAL: Check for "Data protection officer" FIRST (before normalization)
                        # This handles typos like "Data protection offiecer" and variations
                        subtype_lower_original = subtype_normalized.lower().strip()
                        
                        # Use "offic" to catch both "officer" and typos like "offiecer"
                        # Also check for "data protection" without spaces (handles "dataprotectionofficer")
                        subtype_no_spaces = subtype_lower_original.replace(' ', '').replace('-', '').replace('_', '')
                        
                        if ('data protection' in subtype_lower_original and 'offic' in subtype_lower_original) or \
                           ('dataprotection' in subtype_no_spaces and 'offic' in subtype_no_spaces):
                            # Normalize to "Data protection officer" regardless of typos or plural
                            subtype_normalized = 'Data protection officer'
                            logger.info(f"[_detectMultipleCreates] Pattern 1 - Detected Data protection officer (from: '{subtype_name}')")
                        elif 'dpo' in subtype_lower_original and len(subtype_normalized.strip()) <= 5:
                            # Handle standalone "DPO" abbreviation
                            subtype_normalized = 'Data protection officer'
                            logger.info(f"[_detectMultipleCreates] Pattern 1 - Detected DPO abbreviation (from: '{subtype_name}')")
                        else:
                            # Map common variations to correct subtype format
                            # This maps user-friendly names to the format expected by Verinice
                            subtype_mapping = {
                                # Asset subtypes
                                'datatype': 'Datatype',
                                'datatypes': 'Datatype',
                                'it-system': 'IT-System',
                                'itsystem': 'IT-System',
                                'it_system': 'IT-System',
                                'application': 'Application',
                                'applications': 'Application',
                                # Person subtypes
                                'data protection officer': 'Data protection officer',
                                'data protection officers': 'Data protection officer',
                                'dpo': 'Data protection officer',
                                'person': 'Person',
                                'persons': 'Person',
                            }
                            
                            if 'officer' in subtype_normalized.lower():
                                # Normalize to singular "officer" if plural
                                if subtype_normalized.lower().endswith('s') and 'officers' in subtype_normalized.lower():
                                    subtype_normalized = subtype_normalized.rstrip('s').strip()
                                    if not subtype_normalized.lower().endswith('officer'):
                                        subtype_normalized += ' officer'
                            
                            # Normalize for matching (remove spaces, hyphens, underscores, convert to lowercase)
                            subtype_lower = subtype_normalized.lower().replace('-', '').replace('_', '').replace(' ', '')
                            
                            if subtype_lower in subtype_mapping:
                                subtype_normalized = subtype_mapping[subtype_lower]
                            else:
                                # Try partial matching for multi-word subtypes
                                for key, value in subtype_mapping.items():
                                    if key in subtype_lower or subtype_lower in key:
                                        subtype_normalized = value
                                        break
                                else:
                                    # Fallback: remove plural if present (but keep multi-word and hyphenated as is)
                                    if subtype_normalized.lower().endswith('s') and not subtype_normalized.lower().endswith('ss'):
                                        # Only remove 's' if it's a simple word (not multi-word like "Data protection officers")
                                        if ' ' not in subtype_normalized and '-' not in subtype_normalized:
                                            subtype_normalized = subtype_normalized[:-1]
                        
                        logger.info(f"[_detectMultipleCreates] Pattern 1 - Final subtype: '{subtype_normalized}' (from input: '{subtype_name}')")
                        
                        for j in range(1, count + 1):
                            # Generate name based on object type and subtype
                            if obj_type2_normalized == 'person' and 'data protection' in subtype_normalized.lower():
                                auto_name = f"DPO-{j:02d}"
                            elif obj_type2_normalized == 'asset':
                                auto_name = f"{obj_type2_normalized.title()}-{subtype_normalized}-{j:02d}"
                            else:
                                auto_name = f"{obj_type2_normalized.title()}-{j:02d}"
                            
                            operations.append({
                                'operation': 'create',
                                'objectType': obj_type2_normalized,
                                'objectName': auto_name,
                                'subType': subtype_normalized
                            })
                    
                    if operations:
                        logger.info(f"[_detectMultipleCreates] Pattern 1 - Generated {len(operations)} operations (1 {obj_type1_normalized} + {count} {obj_type2_normalized} with subtype {subtype_normalized})")
                        return {'operations': operations}
                    else:
                        logger.warning(f"[_detectMultipleCreates] Pattern 1 - No operations generated")
                        continue
                
                # Pattern 2a: create object X and create object Y with subtype Z in our ISMS
                if i == 2 and len(match.groups()) >= 5:
                    obj_type1_raw = match.group(1).strip()
                    name1 = match.group(2).strip()
                    obj_type2_raw = match.group(3).strip()
                    name2 = match.group(4).strip()
                    subtype_name = match.group(5).strip()
                    
                    obj_type1 = re.sub(r'^(?:a\s+)?(?:new\s+)?', '', obj_type1_raw, flags=re.IGNORECASE).strip()
                    obj_type2 = re.sub(r'^(?:a\s+)?(?:new\s+)?', '', obj_type2_raw, flags=re.IGNORECASE).strip()
                    
                    obj_type1_normalized = self._normalizeObjectType(obj_type1)
                    obj_type2_normalized = self._normalizeObjectType(obj_type2)
                    
                    # Map subtype name to proper format
                    subtype_mapping = {
                        'it-system': 'IT-System',
                        'itsystem': 'IT-System',
                        'it_system': 'IT-System',
                        'datatype': 'Datatype',
                        'datatypes': 'Datatype',
                        'application': 'Application',
                        'applications': 'Application',
                    }
                    
                    subtype_normalized = subtype_name.strip()
                    subtype_lower = subtype_normalized.lower().replace('-', '').replace('_', '').replace(' ', '')
                    if subtype_lower in subtype_mapping:
                        subtype_normalized = subtype_mapping[subtype_lower]
                    else:
                        # Try partial matching
                        for key, value in subtype_mapping.items():
                            if key in subtype_lower or subtype_lower in key:
                                subtype_normalized = value
                                break
                    
                    if obj_type1_normalized and obj_type2_normalized:
                        operations.append({
                            'operation': 'create',
                            'objectType': obj_type1_normalized,
                            'objectName': name1,
                            'subType': None
                        })
                        operations.append({
                            'operation': 'create',
                            'objectType': obj_type2_normalized,
                            'objectName': name2,
                            'subType': subtype_normalized
                        })
                        
                        logger.info(f"[_detectMultipleCreates] Pattern 2a - Detected: {obj_type1_normalized} '{name1}' and {obj_type2_normalized} '{name2}' with subtype '{subtype_normalized}'")
                        return {'operations': operations}
                    else:
                        continue
                
                # Standard patterns (2-8): groups are: obj_type1, name1, obj_type2, name2
                # First create operation
                obj_type1_raw = match.group(1).strip()
                name1 = match.group(2).strip()
                
                # Second create operation
                obj_type2_raw = match.group(3).strip()
                name2 = match.group(4).strip()
                
                logger.info(f"[_detectMultipleCreates] Extracted: obj_type1='{obj_type1_raw}', name1='{name1}', obj_type2='{obj_type2_raw}', name2='{name2}'")
                
                # Extract object type (remove "a new" if present)
                obj_type1 = re.sub(r'^(?:a\s+)?(?:new\s+)?', '', obj_type1_raw, flags=re.IGNORECASE).strip()
                obj_type2 = re.sub(r'^(?:a\s+)?(?:new\s+)?', '', obj_type2_raw, flags=re.IGNORECASE).strip()
                
                logger.info(f"[_detectMultipleCreates] After cleanup: obj_type1='{obj_type1}', obj_type2='{obj_type2}'")
                
                # Normalize object types
                obj_type1_normalized = self._normalizeObjectType(obj_type1)
                obj_type2_normalized = self._normalizeObjectType(obj_type2)
                
                logger.info(f"[_detectMultipleCreates] Normalized types: obj_type1='{obj_type1_normalized}', obj_type2='{obj_type2_normalized}'")
                
                if obj_type1_normalized and obj_type2_normalized:
                    subtype1 = None
                    subtype2 = None
                    
                    if 'data protection officer' in obj_type1.lower() or 'dpo' in obj_type1.lower():
                        obj_type1_normalized = 'person'
                        subtype1 = 'Data protection officer'
                    elif 'controller' in obj_type1.lower():
                        obj_type1_normalized = 'scope'
                        subtype1 = 'Controller'
                    
                    if 'data protection officer' in obj_type2.lower() or 'dpo' in obj_type2.lower():
                        obj_type2_normalized = 'person'
                        subtype2 = 'Data protection officer'
                    elif 'controller' in obj_type2.lower():
                        obj_type2_normalized = 'scope'
                        subtype2 = 'Controller'
                    
                    operations.append({
                        'operation': 'create',
                        'objectType': obj_type1_normalized,
                        'objectName': name1,
                        'subType': subtype1
                    })
                    operations.append({
                        'operation': 'create',
                        'objectType': obj_type2_normalized,
                        'objectName': name2,
                        'subType': subtype2
                    })
                    
                    logger.info(f"[_detectMultipleCreates] ✅ Detected 2 create operations: {obj_type1_normalized} '{name1}' and {obj_type2_normalized} '{name2}'")
                    return {'operations': operations}
        
        return None
    
    def _normalizeSubtypeForObject(self, subtype: str, object_type: str) -> str:
        """Normalize subtype name for a given object type"""
        subtype_normalized = subtype.strip()
        subtype_lower = subtype_normalized.lower()
        
        # Handle DPO/Data protection officer first
        if 'data protection' in subtype_lower and 'offic' in subtype_lower:
            return 'Data protection officer'
        elif 'dpo' in subtype_lower and len(subtype_normalized.strip()) <= 5:
            return 'Data protection officer'
        
        # Map common variations
        subtype_mapping = {
            'datatype': 'Datatype',
            'datatypes': 'Datatype',
            'it-system': 'IT-System',
            'itsystem': 'IT-System',
            'it_system': 'IT-System',
            'application': 'Application',
            'applications': 'Application',
        }
        
        subtype_no_spaces = subtype_lower.replace(' ', '').replace('-', '').replace('_', '')
        if subtype_no_spaces in subtype_mapping:
            return subtype_mapping[subtype_no_spaces]
        
        for key, value in subtype_mapping.items():
            if key in subtype_no_spaces or subtype_no_spaces in key:
                return value
        
        # Fallback: capitalize first letter of each word
        return ' '.join(word.capitalize() for word in subtype_normalized.split())
    
    def _normalizeObjectType(self, obj_type: str) -> Optional[str]:
        """Normalize object type string to standard form"""
        obj_type_lower = obj_type.lower().strip()
        
        obj_type_lower = obj_type_lower.replace('new ', '').replace('a ', '').strip()
        
        # CRITICAL: Check for subtype indicators FIRST (before type mapping)
        # These are subtypes that need to be mapped to their base object type
        if 'data protection officer' in obj_type_lower or 'dpo' in obj_type_lower:
            return 'person'  # Will be handled as person with DPO subtype
        elif 'controller' in obj_type_lower:
            return 'scope'  # Will be handled as scope with Controller subtype
        
        # Map to standard types
        type_mapping = {
            'scope': 'scope',
            'scopes': 'scope',
            'asset': 'asset',
            'assets': 'asset',
            'control': 'control',
            'controls': 'control',
            'person': 'person',
            'persons': 'person',
            'people': 'person',
            'process': 'process',
            'processes': 'process',
            'document': 'document',
            'documents': 'document',
            'incident': 'incident',
            'incidents': 'incident',
            'scenario': 'scenario',
            'scenarios': 'scenario',
        }
        
        if obj_type_lower in type_mapping:
            return type_mapping[obj_type_lower]
        
        for key, value in type_mapping.items():
            if key in obj_type_lower:
                return value
        
        return None
    
    # ==================== FALLBACK ====================
    
    def _hasFallbackAnswer(self, message: str) -> bool:
        """Check if message has a fallback knowledge base answer"""
        messageLower = message.lower().strip()
        
        knowledgePatterns = [
            ('scope' in messageLower and 'asset' in messageLower and 
             ('difference' in messageLower or 'vs' in messageLower)),
            ('asset' in messageLower and ('what' in messageLower or 'explain' in messageLower)),
            ('scope' in messageLower and ('what' in messageLower or 'explain' in messageLower)),
            ('isms' in messageLower and ('what' in messageLower or 'explain' in messageLower)),
            ('create' in messageLower and 'scope' in messageLower and 
             ('how' in messageLower or 'do i' in messageLower)),
            # ISO 27001 questions
            ('iso' in messageLower and ('27001' in messageLower or '27002' in messageLower)),
            ('iso27001' in messageLower or 'iso 27001' in messageLower),
            # General knowledge questions that should go to ReasoningEngine
            (messageLower.startswith('what is') and not any(op in messageLower for op in ['create', 'list', 'get', 'update', 'delete', 'compare', 'analyze', 'link'])),
            (messageLower.startswith('what are') and not any(op in messageLower for op in ['create', 'list', 'get', 'update', 'delete', 'compare', 'analyze', 'link'])),
        ]
        
        return any(knowledgePatterns)
