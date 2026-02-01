"""Session service - manages user sessions"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid


class SessionService:
    """Manages user sessions and conversation state"""
    
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}
    
    def createSession(self, userId: str) -> str:
        """Create new session for user"""
        sessionId = str(uuid.uuid4())
        
        self.sessions[sessionId] = {
            'userId': userId,
            'sessionId': sessionId,
            'createdAt': datetime.now().isoformat(),
            'conversationHistory': [],
            'activeContext': [],
            'lastActivity': datetime.now().isoformat()
        }
        
        return sessionId
    
    def getSession(self, sessionId: str) -> Optional[Dict[str, Any]]:
        """Get session by ID"""
        return self.sessions.get(sessionId)
    
    def updateSession(self, sessionId: str, updates: Dict[str, Any]) -> bool:
        """Update session data"""
        if sessionId not in self.sessions:
            return False
        
        self.sessions[sessionId].update(updates)
        self.sessions[sessionId]['lastActivity'] = datetime.now().isoformat()
        return True
    
    def addMessage(self, sessionId: str, role: str, content: str) -> bool:
        """Add message to conversation history"""
        if sessionId not in self.sessions:
            return False
        
        self.sessions[sessionId]['conversationHistory'].append({
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat()
        })
        
        # Keep last 50 messages
        if len(self.sessions[sessionId]['conversationHistory']) > 50:
            self.sessions[sessionId]['conversationHistory'].pop(0)
        
        self.sessions[sessionId]['lastActivity'] = datetime.now().isoformat()
        return True
    
    def setContext(self, sessionId: str, sources: List[Dict[str, Any]]) -> bool:
        """Set active context sources"""
        if sessionId not in self.sessions:
            return False
        
        self.sessions[sessionId]['activeContext'] = sources
        self.sessions[sessionId]['lastActivity'] = datetime.now().isoformat()
        return True
    
    def deleteSession(self, sessionId: str) -> bool:
        """Delete session"""
        if sessionId in self.sessions:
            del self.sessions[sessionId]
            return True
        return False
    
    def getUserSessions(self, userId: str) -> List[Dict[str, Any]]:
        """Get all sessions for user"""
        return [
            session for session in self.sessions.values()
            if session.get('userId') == userId
        ]
