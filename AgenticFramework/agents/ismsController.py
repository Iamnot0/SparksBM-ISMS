"""
ISMS Controller - Unified Entry Point for All ISMS Operations

Phase 5: Progressive Agentic Architecture (Tiered)

This controller implements a tiered architecture:
- Tier 1 (Fast Path): Simple CRUD operations - deterministic, fast, reliable
- Tier 2 (Agent Path): Multi-step operations - ReAct reasoning loop
- Tier 3 (Expert Path): Analysis & reconciliation - deep reasoning

Single entry point for frontend - routes internally based on complexity.
"""

import re
import logging
from typing import Dict, Any, Optional, Tuple, Callable

logger = logging.getLogger(__name__)


class ISMSController:
    """
    Unified ISMS Controller - Single entry point for all ISMS operations.
    
    Routes internally to:
    - ISMSFastPath: Simple CRUD (Tier 1)
    - ISMSAgent: Complex operations (Tier 2/3)
    
    Provides clean interface for frontend while maintaining reliability
    through tiered architecture.
    """
    
    def __init__(self, verinice_tool, llm_tool=None, event_callback: Optional[Callable] = None):
        """
        Initialize ISMS Controller.
        
        Args:
            verinice_tool: VeriniceTool instance for ISMS operations
            llm_tool: Optional LLMTool for agent reasoning
            event_callback: Optional callback for SSE event streaming
                Function(step_type, content, metadata)
        """
        self.verinice_tool = verinice_tool
        self.llm_tool = llm_tool
        self.event_callback = event_callback
        
        self._fast_path = None
        self._agent_path = None
        self._coordinator = None
        
        logger.info("ISMSController initialized")
    
    def execute(self, request: str, context: Dict = None) -> Dict:
        """
        Execute ISMS operation - single entry point.
        
        Args:
            request: User's ISMS operation request (natural language)
            context: Optional context dictionary (state, session info, etc.)
        
        Returns:
            Dict with operation result:
            {
                'status': 'success' | 'error',
                'result': str,  # Result message or error
                'data': dict,   # Optional operation data
                'tier': int,   # Which tier was used (1, 2, or 3)
                'mode': str    # 'fast_path' or 'agent_path'
            }
        """
        if context is None:
            context = {}
        
        # Detect tier with confidence scoring
        tier, confidence = self._detect_tier(request, context)
        
        # Emit tier decision event
        if self.event_callback:
            self.event_callback('tier_decision', {
                'tier': tier,
                'confidence': confidence,
                'request': request[:100] if len(request) > 100 else request
            })
        
        logger.info(f"ISMSController: Routing to Tier {tier} (confidence: {confidence:.2f})")
        
        # Route to appropriate path
        try:
            if tier == 1:
                # Fast Path - deterministic routing
                fast_path = self._get_fast_path()
                result = fast_path.execute(request, context)
                result['tier'] = 1
                result['mode'] = 'fast_path'
                return result
            elif tier == 2:
                # Agent Path - standard reasoning
                agent_path = self._get_agent_path()
                result = agent_path.execute(request, context, mode='standard')
                result['tier'] = 2
                result['mode'] = 'agent_path'
                return result
            else:  # tier == 3
                # Expert Path - deep reasoning
                agent_path = self._get_agent_path()
                result = agent_path.execute(request, context, mode='deep_reasoning')
                result['tier'] = 3
                result['mode'] = 'agent_path'
                return result
        except Exception as e:
            logger.error(f"ISMSController execution error: {e}", exc_info=True)
            return {
                'status': 'error',
                'result': f"ISMS operation failed: {str(e)}",
                'tier': tier,
                'mode': 'error'
            }
    
    def _detect_tier(self, request: str, context: Dict) -> Tuple[int, float]:
        """
        Detect which tier to use based on request complexity.
        
        Uses pattern matching and confidence scoring to determine:
        - Tier 1: Simple CRUD (list, get, simple create)
        - Tier 2: Multi-step operations
        - Tier 3: Analysis, reconciliation, complex queries
        
        Args:
            request: User's request
            context: Context dictionary
        
        Returns:
            Tuple of (tier, confidence) where:
            - tier: 1, 2, or 3
            - confidence: 0.0 to 1.0 (if < 0.8, defaults to Tier 1 for safety)
        """
        request_lower = request.lower().strip()
        
        # Tier 1 patterns (simple CRUD) - high confidence
        tier1_patterns = [
            r'^list\s+(scopes|assets|controls|processes|persons|scenarios|incidents|documents|domains|units)',
            r'^get\s+(scope|asset|control|process|person|scenario|incident|document)\s+',
            r'^show\s+(scope|asset|control|process|person|scenario|incident|document)\s+',
            r'^view\s+(scope|asset|control|process|person|scenario|incident|document)\s+',
            r'^display\s+(scope|asset|control|process|person|scenario|incident|document)\s+',
        ]
        
        for pattern in tier1_patterns:
            if re.match(pattern, request_lower):
                return (1, 0.95)  # High confidence for simple operations
        
        # Tier 3 patterns (complex analysis) - high confidence
        tier3_patterns = [
            r'compare|reconcile|difference|analyze|audit|gap\s+analysis',
            r'find\s+.*\s+with\s+.*\s+and\s+.*',
            r'find\s+.*\s+with\s+.*',  # "find X with Y" pattern
            r'all\s+.*\s+in\s+.*\s+domain',
            r'risk\s+assessment|compliance\s+check|security\s+audit',
            r'missing\s+\w+|anomalies|issues',  # "missing description", "anomalies", etc.
        ]
        
        for pattern in tier3_patterns:
            if re.search(pattern, request_lower):
                return (3, 0.85)  # High confidence for complex operations
        
        # Tier 2 indicators (multi-step operations)
        multi_step_indicators = ['and', 'then', 'after', 'also', 'next', 'follow', 'create.*link', 'link.*to']
        if any(re.search(indicator, request_lower) for indicator in multi_step_indicators):
            return (2, 0.75)  # Medium confidence for multi-step
        
        simple_create_pattern = r'^create\s+(scope|asset|control|process|person|scenario|incident|document)\s+[\w\s-]+$'
        if re.match(simple_create_pattern, request_lower):
            return (1, 0.90)  # High confidence for simple create
        
        simple_modify_pattern = r'^(update|delete|remove)\s+(scope|asset|control|process|person|scenario|incident|document)\s+[\w\s-]+$'
        if re.match(simple_modify_pattern, request_lower):
            return (1, 0.90)  # High confidence for simple modify
        
        # NOTE: Link/analyze operations will be handled by MCP Server (to be implemented)
        
        # Default: Use Tier 1 (safe fallback)
        # Low confidence means we default to deterministic path
        return (1, 0.6)  # Safe default - use fast path when uncertain
    
    def _get_fast_path(self):
        """Lazy initialize Fast Path."""
        if self._fast_path is None:
            from .ismsFastPath import ISMSFastPath
            coordinator = self._get_coordinator()
            self._fast_path = ISMSFastPath(coordinator, self.event_callback)
        return self._fast_path
    
    def _get_agent_path(self):
        """Lazy initialize Agent Path."""
        if self._agent_path is None:
            from .ismsAgent import ISMSAgent
            agent = ISMSAgent(
                verinice_tool=self.verinice_tool,
                llm_tool=self.llm_tool,
                event_callback=self.event_callback
            )
            # Tools are registered in ISMSAgent.__init__
            self._agent_path = agent
        return self._agent_path
    
    def _get_coordinator(self):
        """Lazy initialize ISMSCoordinator (used by Fast Path)."""
        if self._coordinator is None:
            from .coordinators.ismsCoordinator import ISMSCoordinator
            state = {}  # Coordinator will use state passed in context
            tools = {
                'veriniceTool': self.verinice_tool,
                'llmTool': self.llm_tool
            }
            self._coordinator = ISMSCoordinator(state, tools, None)
        return self._coordinator
