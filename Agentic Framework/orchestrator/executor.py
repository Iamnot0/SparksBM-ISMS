"""Agent executor - orchestrates agent execution and workflow"""
from typing import Dict, List, Optional, Any
from agents.baseAgent import BaseAgent


class AgentExecutor:
    """Orchestrates agent execution, planning, and tool coordination"""
    
    def __init__(self, agents: List[BaseAgent] = None):
        """
        Args:
            agents: List of agents to manage
        """
        self.agents = agents or []
        self.executionHistory = []
        self.currentTask = None
    
    def registerAgent(self, agent: BaseAgent):
        """Register an agent"""
        self.agents.append(agent)
    
    def getAgent(self, name: str) -> Optional[BaseAgent]:
        """Get agent by name"""
        for agent in self.agents:
            if agent.name == name:
                return agent
        return None
    
    def execute(self, task: str, agentName: Optional[str] = None, inputData: Any = None) -> Dict:
        """
        Execute a task using an agent
        
        Args:
            task: Task description or instruction
            agentName: Specific agent to use (None = auto-select)
            inputData: Input data for the agent
            
        Returns:
            Execution result
        """
        # Select agent
        if agentName:
            agent = self.getAgent(agentName)
            if not agent:
                return {
                    'success': False,
                    'error': f'Agent "{agentName}" not found'
                }
        elif self.agents:
            # Use first agent or implement selection logic
            agent = self.agents[0]
        else:
            return {
                'success': False,
                'error': 'No agents available'
            }
        
        # Store task
        self.currentTask = {
            'task': task,
            'agent': agent.name,
            'input': inputData
        }
        
        try:
            # If inputData is None, use task as input
            processInput = inputData if inputData is not None else task
            
            result = agent.process(processInput)
            
            # Log execution
            executionRecord = {
                'task': task,
                'agent': agent.name,
                'result': result,
                'status': result.get('status', 'unknown')
            }
            self.executionHistory.append(executionRecord)
            
            return {
                'success': result.get('status') == 'success',
                'agent': agent.name,
                'result': result,
                'executionId': len(self.executionHistory)
            }
            
        except Exception as e:
            errorResult = {
                'success': False,
                'error': str(e),
                'agent': agent.name
            }
            self.executionHistory.append({
                'task': task,
                'agent': agent.name,
                'error': str(e),
                'status': 'error'
            })
            return errorResult
    
    def executeWorkflow(self, steps: List[Dict]) -> Dict:
        """
        Execute a multi-step workflow
        
        Args:
            steps: List of step dicts with 'task', 'agent', 'input'
            
        Returns:
            Workflow execution results
        """
        results = []
        
        for i, step in enumerate(steps):
            task = step.get('task', '')
            agentName = step.get('agent')
            inputData = step.get('input')
            
            # Use previous step result as input if not specified
            if inputData is None and results:
                inputData = results[-1].get('result')
            
            result = self.execute(task, agentName, inputData)
            results.append({
                'step': i + 1,
                'task': task,
                'result': result
            })
            
            # Stop on error if configured
            if not result.get('success') and step.get('stopOnError', True):
                break
        
        return {
            'success': all(r['result'].get('success') for r in results),
            'steps': results,
            'totalSteps': len(steps),
            'completedSteps': len([r for r in results if r['result'].get('success')])
        }
    
    def getHistory(self) -> List[Dict]:
        """Get execution history"""
        return self.executionHistory.copy()
    
    def clearHistory(self):
        """Clear execution history"""
        self.executionHistory = []

