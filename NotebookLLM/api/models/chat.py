"""Chat request/response models"""
from typing import List, Optional, Union, Dict, Any
from pydantic import BaseModel, Field


class SourceModel(BaseModel):
    """Source model for ISMS objects"""
    id: str = Field(..., description="Source ID")
    type: str = Field(..., description="ISMS object type (scope, asset, control, etc.)")
    name: Optional[str] = Field(None, description="Object name")
    domainId: Optional[str] = Field(..., description="Domain ID (required for ISMS objects)")


class ChatRequest(BaseModel):
    """Chat request model"""
    message: str = Field(..., description="User message")
    sources: Optional[List[SourceModel]] = Field(default=[], description="ISMS object sources")
    sessionId: str = Field(..., description="Session ID")


class ChatResponse(BaseModel):
    """Chat response model"""
    status: str = Field(..., description="Response status")
    result: Optional[Union[str, Dict[str, Any]]] = Field(None, description="Response text or structured data")
    type: Optional[str] = Field(None, description="Response type")
    dataType: Optional[str] = Field(None, description="Data type if result is structured (table, object_detail)")
    error: Optional[str] = Field(None, description="Error message")
    report: Optional[Dict[str, Any]] = Field(None, description="Report data (for report generation responses)")


class ContextRequest(BaseModel):
    """Context request model"""
    source: SourceModel = Field(..., description="Source to add")
    sessionId: str = Field(..., description="Session ID")


class ContextResponse(BaseModel):
    """Context response model"""
    status: str = Field(..., description="Response status")
    sources: List[SourceModel] = Field(default=[], description="Active sources")
    error: Optional[str] = Field(None, description="Error message")
