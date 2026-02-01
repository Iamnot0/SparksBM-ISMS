"""
MCP Server - LLM-based intent understanding and tool execution

Handles complex ISMS operations that require reasoning beyond pattern matching:
- Linking operations (link, unlink, connect, associate)
- Analysis operations (analyze, understand, assess)
- Natural language queries (complex questions)

Uses LLM for intent understanding, then executes appropriate tools.
"""

from typing import Dict, Any, Optional
import logging
import re
from datetime import datetime
from utils.promptVersioning import get_version_manager, register_prompt_version
from agents.instructions import get_error_message

logger = logging.getLogger(__name__)


class MCPServer:
    """
    MCP Server - Provides LLM-based intent understanding for complex ISMS operations.
    
    Architecture:
    1. Receives natural language request
    2. Uses LLM to understand intent and extract parameters
    3. Routes to appropriate tool
    4. Executes tool using VeriniceTool
    5. Returns formatted response
    
    This replaces pattern-based routing with intelligent understanding.
    """
    
    def __init__(self, llm_tool, verinice_tool, state: Dict = None):
        """
        Initialize MCP Server.
        
        Args:
            llm_tool: LLMTool instance for intent understanding
            verinice_tool: VeriniceTool instance for ISMS operations
            state: Agent state dictionary (for context)
        """
        self.llm_tool = llm_tool
        self.verinice_tool = verinice_tool
        self.state = state or {}
        
        # Register available tools
        self._tools = {}
        self._register_tools()
        
        self.version_manager = get_version_manager()
        self.current_prompt_version = None
        self._register_current_prompt()
        
        # Performance tracking
        self.operation_count = 0
        self.success_count = 0
        self.failure_count = 0
        
        logger.info("MCP Server initialized")
    
    def _register_tools(self):
        """Register all available MCP tools"""
        from .tools.linking import link_objects, unlink_objects
        from .tools.analyze import analyze_object
        from .tools.compare import compare_objects
        
        self._tools = {
            'link_objects': link_objects,
            'unlink_objects': unlink_objects,
            'analyze_object': analyze_object,
            'compare_objects': compare_objects,
        }
    
    def _register_current_prompt(self):
        """Register current prompt version for tracking"""
        try:
            prompt_text = self._build_intent_prompt("sample message")
            self.current_prompt_version = register_prompt_version(
                component="mcp_server",
                prompt_text=prompt_text,
                metadata={
                    "description": "MCP Server intent understanding prompt",
                    "features": ["negative_examples", "chain_of_thought", "parameter_validation"]
                }
            )
            logger.info(f"Registered MCP prompt version: {self.current_prompt_version.version}")
        except Exception as e:
            logger.warning(f"Failed to register prompt version: {e}")
    
    def execute(self, message: str, context: Dict = None) -> Dict:
        """
        Execute MCP operation - main entry point.
        
        Process:
        1. Use LLM to understand intent and extract parameters
        2. Route to appropriate tool
        3. Execute tool
        4. Return formatted response
        
        Args:
            message: User's natural language request
            context: Optional context (session data, etc.)
        
        Returns:
            Dict with response:
            {
                'type': 'success' | 'error',
                'text': str,  # Response message
                'data': dict  # Optional operation results
            }
        """
        try:
            # Track operation
            self.operation_count += 1
            
            # Step 1: Understand intent using LLM
            intent_result = self._understand_intent(message, context)
            
            if not intent_result.get('success'):
                self.failure_count += 1
                self._track_performance(False, message, intent_result.get('error'))
                return self._error(intent_result.get('error', get_error_message('mcp', 'intent_understanding_failed')))
            
            tool_name = intent_result.get('tool')
            tool_params = intent_result.get('params', {})
            
            # Step 2: Get tool
            if not tool_name:
                # LLM could not confidently select a tool - treat as unsupported MCP operation
                self.failure_count += 1
                self._track_performance(False, message, "No MCP tool selected")
                return self._error(get_error_message('mcp', 'could_not_route'))
            
            # CRITICAL: Handle create_and_link as a special two-step operation
            if tool_name == 'create_and_link':
                return self._handle_create_and_link(tool_params, message)
            
            tool_func = self._tools.get(tool_name)
            if not tool_func:
                return self._error(get_error_message('mcp', 'tool_not_found', toolName=tool_name, availableTools=', '.join(list(self._tools.keys()))))
            
            # Step 3: Execute tool
            logger.info(f"MCP executing tool: {tool_name} with params: {tool_params}")
            
            # Prepare tool arguments based on tool signature
            if tool_name == 'analyze_object':
                tool_result = tool_func(
                    object_name=tool_params.get('object_name'),
                    object_type=tool_params.get('object_type'),
                    verinice_tool=self.verinice_tool,
                    llm_tool=self.llm_tool,
                    state=self.state
                )
            elif tool_name == 'compare_objects':
                # FIX: Properly map parameters for comparison operations
                # Also handle cases where only one object is specified (should be an error, but handle gracefully)
                object1_name = tool_params.get('object1_name') or tool_params.get('object_name')
                object2_name = tool_params.get('object2_name')
                object1_type = tool_params.get('object1_type') or tool_params.get('object_type')
                object2_type = tool_params.get('object2_type')
                
                if not object1_name or not object2_name:
                    return self._error(get_error_message('validation', 'comparison_requires_two'))
                
                tool_result = tool_func(
                    object1_name=object1_name,
                    object2_name=object2_name,
                    object1_type=object1_type,
                    object2_type=object2_type,
                    verinice_tool=self.verinice_tool,
                    llm_tool=self.llm_tool,
                    state=self.state
                )
            else:
                # For link/unlink tools - only pass expected parameters
                # Filter out invalid parameters (like object_name) that don't belong to linking operations
                # Explicitly build valid_params dict with only allowed keys
                allowed_keys = ['source_type', 'source_name', 'target_type', 'target_name', 'subtype', 'domain_id']
                valid_params = {}
                for key in allowed_keys:
                    if key in tool_params and tool_params[key] is not None:
                        valid_params[key] = tool_params[key]
                
                # CRITICAL: Detect subtype-based linking
                # If target_name looks like a subtype (Datatype, IT-System, etc.) and target_type is "asset",
                # convert to subtype parameter instead
                if tool_name == 'link_objects' and valid_params.get('target_type') == 'asset' and valid_params.get('target_name'):
                    target_name = valid_params.get('target_name', '')
                    common_subtypes = ['IT-System', 'IT System', 'Datatype', 'Data Type', 'DataType', 'Application', 'Process', 'Service', 'Building']
                    target_lower = target_name.lower().strip()
                    for subtype in common_subtypes:
                        subtype_lower = subtype.lower().replace('-', '').replace('_', '').replace(' ', '')
                        target_normalized = target_lower.replace('-', '').replace('_', '').replace(' ', '')
                        if subtype_lower == target_normalized or subtype_lower in target_normalized or target_normalized in subtype_lower:
                            # It's a subtype, not an object name
                            valid_params['subtype'] = subtype
                            valid_params['target_name'] = None  # Clear target_name for bulk linking
                            logger.info(f"Detected subtype-based linking: {subtype} assets")
                            break
                
                # Log for debugging
                if 'object_name' in tool_params or 'object_type' in tool_params:
                    logger.warning(f"Removed invalid parameters (object_name/object_type) from {tool_name} call")
                
                tool_result = tool_func(
                    verinice_tool=self.verinice_tool,
                    state=self.state,
                    **valid_params
                )
            
            # Step 4: Format response and track performance
            if tool_result.get('success'):
                self.success_count += 1
                self._track_performance(True, message, tool_name)
                # - link/unlink tools return 'message'
                # - analyze_object returns 'text'
                response_message = tool_result.get('message') or tool_result.get('text') or 'Operation completed successfully'
                return self._success(
                    response_message,
                    tool_result.get('data')
                )
            else:
                self.failure_count += 1
                self._track_performance(False, message, tool_result.get('error') or tool_result.get('text'))
                # - Some tools return 'error' as string
                # - Some tools return 'text' with error message
                error_message = tool_result.get('error') or tool_result.get('text') or 'Tool execution failed'
                return self._error(error_message)
                
        except Exception as e:
            self.failure_count += 1
            self._track_performance(False, message, str(e))
            logger.error(f"MCP execution error: {e}", exc_info=True)
            return self._error(get_error_message('mcp', 'execution_failed', error=str(e)))
    
    def _track_performance(self, success: bool, message: str, details: str = ""):
        """Track performance metrics for prompt evaluation"""
        try:
            # Calculate success rate
            if self.operation_count > 0:
                success_rate = self.success_count / self.operation_count
                
                # Log every 10 operations or on failures
                if self.operation_count % 10 == 0 or not success:
                    logger.info(f"MCP Performance: {self.success_count}/{self.operation_count} successful ({success_rate:.1%})")
                    
                    if self.current_prompt_version:
                        # Store in state for periodic evaluation
                        if '_mcp_performance' not in self.state:
                            self.state['_mcp_performance'] = {
                                'operation_count': 0,
                                'success_count': 0,
                                'failure_count': 0,
                                'last_updated': None
                            }
                        
                        self.state['_mcp_performance'].update({
                            'operation_count': self.operation_count,
                            'success_count': self.success_count,
                            'failure_count': self.failure_count,
                            'last_updated': datetime.now().isoformat()
                        })
        except Exception as e:
            logger.warning(f"Failed to track performance: {e}")
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        success_rate = self.success_count / self.operation_count if self.operation_count > 0 else 0.0
        return {
            'operation_count': self.operation_count,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'success_rate': success_rate,
            'prompt_version': self.current_prompt_version.version if self.current_prompt_version else None
        }
    
    def _understand_intent(self, message: str, context: Dict = None) -> Dict:
        """
        Use LLM to understand user intent and extract parameters.
        Falls back to pattern matching if API quota is exceeded.
        
        Args:
            message: User's message
            context: Optional context
        
        Returns:
            Dict with:
            {
                'success': bool,
                'tool': str,  # Tool name to execute
                'params': dict  # Tool parameters
            }
        """
        if not self.llm_tool:
            # No LLM available - use fallback immediately
            logger.info("LLM tool not available, using fallback pattern matching")
            return self._fallback_pattern_matching(message)
        
        # Build prompt for intent understanding
        prompt = self._build_intent_prompt(message, context)
        
        try:
            # Use LLM to understand intent with JSON mode for structured output
            response = self.llm_tool.generate(
                prompt=prompt,
                systemPrompt=self._get_system_prompt(),
                maxTokens=500,
                response_format="json_object"
            )
            
            # Parse LLM response to extract tool and parameters
            parsed = self._parse_llm_response(response, message)
            return parsed
            
        except Exception as e:
            error_msg = str(e).lower()
            is_quota_error = (
                'quota' in error_msg or 
                '429' in str(e) or 
                'rate limit' in error_msg or 
                'exhausted' in error_msg or
                'service limit' in error_msg
            )
            
            if is_quota_error:
                # API quota exceeded - use fallback pattern matching
                logger.info(f"API quota exceeded, using fallback pattern matching for: {message[:50]}")
                fallback_result = self._fallback_pattern_matching(message)
                if fallback_result.get('success'):
                    return fallback_result
                # If fallback also fails, return error
                return {
                    'success': False, 
                    'error': get_error_message('mcp', 'api_quota_exceeded')
                }
            
            logger.error(f"Intent understanding failed: {e}")
            return {'success': False, 'error': get_error_message('mcp', 'intent_understanding_failed_detailed', error=str(e))}
    
    def _build_intent_prompt(self, message: str, context: Dict = None) -> str:
        """Build prompt for LLM intent understanding - handles ANY format including typos, incomplete sentences, long sentences"""
        prompt = f"""You are an expert at understanding ISMS operation requests in natural language, even with typos, incomplete sentences, or long explanations.

User Request: "{message}"

REASONING REQUIREMENT:
Before extracting parameters, think through:
1. What is the user's primary intent? (link, unlink, analyze, compare, or list operation that should be rejected)
2. What tool matches this intent? (link_objects, unlink_objects, analyze_object, compare_objects, or null for list operations)
3. What parameters can I extract from the message?
4. What parameters are missing or ambiguous?
5. How should I handle typos/edge cases?

CRITICAL: Extract intent from ANY format:
- Typos are OK: "link Deskop to SCOPE1" → understand as "Desktop"
- Incomplete sentences: "link Desktop" → infer missing parts if possible, or ask for clarification
- Long explanations: "I need to link my Desktop computer which is an IT-System asset to the SCOPE1 scope" → extract: link Desktop to SCOPE1
- Bidirectional: "link SCOPE1 to Desktop" OR "link Desktop to SCOPE1" → both mean the same (link Desktop asset to SCOPE1 scope)
- Mixed word order: "Desktop link SCOPE1" → understand as link Desktop to SCOPE1
- Missing words: "Desktop SCOPE1" → infer "link Desktop to SCOPE1"

Available Tools:
1. link_objects - Link ISMS objects together
   - Works bidirectionally: "link X to Y" = "link Y to X" (system auto-detects scope vs object)
   - Supports: scope ↔ asset, scope ↔ person, scope ↔ process, scope ↔ control, scope ↔ scenario, scope ↔ document
   - Supports subtypes: "link SCOPE1 with IT-System assets" links all IT-System subtype assets
   - CRITICAL: If target_name looks like a subtype (e.g., "Datatype", "IT-System") and target_type is "asset", use subtype parameter instead
   - Parameters:
     * source_type: Type (scope, asset, person, process, control, scenario, document)
     * source_name: Name or ID
     * target_type: Type
     * target_name: Name/ID (null for bulk by subtype)
     * subtype: Optional subtype filter (e.g., "IT-System", "Datatype", "AST_IT-System")

2. unlink_objects - Remove links
   - Parameters: source_type, source_name, target_type, target_name

3. analyze_object - Analyze ISMS objects comprehensively
   - Provides detailed analysis of objects (scopes, assets, controls, etc.)
   - Parameters:
     * object_name: Name or ID of the object to analyze
     * object_type: Type of object (scope, asset, control, etc.) - optional, auto-detected if not provided

4. compare_objects - Compare two ISMS objects
   - Compares two objects of the same type and identifies differences
   - Parameters:
     * object1_name: Name or ID of first object
     * object2_name: Name or ID of second object
     * object1_type: Type of first object (optional, auto-detected)
     * object2_type: Type of second object (optional, auto-detected)
   - Note: Both objects must be the same type for comparison

Examples (handle ALL these formats):

LINKING OPERATIONS:
- "link Desktop to SCOPE1" → link_objects, source_type: "asset", source_name: "Desktop", target_type: "scope", target_name: "SCOPE1"
- "link SCOPE1 to Desktop" → link_objects, source_type: "scope", source_name: "SCOPE1", target_type: "asset", target_name: "Desktop" (bidirectional - same result)
- "connect Desktop with SCOPE1" → link_objects, source_type: "asset", source_name: "Desktop", target_type: "scope", target_name: "SCOPE1"
- "associate Desktop asset to SCOPE1 scope" → link_objects, source_type: "asset", source_name: "Desktop", target_type: "scope", target_name: "SCOPE1"
- "I want to connect my Desktop computer asset to the SCOPE1 scope" → link_objects, source_type: "asset", source_name: "Desktop", target_type: "scope", target_name: "SCOPE1"
- "please link the Desktop to SCOPE1" → link_objects, source_type: "asset", source_name: "Desktop", target_type: "scope", target_name: "SCOPE1"
- "can you link Desktop to SCOPE1?" → link_objects, source_type: "asset", source_name: "Desktop", target_type: "scope", target_name: "SCOPE1"
- "Desktop SCOPE1" (missing verb) → link_objects, source_type: "asset", source_name: "Desktop", target_type: "scope", target_name: "SCOPE1"
- "Deskop SCOPE1" (typo) → link_objects, source_type: "asset", source_name: "Desktop", target_type: "scope", target_name: "SCOPE1"
- "link SCOPE1 with IT-System assets" → link_objects, source_type: "scope", source_name: "SCOPE1", target_type: "asset", subtype: "IT-System"
- "link all IT-System assets to SCOPE1" → link_objects, source_type: "scope", source_name: "SCOPE1", target_type: "asset", subtype: "IT-System"
- "connect SCOPE1 to all IT-System type assets" → link_objects, source_type: "scope", source_name: "SCOPE1", target_type: "asset", subtype: "IT-System"
- "link Datatype assets to SCOPE1" → link_objects, source_type: "scope", source_name: "SCOPE1", target_type: "asset", subtype: "Datatype"
- "link SCOPE1 with Datatype assets" → link_objects, source_type: "scope", source_name: "SCOPE1", target_type: "asset", subtype: "Datatype"
- "i am data protection officer, link Datatype assets to SCOPE1" → link_objects, source_type: "scope", source_name: "SCOPE1", target_type: "asset", subtype: "Datatype"
- "link John Doe person to SCOPE1" → link_objects, source_type: "person", source_name: "John Doe", target_type: "scope", target_name: "SCOPE1"
- "associate control A.8.1.1 with SCOPE1" → link_objects, source_type: "control", source_name: "A.8.1.1", target_type: "scope", target_name: "SCOPE1"

UNLINKING OPERATIONS:
- "unlink Desktop from SCOPE1" → unlink_objects, source_type: "asset", source_name: "Desktop", target_type: "scope", target_name: "SCOPE1"
- "remove Desktop from SCOPE1" → unlink_objects, source_type: "asset", source_name: "Desktop", target_type: "scope", target_name: "SCOPE1"
- "disconnect Desktop and SCOPE1" → unlink_objects, source_type: "asset", source_name: "Desktop", target_type: "scope", target_name: "SCOPE1"
- "unlink SCOPE1 from Desktop" → unlink_objects, source_type: "scope", source_name: "SCOPE1", target_type: "asset", target_name: "Desktop"

ANALYSIS OPERATIONS:
- "analyze SCOPE1" → analyze_object, object_name: "SCOPE1", object_type: "scope"
- "analyze the SCOPE1" → analyze_object, object_name: "SCOPE1", object_type: "scope"
- "analyze SCOPE1 scope" → analyze_object, object_name: "SCOPE1", object_type: "scope"
- "I am data protection officer, analyze SCOPE1" → analyze_object, object_name: "SCOPE1", object_type: "scope"
- "can you analyze SCOPE1 for me?" → analyze_object, object_name: "SCOPE1", object_type: "scope"
- "please analyze SCOPE1" → analyze_object, object_name: "SCOPE1", object_type: "scope"
- "understand SCOPE1" → analyze_object, object_name: "SCOPE1", object_type: "scope"
- "what is SCOPE1?" → analyze_object, object_name: "SCOPE1", object_type: "scope"
- "tell me about SCOPE1" → analyze_object, object_name: "SCOPE1", object_type: "scope"
- "assess Desktop asset" → analyze_object, object_name: "Desktop", object_type: "asset"
- "analyze the Desktop asset" → analyze_object, object_name: "Desktop", object_type: "asset"
- "what can you tell me about Desktop?" → analyze_object, object_name: "Desktop", object_type: "asset"
- "review control A.8.1.1" → analyze_object, object_name: "A.8.1.1", object_type: "control"
- "analyze control A.8.1.1" → analyze_object, object_name: "A.8.1.1", object_type: "control"
- "what is linked with SCOPE1" → analyze_object, object_name: "SCOPE1", object_type: "scope"
- "what is linked with SCOPE1 analyze on it" → analyze_object, object_name: "SCOPE1", object_type: "scope"
- "what is linked to SCOPE1" → analyze_object, object_name: "SCOPE1", object_type: "scope"
- "show me what is linked with SCOPE1" → analyze_object, object_name: "SCOPE1", object_type: "scope"

COMPARISON OPERATIONS:
- "compare SCOPE1 and SCOPE2" → compare_objects, object1_name: "SCOPE1", object2_name: "SCOPE2"
- "compare SCOPE1 vs SCOPE2" → compare_objects, object1_name: "SCOPE1", object2_name: "SCOPE2"
- "compare IT-System assets with DataType assets" → compare_objects, object1_name: "IT-System", object2_name: "DataType", object1_type: "asset", object2_type: "asset"
- "compare IT-System asset and DataType asset" → compare_objects, object1_name: "IT-System", object2_name: "DataType", object1_type: "asset", object2_type: "asset"
- "what are the differences between SCOPE1 and SCOPE2?" → compare_objects, object1_name: "SCOPE1", object2_name: "SCOPE2"
- "show me differences between IT-System and DataType assets" → compare_objects, object1_name: "IT-System", object2_name: "DataType", object1_type: "asset", object2_type: "asset"
- "compare Desktop and Laptop assets" → compare_objects, object1_name: "Desktop", object2_name: "Laptop", object1_type: "asset", object2_type: "asset"
- "can you compare SCOPE1 with SCOPE2?" → compare_objects, object1_name: "SCOPE1", object2_name: "SCOPE2"

REPORT OPERATIONS (use compare_objects):
- "compare reports" → compare_objects (if objects are reports/documents)
- "show me comparison report" → compare_objects (extract objects from context)
- "generate comparison report for SCOPE1 and SCOPE2" → compare_objects, object1_name: "SCOPE1", object2_name: "SCOPE2"
- "compare reports for IT-System and DataType assets" → compare_objects, object1_name: "IT-System", object2_name: "DataType", object1_type: "asset", object2_type: "asset"

BAD EXAMPLES (what NOT to do):
- "compare SCOPE1 and SCOPE2" → ❌ WRONG: {{"tool": "compare_objects", "params": {{"object_name": "SCOPE1"}}}} (missing object2_name, wrong parameter name)
  ✅ CORRECT: {{"tool": "compare_objects", "params": {{"object1_name": "SCOPE1", "object2_name": "SCOPE2"}}}}
- "analyze SCOPE1" → ❌ WRONG: {{"tool": "analyze_object", "params": {{"object1_name": "SCOPE1"}}}} (wrong parameter name for analyze)
  ✅ CORRECT: {{"tool": "analyze_object", "params": {{"object_name": "SCOPE1"}}}}
- "link Desktop to SCOPE1" → ❌ WRONG: {{"tool": "link_objects", "params": {{"object_name": "Desktop"}}}} (wrong parameters for linking)
  ✅ CORRECT: {{"tool": "link_objects", "params": {{"source_name": "Desktop", "target_name": "SCOPE1"}}}}
- "show me the scopes" → ❌ WRONG: This should NOT be routed to MCP (it's a list operation, handled by Verinice)
  ✅ CORRECT: Return null/None - let router handle it as Verinice list operation

IMPORTANT RULES:
1. Auto-detect scope vs object: If one is "scope" and other is not, scope is always the container
2. Handle typos: Use context to correct (e.g., "Deskop" → "Desktop", "SCOPE" → "SCOPE1")
3. Extract from long sentences: Find the core operation, ignore filler words
4. Bidirectional linking: "X to Y" and "Y to X" are equivalent for linking
5. If unclear, extract what you can and let the system handle resolution
6. CRITICAL: Use correct parameter names for each tool:
   - compare_objects: object1_name, object2_name (NEVER object_name)
   - analyze_object: object_name (NEVER object1_name or object2_name)
   - link_objects/unlink_objects: source_name, target_name (NEVER object_name)
7. List operations (show me, list, display) should NOT be handled by MCP - return null

CRITICAL PARAMETER RULES:
- For compare_objects: ALWAYS use object1_name and object2_name (NEVER use object_name)
- For analyze_object: ALWAYS use object_name (NEVER use object1_name or object2_name)
- For link_objects/unlink_objects: Use source_name, target_name, source_type, target_type (NEVER use object_name)

OUTPUT FORMAT (respond ONLY with valid JSON, no explanations, no markdown):
{{
    "reasoning": "Brief explanation of your reasoning: intent identified, tool selected, parameters extracted, any edge cases handled",
    "tool": "tool_name",
    "params": {{
        "source_type": "...",     // For link/unlink ONLY
        "source_name": "...",      // For link/unlink ONLY
        "target_type": "...",      // For link/unlink ONLY
        "target_name": "...",      // For link/unlink ONLY
        "subtype": "...",          // For link/unlink ONLY
        "object_name": "...",      // For analyze_object ONLY
        "object_type": "...",      // For analyze_object ONLY (optional)
        "object1_name": "...",     // For compare_objects ONLY
        "object2_name": "...",     // For compare_objects ONLY
        "object1_type": "...",     // For compare_objects ONLY (optional)
        "object2_type": "..."      // For compare_objects ONLY (optional)
    }}
}}
"""
        return prompt
    
    def _get_system_prompt(self) -> str:
        """Get system prompt for intent understanding"""
        return """You are an expert at understanding ISMS operation requests in natural language.

Your job:
1. Understand intent from ANY format (typos, incomplete sentences, long explanations)
2. Extract which tool to use
3. Extract parameters (object names, types, subtypes)
4. Handle bidirectional operations (X to Y = Y to X for linking)
5. Correct typos using context
6. Extract core operation from long sentences

CRITICAL:
- Be tolerant of typos and variations
- Support bidirectional linking (scope ↔ object)
- Extract exact object names even with typos
- Return ONLY valid JSON, no explanations, no markdown code blocks"""
    
    def _parse_llm_response(self, llm_response: str, original_message: str) -> Dict:
        """
        Parse LLM response to extract tool and parameters.
        
        With JSON mode enabled, response should be clean JSON.
        Falls back to regex extraction for compatibility.
        """
        import json
        
        # Pattern 1: Try parsing entire response as JSON (JSON mode should return clean JSON)
        try:
            parsed = json.loads(llm_response.strip())
            # Extract reasoning if present (for debugging/performance tracking)
            reasoning = parsed.get('reasoning', '')
            if reasoning:
                logger.debug(f"MCP reasoning: {reasoning}")
            return {
                'success': True,
                'tool': parsed.get('tool'),
                'params': parsed.get('params', {}),
                'reasoning': reasoning
            }
        except json.JSONDecodeError:
            pass
        
        # Pattern 2: JSON in markdown code block (fallback for non-JSON mode)
        json_match = re.search(r'```json\s*\n(.*?)\n```', llm_response, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group(1))
                return {'success': True, 'tool': parsed.get('tool'), 'params': parsed.get('params', {})}
            except json.JSONDecodeError:
                pass
        
        # Pattern 3: JSON object directly in response (fallback)
        json_match = re.search(r'\{[^{}]*"tool"[^{}]*\}', llm_response, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group(0))
                return {'success': True, 'tool': parsed.get('tool'), 'params': parsed.get('params', {})}
            except json.JSONDecodeError:
                pass
        
        # Fallback: Use simple pattern matching if LLM fails
        logger.warning(f"LLM response parsing failed, using fallback pattern matching: {llm_response[:200]}")
        return self._fallback_pattern_matching(original_message)
    
    def _fallback_pattern_matching(self, message: str) -> Dict:
        """
        Fallback pattern matching if LLM parsing fails or API quota is exceeded.
        
        Supports friendly linking patterns without requiring "link" keyword.
        This provides basic functionality even if LLM is unavailable.
        """
        message_lower = message.lower().strip()
        original_message = message  # Preserve original for case-sensitive name extraction
        
        # ========== FRIENDLY LINKING PATTERNS (without "link" keyword) ==========
        
        # Pattern 1: "make X part of Y"
        pattern = r'make\s+([A-Za-z0-9_\s-]+?)\s+part\s+of\s+([A-Za-z0-9_\s-]+)'
        match = re.search(pattern, message_lower)
        if match:
            source = self._extract_object_name(original_message, match.start(1), match.end(1))
            target = self._extract_object_name(original_message, match.start(2), match.end(2))
            return self._build_link_params(source, target)
        
        # Pattern 2: "add X to Y"
        pattern = r'add\s+([A-Za-z0-9_\s-]+?)\s+to\s+([A-Za-z0-9_\s-]+)'
        match = re.search(pattern, message_lower)
        if match:
            source = self._extract_object_name(original_message, match.start(1), match.end(1))
            target = self._extract_object_name(original_message, match.start(2), match.end(2))
            return self._build_link_params(source, target)
        
        # Pattern 3: "put X in Y"
        pattern = r'put\s+([A-Za-z0-9_\s-]+?)\s+in\s+([A-Za-z0-9_\s-]+)'
        match = re.search(pattern, message_lower)
        if match:
            source = self._extract_object_name(original_message, match.start(1), match.end(1))
            target = self._extract_object_name(original_message, match.start(2), match.end(2))
            return self._build_link_params(source, target)
        
        # Pattern 4: "assign X to Y"
        pattern = r'assign\s+([A-Za-z0-9_\s-]+?)\s+to\s+([A-Za-z0-9_\s-]+)'
        match = re.search(pattern, message_lower)
        if match:
            source = self._extract_object_name(original_message, match.start(1), match.end(1))
            target = self._extract_object_name(original_message, match.start(2), match.end(2))
            return self._build_link_params(source, target)
        
        # Pattern 5: "X belongs to Y"
        pattern = r'([A-Za-z0-9_\s-]+?)\s+belongs\s+to\s+([A-Za-z0-9_\s-]+)'
        match = re.search(pattern, message_lower)
        if match:
            source = self._extract_object_name(original_message, match.start(1), match.end(1))
            target = self._extract_object_name(original_message, match.start(2), match.end(2))
            return self._build_link_params(source, target)
        
        # Pattern 6: "X is part of Y"
        pattern = r'([A-Za-z0-9_\s-]+?)\s+is\s+part\s+of\s+([A-Za-z0-9_\s-]+)'
        match = re.search(pattern, message_lower)
        if match:
            source = self._extract_object_name(original_message, match.start(1), match.end(1))
            target = self._extract_object_name(original_message, match.start(2), match.end(2))
            return self._build_link_params(source, target)
        
        # Pattern 7: "X should be in Y"
        pattern = r'([A-Za-z0-9_\s-]+?)\s+should\s+be\s+in\s+([A-Za-z0-9_\s-]+)'
        match = re.search(pattern, message_lower)
        if match:
            source = self._extract_object_name(original_message, match.start(1), match.end(1))
            target = self._extract_object_name(original_message, match.start(2), match.end(2))
            return self._build_link_params(source, target)
        
        # Pattern 8: "include X in Y"
        pattern = r'include\s+([A-Za-z0-9_\s-]+?)\s+in\s+([A-Za-z0-9_\s-]+)'
        match = re.search(pattern, message_lower)
        if match:
            source = self._extract_object_name(original_message, match.start(1), match.end(1))
            target = self._extract_object_name(original_message, match.start(2), match.end(2))
            return self._build_link_params(source, target)
        
        # Pattern 9: "I want X to be in Y" or "I need X linked to Y"
        pattern = r'(?:i\s+(?:want|need)\s+)?([A-Za-z0-9_\s-]+?)\s+(?:to\s+be\s+in|linked\s+to)\s+([A-Za-z0-9_\s-]+)'
        match = re.search(pattern, message_lower)
        if match:
            source = self._extract_object_name(original_message, match.start(1), match.end(1))
            target = self._extract_object_name(original_message, match.start(2), match.end(2))
            return self._build_link_params(source, target)
        
        # Pattern 10: Two object names without explicit linking word (e.g., "Desktop SCOPE1")
        # Only if message is short and has two capitalized words or alphanumeric identifiers
        if len(message.split()) <= 5:  # Short message
            # Look for two potential object names (capitalized words or alphanumeric with underscores)
            object_pattern = r'\b([A-Z][A-Za-z0-9_]+)\b'
            matches = list(re.finditer(object_pattern, message))
            if len(matches) >= 2:
                # Take last two matches as source and target
                source = matches[-2].group(1)
                target = matches[-1].group(1)
                return self._build_link_params(source, target)
        
        # ========== TRADITIONAL LINKING PATTERNS ==========
        
        # Detect link operations with explicit keywords
        if 'link' in message_lower or 'connect' in message_lower or 'associate' in message_lower:
            # Pattern: "link X to Y" or "link X with Y"
            link_patterns = [
                r'(?:link|connect|associate)\s+["\']?([^"\',\s]+)["\']?\s+(?:to|with)\s+["\']?([^"\',\s]+)["\']?',  # Quoted or unquoted
                r'(?:link|connect|associate)\s+([A-Za-z0-9_\s-]+?)\s+(?:to|with)\s+([A-Za-z0-9_\s-]+)',  # Original pattern
            ]
            
            for link_pattern in link_patterns:
                match = re.search(link_pattern, message, re.IGNORECASE)
                if match:
                    source = self._extract_object_name(original_message, match.start(1), match.end(1))
                    target = self._extract_object_name(original_message, match.start(2), match.end(2))
                    # Skip if source is a pronoun (should have been resolved already, but handle gracefully)
                    if source.lower() in ['it', 'him', 'her', 'this', 'that']:
                        # Try to extract from context or skip this pattern
                        continue
                    return self._build_link_params(source, target)
        
        # ========== ANALYZE OPERATIONS ==========
        
        # Detect analyze operations (must come before link to avoid misrouting)
        analysis_keywords = ['analyze', 'analysis', 'understand', 'assess', 'evaluate', 'examine', 'review']
        analysis_typos = ['ananlyze', 'analzye', 'anaylze', 'analze', 'anlyze', 'anlyse', 'analise']
        has_analysis = any(keyword in message_lower for keyword in analysis_keywords) or \
                      any(typo in message_lower for typo in analysis_typos)
        
        if has_analysis:
            # Extract object name (usually after "analyze" keyword)
            # Pattern: "analyze X" or "analyze X scope" or "analyze the X"
            analyze_patterns = [
                r'(?:analyze|analysis|understand|assess|evaluate|examine|review)\s+(?:the\s+)?([A-Za-z0-9_\s-]+?)(?:\s+(?:scope|asset|control|process|person|document|incident|scenario))?\s*$',
                r'(?:analyze|analysis|understand|assess|evaluate|examine|review)\s+([A-Za-z0-9_\s-]+?)(?:\s+(?:scope|asset|control|process|person|document|incident|scenario))?\s*$',
            ]
            for pattern in analyze_patterns:
                match = re.search(pattern, message_lower)
                if match:
                    obj_name = self._extract_object_name(original_message, match.start(1), match.end(1))
                    obj_name = re.sub(r'\s+(scope|asset|control|process|person|document|incident|scenario)$', '', obj_name, flags=re.IGNORECASE).strip()
                    if obj_name:
                        return {
                            'success': True,
                            'tool': 'analyze_object',
                            'params': {
                                'object_name': obj_name.strip()
                            }
                        }
        
        # ========== COMPARE OPERATIONS ==========
        
        # Detect compare operations
        comparison_keywords = ['compare', 'comparison', 'difference', 'differences', 'vs', 'versus']
        has_comparison = any(keyword in message_lower for keyword in comparison_keywords)
        
        if has_comparison:
            # Extract two object names
            # Patterns: "compare X and Y", "compare X vs Y", "X vs Y", "compare X with Y"
            compare_patterns = [
                r'compare\s+([A-Za-z0-9_\s-]+?)\s+(?:and|with|vs|versus)\s+([A-Za-z0-9_\s-]+)',
                r'([A-Za-z0-9_\s-]+?)\s+vs\s+([A-Za-z0-9_\s-]+)',
                r'([A-Za-z0-9_\s-]+?)\s+versus\s+([A-Za-z0-9_\s-]+)',
                r'difference\s+between\s+([A-Za-z0-9_\s-]+?)\s+(?:and|with|vs|versus)\s+([A-Za-z0-9_\s-]+)',
            ]
            
            for pattern in compare_patterns:
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    obj1 = self._extract_object_name(original_message, match.start(1), match.end(1))
                    obj2 = self._extract_object_name(original_message, match.start(2), match.end(2))
                    obj1 = re.sub(r'\s+(scope|asset|control|process|person|document|incident|scenario)$', '', obj1, flags=re.IGNORECASE).strip()
                    obj2 = re.sub(r'\s+(scope|asset|control|process|person|document|incident|scenario)$', '', obj2, flags=re.IGNORECASE).strip()
                    
                    if obj1 and obj2:
                        return {
                            'success': True,
                            'tool': 'compare_objects',
                            'params': {
                                'object1_name': obj1.strip(),
                                'object2_name': obj2.strip()
                            }
                        }
        
        # ========== UNLINK OPERATIONS ==========
        
        # Detect unlink operations
        unlink_keywords = ['unlink', 'disconnect', 'remove', 'delete link', 'break link', 'separate']
        has_unlink = any(keyword in message_lower for keyword in unlink_keywords)
        
        if has_unlink:
            # Pattern: "unlink X from Y" or "remove X from Y" or "disconnect X and Y"
            unlink_patterns = [
                r'(?:unlink|disconnect|remove)\s+([A-Za-z0-9_\s-]+?)\s+(?:from|with)\s+([A-Za-z0-9_\s-]+)',
                r'(?:unlink|disconnect)\s+([A-Za-z0-9_\s-]+?)\s+and\s+([A-Za-z0-9_\s-]+)',
                r'remove\s+([A-Za-z0-9_\s-]+?)\s+from\s+([A-Za-z0-9_\s-]+)',
                r'break\s+(?:the\s+)?link\s+(?:between\s+)?([A-Za-z0-9_\s-]+?)\s+(?:and|with)\s+([A-Za-z0-9_\s-]+)',
            ]
            
            for pattern in unlink_patterns:
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    source = self._extract_object_name(original_message, match.start(1), match.end(1))
                    target = self._extract_object_name(original_message, match.start(2), match.end(2))
                    return {
                        'success': True,
                        'tool': 'unlink_objects',
                        'params': {
                            'source_name': source.strip(),
                            'target_name': target.strip()
                        }
                    }
        
        # ========== CREATE AND LINK PATTERNS (for fallback) ==========
        
        # Pattern: "create X and link with Y" (simpler format)
        create_link_pattern = r'(?:create|creat|new|add)\s+(?:a\s+)?(?:new\s+)?([A-Za-z0-9_\s-]+?)\s+(?:named|called)?\s*["\']?([^"\']+)["\']?\s+and\s+(?:link|connect|associate)\s+(?:it|them)?\s+(?:with|to)\s+(?:the\s+)?["\']?([^"\']+)["\']?'
        match = re.search(create_link_pattern, message, re.IGNORECASE)
        if match:
            # This is handled by chatRouter, but we can provide fallback here too
            pass
        
        # ========== CREATE AND LINK OPERATIONS ==========
        # Pattern: "Create a new Scope named 'Project Phoenix' and immediately link it with the 'IT-System assets' assets"
        # Pattern: "create scope 'X' and link it to 'Y' asset"
        # Pattern: "create asset 'X' and link it with 'Y' scope"
        # Pattern: "create person 'John' and link it to 'Team A' scope"
        
        # Object types to match (including plurals and variations)
        object_types = r'(?:scope|scopes|asset|assets|control|controls|controller|person|persons|people|process|processes|document|documents|incident|incidents|scenario|scenarios)'
        
        create_and_link_patterns = [
            # Pattern 1: "Create a new Scope named 'Project Phoenix' and immediately link it with the 'IT-System assets' assets"
            rf'(?:create|creat|new|add)\s+(?:a\s+)?(?:new\s+)?({object_types})\s+(?:named|called)\s+["\']([^"\']+)["\']\s+and\s+(?:immediately\s+)?(?:link|connect|associate)\s+(?:it|them)\s+(?:with|to)\s+(?:the\s+)?["\']([^"\']+)["\']\s+({object_types})',
            # Pattern 2: "create scope 'X' and link it to 'Y' asset"
            rf'(?:create|creat|new|add)\s+(?:a\s+)?({object_types})\s+["\']([^"\']+)["\']\s+and\s+(?:link|connect|associate)\s+(?:it|them)\s+(?:with|to)\s+["\']([^"\']+)["\']\s+({object_types})',
            # Pattern 3: "create asset 'X' and link it with 'Y' scope" (unquoted target)
            rf'(?:create|creat|new|add)\s+(?:a\s+)?({object_types})\s+["\']([^"\']+)["\']\s+and\s+(?:link|connect|associate)\s+(?:it|them)\s+(?:with|to)\s+([A-Za-z0-9_\s-]+?)(?:\s+{object_types})?\s*$',
            # Pattern 4: "create scope X and link it to Y" (unquoted both)
            rf'(?:create|creat|new|add)\s+(?:a\s+)?({object_types})\s+([A-Za-z0-9_\s-]+?)\s+and\s+(?:link|connect|associate)\s+(?:it|them)\s+(?:with|to)\s+([A-Za-z0-9_\s-]+?)(?:\s+{object_types})?\s*$',
        ]
        
        for pattern in create_and_link_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                # Extract source type and name
                source_type = match.group(1).strip().lower()
                source_name = match.group(2).strip().strip('"').strip("'")
                
                # Normalize source type - CRITICAL: "Scope" (capitalized) should stay as "scope", not be normalized
                if source_type == 'scope' or source_type == 'scopes':
                    source_type = 'scope'  # Keep as scope
                elif source_type.endswith('s') and source_type != 'process':
                    source_type = source_type.rstrip('s')
                elif source_type == 'controller':
                    # "Controller" is a subtype of scope, but if detected as object type, treat as scope
                    source_type = 'scope'
                elif source_type == 'people':
                    source_type = 'person'
                
                # Extract target name and type
                target_name = match.group(3).strip().strip('"').strip("'")
                target_type = None
                
                if len(match.groups()) >= 4 and match.group(4) and match.group(4).strip():
                    target_type = match.group(4).strip().lower()
                    # Normalize target type
                    if target_type.endswith('s') and target_type != 'process':
                        target_type = target_type.rstrip('s')
                    elif target_type == 'controller':
                        target_type = 'control'
                    elif target_type == 'people':
                        target_type = 'person'
                
                if source_name and target_name:
                    # Return a special marker that this is a create-and-link operation
                    # The caller should handle this as a two-step operation
                    return {
                        'success': True,
                        'tool': 'create_and_link',
                        'params': {
                            'source_type': source_type,
                            'source_name': source_name,
                            'target_name': target_name,
                            'target_type': target_type
                        },
                        '_is_create_and_link': True
                    }
        
        return {'success': False, 'error': get_error_message('mcp', 'could_not_understand_intent')}
    
    def _handle_create_and_link(self, params: Dict, original_message: str) -> Dict:
        """
        Handle create_and_link operation as a two-step process:
        1. Create the source object
        2. Link it to the target object
        
        This works even when LLM API quota is hit, using pattern-based parsing.
        """
        source_type = params.get('source_type')
        source_name = params.get('source_name')
        target_name = params.get('target_name')
        target_type = params.get('target_type')
        
        if not source_type or not source_name or not target_name:
            return self._error("Missing required parameters for create and link operation")
        
        # Step 1: Create the source object using VeriniceTool
        try:
            domain_id = self.verinice_tool.get_default_domain()
            if not domain_id:
                return self._error("No domain found. Please ensure you have access to a domain.")
            
            unit_id = self.verinice_tool.get_default_unit()
            
            create_result = self.verinice_tool.createObject(
                source_type,
                domain_id,
                unit_id,
                source_name,
                subType=None,  # Let the system auto-select or use default
                description="",
                abbreviation=None
            )
            
            if not create_result.get('success'):
                return self._error(f"Failed to create {source_type} '{source_name}': {create_result.get('error', 'Unknown error')}")
            
            # Step 2: Link the created object to the target
            from .tools.linking import link_objects
            
            link_params = {
                'source_type': source_type,
                'source_name': source_name,
                'target_name': target_name,
            }
            
            if target_type:
                link_params['target_type'] = target_type
            
            link_result = link_objects(
                verinice_tool=self.verinice_tool,
                state=self.state,
                **link_params
            )
            
            if link_result.get('success'):
                return self._success(
                    f"✅ Multi-step operation completed:\n  Step 1: Created {source_type} '{source_name}'\n  Step 2: Linked to {target_type} '{target_name}'",
                    {
                        'created': create_result,
                        'linked': link_result
                    }
                )
            else:
                # Acknowledge multi-step operation even when linking fails
                link_error = link_result.get('error', 'Unknown error')
                return self._success(
                    f"✅ Step 1 completed: Created {source_type} '{source_name}'\n⚠️  Step 2 (Link) failed: {link_error}\n\nNote: The {source_type} was created successfully. The linking step encountered an issue.",
                    {
                        'created': create_result,
                        'link_error': link_error
                    }
                )
                
        except Exception as e:
            logger.error(f"Create and link operation failed: {e}", exc_info=True)
            return self._error(f"Create and link operation failed: {str(e)}")
    
    def _extract_object_name(self, original_message: str, start: int, end: int) -> str:
        """Extract object name from original message preserving case"""
        return original_message[start:end].strip()
    
    def _build_link_params(self, source: str, target: str) -> Dict:
        """
        Build link_objects parameters from source and target names.
        Auto-detects which is scope vs object (scope is always the container).
        """
        source = re.sub(r'\b(?:the|a|an|my|this|that)\s+', '', source, flags=re.IGNORECASE).strip()
        target = re.sub(r'\b(?:the|a|an|my|this|that)\s+', '', target, flags=re.IGNORECASE).strip()
        
        # Simple heuristic: if target contains "scope" in name, it's likely a scope
        # Otherwise, we'll let the linking tool auto-detect
        if 'scope' in target.lower():
            return {
                'success': True,
                'tool': 'link_objects',
                'params': {
                    'source_name': source,
                    'target_type': 'scope',
                    'target_name': target
                }
            }
        elif 'scope' in source.lower():
            return {
                'success': True,
                'tool': 'link_objects',
                'params': {
                    'source_type': 'scope',
                    'source_name': source,
                    'target_name': target
                }
            }
        else:
            # Let the linking tool auto-detect types
            return {
                'success': True,
                'tool': 'link_objects',
                'params': {
                    'source_name': source,
                    'target_name': target
                }
            }
    
    def _success(self, message: str, data: Any = None) -> Dict:
        """Format success response"""
        return {
            'type': 'success',
            'text': message,
            'data': data
        }
    
    def _error(self, message: str) -> Dict:
        """Format error response"""
        return {
            'type': 'error',
            'text': message
        }
