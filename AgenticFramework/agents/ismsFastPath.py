"""
ISMS Fast Path - Tier 1: Deterministic Routing for Simple CRUD Operations

Phase 5: Progressive Agentic Architecture

This module handles simple ISMS operations deterministically:
- List operations (list scopes, list assets, etc.)
- Get operations (get asset X, show scope Y)
- Simple create operations (create asset Name)
- Simple update/delete operations

No LLM calls - direct tool execution for maximum speed and reliability.
"""

import re
import logging
from typing import Dict, Any, Optional, Callable

logger = logging.getLogger(__name__)


class ISMSFastPath:
    """
    Fast Path for simple ISMS operations.
    
    Provides deterministic, fast execution for simple CRUD operations.
    Uses ISMSCoordinator internally for consistency.
    """
    
    def __init__(self, coordinator, event_callback: Optional[Callable] = None):
        """
        Initialize Fast Path.
        
        Args:
            coordinator: ISMSCoordinator instance
            event_callback: Optional callback for event streaming
        """
        self.coordinator = coordinator
        self.event_callback = event_callback
        logger.info("ISMSFastPath initialized")
    
    def execute(self, request: str, context: Dict = None) -> Dict:
        """
        Execute simple ISMS operation deterministically.
        
        Args:
            request: User's request (e.g., "list assets", "get scope MyScope")
            context: Context dictionary (state, session info)
        
        Returns:
            Dict with operation result in MainAgent format:
            {
                'status': 'success' | 'error',
                'result': str,  # Result message
                'type': 'tool_result',
                'data': dict    # Optional operation data
            }
        """
        if context is None:
            context = {}
        
        if 'state' in context:
            self.coordinator.state.update(context['state'])
        
        # Parse request to extract operation and object type
        parsed = self._parse_request(request)
        if not parsed:
            return {
                'status': 'error',
                'result': f"Could not parse request: {request}",
                'type': 'tool_result'
            }
        
        operation = parsed['operation']
        object_type = parsed['object_type']
        message = parsed.get('message', request)
        
        # Emit event for fast path execution
        if self.event_callback:
            self.event_callback('fast_path_start', {
                'operation': operation,
                'object_type': object_type,
                'request': request[:100]
            })
        
        try:
            # Route to coordinator
            if operation in ['create', 'list', 'get', 'view', 'show', 'update', 'delete', 'remove']:
                # Use handleOperation for CRUD operations only
                result = self.coordinator.handleOperation(operation, object_type, message)
                
                # Convert coordinator format to MainAgent format
                return self._format_response(result)
            else:
                return {
                    'status': 'error',
                    'result': f"Unsupported operation in Fast Path: {operation}",
                    'type': 'tool_result'
                }
        except Exception as e:
            logger.error(f"FastPath execution error: {e}", exc_info=True)
            return {
                'status': 'error',
                'result': f"Fast Path execution failed: {str(e)}",
                'type': 'tool_result'
            }
    
    def _parse_request(self, request: str) -> Optional[Dict]:
        """
        Parse simple ISMS request to extract operation and object type.
        
        Args:
            request: User's request
        
        Returns:
            Dict with 'operation', 'object_type', 'message' or None if cannot parse
        """
        request_lower = request.lower().strip()
        
        # Object types
        object_types = [
            'scope', 'scopes', 'asset', 'assets', 'control', 'controls',
            'process', 'processes', 'person', 'persons', 'scenario', 'scenarios',
            'incident', 'incidents', 'document', 'documents', 'domain', 'domains',
            'unit', 'units'
        ]
        
        # Operation patterns
        patterns = [
            # List operations
            (r'^list\s+(\w+)', 'list'),
            # Get/Show/View operations
            (r'^(get|show|view|display)\s+(\w+)\s+(.+)', 'get'),
            (r'^create\s+(\w+)\s+(.+)', 'create'),
            (r'^update\s+(\w+)\s+(.+)', 'update'),
            (r'^(delete|remove)\s+(\w+)\s+(.+)', 'delete'),
        ]
        
        for pattern, op in patterns:
            match = re.match(pattern, request_lower)
            if match:
                groups = match.groups()
                
                if op == 'list':
                    object_type = groups[0]
                    # Normalize plural to singular
                    # Special cases: 'process' -> 'process' (not 'proces'), but 'scopes' -> 'scope'
                    if object_type == 'scopes':
                        object_type = 'scope'
                    elif object_type == 'domains':
                        object_type = 'domain'
                    elif object_type == 'units':
                        object_type = 'unit'
                    elif object_type == 'processes':
                        object_type = 'process'
                    elif object_type.endswith('s'):
                        object_type = object_type[:-1]
                    return {
                        'operation': 'list',
                        'object_type': object_type,
                        'message': request
                    }
                elif op in ['get', 'create', 'update', 'delete']:
                    # For GET/DELETE: groups[0] = operation word ("get"/"delete"), groups[1] = object type, groups[2] = object name
                    # For CREATE/UPDATE: groups[0] = object type, groups[1] = object name
                    if op in ['get', 'delete']:
                        object_type = groups[1] if len(groups) > 1 else None  # groups[1] is object type
                        message = groups[2] if len(groups) > 2 else request  # groups[2] is object name
                    else:  # create, update
                        object_type = groups[0] if len(groups) > 0 else None  # groups[0] is object type
                        message = groups[1] if len(groups) > 1 else request  # groups[1] is object name
                    
                    if not object_type:
                        return None
                    
                    # Normalize plural to singular
                    if object_type == 'scopes':
                        object_type = 'scope'
                    elif object_type == 'domains':
                        object_type = 'domain'
                    elif object_type == 'units':
                        object_type = 'unit'
                    elif object_type == 'processes':
                        object_type = 'process'
                    elif object_type == 'proces':  # Fix typo
                        object_type = 'process'
                    elif object_type.endswith('s'):
                        object_type = object_type[:-1]
                    
                    return {
                        'operation': op,
                        'object_type': object_type,
                        'message': request
                    }
        
        # Fallback: try to detect object type in request
        for obj_type in object_types:
            if obj_type in request_lower:
                # Default to list if no operation specified
                # Normalize plural to singular
                normalized_type = obj_type
                if obj_type == 'scopes':
                    normalized_type = 'scope'
                elif obj_type == 'domains':
                    normalized_type = 'domain'
                elif obj_type == 'units':
                    normalized_type = 'unit'
                elif obj_type == 'processes':
                    normalized_type = 'process'
                elif obj_type.endswith('s'):
                    normalized_type = obj_type[:-1]
                return {
                    'operation': 'list',
                    'object_type': normalized_type,
                    'message': request
                }
        
        return None
    
    def _format_response(self, coordinator_result: Dict) -> Dict:
        """
        Convert coordinator response format to MainAgent format.
        
        Coordinator format: {'type': 'success'|'error', 'text': str, 'data': dict}
        MainAgent format: {'status': 'success'|'error', 'result': str, 'type': 'tool_result', 'data': dict, 'mode': str}
        
        Args:
            coordinator_result: Result from ISMSCoordinator
        
        Returns:
            Formatted response in MainAgent format
        """
        if coordinator_result.get('type') == 'success':
            return {
                'status': 'success',
                'result': coordinator_result.get('text', ''),
                'type': 'tool_result',
                'data': coordinator_result.get('data'),
                'mode': 'fast_path'  # Add mode field
            }
        else:
            return {
                'status': 'error',
                'result': coordinator_result.get('text', 'Unknown error'),
                'type': 'tool_result',
                'error': coordinator_result.get('text', 'Unknown error'),
                'mode': 'fast_path'  # Add mode field
            }
