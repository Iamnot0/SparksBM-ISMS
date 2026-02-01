"""
MCP Linking Tools - Link and unlink ISMS objects

Uses VeriniceTool for actual API operations.
Handles intelligent name resolution and bulk linking.
"""

from typing import Dict, Optional
import logging
import re
from agents.instructions import get_error_message

logger = logging.getLogger(__name__)


# ==================== HELPER FUNCTIONS (defined first for use by other functions) ====================

def _resolve_object_id(verinice_tool, domain_id: str, object_type: str, name_or_id: str, retry_count: int = 0) -> Optional[str]:
    """Resolve object name to ID - handles typos and variations"""
    if not name_or_id:
        return None
    
    uuid_match = re.search(r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})', name_or_id, re.IGNORECASE)
    if uuid_match:
        # If it's a UUID, verify it exists by trying to get it directly
        object_id = uuid_match.group(1)
        get_result = verinice_tool.getObject(object_type, domain_id, object_id)
        if get_result.get('success'):
            return object_id
        # If get fails, it might not exist yet (newly created), return None to trigger retry
        return None
    
    # Search by name (exact match first)
    list_result = verinice_tool.listObjects(object_type, domain_id)
    if not list_result.get('success'):
        # Try unit-level search for scopes
        if object_type == 'scope':
            units_result = verinice_tool.listUnits()
            if units_result.get('success') and units_result.get('units'):
                for unit in units_result.get('units', []):
                    if isinstance(unit, dict):
                        scopes = unit.get('scopes', [])
                        if isinstance(scopes, list):
                            for scope in scopes:
                                if isinstance(scope, dict):
                                    scope_name = scope.get('name', '').strip()
                                    if scope_name.lower() == name_or_id.lower():
                                        return scope.get('id') or scope.get('resourceId')
        # If list failed and we haven't retried, try once more after a brief delay
        if retry_count < 2:  # Retry up to 2 times
            import time
            time.sleep(1.0)  # Increased delay for newly created objects to appear
            return _resolve_object_id(verinice_tool, domain_id, object_type, name_or_id, retry_count=retry_count+1)
        return None
    
    objects = list_result.get('objects', {}).get('items', [])
    if not isinstance(objects, list):
        # If no objects and we haven't retried, try once more after a brief delay
        if retry_count < 2:
            import time
            time.sleep(1.0)
            return _resolve_object_id(verinice_tool, domain_id, object_type, name_or_id, retry_count=retry_count+1)
        return None
    
    name_lower = name_or_id.lower().strip()
    
    # First try exact match
    for obj in objects:
        if isinstance(obj, dict):
            obj_name = obj.get('name', '').strip()
            if obj_name.lower() == name_lower:
                return obj.get('id') or obj.get('resourceId')
    
    # Then try fuzzy match (handles typos and pluralization)
    # Improved matching: handles "Databases Server" vs "Database Server"
    best_match = None
    best_score = 0
    for obj in objects:
        if isinstance(obj, dict):
            obj_name = obj.get('name', '').strip().lower()
            
            # Exact match after normalization (remove common pluralization differences)
            name_normalized = name_lower.replace('s ', ' ').replace('s-', '-').rstrip('s')
            obj_name_normalized = obj_name.replace('s ', ' ').replace('s-', '-').rstrip('s')
            
            if name_normalized == obj_name_normalized:
                return obj.get('id') or obj.get('resourceId')
            
            # Calculate similarity (simple character overlap)
            if name_lower in obj_name or obj_name in name_lower:
                score = len(set(name_lower) & set(obj_name))
                if score > best_score:
                    best_score = score
                    best_match = obj
            # Also check normalized versions
            elif name_normalized in obj_name_normalized or obj_name_normalized in name_normalized:
                score = len(set(name_normalized) & set(obj_name_normalized))
                if score > best_score:
                    best_score = score
                    best_match = obj
    
    if best_match:
        return best_match.get('id') or best_match.get('resourceId')
    
    # If not found and we haven't retried, try once more after a brief delay (for newly created objects)
    if retry_count == 0:
        import time
        time.sleep(0.5)  # Brief delay for newly created objects to appear in list
        return _resolve_object_id(verinice_tool, domain_id, object_type, name_or_id, retry_count=1)
    
    return None


