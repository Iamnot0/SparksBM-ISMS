"""
ISMS Agent - Tier 2/3: ReAct Reasoning Loop for Complex ISMS Operations

Phase 5: Progressive Agentic Architecture

This agent implements the ReAct (Reasoning + Acting) pattern for ISMS operations:
1. THOUGHT: Reason about what ISMS operation to perform
2. ACTION: Execute an ISMS tool
3. OBSERVATION: Process tool result
4. Repeat until task is complete

Handles:
- Multi-step ISMS operations (complex workflows)
- Reconciliation operations (compare domains, find differences)
- Complex queries (all assets in domain X with property Y)
"""

import os
import json
import re
import logging
from typing import Dict, Any, Optional, List, Callable

logger = logging.getLogger(__name__)


class ISMSAgent:
    """
    ISMS Operations Specialist - Autonomous agent for complex ISMS operations.
    
    Implements ReAct pattern: Thought → Action → Observation → Repeat
    
    Expertise:
    - ISO 27001, ISO 22301, NIS-2 compliance standards
    - Verinice ISMS platform operations
    - Risk, Asset, Control management
    - Report generation and analysis
    - Domain reconciliation and comparison
    """
    
    # Response action types
    ACTION_USE_TOOL = "use_tool"
    ACTION_COMPLETE = "complete"
    ACTION_ASK_CLARIFICATION = "ask_clarification"
    
    def __init__(self, verinice_tool, llm_tool=None, event_callback: Optional[Callable] = None):
        """
        Initialize ISMS Agent.
        
        Args:
            verinice_tool: VeriniceTool instance for ISMS operations
            llm_tool: LLMTool instance for reasoning
            event_callback: Optional callback for SSE event streaming
                Function(step_type, content, metadata)
        """
        self.verinice_tool = verinice_tool
        self.llm_tool = llm_tool
        self.event_callback = event_callback
        
        self.tools: Dict[str, Dict] = {}  # name -> {func, description, parameters}
        self.max_iterations = 10  # Safety limit
        self.conversation: List[Dict] = []  # Conversation history
        
        # Execution state
        self.current_task = None
        self.iterations = 0
        self.observations = []
        
        # Register ISMS tools
        if verinice_tool:
            from .ismsTools import register_isms_tools
            register_isms_tools(self, verinice_tool)
        
        logger.info("ISMSAgent initialized")
    
    def set_thought_callback(self, callback: Callable[[str, str, Dict], None]):
        """
        Set callback for streaming thoughts to frontend.
        
        Args:
            callback: Function(step_type, content, metadata)
        """
        self.event_callback = callback
    
    def register_tool(self, name: str, func: Callable, description: str, parameters: Dict = None):
        """
        Register a tool the agent can use.
        
        Args:
            name: Tool name (used in LLM responses)
            func: Function to call
            description: Description for LLM to understand when to use it
            parameters: JSON schema for parameters
        """
        self.tools[name] = {
            'func': func,
            'description': description,
            'parameters': parameters or {}
        }
        logger.info(f"ISMSAgent registered tool: {name}")
    
    def _emit_event(self, event_type: str, data: Dict[str, Any]):
        """
        Emit a real-time event for the reasoning dashboard.
        
        Args:
            event_type: 'thought', 'tool_call', 'tool_result', 'complete', 'error'
            data: Event payload
        """
        event = {
            'type': event_type,
            'timestamp': __import__('time').time(),
            **data
        }
        
        # Emit via callback
        if self.event_callback:
            # ISMSAgent uses (event_type, data) format to match ISMSController
            if self.event_callback:
                self.event_callback(event_type, {
                    'content': data.get('content', ''),
                    **event
                })
        
        logger.info(f"ISMSAgent EVENT [{event_type.upper()}]: {data.get('content', data.get('tool_name', ''))}")
    
    def _emit_thought(self, step_type: str, content: str, metadata: Dict = None):
        """
        Emits a reasoning step to the frontend.
        Fix: Filters out raw system prompts or internal instruction dumps.
        """
        if not content:
            return
        
        # 1. CLEANUP: Remove "System:" or "Instructions:" prefixes if the LLM hallucinated them
        clean_content = content.replace("System:", "").replace("Instructions:", "").strip()
        
        # 2. FILTER: If the thought is just regurgitating the prompt, DROP IT.
        # We check for signature phrases from system prompts
        internal_signatures = [
            "You are an ISMS Operations Specialist",
            "You are a Full Stack DevOps",
            "CRITICAL:",
            "EXECUTION task",
            "## Your Role & Expertise",
            "## Available Tools",
            "## Response Format",
            "## Critical Rules",
            "ALWAYS USE TOOLS",
            "You MUST respond in valid JSON"
        ]
        
        if any(sig in clean_content for sig in internal_signatures):
            # Log it for debugging, but DO NOT send to user
            logger.debug(f"Suppressed internal system thought: {clean_content[:100]}...")
            return
        
        # 3. HUMANIZING: If it passes the filter, send it!
        self._emit_event(step_type, {'content': clean_content, **(metadata or {})})
    
    def execute(self, task: str, context: Dict = None, mode: str = 'standard') -> Dict:
        """
        Execute ISMS operation with ReAct reasoning loop.
        
        Args:
            task: The ISMS task to execute
            context: Optional context dictionary (state, session info)
            mode: 'standard' (Tier 2) or 'deep_reasoning' (Tier 3)
        
        Returns:
            Dict with:
                - status: 'success' | 'error' | 'needs_clarification'
                - result: Final result or error message
                - thoughts: List of all thoughts during execution
                - tool_calls: List of all tool calls made
        """
        if context is None:
            context = {}
        
        self.current_task = task
        self.iterations = 0
        self.observations = []
        
        # Build initial conversation
        system_prompt = self._build_system_prompt(mode)
        self.conversation = [
            {"role": "system", "content": system_prompt}
        ]
        
        if context:
            context_str = self._format_context(context)
            if context_str:
                self.conversation.append({
                    "role": "user",
                    "content": f"Context:\n{context_str}"
                })
        
        self.conversation.append({
            "role": "user",
            "content": f"ISMS Operation: {task}"
        })
        
        self._emit_thought('task_start', f"Starting ISMS operation: {task}", {'task': task, 'mode': mode})
        
        # Result tracking
        all_thoughts = []
        all_tool_calls = []
        
        # ReAct loop
        while self.iterations < self.max_iterations:
            self.iterations += 1
            logger.info(f"ISMSAgent ReAct iteration {self.iterations}/{self.max_iterations}")
            
            try:
                if not self.llm_tool:
                    raise RuntimeError("LLM tool not configured")
                llm_response = self._call_llm()
            except Exception as e:
                logger.error(f"LLM call failed: {e}")
                self._emit_thought('error', f"LLM call failed: {e}")
                return {
                    'status': 'error',
                    'result': f"LLM call failed: {str(e)}",
                    'thoughts': all_thoughts,
                    'tool_calls': all_tool_calls
                }
            
            # Parse response
            parsed = self._parse_llm_response(llm_response)
            thought = parsed.get('thought', '')
            action = parsed.get('action', '')
            
            # Emit and track thought
            self._emit_thought('thought', thought, {'iteration': self.iterations})
            all_thoughts.append({
                'iteration': self.iterations,
                'thought': thought,
                'action': action
            })
            
            if action == self.ACTION_COMPLETE:
                result = parsed.get('result', 'Task completed')
                self._emit_thought('complete', result, {'iteration': self.iterations})
                return {
                    'status': 'success',
                    'result': result,
                    'thoughts': all_thoughts,
                    'tool_calls': all_tool_calls
                }
            elif action == self.ACTION_USE_TOOL:
                tool_name = parsed.get('tool_name')
                tool_args = parsed.get('tool_args', {})
                
                if not tool_name or tool_name not in self.tools:
                    self._emit_thought('error', f"Unknown tool: {tool_name}")
                    observation = f"Error: Tool '{tool_name}' not available"
                else:
                    self._emit_event('tool_call', {
                        'tool_name': tool_name,
                        'tool_args': tool_args,
                        'iteration': self.iterations
                    })
                    
                    observation = self._execute_tool(tool_name, tool_args)
                    
                    self._emit_event('tool_result', {
                        'tool_name': tool_name,
                        'observation': observation[:1000],  # Limit length
                        'result': observation[:1000],  # Also include 'result' for frontend compatibility
                        'iteration': self.iterations
                    })
                    
                    all_tool_calls.append({
                        'iteration': self.iterations,
                        'tool_name': tool_name,
                        'tool_args': tool_args,
                        'result': observation[:500]
                    })
                
                self.conversation.append({
                    "role": "assistant",
                    "content": json.dumps({
                        "thought": thought,
                        "action": action,
                        "tool_name": tool_name,
                        "tool_args": tool_args
                    })
                })
                self.conversation.append({
                    "role": "user",
                    "content": f"Tool result: {observation}"
                })
                
                self.observations.append(observation)
            elif action == self.ACTION_ASK_CLARIFICATION:
                question = parsed.get('question', 'Need clarification')
                self._emit_thought('clarification', question)
                return {
                    'status': 'needs_clarification',
                    'result': question,
                    'thoughts': all_thoughts,
                    'tool_calls': all_tool_calls
                }
            else:
                # Unknown action - treat as complete
                logger.warning(f"Unknown action: {action}")
                return {
                    'status': 'error',
                    'result': f"Unknown action: {action}",
                    'thoughts': all_thoughts,
                    'tool_calls': all_tool_calls
                }
        
        # Max iterations reached
        self._emit_thought('error', f"Max iterations ({self.max_iterations}) reached")
        return {
            'status': 'error',
            'result': f"Task incomplete after {self.max_iterations} iterations",
            'thoughts': all_thoughts,
            'tool_calls': all_tool_calls
        }
    
    def _build_system_prompt(self, mode: str = 'standard') -> str:
        """Build the system prompt with tool descriptions."""
        tools_desc = "\n".join([
            f"- **{name}**: {info['description']}"
            for name, info in self.tools.items()
        ])
        
        mode_instruction = ""
        if mode == 'deep_reasoning':
            mode_instruction = """
## Deep Reasoning Mode
You are in deep reasoning mode. Take extra time to:
- Analyze all dependencies and relationships
- Consider multiple approaches before acting
- Validate assumptions thoroughly
- Provide detailed analysis and insights
"""
        
        return f"""You are an ISMS Operations Specialist, an expert in Information Security Management Systems with deep knowledge of ISO 27001, ISO 22301, and NIS-2 compliance standards.

## Your Role & Expertise
As an ISMS Operations Specialist, you possess expertise in:

**ISMS Standards:**
- ISO 27001: Information Security Management
- ISO 22301: Business Continuity Management
- NIS-2: Network and Information Systems Directive

**Verinice ISMS Platform:**
- Risk management and assessment
- Asset management and inventory
- Control implementation and monitoring
- Process management
- Incident and scenario handling
- Compliance reporting

**Operations:**
- CRUD operations for all ISMS objects (scopes, assets, controls, processes, persons, scenarios, incidents, documents)
- Report generation (inventory, risk assessment, statement of applicability)
- Domain and unit management
- Object analysis and insights
- Reconciliation and comparison operations

## Available Tools
{tools_desc}

## Few-Shot Examples

**User:** Create a new scope 'Project-X' and add a person 'John Doe' to it.
**Thought:** I need to create a scope and a person, then link them. First, I'll create the scope.
**Action:** use_tool {"tool_name": "create_object", "tool_args": {"type": "scope", "name": "Project-X"}}
**Observation:** Created scope 'Project-X' (ID: scp-123).
**Thought:** Now I'll create the person 'John Doe'.
**Action:** use_tool {"tool_name": "create_object", "tool_args": {"type": "person", "name": "John Doe"}}
**Observation:** Created person 'John Doe' (ID: per-456).
**Thought:** Now I will link John Doe to Project-X.
**Action:** use_tool {"tool_name": "link_objects", "tool_args": {"source_id": "scp-123", "target_id": "per-456"}}
**Observation:** Successfully linked.
**Thought:** All steps complete.
**Action:** complete {"result": "Created scope 'Project-X' and person 'John Doe', and linked them."}

**User:** Analyze the risk for asset 'Server-01'.
**Thought:** I need to find the asset 'Server-01' and then analyze its risk data.
**Action:** use_tool {"tool_name": "get_object", "tool_args": {"type": "asset", "name": "Server-01"}}
**Observation:** Asset 'Server-01' found (ID: ast-789). Risks: [R1: High, R2: Medium].
**Thought:** I have the risk data. I will summarize it.
**Action:** complete {"result": "Asset 'Server-01' has 2 risks: R1 (High) and R2 (Medium)."}

## Response Format
You MUST respond with valid JSON in this format:
```json
{{
  "thought": "Your reasoning about what to do next",
  "action": "use_tool" | "complete" | "ask_clarification",
  "tool_name": "name_of_tool" (if action is use_tool),
  "tool_args": {{"arg1": "value1"}} (if action is use_tool),
  "result": "Final result message" (if action is complete),
  "question": "Your question" (if action is ask_clarification),
  "confidence": 0.0-1.0
}}
```

## REASONING STYLE GUIDE
When writing your "thought" field, be conversational but professional:
- Use "I" statements to describe your actions
- Summarize intent, don't just list tool names
- BAD: "Calling tool list_assets."
- GOOD: "I'm retrieving the list of assets to understand what we're working with."
- BAD: "Creating scope with name."
- GOOD: "I'm creating a new scope for the security assessment project."
- BAD: "Updating control status."
- GOOD: "I'm updating the control status to reflect the latest compliance check."

Your thoughts should read naturally, as if you're explaining your approach to a colleague.

## Critical Rules
1. **ALWAYS USE TOOLS**: For any ISMS operation, you MUST use the appropriate tools. DO NOT just explain - EXECUTE.
2. Always understand dependencies: Some operations require domains/units to exist first
3. Think end-to-end: Consider how operations affect compliance, risk, and reporting
4. Make minimal, targeted changes that maintain ISMS integrity
5. Verify your operations work - check results after execution
6. Consider ISMS implications: Will this affect compliance? Need risk assessment? Require documentation?
7. If a tool fails, analyze the error systematically and retry with corrections
8. Stop after completing the task - don't keep looping unnecessarily
9. Document complex operations - ensure ISMS objects are properly configured
10. **FOR MULTI-STEP OPERATIONS**: Plan the sequence, execute step by step, verify each step
11. **VERINICE LINKING CONSTRAINTS**: Be aware that some object types cannot be linked. For example, "assets cannot be parts of incidents." Always check if a linking operation is valid before attempting it.

{mode_instruction}

## Working Context
You are operating on a Verinice ISMS platform. All operations must comply with ISMS standards and best practices.
"""
    
    def _format_context(self, context: Dict) -> str:
        """Format context dictionary into readable string."""
        parts = []
        if 'state' in context:
            state = context['state']
            if 'pendingReportGeneration' in state:
                parts.append(f"Pending report generation: {state['pendingReportGeneration'].get('reportType')}")
            if '_pendingSubtypeSelection' in state:
                parts.append(f"Pending subtype selection for: {state['_pendingSubtypeSelection'].get('objectType')}")
        return "\n".join(parts) if parts else ""
    
    def _parse_llm_response(self, response: str) -> Dict:
        """
        Parse LLM response as JSON.
        
        Returns:
            Parsed JSON dict with thought/action/tool_name/tool_args/confidence
        """
        try:
            json_str = None
            
            # PRIORITY 1: Look for JSON in markdown code blocks
            json_block_match = re.search(r"```json\s*\n?(.*?)\n?```", response, re.DOTALL)
            if json_block_match:
                json_str = json_block_match.group(1).strip()
            elif '```' in response:
                parts = response.split('```')
                if len(parts) >= 3:
                    json_str = parts[1].strip()
                    if json_str.startswith('json'):
                        json_str = json_str[4:].strip()
            else:
                json_str = response.strip()
            
            if not json_str:
                raise ValueError("No JSON content found")
            
            # Find complete JSON object by balanced braces
            brace_count = 0
            json_start = -1
            json_end = -1
            
            for i, char in enumerate(json_str):
                if char == '{':
                    if brace_count == 0:
                        json_start = i
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0 and json_start >= 0:
                        json_end = i + 1
                        break
            
            if json_start >= 0 and json_end > json_start:
                json_str = json_str[json_start:json_end]
            elif json_start >= 0:
                json_str = json_str[json_start:] + '}'
                logger.warning("JSON appears incomplete, attempting to close it")
            
            # Parse JSON
            parsed = json.loads(json_str.strip())
            
            if 'action' not in parsed:
                raise ValueError("Missing 'action' field")
            
            # Calculate confidence if not provided
            if 'confidence' not in parsed:
                parsed['confidence'] = self._calculate_confidence(parsed, response)
            
            return parsed
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse LLM response: {e}\nResponse: {response[:500]}")
            return {
                "thought": f"Failed to parse response: {str(e)}",
                "action": "complete",
                "result": f"Error: Could not parse LLM response",
                "confidence": 0.0
            }
    
    def _calculate_confidence(self, parsed: Dict, raw_response: str) -> float:
        """Calculate confidence score for agent decision."""
        confidence = 0.5  # Base confidence
        
        # Action type affects confidence
        action = parsed.get('action', '')
        if action == self.ACTION_COMPLETE:
            confidence += 0.2
        elif action == self.ACTION_USE_TOOL:
            confidence += 0.1
        
        # Tool selection affects confidence
        if 'tool_name' in parsed and parsed['tool_name'] in self.tools:
            confidence += 0.1
        
        # Response clarity
        thought = parsed.get('thought', '')
        if len(thought) > 50:
            confidence += 0.1
        
        return min(1.0, confidence)
    
    def _execute_tool(self, tool_name: str, tool_args: Dict) -> str:
        """
        Execute a registered tool.
        
        Args:
            tool_name: Name of the tool
            tool_args: Arguments for the tool
        
        Returns:
            Tool result as string (observation)
        """
        if tool_name not in self.tools:
            return f"Error: Tool '{tool_name}' not available"
        
        try:
            tool_func = self.tools[tool_name]['func']
            result = tool_func(**tool_args)
            
            # Format result for observation
            if isinstance(result, dict):
                if result.get('success'):
                    return result.get('message') or result.get('text') or str(result.get('data', 'Success'))
                else:
                    return f"Error: {result.get('error') or result.get('text') or 'Unknown error'}"
            else:
                return str(result)
        except Exception as e:
            logger.error(f"Tool execution error ({tool_name}): {e}", exc_info=True)
            return f"Error executing {tool_name}: {str(e)}"
    
    def _call_llm(self) -> str:
        """Call the LLM with current conversation."""
        if not self.llm_tool:
            raise RuntimeError("LLM tool not configured")
        
        # Build prompt from conversation
        prompt_parts = []
        system_content = ""
        
        for msg in self.conversation:
            if msg['role'] == 'system':
                system_content = msg['content']
            elif msg['role'] == 'user':
                prompt_parts.append(f"User: {msg['content']}")
            elif msg['role'] == 'assistant':
                prompt_parts.append(f"Assistant: {msg['content']}")
        
        full_prompt = "\n\n".join(prompt_parts)
        
        # Use LLMTool to generate
        response = self.llm_tool.generate(
            prompt=full_prompt,
            systemPrompt=system_content,
            maxTokens=4000
        )
        
        return response
