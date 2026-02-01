"""Error presenter - formats error messages"""
from typing import Any, Dict, Optional
from .base import BasePresenter


class ErrorPresenter(BasePresenter):
    """Presents error messages in user-friendly format"""
    
    def present(self, data: Any, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Present error message
        
        Expected input format:
        - String error message
        - Dict with 'error' key
        - Exception object
        """
        # Extract error message
        if isinstance(data, str):
            error_msg = data
        elif isinstance(data, dict):
            error_msg = data.get('error') or data.get('message') or str(data)
        else:
            error_msg = str(data)
        
        # Clean up technical error messages
        error_msg = self._clean_error(error_msg)
        
        return {
            'type': 'error',
            'content': error_msg
        }
    
    def _clean_error(self, error_msg: str) -> str:
        """Clean up technical error messages for users"""
        error_msg = error_msg.strip()
        
        error_msg = error_msg.replace('Error:', '').replace('error:', '').strip()
        
        if 'FileNotFoundError' in error_msg:
            return "The requested file could not be found. Please check the file path."
        
        # Only format LLM/API errors if they're actually LLM/API related errors
        # Don't mask other errors that happen to contain "LLM" or "API" in the message
        if ('LLM' in error_msg or 'API' in error_msg) and (
            'llm' in error_msg.lower() or 
            'api' in error_msg.lower() or
            'quota' in error_msg.lower() or 
            '429' in error_msg or
            '404' in error_msg or
            'not found' in error_msg.lower() or
            'service' in error_msg.lower() or
            'unavailable' in error_msg.lower()
        ):
            if 'quota' in error_msg.lower() or '429' in error_msg:
                return "I've reached a service limit. Please try again in a few moments, or check your API settings.\n\nBasic operations like listing assets and scopes still work."
            if '404' in error_msg or 'not found' in error_msg.lower():
                return "The advanced service is temporarily unavailable.\n\nYou can still:\n• List and view your ISMS objects\n• Create new objects\n\nTry again in a moment."
            # For other LLM/API errors, show the actual error but in a user-friendly way
            if 'LLM' in error_msg or 'llm' in error_msg.lower():
                if 'not configured' in error_msg.lower() or 'not available' in error_msg.lower():
                    return "LLM service is not configured. Please check your API settings."
                return f"LLM service error: {error_msg.split('LLM')[-1].split('API')[0].strip()[:100]}"
            if 'API' in error_msg or 'api' in error_msg.lower():
                if 'not configured' in error_msg.lower() or 'not available' in error_msg.lower():
                    return "API service is not configured. Please check your API settings."
                return f"API service error: {error_msg.split('API')[-1].strip()[:100]}"
        
        # Preserve actual error messages for debugging - don't mask everything
        
        # Truncate long errors
        if len(error_msg) > 200:
            error_msg = error_msg[:200] + "..."
        
        return error_msg