def _get_object_name(verinice_tool, domain_id: str, object_type: str, object_id: str) -> str:
    """Get object name from ID"""
    get_result = verinice_tool.getObject(object_type, domain_id, object_id)
    if get_result.get('success') and get_result.get('data'):
        obj = get_result.get('data', {})
        if isinstance(obj, dict):
            return obj.get('name', object_id[:8] + '...')
    return object_id[:8] + '...'


def _get_defaults(verinice_tool) -> tuple:
    """Get default domain and unit IDs"""
    # Try units first
    units_result = verinice_tool.listUnits()
    if units_result.get('success') and units_result.get('units'):
        units = units_result.get('units', [])
        if units and isinstance(units, list) and len(units) > 0:
            unit = units[0]
            unit_id = unit.get('id')
            domains = unit.get('domains', [])
            if domains and isinstance(domains, list) and len(domains) > 0:
                domain_id = domains[0].get('id') if isinstance(domains[0], dict) else domains[0]
                if domain_id:
                    return domain_id, unit_id
    
    # Fallback to domains
    domains_result = verinice_tool.listDomains()
    if domains_result.get('success') and domains_result.get('domains'):
        domains = domains_result.get('domains', [])
        if domains and isinstance(domains, list) and len(domains) > 0:
            domain_id = domains[0].get('id')
            return domain_id, None
    
    return None, None


def _detect_object_types(verinice_tool, domain_id: str, source_name: str, target_name: str) -> Dict:
    """Auto-detect object types by searching"""
    detected = {}
    
    # Try to find source
    object_types = ['scope', 'asset', 'person', 'process', 'control', 'scenario', 'document']
    for obj_type in object_types:
        obj_id = _resolve_object_id(verinice_tool, domain_id, obj_type, source_name)
        if obj_id:
            detected['source_type'] = obj_type
            break
    
    # Try to find target
    for obj_type in object_types:
        if target_name:
            obj_id = _resolve_object_id(verinice_tool, domain_id, obj_type, target_name)
            if obj_id:
                detected['target_type'] = obj_type
                break
    
    return detected


# ==================== MAIN FUNCTIONS ====================

