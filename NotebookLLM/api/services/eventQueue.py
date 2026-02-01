"""Event queue manager for SSE streaming"""
import asyncio
import time
from typing import Dict, List, Optional, Union, Any
from collections import defaultdict
import logging
from ..models.events import SSEEvent

logger = logging.getLogger(__name__)


class EventQueue:
    """
    Thread-safe event queue for SSE streaming.
    Manages events per session and allows async consumption.
    """
    
    def __init__(self):
        # session_id -> asyncio.Queue
        self._queues: Dict[str, asyncio.Queue] = {}
        # session_id -> list of events (for history)
        self._history: Dict[str, List[Dict]] = defaultdict(list)
        self._max_history = 100  # Keep last 100 events per session
        
    def get_queue(self, session_id: str) -> asyncio.Queue:
        """Get or create event queue for a session"""
        if session_id not in self._queues:
            self._queues[session_id] = asyncio.Queue()
        return self._queues[session_id]
    
    def push_event(self, session_id: str, event: Union[Dict[str, Any], SSEEvent]):
        """
        Push an event to the session's queue.
        Validates the event using SSEEvent model.
        
        Args:
            session_id: Session identifier
            event: Event dict or SSEEvent object
        """
        if not session_id:
            logger.warning("Attempted to push event without session_id")
            return
            
        # Validate and convert to dict
        try:
            if isinstance(event, dict):
                # Add timestamp if missing to pass validation if default is relied upon
                if 'timestamp' not in event:
                    event['timestamp'] = time.time()
                event_model = SSEEvent(**event)
                event_dict = event_model.model_dump()
            elif isinstance(event, SSEEvent):
                event_dict = event.model_dump()
            else:
                logger.warning(f"Invalid event type: {type(event)}")
                return
        except Exception as e:
            logger.error(f"Event validation failed: {e}")
            return
            
        queue = self.get_queue(session_id)
        
        self._history[session_id].append(event_dict)
        if len(self._history[session_id]) > self._max_history:
            self._history[session_id].pop(0)
        
        # Push to queue (non-blocking)
        try:
            queue.put_nowait(event_dict)
            logger.debug(f"Pushed event to session {session_id}: {event_dict.get('type')}")
        except asyncio.QueueFull:
            logger.warning(f"Event queue full for session {session_id}, dropping event")
    
    async def get_event(self, session_id: str, timeout: Optional[float] = None) -> Optional[Dict]:
        """
        Get next event from queue (async, blocking).
        
        Args:
            session_id: Session identifier
            timeout: Optional timeout in seconds
            
        Returns:
            Event dict or None if timeout
        """
        queue = self.get_queue(session_id)
        try:
            if timeout:
                event = await asyncio.wait_for(queue.get(), timeout=timeout)
            else:
                event = await queue.get()
            return event
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            logger.error(f"Error getting event for session {session_id}: {e}")
            return None
    
    def get_history(self, session_id: str) -> List[Dict]:
        """Get event history for a session"""
        return self._history.get(session_id, []).copy()
    
    def clear_history(self, session_id: str):
        """Clear event history for a session"""
        if session_id in self._history:
            self._history[session_id].clear()
    
    def cleanup(self, session_id: str):
        """Clean up resources for a session"""
        if session_id in self._queues:
            del self._queues[session_id]
        if session_id in self._history:
            del self._history[session_id]


# Global singleton instance
_event_queue = EventQueue()


def get_event_queue() -> EventQueue:
    """Get the global event queue instance"""
    return _event_queue
