"""Conversation memory - typed memory for chat history"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Message:
    """Single message in conversation"""
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationMemory:
    """Typed conversation memory"""
    session_id: str
    messages: List[Message] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    
    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None):
        """Add a message to conversation"""
        self.messages.append(Message(
            role=role,
            content=content,
            metadata=metadata or {}
        ))
    
    def get_recent_messages(self, count: int = 10) -> List[Message]:
        """Get recent messages"""
        return self.messages[-count:] if len(self.messages) > count else self.messages
    
    def get_last_user_message(self) -> Optional[Message]:
        """Get last user message"""
        for msg in reversed(self.messages):
            if msg.role == 'user':
                return msg
        return None
    
    def get_last_assistant_message(self) -> Optional[Message]:
        """Get last assistant message"""
        for msg in reversed(self.messages):
            if msg.role == 'assistant':
                return msg
        return None
    
    def clear(self):
        """Clear conversation history"""
        self.messages.clear()
        self.context.clear()