def link_objects(
    verinice_tool,
    state: Dict,
    source_type: Optional[str] = None,
    source_name: str = None,
    target_type: Optional[str] = None,
    target_name: Optional[str] = None,
    subtype: Optional[str] = None,
    domain_id: Optional[str] = None
) -> Dict:
    """
    Link ISMS objects together.
    
    Supports multiple formats:
    - Single object to scope: "link Desktop to SCOPE1"
    - Scope to multiple objects by subtype: "link SCOPE1 with IT-System assets"
    - Scope to all objects of a type: "link SCOPE1 with assets"
    
    Args:
        verinice_tool: VeriniceTool instance
        state: Agent state dictionary
        source_type: Type of source object (scope, asset, etc.)
        source_name: Name or ID of source object
        target_type: Type of target object
        target_name: Name or ID of target object (None for bulk linking)
        subtype: Optional subtype filter (e.g., "IT-System" for assets)
        domain_id: Optional domain ID (will be resolved if not provided)
    
    Returns:
        Dict with success/error response
    """
    try:
        # Resolve domain if not provided
        if not domain_id:
            domain_id, _ = _get_defaults(verinice_tool)
            if not domain_id:
                return {'success': False, 'error': get_error_message('not_found', 'domain')}
        
        # Auto-detect types if not provided - handle bidirectional linking
        if not source_type or not target_type:
            detected = _detect_object_types(verinice_tool, domain_id, source_name, target_name)
            source_type = source_type or detected.get('source_type')
            target_type = target_type or detected.get('target_type')
        
        # CRITICAL: Verinice linking constraints
        # ONLY Scope can be linked to other objects (and vice versa)
        # Direct object-to-object linking (e.g., person-to-asset, scenario-to-document) is NOT supported
        # Valid relationships: Scope ↔ X (where X is any object type)
        # Invalid relationships: X ↔ Y (where both X and Y are non-scope objects)
        if source_type and target_type:
            if source_type != 'scope' and target_type != 'scope':
                # This is invalid - suggest linking both to a scope instead
                return {
                    'success': False,
                    'error': f"Cannot directly link {source_type} to {target_type}. In Verinice, only Scope can be linked to other objects.\n\nTo link these objects:\n1. Link '{source_name}' to a scope\n2. Link '{target_name}' to the same scope\n\nThis way both objects will be associated through the scope."
                }
        
        # Bidirectional linking: If one is scope and other is not, scope is always the container
        # Normalize: scope should be source, object should be target
        if source_type and target_type:
            if source_type == 'scope' and target_type != 'scope':
                # Already correct: scope → object
                pass
            elif target_type == 'scope' and source_type != 'scope':
                # Reverse: object → scope, so swap them
                source_type, target_type = target_type, source_type
                source_name, target_name = target_name, source_name
            elif source_type != 'scope' and target_type != 'scope':
                # Neither is scope - try to find which one exists as scope
                source_as_scope = _resolve_object_id(verinice_tool, domain_id, 'scope', source_name)
                target_as_scope = _resolve_object_id(verinice_tool, domain_id, 'scope', target_name)
                if target_as_scope and not source_as_scope:
                    # Target is scope, swap
                    source_type, target_type = target_type, source_type
                    source_name, target_name = target_name, source_name
        
        # Resolve source object ID (try both types if needed)
        # First check if source_name is already a UUID - if so, use it directly
        source_id = None
        uuid_match = re.search(r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})', source_name or '', re.IGNORECASE)
        if uuid_match:
            # It's a UUID - use it directly (trust it's valid if passed from create operation)
            potential_id = uuid_match.group(1)
            # For newly created objects, we trust the ID is valid
            # Only verify if we have source_type, but don't fail if verification fails (timing issues)
            if source_type:
                # Try to verify, but don't fail if it doesn't work (newly created objects)
                get_result = verinice_tool.getObject(source_type, domain_id, potential_id)
                if get_result.get('success'):
                    source_id = potential_id
                else:
                    # Verification failed, but trust the ID anyway (newly created objects may not be immediately available)
                    # The actual linking operation will fail gracefully if the ID is truly invalid
                    source_id = potential_id
            else:
                # No source_type specified, try common types but don't require success
                found_type = False
                for obj_type in ['scope', 'asset', 'person', 'control']:
                    get_result = verinice_tool.getObject(obj_type, domain_id, potential_id)
                    if get_result.get('success'):
                        source_id = potential_id
                        source_type = obj_type
                        found_type = True
                        break
                # If none found but we have a UUID, use it anyway (might be newly created)
                if not found_type:
                    source_id = potential_id
                    # Default to scope if no type detected (most common case)
                    source_type = source_type or 'scope'
        
        # If not a UUID or UUID verification failed, resolve by name
        if not source_id:
            if source_type:
                source_id = _resolve_object_id(verinice_tool, domain_id, source_type, source_name)
            if not source_id and source_name:
                # Try reverse: maybe source_name is actually the target
                source_id = _resolve_object_id(verinice_tool, domain_id, 'scope', source_name)
                if source_id:
                    # Found as scope, so swap
                    if target_type and target_type != 'scope':
                        source_type, target_type = 'scope', target_type
                        source_name, target_name = target_name, source_name
                    else:
                        source_type = 'scope'
        
        if not source_id:
            return {'success': False, 'error': get_error_message('not_found', 'object_by_name_check', name=source_name)}
        
        if not target_name and target_type:
            return _link_bulk_objects(
                verinice_tool, domain_id, source_type, source_id, target_type, subtype
            )
        
        if target_name:
            target_id = _resolve_object_id(verinice_tool, domain_id, target_type, target_name)
            if not target_id:
                # Common asset subtypes: IT-System, Datatype, Application, etc.
                common_subtypes = ['IT-System', 'IT System', 'Datatype', 'Data Type', 'Application', 'Process', 'Service']
                if any(subtype.lower() in target_name.lower() or target_name.lower() in subtype.lower() for subtype in common_subtypes):
                    # It might be a subtype - suggest bulk linking
                    return {
                        'success': False, 
                        'error': get_error_message('validation', 'subtype_appears_to_be_subtype', targetType=target_type, targetName=target_name)
                    }
                return {'success': False, 'error': get_error_message('not_found', 'object_by_name', objectType=target_type, name=target_name)}
            
            result = _link_single_object(
                verinice_tool, domain_id, source_type, source_id, target_type, target_id
            )
            # Enhance response message with context-aware, friendly language
            # CRITICAL: Check for Verinice linking constraints
            if not result.get('success'):
                error_msg = result.get('error', '')
                error_detail = error_msg
                
                if 'cannot be parts of' in error_msg.lower() or 'cannot be members of' in error_msg.lower():
                    if source_type != 'scope' and target_type != 'scope':
                        return {
                            'success': False,
                            'error': f"Cannot directly link {source_type} to {target_type}. In Verinice, only Scope can be linked to other objects.\n\nTo link these objects:\n1. Link '{source_name}' to a scope\n2. Link '{target_name}' to the same scope\n\nThis way both objects will be associated through the scope."
                        }
                    else:
                        # One is scope, but still failed - provide specific error
                        return {
                            'success': False,
                            'error': f"Linking constraint: {error_detail}. This relationship may not be supported in Verinice. Valid relationships:\n  • Scopes can contain: assets, controls, persons, processes, scenarios, documents, incidents\n  • Objects can be linked to scopes (not directly to each other)"
                        }
            
            if result.get('success'):
                source_obj = _get_object_name(verinice_tool, domain_id, source_type, source_id)
                target_obj = _get_object_name(verinice_tool, domain_id, target_type, target_id)
                
                # Context-aware friendly messages based on object types
                # Note: Only scope-based relationships are valid
                if source_type == 'scope' and target_type == 'asset':
                    result['message'] = f"✅ Added {target_obj} to {source_obj}. The asset is now part of this scope."
                elif source_type == 'scope' and target_type == 'person':
                    result['message'] = f"✅ Assigned {target_obj} to {source_obj}. The person is now associated with this scope."
                elif source_type == 'scope' and target_type == 'control':
                    result['message'] = f"✅ Linked {target_obj} to {source_obj}. The control is now part of this scope."
                elif source_type == 'scope' and target_type == 'process':
                    result['message'] = f"✅ Linked {target_obj} to {source_obj}. The process is now part of this scope."
                elif source_type == 'scope' and target_type == 'scenario':
                    result['message'] = f"✅ Linked {target_obj} to {source_obj}. The scenario is now part of this scope."
                elif source_type == 'scope' and target_type == 'document':
                    result['message'] = f"✅ Linked {target_obj} to {source_obj}. The document is now part of this scope."
                elif source_type == 'scope' and target_type == 'incident':
                    result['message'] = f"✅ Linked {target_obj} to {source_obj}. The incident is now part of this scope."
                elif source_type == 'asset' and target_type == 'scope':
                    result['message'] = f"✅ Added {source_obj} to {target_obj}. The asset is now part of this scope."
                elif source_type == 'person' and target_type == 'scope':
                    result['message'] = f"✅ Assigned {source_obj} to {target_obj}. The person is now associated with this scope."
                elif source_type == 'control' and target_type == 'scope':
                    result['message'] = f"✅ Linked {source_obj} to {target_obj}. The control is now part of this scope."
                elif source_type == 'process' and target_type == 'scope':
                    result['message'] = f"✅ Linked {source_obj} to {target_obj}. The process is now part of this scope."
                elif source_type == 'scenario' and target_type == 'scope':
                    result['message'] = f"✅ Linked {source_obj} to {target_obj}. The scenario is now part of this scope."
                elif source_type == 'document' and target_type == 'scope':
                    result['message'] = f"✅ Linked {source_obj} to {target_obj}. The document is now part of this scope."
                elif source_type == 'incident' and target_type == 'scope':
                    result['message'] = f"✅ Linked {source_obj} to {target_obj}. The incident is now part of this scope."
                else:
                    result['message'] = f"✅ Successfully linked {source_obj} to {target_obj}."
            return result
        
        return {'success': False, 'error': get_error_message('validation', 'missing_target_info')}
        
    except Exception as e:
        logger.error(f"Link objects error: {e}", exc_info=True)
        return {'success': False, 'error': get_error_message('operation_failed', 'linking_failed', error=str(e))}


