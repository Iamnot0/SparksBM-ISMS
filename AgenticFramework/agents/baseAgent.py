"""Base agent class - all agents inherit from this"""
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod


class BaseAgent(ABC):
    """Base class for all agents. Handles role, goals, and basic execution."""
    
    def __init__(self, name: str, role: str, goals: List[str], instructions: str = ""):
        """
        Args:
            name: Agent identifier
            role: What this agent does (e.g., "ISMS Operations Agent")
            goals: List of objectives
            instructions: System instructions for behavior
        """
        self.name = name
        self.role = role
        self.goals = goals
        self.instructions = instructions
        self.tools = {}  # Tool registry: name -> function
        self.state = {}  # Current execution state
        self.history = []  # Action history
    
    def registerTool(self, name: str, toolFunc: callable, description: str = ""):
        """Register a tool this agent can use"""
        self.tools[name] = {
            'func': toolFunc,
            'description': description
        }
    
    def getAvailableTools(self) -> List[str]:
        """Returns list of tool names this agent can use"""
        return list(self.tools.keys())
    
    def executeTool(self, toolName: str, **kwargs) -> Any:
        """Execute a tool by name"""
        if toolName not in self.tools:
            raise ValueError(f"Tool '{toolName}' not available")
        
        tool = self.tools[toolName]['func']
        result = tool(**kwargs)
        
        # Log action
        self.history.append({
            'action': 'tool_execution',
            'tool': toolName,
            'args': kwargs,
            'result': result
        })
        
        return result
    
    @abstractmethod
    def process(self, inputData: Any) -> Dict:
        """
        Main processing method - each agent implements this differently
        Returns dict with 'status', 'result', 'next_steps'
        """
        pass
    
    def getContext(self) -> Dict:
        """Get current agent context for LLM or other systems"""
        return {
            'name': self.name,
            'role': self.role,
            'goals': self.goals,
            'instructions': self.instructions,
            'available_tools': self.getAvailableTools(),
            'state': self.state,
            'history_count': len(self.history)
        }

