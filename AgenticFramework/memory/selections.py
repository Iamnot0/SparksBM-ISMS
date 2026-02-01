"""Selections memory - tracks selected objects, scopes, assets, etc."""
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field


@dataclass
class Selection:
    """Selected object reference"""
    object_type: str  # 'scope', 'asset', 'report', etc.
    object_id: str
    object_name: str
    domain_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SelectionsMemory:
    """Memory for user selections"""
    current_selection: Optional[Selection] = None
    selection_history: List[Selection] = field(default_factory=list)
    list_cache: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)  # Cache recent lists
    
    def select(self, object_type: str, object_id: str, object_name: str, 
               domain_id: Optional[str] = None, metadata: Optional[Dict] = None):
        """Select an object"""
        selection = Selection(
            object_type=object_type,
            object_id=object_id,
            object_name=object_name,
            domain_id=domain_id,
            metadata=metadata or {}
        )
        self.current_selection = selection
        self.selection_history.append(selection)
        # Keep only last 20 selections
        if len(self.selection_history) > 20:
            self.selection_history = self.selection_history[-20:]
    
    def get_selection(self, index: int = -1) -> Optional[Selection]:
        """Get selection by index (negative for reverse, -1 is most recent)"""
        if not self.selection_history:
            return None
        try:
            return self.selection_history[index]
        except IndexError:
            return None
    
    def get_selection_by_type(self, object_type: str) -> Optional[Selection]:
        """Get most recent selection of specific type"""
        for selection in reversed(self.selection_history):
            if selection.object_type == object_type:
                return selection
        return None
    
    def cache_list(self, list_type: str, items: List[Dict[str, Any]]):
        """Cache a list result"""
        self.list_cache[list_type] = items
        # Keep only last 10 cached lists
        if len(self.list_cache) > 10:
            oldest_key = next(iter(self.list_cache))
            del self.list_cache[oldest_key]
    
    def get_cached_list(self, list_type: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached list"""
        return self.list_cache.get(list_type)
    
    def clear(self):
        """Clear all selections"""
        self.current_selection = None
        self.selection_history.clear()
        self.list_cache.clear()