def unlink_objects(
    verinice_tool,
    state: Dict,
    source_type: Optional[str] = None,
    source_name: str = None,
    target_type: Optional[str] = None,
    target_name: str = None,
    domain_id: Optional[str] = None
) -> Dict:
    """
    Unlink ISMS objects.
    
    Args:
        verinice_tool: VeriniceTool instance
        state: Agent state dictionary
        source_type: Type of source object
        source_name: Name or ID of source object
        target_type: Type of target object
        target_name: Name or ID of target object
        domain_id: Optional domain ID
    
    Returns:
        Dict with success/error response
    """
    try:
        if not domain_id:
            domain_id, _ = _get_defaults(verinice_tool)
            if not domain_id:
                return {'success': False, 'error': get_error_message('not_found', 'domain')}
        
        # Resolve object IDs
        source_id = _resolve_object_id(verinice_tool, domain_id, source_type or 'scope', source_name)
        if not source_id:
            return {'success': False, 'error': get_error_message('not_found', 'source_object', sourceName=source_name)}
        
        target_id = _resolve_object_id(verinice_tool, domain_id, target_type or 'asset', target_name)
        if not target_id:
            return {'success': False, 'error': get_error_message('not_found', 'target_object', targetName=target_name)}
        
        get_result = verinice_tool.getObject(source_type or 'scope', domain_id, source_id)
        if not get_result.get('success'):
            return {'success': False, 'error': get_error_message('operation_failed', 'get_source_object', error=get_result.get('error'))}
        
        source_obj = get_result.get('data', {})
        if not isinstance(source_obj, dict):
            return {'success': False, 'error': get_error_message('validation', 'invalid_source_object_data')}
        
        if source_type == 'scope':
            members = source_obj.get('members', [])
        elif source_type == 'scenario':
            members = source_obj.get('parts', [])
        else:
            members = source_obj.get('parts', [])
        if not isinstance(members, list):
            members = []
        
        # Filter out the target
        filtered_members = [
            m for m in members
            if isinstance(m, dict) and m.get('id') != target_id
            and not (m.get('targetUri', '').endswith(f'/{target_id}'))
        ]
        
        if source_type == 'scope':
            update_data = {'members': filtered_members}
        elif source_type == 'scenario':
            update_data = {'parts': filtered_members}
        else:
            update_data = {'parts': filtered_members}
        update_result = verinice_tool.updateObject(source_type or 'scope', domain_id, source_id, update_data)
        
        if update_result.get('success'):
            return {
                'success': True,
                'message': f"Successfully unlinked '{target_name}' from '{source_name}'"
            }
        else:
            return {'success': False, 'error': get_error_message('operation_failed', 'unlink_objects', error=update_result.get('error'))}
            
    except Exception as e:
        logger.error(f"Unlink objects error: {e}", exc_info=True)
        return {'success': False, 'error': get_error_message('operation_failed', 'unlinking_failed', error=str(e))}


