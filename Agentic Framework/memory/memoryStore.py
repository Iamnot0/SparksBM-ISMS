"""Memory store for agent state and history"""
from typing import Dict, List, Any, Optional
from datetime import datetime


class MemoryStore:
    """Simple in-memory store for agent state and conversation history"""
    
    def __init__(self):
        self.shortTerm = {}  # Current session data
        self.longTerm = []  # Historical records
        self.maxHistory = 1000  # Max records to keep
    
    def store(self, key: str, value: Any, persistent: bool = False):
        """
        Store data in memory
        
        Args:
            key: Storage key
            value: Data to store
            persistent: If True, also store in long-term
        """
        self.shortTerm[key] = {
            'value': value,
            'timestamp': datetime.now().isoformat()
        }
        
        if persistent:
            self.longTerm.append({
                'key': key,
                'value': value,
                'timestamp': datetime.now().isoformat()
            })
            
            # Trim if too long
            if len(self.longTerm) > self.maxHistory:
                self.longTerm = self.longTerm[-self.maxHistory:]
    
    def retrieve(self, key: str, useLongTerm: bool = False) -> Optional[Any]:
        """
        Retrieve data from memory
        
        Args:
            key: Storage key
            useLongTerm: Also search long-term memory
            
        Returns:
            Stored value or None
        """
        if key in self.shortTerm:
            return self.shortTerm[key]['value']
        
        if useLongTerm:
            # Search backwards for most recent
            for record in reversed(self.longTerm):
                if record['key'] == key:
                    return record['value']
        
        return None
    
    def getAll(self) -> Dict:
        """Get all short-term memory"""
        return {k: v['value'] for k, v in self.shortTerm.items()}
    
    def getHistory(self, limit: int = 100) -> List[Dict]:
        """Get recent history"""
        return self.longTerm[-limit:]
    
    def clear(self):
        """Clear short-term memory"""
        self.shortTerm = {}
    
    def clearAll(self):
        """Clear all memory"""
        self.shortTerm = {}
        self.longTerm = []

