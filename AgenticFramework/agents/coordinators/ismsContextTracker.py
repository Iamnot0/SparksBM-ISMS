"""
ISMS Context Tracker - Tracks ISMS objects in conversation context

This module tracks all ISMS objects (scopes, assets, controls, etc.) that are
created or mentioned during a conversation, enabling:
- Object name resolution (name → ID)
- Reconciliation operations (compare objects by name)
- Context-aware responses ("their abbreviations" → recent objects)
"""

from typing import Dict, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ISMSContextTracker:
    """Tracks ISMS objects in conversation context"""
    
    def __init__(self):
        self.created_objects = []  # List of created objects
        self.mentioned_objects = []  # Objects mentioned by name
        self.name_to_id_map = {}  # name → (objectType, objectId, domainId, abbreviation)
    
    def track_creation(self, objectType: str, name: str, objectId: str, 
                      domainId: str, abbreviation: str = None):
        """Track when object is created"""
        obj = {
            'objectType': objectType,
            'name': name,
            'objectId': objectId,
            'domainId': domainId,
            'abbreviation': abbreviation,
            'created_at': datetime.now().isoformat()
        }
        self.created_objects.append(obj)
        
        # Store in name map (case-insensitive)
        name_lower = name.lower()
        self.name_to_id_map[name_lower] = {
            'objectType': objectType,
            'objectId': objectId,
            'domainId': domainId,
            'abbreviation': abbreviation,
            'name': name
        }
        
        logger.info(f"Tracked ISMS object creation: {objectType} '{name}' (ID: {objectId})")
    
    def find_object_by_name(self, name: str) -> Optional[Dict]:
        """Find object by name (case-insensitive)"""
        name_lower = name.lower()
        if name_lower in self.name_to_id_map:
            return self.name_to_id_map[name_lower]
        return None
    
    def find_objects_by_names(self, names: List[str]) -> List[Dict]:
        """Find multiple objects by names"""
        results = []
        for name in names:
            obj = self.find_object_by_name(name)
            if obj:
                results.append(obj)
        return results
    
    def get_recent_objects(self, limit: int = 10) -> List[Dict]:
        """Get recently created/mentioned objects"""
        return self.created_objects[-limit:]
    
    def get_all_objects_of_type(self, objectType: str) -> List[Dict]:
        """Get all objects of a specific type"""
        return [obj for obj in self.created_objects if obj.get('objectType') == objectType]
    
    def clear(self):
        """Clear all tracked objects"""
        self.created_objects = []
        self.mentioned_objects = []
        self.name_to_id_map = {}
        logger.info("Cleared ISMS context tracker")
    
    def get_context_summary(self) -> str:
        """Get a summary of tracked objects for context"""
        if not self.created_objects:
            return "No ISMS objects tracked in this session."
        
        summary = f"Tracked {len(self.created_objects)} ISMS object(s):\n"
        for obj in self.created_objects[-10:]:  # Last 10
            summary += f"- {obj.get('objectType', 'unknown')}: '{obj.get('name', 'unknown')}'"
            if obj.get('abbreviation'):
                summary += f" (abbr: {obj.get('abbreviation')})"
            summary += "\n"
        
        return summary
    
    def to_dict(self) -> Dict:
        """Serialize to dict for session storage"""
        return {
            'created_objects': self.created_objects,
            'name_to_id_map': self.name_to_id_map
        }
    
    def from_dict(self, data: Dict):
        """Restore from dict"""
        self.created_objects = data.get('created_objects', [])
        self.name_to_id_map = data.get('name_to_id_map', {})
        logger.info(f"Restored ISMS context: {len(self.created_objects)} objects")
