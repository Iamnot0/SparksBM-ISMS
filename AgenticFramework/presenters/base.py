"""Base presenter class"""
from typing import Any, Dict, Optional
from abc import ABC, abstractmethod


class BasePresenter(ABC):
    """Base class for all presenters"""
    
    @abstractmethod
    def present(self, data: Any, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Present data in a format suitable for UI rendering
        
        Args:
            data: Semantic data from agent
            context: Optional context (message, session, etc.)
            
        Returns:
            Dict with 'type', 'content', and optional metadata
        """
        pass
    
    @staticmethod
    def create_presenter(data_type: str) -> 'BasePresenter':
        """Factory method to create appropriate presenter"""
        from .table import TablePresenter
        from .list import ListPresenter
        from .report import ReportPresenter
        from .error import ErrorPresenter
        from .text import TextPresenter
        
        if data_type == 'table':
            return TablePresenter()
        elif data_type == 'list':
            return ListPresenter()
        elif data_type == 'report':
            return ReportPresenter()
        elif data_type == 'error':
            return ErrorPresenter()
        elif data_type == 'text':
            return TextPresenter()
        else:
            # Default to text presenter for general text
            return TextPresenter()

