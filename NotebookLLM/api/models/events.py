from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
import time

class SSEEvent(BaseModel):
    """
    Server-Sent Event model for streaming updates to the frontend.
    """
    type: str = Field(..., description="Type of the event (e.g., 'thought', 'tool_start', 'tool_complete')")
    data: Dict[str, Any] = Field(..., description="Payload data for the event")
    timestamp: float = Field(default_factory=time.time, description="Timestamp of the event")

    class Config:
        arbitrary_types_allowed = True