def _link_single_object(
    verinice_tool,
    domain_id: str,
    source_type: str,
    source_id: str,
    target_type: str,
    target_id: str
) -> Dict:
    """Link a single object to a source (typically scope)"""
    get_result = verinice_tool.getObject(source_type, domain_id, source_id)
    if not get_result.get('success'):
        return {'success': False, 'error': get_error_message('operation_failed', 'get_source_object', error=get_result.get('error'))}
    
    source_obj = get_result.get('data', {})
    if not isinstance(source_obj, dict):
        return {'success': False, 'error': get_error_message('validation', 'invalid_source_object_data')}
    
    # Prepare members/parts array
    # CRITICAL: Scenarios use 'parts' not 'members', and some relationships are reversed
    # For asset → scenario: add scenario to asset's parts
    # For scenario → asset: add asset to scenario's parts (but this may fail due to constraints)
    if source_type == 'scenario':
        members_key = 'parts'  # Scenarios use 'parts'
    elif source_type == 'scope':
        members_key = 'members'  # Scopes use 'members'
    else:
        members_key = 'parts'  # Other types use 'parts'
    
    members = source_obj.get(members_key, [])
    if not isinstance(members, list):
        members = []
    
    already_linked = any(
        isinstance(m, dict) and (m.get('id') == target_id or m.get('targetUri', '').endswith(f'/{target_id}'))
        for m in members
    )
    
    if already_linked:
        source_name = _get_object_name(verinice_tool, domain_id, source_type, source_id)
        target_name = _get_object_name(verinice_tool, domain_id, target_type, target_id)
        return {
            'success': True, 
            'message': f"✅ {target_name} is already part of {source_name}. No changes needed."
        }
    
    from config.settings import Settings
    API_URL = Settings.VERINICE_API_URL
    plural = verinice_tool.OBJECT_TYPES.get(target_type.lower(), f"{target_type}s")
    
    members.append({
        'targetUri': f'{API_URL}/{plural}/{target_id}',
        'id': target_id
    })
    
    update_data = {members_key: members}
    update_result = verinice_tool.updateObject(source_type, domain_id, source_id, update_data)
    
    if update_result.get('success'):
        # Message is already set in link_objects function with context-aware language
        return {'success': True}
    else:
        error_msg = update_result.get('error', 'Unknown error')
        return {'success': False, 'error': get_error_message('operation_failed', 'link_objects', error=error_msg)}


