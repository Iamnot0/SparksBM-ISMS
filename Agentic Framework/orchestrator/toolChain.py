"""Tool chaining system - chain multiple tools together with result passing"""
from typing import Dict, List, Any, Optional, Callable
import json


class ToolChain:
    """Manages chaining of multiple tools with result passing"""
    
    def __init__(self, agent):
        """
        Args:
            agent: MainAgent instance with tools
        """
        self.agent = agent
        self.executionHistory = []
    
    def executeChain(self, chain: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Execute a chain of tools
        
        Args:
            chain: List of tool execution steps, each with:
                - tool: Tool name
                - params: Parameters (can reference previous results with $stepN.field)
                - storeAs: Variable name to store result
                - condition: Optional condition to check before execution
                
        Returns:
            Final result and execution history
        """
        results = {}
        executionLog = []
        
        for i, step in enumerate(chain):
            stepNum = i + 1
            
            if 'condition' in step:
                conditionMet = self._evaluateCondition(step['condition'], results)
                if not conditionMet:
                    executionLog.append({
                        'step': stepNum,
                        'tool': step.get('tool'),
                        'status': 'skipped',
                        'reason': 'Condition not met'
                    })
                    continue
            
            # Resolve parameters (replace $stepN.field references)
            params = self._resolveParameters(step.get('params', {}), results)
            
            try:
                toolName = step['tool']
                if toolName not in self.agent.tools:
                    raise ValueError(f"Tool '{toolName}' not available")
                
                toolResult = self.agent.executeTool(toolName, **params)
                
                # Store result if specified
                storeAs = step.get('storeAs', f'step{stepNum}')
                results[storeAs] = toolResult
                
                executionLog.append({
                    'step': stepNum,
                    'tool': toolName,
                    'params': params,
                    'status': 'success',
                    'result': toolResult,
                    'storedAs': storeAs
                })
                
            except Exception as e:
                executionLog.append({
                    'step': stepNum,
                    'tool': step.get('tool'),
                    'status': 'error',
                    'error': str(e)
                })
                
                # Decide whether to continue or stop
                if step.get('stopOnError', True):
                    return {
                        'status': 'error',
                        'error': f"Chain failed at step {stepNum}: {str(e)}",
                        'executionLog': executionLog,
                        'results': results
                    }
        
        # Return final result
        finalResult = results.get('final', results.get(f'step{len(chain)}', results))
        
        return {
            'status': 'success',
            'result': finalResult,
            'executionLog': executionLog,
            'results': results
        }
    
    def _resolveParameters(self, params: Dict[str, Any], results: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve parameter references to previous step results"""
        resolved = {}
        
        for key, value in params.items():
            if isinstance(value, str) and value.startswith('$'):
                # Reference to previous result: $step1.field or $variable.field
                resolved[key] = self._resolveReference(value, results)
            elif isinstance(value, dict):
                # Recursively resolve nested dicts
                resolved[key] = self._resolveParameters(value, results)
            elif isinstance(value, list):
                # Resolve list items
                resolved[key] = [
                    self._resolveReference(item, results) if isinstance(item, str) and item.startswith('$') else item
                    for item in value
                ]
            else:
                resolved[key] = value
        
        return resolved
    
    def _resolveReference(self, ref: str, results: Dict[str, Any]) -> Any:
        """Resolve a reference like $step1.field or $variable.field"""
        ref = ref[1:]
        
        # Split by dot
        parts = ref.split('.', 1)
        varName = parts[0]
        fieldPath = parts[1] if len(parts) > 1 else None
        
        if varName not in results:
            raise ValueError(f"Reference '{varName}' not found in results")
        
        value = results[varName]
        
        # Navigate field path if present
        if fieldPath:
            for field in fieldPath.split('.'):
                if isinstance(value, dict):
                    value = value.get(field)
                elif isinstance(value, list) and field.isdigit():
                    value = value[int(field)]
                else:
                    raise ValueError(f"Cannot access field '{field}' in {type(value)}")
        
        return value
    
    def _evaluateCondition(self, condition: Dict[str, Any], results: Dict[str, Any]) -> bool:
        """
        Evaluate a condition
        
        Condition format:
        {
            "type": "compare" | "exists" | "custom",
            "left": "$step1.field",
            "operator": ">" | "<" | "==" | "!=" | ">=" | "<=",
            "right": value
        }
        """
        condType = condition.get('type', 'compare')
        
        if condType == 'compare':
            left = self._resolveReference(condition['left'], results) if isinstance(condition['left'], str) and condition['left'].startswith('$') else condition['left']
            right = self._resolveReference(condition['right'], results) if isinstance(condition.get('right'), str) and condition.get('right', '').startswith('$') else condition.get('right')
            operator = condition.get('operator', '==')
            
            if operator == '>':
                return left > right
            elif operator == '<':
                return left < right
            elif operator == '==':
                return left == right
            elif operator == '!=':
                return left != right
            elif operator == '>=':
                return left >= right
            elif operator == '<=':
                return left <= right
        
        elif condType == 'exists':
            ref = condition.get('reference')
            if ref:
                try:
                    self._resolveReference(ref, results)
                    return True
                except ValueError:
                    return False
        
        return False
    
    def createChainFromQuery(self, query: str, context: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        Create tool chain from natural language query
        
        This uses LLM to understand the query and create a chain
        
        Args:
            query: User query
            context: Current context (documents, etc.)
            
        Returns:
            List of chain steps or None if can't create chain
        """
        # This would use LLM to understand query and create chain
        # For now, return None (will be enhanced)
        return None

