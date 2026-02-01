"""UI state memory - tracks UI preferences and state"""
from typing import Optional, Dict, Any
from dataclasses import dataclass, field


@dataclass
class UIState:
    """UI state and preferences"""
    view_mode: str = 'table'  # 'table', 'list', 'card'
    export_format: str = 'table'  # 'table', 'csv', 'json'
    last_report_type: Optional[str] = None
    last_report_id: Optional[str] = None
    preferences: Dict[str, Any] = field(default_factory=dict)
    
    def set_view_mode(self, mode: str):
        """Set view mode"""
        if mode in ['table', 'list', 'card']:
            self.view_mode = mode
    
    def set_export_format(self, format: str):
        """Set export format"""
        if format in ['table', 'csv', 'json', 'pdf']:
            self.export_format = format
    
    def set_last_report(self, report_type: str, report_id: str):
        """Remember last generated report"""
        self.last_report_type = report_type
        self.last_report_id = report_id
    
    def get_preference(self, key: str, default: Any = None) -> Any:
        """Get preference value"""
        return self.preferences.get(key, default)
    
    def set_preference(self, key: str, value: Any):
        """Set preference value"""
        self.preferences[key] = value