def _link_bulk_objects(
    verinice_tool,
    domain_id: str,
    source_type: str,
    source_id: str,
    target_type: str,
    subtype: Optional[str] = None
) -> Dict:
    """Link multiple objects to a source (typically scope) by type and optional subtype"""
    logger.info(f"[_link_bulk_objects] Linking {target_type}s to {source_type} '{source_id}' in domain '{domain_id}'" + (f" with subtype '{subtype}'" if subtype else ""))
    
    # List target objects - CRITICAL: Use the same domain_id that was used for creation
    list_result = verinice_tool.listObjects(target_type, domain_id)
    if not list_result.get('success'):
        error_detail = list_result.get('error', 'Unknown error')
        logger.error(f"[_link_bulk_objects] Failed to list {target_type}s in domain '{domain_id}': {error_detail}")
        return {'success': False, 'error': get_error_message('operation_failed', 'list_objects', objectType=target_type, error=f'Failed to list: {error_detail}')}
    
    objects = list_result.get('objects', {}).get('items', [])
    if not isinstance(objects, list):
        objects = []
    
    # Fallback: Check unit if no objects found in domain
    if not objects:
        _, unit_id = _get_defaults(verinice_tool)
        if unit_id:
            logger.info(f"[_link_bulk_objects] No objects in domain, checking unit '{unit_id}'")
            unit_result = verinice_tool.listObjects(target_type, None, unitId=unit_id)
            if unit_result.get('success'):
                unit_objects = unit_result.get('objects', {}).get('items', [])
                if isinstance(unit_objects, list):
                    objects = unit_objects
                    logger.info(f"[_link_bulk_objects] Found {len(objects)} {target_type}(s) in unit '{unit_id}'")

    if not isinstance(objects, list):
        logger.warning(f"[_link_bulk_objects] No {target_type}s found in domain '{domain_id}' (result was not a list)")
        return {'success': False, 'error': get_error_message('not_found', 'no_objects_found', targetType=target_type)}
    
    logger.info(f"[_link_bulk_objects] Found {len(objects)} {target_type}(s) in domain '{domain_id}' before filtering")
    
    # DEBUG: Log all found objects and their subtypes
    for i, obj in enumerate(objects):
        if isinstance(obj, dict):
            logger.info(f"[_link_bulk_objects] Object {i}: name='{obj.get('name')}', subType='{obj.get('subType')}'")

    # Filter by subtype if specified
    if subtype:
        filtered = []
        subtype_normalized = subtype.lower().replace('-', '').replace('_', '').replace(' ', '')
        logger.error(f"[_link_bulk_objects] DEBUG: Filtering by subtype '{subtype}' (normalized: '{subtype_normalized}')")
        
        # Also normalize common subtype variations
        # Map user-friendly names to technical IDs
        subtype_mappings = {
            'itsystem': ['ast_itsystem', 'itsystem', 'it_system', 'it-system'],
            'itsystems': ['ast_itsystem', 'itsystem', 'it_system', 'it-system'],
            'datatype': ['ast_datatype', 'datatype', 'data_type'],
            'datatypes': ['ast_datatype', 'datatype', 'data_type'],
            'application': ['ast_application', 'application'],
            'applications': ['ast_application', 'application'],
        }
        
        possible_matches = [subtype_normalized]
        if subtype_normalized in subtype_mappings:
            possible_matches.extend(subtype_mappings[subtype_normalized])
        
        logger.error(f"[_link_bulk_objects] DEBUG: Possible matches: {possible_matches}")
        
        for obj in objects:
            if isinstance(obj, dict):
                obj_subtype = obj.get('subType', '')
                if obj_subtype:
                    obj_subtype_normalized = obj_subtype.lower().replace('-', '').replace('_', '').replace(' ', '')
                    logger.error(f"[_link_bulk_objects] DEBUG: Checking object '{obj.get('name')}' subtype '{obj_subtype}' (norm: '{obj_subtype_normalized}')")
                    
                    matches = False
                    for possible_match in possible_matches:
                        if possible_match in obj_subtype_normalized or obj_subtype_normalized in possible_match:
                            matches = True
                            break
                    
                    # Also check if subtype without prefix matches (e.g., "IT-System" matches "AST_IT-System")
                    if not matches:
                        obj_subtype_no_prefix = obj_subtype
                        for prefix in ['AST_', 'SCP_', 'PER_', 'CTL_', 'PRO_', 'INC_', 'DOC_', 'SCN_']:
                            if obj_subtype_no_prefix.startswith(prefix):
                                obj_subtype_no_prefix = obj_subtype_no_prefix[len(prefix):]
                                break
                        obj_subtype_no_prefix_normalized = obj_subtype_no_prefix.lower().replace('-', '').replace('_', '').replace(' ', '')
                        if subtype_normalized in obj_subtype_no_prefix_normalized or obj_subtype_no_prefix_normalized in subtype_normalized:
                            matches = True
                    
                    if matches:
                        filtered.append(obj)
                    else:
                        logger.error(f"[_link_bulk_objects] DEBUG: No match for '{obj.get('name')}'")
        objects = filtered
        logger.info(f"[_link_bulk_objects] After filtering by subtype '{subtype}': {len(objects)} {target_type}(s) found")
    
    if not objects:
        if subtype:
            return {'success': False, 'error': f"No {subtype} {target_type}s found in the domain to link. You may need to create {target_type}s with subtype '{subtype}' first."}
        else:
            return {'success': False, 'error': f"No {target_type}s found in the domain to link"}
    
    # Log which objects were found (for better user feedback)
    found_names = [obj.get('name', 'N/A') for obj in objects[:5]]  # First 5 names
    if len(objects) > 5:
        found_names.append(f"... and {len(objects) - 5} more")
    
    get_result = verinice_tool.getObject(source_type, domain_id, source_id)
    if not get_result.get('success'):
        return {'success': False, 'error': get_error_message('operation_failed', 'get_source_object', error=get_result.get('error'))}
    
    source_obj = get_result.get('data', {})
    if not isinstance(source_obj, dict):
        return {'success': False, 'error': get_error_message('validation', 'invalid_source_object_data')}
    
    # Prepare members array
    members_key = 'members' if source_type == 'scope' else 'parts'
    members = source_obj.get(members_key, [])
    if not isinstance(members, list):
        members = []
    
    from config.settings import Settings
    API_URL = Settings.VERINICE_API_URL
    plural = verinice_tool.OBJECT_TYPES.get(target_type.lower(), f"{target_type}s")
    
    linked_count = 0
    linked_names = []
    for obj in objects:
        if isinstance(obj, dict):
            obj_id = obj.get('id') or obj.get('resourceId')
            obj_name = obj.get('name', 'N/A')
            if obj_id:
                already_linked = any(
                    isinstance(m, dict) and (m.get('id') == obj_id or m.get('targetUri', '').endswith(f'/{obj_id}'))
                    for m in members
                )
                if not already_linked:
                    members.append({
                        'targetUri': f'{API_URL}/{plural}/{obj_id}',
                        'id': obj_id
                    })
                    linked_count += 1
                    linked_names.append(obj_name)
    
    if linked_count == 0:
        subtype_msg = f" {subtype}" if subtype else ""
        source_name = _get_object_name(verinice_tool, domain_id, source_type, source_id)
        return {
            'success': True, 
            'message': f"✅ All{subtype_msg} {target_type}s are already part of {source_name}. No changes needed."
        }
    
    update_data = {members_key: members}
    update_result = verinice_tool.updateObject(source_type, domain_id, source_id, update_data)
    
    if update_result.get('success'):
        source_name = _get_object_name(verinice_tool, domain_id, source_type, source_id)
        subtype_msg = f" {subtype}" if subtype else ""
        if linked_count == 1:
            return {
                'success': True,
                'message': f"✅ Added {linked_names[0]} to {source_name}. The {target_type} is now part of this scope."
            }
        else:
            # Show which assets were found and linked
            names_list = ', '.join(linked_names[:5])
            if len(linked_names) > 5:
                names_list += f" and {len(linked_names) - 5} more"
            subtype_info = f" ({subtype} subtype)" if subtype else ""
            return {
                'success': True,
                'message': f"✅ Linked {linked_count} {target_type}(s){subtype_info} to {source_name}:\n  • {names_list}"
            }
    else:
        error_msg = update_result.get('error', 'Unknown error')
        return {'success': False, 'error': get_error_message('operation_failed', 'link_targets', targetType=target_type, error=error_msg)}


