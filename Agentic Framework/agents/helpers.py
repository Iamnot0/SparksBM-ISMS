"""
Helper Functions for MainAgent
Phase 1 Refactoring: Stateless utility functions extracted from MainAgent

These functions are pure (input -> output) with no side effects.
They don't depend on agent state and can be safely extracted.
"""

from typing import Optional, List, Dict, Any
import re
from .instructions import GREETING_PATTERN, THANKS_PATTERN, GREETING_PATTERNS, AGENT_NAME_GREETING_PATTERNS, THANKS_PATTERNS


def parseSubtypeSelection(message: str, availableSubTypes: List[str]) -> Optional[str]:
    """
    Parse subtype selection from user message.
    Handles: "2", "PER_DataProtectionOfficer", "Data protection officer", etc.
    
    Args:
        message: User input message
        availableSubTypes: List of available subtype identifiers
    
    Returns:
        Selected subtype identifier or None if no match found
    """
    if not availableSubTypes:
        return None
    
    message = message.strip()
    
    # Try to parse as number (1-based index)
    try:
        num = int(message)
        if 1 <= num <= len(availableSubTypes):
            return availableSubTypes[num - 1]
    except ValueError:
        pass
    
    # Try exact match (case-insensitive)
    message_lower = message.lower()
    for subtype in availableSubTypes:
        if message_lower == subtype.lower():
            return subtype
    
    # Try partial match
    for subtype in availableSubTypes:
        if message_lower in subtype.lower() or subtype.lower() in message_lower:
            return subtype
    
    return None


def checkGreeting(message: str, processedCount: int = 0) -> Optional[str]:
    """
    Check for greeting and return response.
    
    Args:
        message: User message to check
        processedCount: Number of operations processed (for personalized greeting)
    
    Returns:
        Greeting response string or None if not a greeting
    """
    messageLower = message.lower().strip()
    
    if re.match(GREETING_PATTERN, messageLower, re.IGNORECASE):
        if processedCount > 0:
            return f"Hi! I've completed {processedCount} operation(s) and I'm ready to help. What would you like me to do?"
        else:
            return "Hi! I'm ready to help with ISMS operations."
    
    if re.match(THANKS_PATTERN, messageLower, re.IGNORECASE):
        return "You're welcome! Let me know if you need anything else."
    
    return None


def formatTextResponse(text: str) -> str:
    """
    Format text responses using text presenter for better readability.
    
    Args:
        text: Text to format
    
    Returns:
        Formatted text string
    """
    from presenters.text import TextPresenter
    
    if not text or not isinstance(text, str):
        return str(text) if text else ''
    
    presenter = TextPresenter()
    formatted = presenter.present(text)
    return formatted.get('content', str(formatted)) if isinstance(formatted, dict) else formatted


def successResponse(result: Any) -> Dict:
    """
    Create a success response dictionary.
    
    Args:
        result: Result data to include in response
    
    Returns:
        Success response dictionary
    """
    return {'status': 'success', 'result': result, 'type': 'chat_response'}


def errorResponse(message: str) -> Dict:
    """
    Create an error response dictionary.
    
    Args:
        message: Error message
    
    Returns:
        Error response dictionary
    """
    return {'status': 'error', 'result': message, 'type': 'error'}