def _detect_object_types(verinice_tool, domain_id: str, source_name: str, target_name: str) -> Dict:
    """Auto-detect object types by searching"""
    detected = {}
    
    # Try to find source
    object_types = ['scope', 'asset', 'person', 'process', 'control', 'scenario', 'document']
    for obj_type in object_types:
        obj_id = _resolve_object_id(verinice_tool, domain_id, obj_type, source_name)
        if obj_id:
            detected['source_type'] = obj_type
            break
    
    # Try to find target
    for obj_type in object_types:
        if target_name:
            obj_id = _resolve_object_id(verinice_tool, domain_id, obj_type, target_name)
            if obj_id:
                detected['target_type'] = obj_type
                break
    
    return detected


def _get_defaults(verinice_tool) -> tuple:
    """Get default domain and unit IDs"""
    # Try units first
    units_result = verinice_tool.listUnits()
    if units_result.get('success') and units_result.get('units'):
        units = units_result.get('units', [])
        if units and isinstance(units, list) and len(units) > 0:
            unit = units[0]
            unit_id = unit.get('id')
            domains = unit.get('domains', [])
            if domains and isinstance(domains, list) and len(domains) > 0:
                domain_id = domains[0].get('id') if isinstance(domains[0], dict) else domains[0]
                if domain_id:
                    return domain_id, unit_id
    
    # Fallback to domains
    domains_result = verinice_tool.listDomains()
    if domains_result.get('success') and domains_result.get('domains'):
        domains = domains_result.get('domains', [])
        if domains and isinstance(domains, list) and len(domains) > 0:
            domain_id = domains[0].get('id')
            return domain_id, None
    
    return None, None
