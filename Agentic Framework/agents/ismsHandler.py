"""Simplified ISMS operation handler - clean, robust, maintainable"""
from typing import Dict, Optional, List, Any
import re
import json
import time
import logging
from .instructions import get_error_message

logger = logging.getLogger(__name__)


class ISMSHandler:
    """Handles all ISMS operations with clean, simple logic"""
    
    def __init__(self, veriniceTool, formatFunc, llmTool=None, event_callback=None):
        self.veriniceTool = veriniceTool
        self.formatResult = formatFunc
        self.llmTool = llmTool  # Optional LLM for intelligent parsing
        self.event_callback = event_callback  # Callback for SSE event streaming
        self._domainCache = None
        self._unitCache = None
        self.state = {}  # State for storing pending operations
    
    def _emit_event(self, event_type: str, data: Dict[str, Any]):
        """Emit event via callback if available"""
        if self.event_callback:
            self.event_callback(event_type, data)
    
    def _emit_thought(self, step_type: str, content: str, metadata: Dict = None):
        """Emit a reasoning step to the frontend via event callback"""
        if self.event_callback:
            self.event_callback(step_type, {
                'content': content,
                **(metadata or {})
            })
    
    def execute(self, operation: str, objectType: str, message: str, preDetectedSubType: Optional[str] = None, subtypeFilter: Optional[str] = None) -> Dict:
        """
        Execute Verinice operation with auto-detection
        
        Single entry point for all operations - simple dispatch
        
        Args:
            operation: Operation type (create, list, get, etc.)
            objectType: Object type (scope, asset, etc.)
            message: User's original message
            preDetectedSubType: Optional subtype detected by router (e.g., "Controllers" from "create Controllers named X")
            subtypeFilter: Optional subtype filter for list operations (e.g., "IT-System" for filtering assets)
        """
        domainId, unitId = self._getDefaults()
        
        # Allow listing scopes without domain (scopes can be listed at unit level)
        # Allow listing domains without requiring a domain
        requiresDomain = operation != 'list_domains' and not (operation == 'list' and objectType == 'scope')
        
        if not domainId and requiresDomain:
            return self._error(get_error_message('not_found', 'domain'))
        
        # Dispatch to operation handler
        handlers = {
            'create': self._handleCreate,
            'list': self._handleList,
            'get': self._handleGet,
            'view': self._handleGet,  # view = get
            'update': self._handleUpdate,
            'delete': self._handleDelete,
            'analyze': self._handleAnalyze,
            'compare': self._handleCompare
        }
        
        handler = handlers.get(operation)
        if not handler:
            return self._error(get_error_message('validation', 'unknown_operation', operation=operation))
        
        # Pass preDetectedSubType to create handler
        if operation == 'create' and preDetectedSubType:
            return handler(objectType, message, domainId, unitId, preDetectedSubType)
        
        # Pass returnSubtype flag to get handler (from command dict)
        if operation == 'get' and hasattr(self, 'state') and self.state.get('_returnSubtype'):
            returnSubtype = self.state.get('_returnSubtype')
            del self.state['_returnSubtype']  # Clear flag after use
            return handler(objectType, message, domainId, unitId, returnSubtype)
        
        # For list operation, pass subtypeFilter if provided
        if operation == 'list' and subtypeFilter:
            return handler(objectType, message, domainId, unitId, subtypeFilter)
        
        # Special handling for compare - needs to extract two object names
        if operation == 'compare':
            return handler(objectType, message, domainId, unitId)
        
        return handler(objectType, message, domainId, unitId)
    
    # ==================== OPERATION HANDLERS ====================
    
    def _handleCreate(self, objectType: str, message: str, domainId: str, unitId: str, preDetectedSubType: Optional[str] = None) -> Dict:
        """Create operation - simple and efficient"""
        # Emit thought: Starting create operation
        self._emit_thought('thought', f"Creating {objectType}...")
        
        # CRITICAL: Check if VeriniceTool is available and authenticated
        if not self.veriniceTool:
            self._emit_thought('error', "ISMS client not available")
            return self._error(get_error_message('connection', 'isms_client_not_available'))
        
        # Ensure authentication before proceeding
        if not self.veriniceTool._ensureAuthenticated():
            self._emit_thought('error', "ISMS client not available")
            return self._error(get_error_message('connection', 'isms_init_failed', error='ISMS client not available'))
        
        # CRITICAL: Handle period-separated commands FIRST (e.g., "Create person 'John'.assign his role to 'DPO'")
        # Pattern: sentence ending with period, followed by lowercase action word
        period_sep_pattern = r'([^\.]+\.)\s*([a-z][^\.]+?)(?:\.|$)'
        period_match = re.search(period_sep_pattern, message, re.IGNORECASE)
        if period_match:
            # Split into two parts
            first_part = period_match.group(1).rstrip('.').strip()
            second_part = period_match.group(2).strip()
            
            # Extract name from first part (before period)
            name = self._extractName(first_part, objectType)
            if name:
                # Extract subtype from second part (after period) - handles "assign his role to 'DPO'"
                subType = self._extractSubType(second_part, objectType)
                if not subType:
                    # Also try extracting from the full message as fallback
                    subType = self._extractSubType(message, objectType)
                
                # If we got name, proceed with creation
                if name:
                    abbreviation = self._extractAbbreviation(first_part)
                    description = self._extractDescription(first_part) or ""
                    
                    if subType:
                        subTypesInfo = self._getSubTypesInfo(domainId, objectType)
                        availableSubTypes = subTypesInfo.get('subTypes', [])
                        if availableSubTypes:
                            if subType in availableSubTypes:
                                pass  # subType is correct
                            else:
                                # Try intelligent matching
                                matched = self._matchSubType(subType, availableSubTypes)
                                if matched:
                                    subType = matched
                                else:
                                    return self._error(get_error_message('validation', 'invalid_subtype', subType=subType, available=', '.join(availableSubTypes[:5])))
                    
                    # Emit thought: Creating object
                    self._emit_thought('thought', f"Creating {objectType} '{name}'" + (f" with subtype '{subType}'" if subType else ""))
                    
                    result = self.veriniceTool.createObject(
                        objectType,
                        name=name,
                        abbreviation=abbreviation,
                        description=description,
                        subType=subType,
                        domainId=domainId,
                        unitId=unitId
                    )
                    
                    if result.get('success'):
                        # Store created object info in state for quick lookup (helps with linking immediately after CREATE)
                        objectId = result.get('objectId') or result.get('data', {}).get('resourceId') or result.get('data', {}).get('id')
                        if objectId and name:
                            if '_created_objects' not in self.state:
                                self.state['_created_objects'] = {}
                            key = f"{objectType}:{name.lower().replace('_', ' ').replace('-', ' ').strip()}"
                            self.state['_created_objects'][key] = {
                                'objectId': objectId,
                                'domainId': domainId,
                                'objectType': objectType,
                                'name': name
                            }
                        # Emit success thought
                        success_msg = f"Created {objectType} '{name}'" + (f" with subtype '{subType}'" if subType else "")
                        self._emit_thought('complete', success_msg)
                        return self._success(success_msg)
                    else:
                        # Extract specific error details
                        error_detail = self._extract_error_details(result)
                        error_msg = f"Failed to create {objectType} '{name}': {error_detail}"
                        self._emit_thought('error', error_msg)
                        return self._error(error_msg)
        
        # If subtype was pre-detected (from router), use it and extract name differently
        if preDetectedSubType:
            # Pattern: "create Controllers named 'MFA for VPN'"
            # Extract name after "named" or "called"
            namePatterns = [
                rf'create\s+(?:a\s+)?["\']?{re.escape(preDetectedSubType)}["\']?\s+(?:named|called)\s+["\']([^"\']+)["\']',
                rf'create\s+(?:a\s+)?["\']?{re.escape(preDetectedSubType)}["\']?\s+(?:named|called)\s+([A-Za-z0-9_\s-]+?)(?:\s|$)',
            ]
            name = None
            for pattern in namePatterns:
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    name = match.group(1).strip()
                    break
            
            if not name:
                return self._error(get_error_message('validation', 'what_name_for_subtype', subType=preDetectedSubType))
            
            abbreviation = self._extractAbbreviation(message)
            description = self._extractDescription(message) or ""
            subType = preDetectedSubType  # Use pre-detected subtype
        else:
            # Normal flow: Try simple format first: "create {objectType} {name} {abbreviation} {description}"
            simpleFormat = self._extractSimpleFormat(message, objectType)
            if simpleFormat:
                name = simpleFormat['name']
                abbreviation = simpleFormat.get('abbreviation')
                description = simpleFormat.get('description', '')
                subType = simpleFormat.get('subType')
            else:
                # Fallback to old format with keywords
                name = self._extractName(message, objectType)
                if not name:
                    return self._error(get_error_message('validation', 'missing_name', objectType=objectType))
                abbreviation = self._extractAbbreviation(message)
                description = self._extractDescription(message) or ""
                subType = self._extractSubType(message, objectType)
        
        if subType:
            subTypesInfo = self._getSubTypesInfo(domainId, objectType)
            availableSubTypes = subTypesInfo.get('subTypes', [])
            if availableSubTypes:
                # If exact match, use it
                if subType in availableSubTypes:
                    pass  # subType is already correct
                else:
                    # Try intelligent matching (handles case variations, prefixes, etc.)
                    matched = self._matchSubType(subType, availableSubTypes)
                    if matched:
                        subType = matched  # Use the matched subtype
                    else:
                        # For pre-detected subtypes, be more lenient - try case-insensitive match
                        if preDetectedSubType:
                            subTypeLower = subType.lower()
                            for availableSubType in availableSubTypes:
                                if availableSubType.lower() == subTypeLower or availableSubType.lower().replace('_', ' ').replace('-', ' ') == subTypeLower:
                                    subType = availableSubType
                                    break
                            else:
                                return self._error(get_error_message('validation', 'subtype_not_found', subType=subType, objectType=objectType, available=', '.join(availableSubTypes[:5])))
                        else:
                            return self._error(get_error_message('validation', 'invalid_subtype', subType=subType, available=', '.join(availableSubTypes[:5])))
        
        # If subType not provided, try to infer it or auto-select default
        if not subType:
            subTypesInfo = self._getSubTypesInfo(domainId, objectType)
            availableSubTypes = subTypesInfo.get('subTypes', [])
            
            if not availableSubTypes:
                # No subtypes available, proceed without subtype (tool will handle)
                pass
            elif len(availableSubTypes) == 1:
                # Only one subtype, use it automatically
                subType = availableSubTypes[0]
            else:
                # Multiple subtypes - try pattern matching first
                inferred = self._inferSubTypeFromPattern(objectType, name, abbreviation, description, availableSubTypes)
                if inferred:
                    subType = inferred
                else:
                    # Pattern matching failed - auto-select first available subtype for consistency
                    # This ensures consistent behavior in automated flows
                    # If user wants specific subtype, they can specify it in the command
                    subType = availableSubTypes[0]
        
        result = self.veriniceTool.createObject(
            objectType, 
            domainId, 
            unitId, 
            name, 
            subType=subType, 
            description=description,
            abbreviation=abbreviation
        )
        
        if result.get('success'):
            # Store created object info in state for quick lookup (helps with linking immediately after CREATE)
            objectId = result.get('objectId') or result.get('data', {}).get('resourceId') or result.get('data', {}).get('id')
            if objectId and name:
                if '_created_objects' not in self.state:
                    self.state['_created_objects'] = {}
                key = f"{objectType}:{name.lower().replace('_', ' ').replace('-', ' ').strip()}"
                self.state['_created_objects'][key] = {
                    'objectId': objectId,
                    'domainId': domainId,
                    'objectType': objectType,
                    'name': name
                }
            
            info = f"Created {objectType} '{name}'"
            if abbreviation:
                info += f" (abbreviation: {abbreviation})"
            if subType:
                info += f" (subType: {subType})"
            return self._success(info)
        
        # Extract specific error details
        error_detail = self._extract_error_details(result)
        return self._error(f"Failed to create {objectType}: {error_detail}")
    
    def _normalizeSubtypeFilter(self, subtypeFilter: str, objectType: str) -> str:
        """
        Normalize subtype filter to match against actual subtype values.
        Handles variations like "DPO" -> "Data protection officer" or "PER_DataProtectionOfficer"
        Returns normalized form for matching (lowercase, no spaces/hyphens/underscores)
        """
        if not subtypeFilter:
            return subtypeFilter
        
        subtype_lower = subtypeFilter.lower().strip()
        subtype_no_spaces = subtype_lower.replace(' ', '').replace('-', '').replace('_', '')
        
        # CRITICAL: Check for "Data protection officer" FIRST (handles typos like "offiecer")
        if ('data protection' in subtype_lower and 'offic' in subtype_lower) or \
           ('dataprotection' in subtype_no_spaces and 'offic' in subtype_no_spaces):
            return 'data protection officer'
        
        # Handle standalone "DPO" abbreviation
        if subtype_lower == 'dpo' or (len(subtypeFilter.strip()) <= 5 and 'dpo' in subtype_lower):
            return 'data protection officer'
        
        # Map common user-friendly names to normalized forms
        subtype_mapping = {
            # Person subtypes
            'dpo': 'data protection officer',
            'data protection officer': 'data protection officer',
            'data protection officers': 'data protection officer',
            'data protection offiecer': 'data protection officer',  # Handle typo
            'data protection offiecers': 'data protection officer',  # Handle typo
            # Asset subtypes
            'it-system': 'it-system',
            'it-systems': 'it-system',
            'itsystem': 'it-system',
            'it system': 'it-system',
            'datatype': 'datatype',
            'datatypes': 'datatype',
            'data type': 'datatype',
            'application': 'application',
            'applications': 'application',
        }
        
        # Check exact match first
        if subtype_lower in subtype_mapping:
            return subtype_mapping[subtype_lower]
        
        # Check partial matches (e.g., "dpo" in "dpo officer")
        for key, value in subtype_mapping.items():
            if key in subtype_lower or subtype_lower in key:
                return value
        
        # Return original if no match found
        return subtypeFilter
    
    def _filterObjectsBySubtype(self, objects: List[Dict], subtypeFilter: str, objectType: str) -> List[Dict]:
        """
        Filter objects by subtype with proper normalization.
        Handles "Data protection officer", "DPO", "PER_DataProtectionOfficer", etc.
        """
        if not subtypeFilter or not objects:
            return objects
        
        # Normalize filter: handle "Data protection officer", "DPO", etc.
        filter_normalized = self._normalizeSubtypeFilter(subtypeFilter, objectType)
        filter_normalized_lower = filter_normalized.lower().replace('-', '').replace('_', '').replace(' ', '')
        
        filtered = []
        for obj in objects:
            if isinstance(obj, dict):
                obj_subtype = obj.get('subType', '')
                if obj_subtype:
                    obj_subtype_normalized = obj_subtype.lower().replace('-', '').replace('_', '').replace(' ', '')
                    
                    # Check if normalized filter matches normalized subtype
                    # Handle "Data protection officer" -> "PER_DataProtectionOfficer"
                    matches = (
                        filter_normalized_lower in obj_subtype_normalized or 
                        obj_subtype_normalized in filter_normalized_lower or
                        (filter_normalized_lower == 'dataprotectionofficer' and 'dataprotectionofficer' in obj_subtype_normalized) or
                        (obj_subtype_normalized == 'per_dataprotectionofficer' and 'dataprotectionofficer' in filter_normalized_lower) or
                        (filter_normalized_lower == 'dpo' and 'dataprotectionofficer' in obj_subtype_normalized) or
                        (filter_normalized_lower.replace(' ', '') == 'dataprotectionofficer' and obj_subtype_normalized == 'per_dataprotectionofficer')
                    )
                    
                    if matches:
                        filtered.append(obj)
        
        return filtered
    
    def _handleList(self, objectType: str, message: str, domainId: str, unitId: str, subtypeFilter: Optional[str] = None) -> Dict:
        """List operation - simple and clean, with optional subtype filtering"""
        # Extract subtype filter from message if not provided
        if not subtypeFilter:
            subtypeFilter = self._extractSubType(message, objectType)
        
        # Normalize subtype filter before filtering
        if subtypeFilter:
            subtypeFilter = self._normalizeSubtypeFilter(subtypeFilter, objectType)
        
        # For scopes, try to list without domain first (at unit level)
        if objectType == 'scope' and not domainId:
            # Try to list scopes at unit level
            if unitId:
                result = self.veriniceTool.listObjects(objectType, None, unitId=unitId)
                if result.get('success'):
                    # Filter by subtype if specified
                    if subtypeFilter:
                        objects = result.get('objects', {}).get('items', [])
                        if isinstance(objects, list):
                            filtered = self._filterObjectsBySubtype(objects, subtypeFilter, objectType)
                            if 'objects' not in result:
                                result['objects'] = {}
                            result['objects']['items'] = filtered
                            result['objects']['total'] = len(filtered)
                    result['objectType'] = objectType
                    # Store last list result in state for conversational references
                    # CRITICAL: State is shared with MainAgent (see mainAgent.py line 1133)
                    # So storing here makes it available for bulk delete detection
                    if '_last_list_result' not in self.state:
                        self.state['_last_list_result'] = {}
                    objects = result.get('objects', {})
                    items = objects.get('items', []) if isinstance(objects, dict) else (objects if isinstance(objects, list) else [])
                    self.state['_last_list_result'] = {
                        'objectType': objectType,
                        'items': items,
                        'count': len(items)
                    }
                    logger.info(f"[_handleList] Stored last list result: objectType={objectType}, count={len(items)}")
                    formatted = self.formatResult('listVeriniceObjects', result)
                    return self._success(formatted)
                error_detail = self._extract_error_details(result)
                return self._error(f"Could not list scopes: {error_detail}")
            else:
                unitsResult = self.veriniceTool.listUnits()
                if not unitsResult.get('success'):
                    # listUnits() failed - check if it's an auth/connection issue
                    errorMsg = unitsResult.get('error', 'Unknown error')
                    if 'not available' in errorMsg.lower() or 'authentication' in errorMsg.lower() or 'connection' in errorMsg.lower():
                        return self._error(get_error_message('connection', 'isms_unavailable', error=errorMsg))
                    # Try domains as fallback
                    domainsResult = self.veriniceTool.listDomains()
                    if domainsResult.get('success') and domainsResult.get('domains'):
                        domainId = domainsResult['domains'][0].get('id')
                        result = self.veriniceTool.listObjects(objectType, domainId)
                        if result.get('success'):
                            # Filter by subtype if specified
                            if subtypeFilter:
                                objects = result.get('objects', {}).get('items', [])
                                if isinstance(objects, list):
                                    subtype_normalized = subtypeFilter.lower().replace('-', '').replace('_', '').replace(' ', '')
                                    filtered = []
                                    for obj in objects:
                                        if isinstance(obj, dict):
                                            obj_subtype = obj.get('subType', '')
                                            if obj_subtype:
                                                obj_subtype_normalized = obj_subtype.lower().replace('-', '').replace('_', '').replace(' ', '')
                                                # Check if normalized filter matches normalized subtype
                                                # Also check if "data protection officer" matches "per_dataprotectionofficer"
                                                if (subtype_normalized in obj_subtype_normalized or 
                                                    obj_subtype_normalized in subtype_normalized or
                                                    (subtype_normalized == 'dataprotectionofficer' and 'dataprotectionofficer' in obj_subtype_normalized) or
                                                    (obj_subtype_normalized == 'dataprotectionofficer' and 'dataprotectionofficer' in subtype_normalized)):
                                                    filtered.append(obj)
                                    if 'objects' not in result:
                                        result['objects'] = {}
                                    result['objects']['items'] = filtered
                                    result['objects']['total'] = len(filtered)
                            result['objectType'] = objectType
                            # Store last list result in state for conversational references
                            if '_last_list_result' not in self.state:
                                self.state['_last_list_result'] = {}
                            objects = result.get('objects', {})
                            items = objects.get('items', []) if isinstance(objects, dict) else (objects if isinstance(objects, list) else [])
                            self.state['_last_list_result'] = {
                                'objectType': objectType,
                                'items': items,
                                'count': len(items)
                            }
                            formatted = self.formatResult('listVeriniceObjects', result)
                            return self._success(formatted)
                        error_detail = self._extract_error_details(result)
                        return self._error(f"Could not list scopes: {error_detail}")
                    return self._error(get_error_message('operation_failed', 'list_units', error=errorMsg))
                
                units = unitsResult.get('units')
                if not units or (isinstance(units, list) and len(units) == 0):
                    # No units found - try domains as fallback
                    domainsResult = self.veriniceTool.listDomains()
                    if domainsResult.get('success') and domainsResult.get('domains'):
                        domains_list = domainsResult.get('domains', [])
                        if domains_list and len(domains_list) > 0:
                            domainId = domains_list[0].get('id')
                            result = self.veriniceTool.listObjects(objectType, domainId)
                        if result.get('success'):
                            # Filter by subtype if specified
                            if subtypeFilter:
                                objects = result.get('objects', {}).get('items', [])
                                if isinstance(objects, list):
                                    subtype_normalized = subtypeFilter.lower().replace('-', '').replace('_', '').replace(' ', '')
                                    filtered = []
                                    for obj in objects:
                                        if isinstance(obj, dict):
                                            obj_subtype = obj.get('subType', '')
                                            if obj_subtype:
                                                obj_subtype_normalized = obj_subtype.lower().replace('-', '').replace('_', '').replace(' ', '')
                                                # Check if normalized filter matches normalized subtype
                                                # Also check if "data protection officer" matches "per_dataprotectionofficer"
                                                if (subtype_normalized in obj_subtype_normalized or 
                                                    obj_subtype_normalized in subtype_normalized or
                                                    (subtype_normalized == 'dataprotectionofficer' and 'dataprotectionofficer' in obj_subtype_normalized) or
                                                    (obj_subtype_normalized == 'dataprotectionofficer' and 'dataprotectionofficer' in subtype_normalized)):
                                                    filtered.append(obj)
                                    if 'objects' not in result:
                                        result['objects'] = {}
                                    result['objects']['items'] = filtered
                                    result['objects']['total'] = len(filtered)
                            result['objectType'] = objectType
                            # Store last list result in state for conversational references
                            if '_last_list_result' not in self.state:
                                self.state['_last_list_result'] = {}
                            objects = result.get('objects', {})
                            items = objects.get('items', []) if isinstance(objects, dict) else (objects if isinstance(objects, list) else [])
                            self.state['_last_list_result'] = {
                                'objectType': objectType,
                                'items': items,
                                'count': len(items)
                            }
                            formatted = self.formatResult('listVeriniceObjects', result)
                            return self._success(formatted)
                        error_detail = self._extract_error_details(result)
                        return self._error(f"Could not list scopes: {error_detail}")
                    return self._error(get_error_message('not_found', 'unit'))
                
                # Use first unit to list scopes
                if units and len(units) > 0:
                    firstUnit = units[0]
                    unitId = firstUnit.get('id')
                    if not unitId:
                        return self._error(get_error_message('not_found', 'unit_missing_id'))
                else:
                    return self._error(get_error_message('not_found', 'unit'))
                
                result = self.veriniceTool.listObjects(objectType, None, unitId=unitId)
                if result.get('success'):
                    # Filter by subtype if specified
                    if subtypeFilter:
                        objects = result.get('objects', {}).get('items', [])
                        if isinstance(objects, list):
                            filtered = self._filterObjectsBySubtype(objects, subtypeFilter, objectType)
                            if 'objects' not in result:
                                result['objects'] = {}
                            result['objects']['items'] = filtered
                            result['objects']['total'] = len(filtered)
                    result['objectType'] = objectType
                    # Store last list result in state for conversational references
                    # CRITICAL: State is shared with MainAgent (see mainAgent.py line 1133)
                    # So storing here makes it available for bulk delete detection
                    if '_last_list_result' not in self.state:
                        self.state['_last_list_result'] = {}
                    objects = result.get('objects', {})
                    items = objects.get('items', []) if isinstance(objects, dict) else (objects if isinstance(objects, list) else [])
                    self.state['_last_list_result'] = {
                        'objectType': objectType,
                        'items': items,
                        'count': len(items)
                    }
                    logger.info(f"[_handleList] Stored last list result: objectType={objectType}, count={len(items)}")
                    formatted = self.formatResult('listVeriniceObjects', result)
                    return self._success(formatted)
                error_detail = self._extract_error_details(result)
                return self._error(f"Could not list scopes: {error_detail}")
        
        # Standard list operation with domain
        if not domainId:
            return self._error(get_error_message('operation_failed', 'list', objectType=objectType, error='No domain available. Please create a domain first.'))
        
        result = self.veriniceTool.listObjects(objectType, domainId)
        if result.get('success'):
            # Filter by subtype if specified
            if subtypeFilter:
                objects = result.get('objects', {}).get('items', [])
                if isinstance(objects, list):
                    filtered = self._filterObjectsBySubtype(objects, subtypeFilter, objectType)
                    if 'objects' not in result:
                        result['objects'] = {}
                    result['objects']['items'] = filtered
                    result['objects']['total'] = len(filtered)
            
            result['objectType'] = objectType
            # Store last list result in state for conversational references
            if '_last_list_result' not in self.state:
                self.state['_last_list_result'] = {}
            objects = result.get('objects', {})
            items = objects.get('items', []) if isinstance(objects, dict) else (objects if isinstance(objects, list) else [])
            self.state['_last_list_result'] = {
                'objectType': objectType,
                'items': items,
                'count': len(items)
            }
            formatted = self.formatResult('listVeriniceObjects', result)
            return self._success(formatted)
        error_detail = self._extract_error_details(result)
        return self._error(f"Could not list {objectType}s: {error_detail}")
    
    def _handleGet(self, objectType: str, message: str, domainId: str, unitId: str, returnSubtype: bool = False) -> Dict:
        """Get operation - find by name or ID"""
        objectId = self._resolveToId(objectType, message, domainId)
        if not objectId:
            return self._error(get_error_message('validation', 'missing_params', objectType=objectType))
        
        result = self.veriniceTool.getObject(objectType, domainId, objectId)
        if result.get('success'):
            obj = result.get('object', {})
            # If returnSubtype flag is set, return just the subtype information
            if returnSubtype:
                subtype = obj.get('subType', 'Unknown')
                # Map technical subtype ID to user-friendly name
                subtype_mapping = {
                    'AST_Datatype': 'Datatype',
                    'AST_ITSystem': 'IT-System',
                    'AST_Application': 'Application',
                    'PER_DataProtectionOfficer': 'Data protection officer',
                    'SCP_Scope': 'Scope',
                    'SCP_Controller': 'Controller',
                    'SCP_Processor': 'Processor',
                }
                friendly_subtype = subtype_mapping.get(subtype, subtype)
                object_name = obj.get('name', 'Unknown')
                return self._success(f"The asset '{object_name}' is of type: {friendly_subtype}")
            
            formatted = self.formatResult('getVeriniceObject', result)
            return self._success(formatted)
        error_detail = self._extract_error_details(result)
        return self._error(f"Could not find {objectType}: {error_detail}")
    
    def _handleDelete(self, objectType: str, message: str, domainId: str, unitId: str) -> Dict:
        """Delete operation - find by name or ID and delete"""
        objectId = self._resolveToId(objectType, message, domainId)
        if not objectId:
            return self._error(get_error_message('validation', 'missing_params_delete', objectType=objectType))
        
        result = self.veriniceTool.deleteObject(objectType, domainId, objectId)
        if result.get('success'):
            return self._success(f"Deleted {objectType} successfully")
        error_detail = self._extract_error_details(result)
        return self._error(f"Failed to delete {objectType}: {error_detail}")
    
    def _handleUpdate(self, objectType: str, message: str, domainId: str, unitId: str) -> Dict:
        """
        Update operation - supports both keyword and positional formats
        """
        # CRITICAL: Check if VeriniceTool is available and authenticated
        if not self.veriniceTool:
            return self._error(get_error_message('connection', 'isms_client_not_available'))
        
        # Ensure authentication before proceeding
        if not self.veriniceTool._ensureAuthenticated():
            return self._error(get_error_message('connection', 'isms_init_failed', error='ISMS client not available'))
        
        # Resolve current object ID
        objectId = self._resolveToId(objectType, message, domainId)
        if not objectId:
            # Try to extract name manually for better error message
            name_patterns = [
                rf'(?:update|change|modify|edit|set)\s+(?:the\s+)?{objectType}\s+["\']([^"\']+)["\']',
                rf'(?:update|change|modify|edit|set)\s+(?:the\s+)?{objectType}\s+([A-Za-z0-9_\s-]+?)(?:\s|\.|$)',
            ]
            extracted_name = None
            for pattern in name_patterns:
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    extracted_name = match.group(1).strip()
                    break
            if extracted_name:
                return self._error(get_error_message('validation', 'object_not_found_with_name', objectType=objectType, name=extracted_name))
            return self._error(get_error_message('validation', 'missing_params_update', objectType=objectType))
        
        # Extract current name for response
        currentName = self._extractName(message, objectType) or objectId
        
        # Build update data
        updateData = {}
        messageLower = message.lower()
        
        # 1. Check for keyword-based updates (priority)
        # Handle subType/subtype
        subtype_match = re.search(r'subtypes?[:\s]+([A-Za-z0-9_\s-]+)', message, re.IGNORECASE)
        if subtype_match:
            updateData['subType'] = subtype_match.group(1).strip()
            
        # Handle description
        desc_match = re.search(r'description[:\s]+(.+?)(?:\s+subType|\s+status|$)', message, re.IGNORECASE)
        if desc_match:
            updateData['description'] = desc_match.group(1).strip().strip('"').strip("'")
            
        # Handle abbreviation
        abbr_match = re.search(r'(?:abbreviation|abbr)[:\s]+([A-Za-z0-9_-]{1,10})', message, re.IGNORECASE)
        if abbr_match:
            updateData['abbreviation'] = abbr_match.group(1).strip()
            
        # Handle name change (explicit)
        name_change_match = re.search(r'name[:\s]+["\']?([^"\']+)["\']?', message, re.IGNORECASE)
        if name_change_match:
            # Only use if it's not the same as currentName
            new_name = name_change_match.group(1).strip()
            if new_name.lower() != currentName.lower():
                updateData['name'] = new_name

        # 2. Fallback to positional parsing ONLY if no keywords found
        if not updateData:
            parts = message.split()
            filteredParts = []
            skipWords = ['update', 'edit', 'modify', 'change', objectType, objectType + 's']
            for part in parts:
                if part.lower() not in skipWords:
                    filteredParts.append(part)
            
            if len(filteredParts) >= 2:
                # First part is current name, rest are updates
                updateParts = filteredParts[1:]
                if len(updateParts) >= 1:
                    updateData['name'] = updateParts[0]
                if len(updateParts) >= 2:
                    updateData['abbreviation'] = updateParts[1]
                if len(updateParts) >= 3:
                    updateData['description'] = ' '.join(updateParts[2:])
        
        if not updateData:
            return self._error(get_error_message('validation', 'what_to_update', objectType=objectType, currentName=currentName))
        
        # If updating subtype, validate it
        if 'subType' in updateData:
            subTypesInfo = self._getSubTypesInfo(domainId, objectType)
            availableSubTypes = subTypesInfo.get('subTypes', [])
            if availableSubTypes:
                matched = self._matchSubType(updateData['subType'], availableSubTypes)
                if matched:
                    updateData['subType'] = matched
                else:
                    return self._error(get_error_message('validation', 'invalid_subtype', subType=updateData['subType'], available=', '.join(availableSubTypes[:5])))

        result = self.veriniceTool.updateObject(objectType, domainId, objectId, updateData)
        if result.get('success'):
            updatedFields = ', '.join(updateData.keys())
            return self._success(f"Updated {objectType} '{currentName}' ({updatedFields})")
        
        # FIX: Handle subtype change restriction by re-creating the object if it's "fresh"
        error_detail = self._extract_error_details(result)
        is_subtype_error = any(phrase in error_detail.lower() for phrase in ['sub type', 'subtype', 'cannot change'])
        
        if is_subtype_error and 'subType' in updateData:
            # Check if this object was recently created
            created_objs = self.state.get('_created_objects', {})
            key = f"{objectType}:{currentName.lower().replace('_', ' ').replace('-', ' ').strip()}"
            
            if key in created_objs:
                logger.info(f"[_handleUpdate] Detected subtype change restriction for fresh object '{currentName}'. Attempting delete and recreate...")
                # 1. Delete
                delete_res = self.veriniceTool.deleteObject(objectType, domainId, objectId)
                if delete_res.get('success'):
                    # 2. Re-create with new subtype
                    new_sub = updateData['subType']
                    # Use original creation data if available, or just name
                    create_res = self.veriniceTool.createObject(
                        objectType, domainId, unitId, currentName, 
                        subType=new_sub, 
                        description=updateData.get('description', ''),
                        abbreviation=updateData.get('abbreviation')
                    )
                    if create_res.get('success'):
                        # Update state with new ID
                        new_id = create_res.get('objectId')
                        created_objs[key]['objectId'] = new_id
                        return self._success(f"Updated {objectType} '{currentName}' by re-creating it with subtype '{new_sub}' (due to Verinice restriction)")
        
        return self._error(f"Failed to update {objectType} '{currentName}': {error_detail}")
    
    def _extractFieldAndValue(self, message: str, objectType: str, objectId: str) -> tuple:
        """
        Intelligently extract field and value using LLM (with pattern fallback)
        
        Returns:
            (field, value) tuple or (None, None) if extraction fails
        """
        # Try LLM first if available
        if self.llmTool:
            try:
                prompt = f"""Extract the field name and new value from this update command:

User Message: "{message}"
Object Type: {objectType}
Object ID: {objectId}

Common fields for {objectType}:
- name: Object name
- description: Object description
- status: Object status (e.g., NEW, ACTIVE, INACTIVE)
- subType: Object subtype

Extract the field name and value. The user wants to update a specific field.

Examples:
- "update scope BLUETEAM description New description" → field: "description", value: "New description"
- "update asset MyAsset status ACTIVE" → field: "status", value: "ACTIVE"
- "change scope NAME to NewName" → field: "name", value: "NewName"
- "set description to Updated description" → field: "description", value: "Updated description"

Respond ONLY in JSON format:
{{
    "field": "field_name",
    "value": "new_value"
}}

If you cannot determine the field or value, return:
{{
    "field": null,
    "value": null
}}
"""
                response = self.llmTool.generate(prompt, maxTokens=200)
                
                # Extract JSON from response
                jsonMatch = re.search(r'\{[^}]+\}', response, re.DOTALL)
                if jsonMatch:
                    result = json.loads(jsonMatch.group(0))
                    field = result.get('field')
                    value = result.get('value')
                    if field and value:
                        return (field.strip(), value.strip())
            except Exception:
                pass  # Fallback to pattern-based
        
        return (None, None)
    
    def _extractFieldAndValuePattern(self, message: str, objectType: str) -> tuple:
        """
        Pattern-based extraction (fallback)
        
        Returns:
            (field, value) tuple or (None, None) if extraction fails
        """
        patterns = [
            r'(?:set|update|change)\s+(\w+)\s+(?:to|as|=)\s+(.+)',  # "set description to value"
            rf'{objectType}\s+\w+\s+(\w+)\s+(.+)',                    # "scope NAME field value"
            r'(\w+)\s*=\s*(.+)',                                      # "field = value"
        ]
        
        for pattern in patterns:
            fieldMatch = re.search(pattern, message, re.IGNORECASE)
            if fieldMatch:
                field = fieldMatch.group(1)
                value = fieldMatch.group(2).strip()
                value = re.sub(r'\s+(in|for|with|using|to|the).*$', '', value, flags=re.IGNORECASE).strip()
                if field and value:
                    return (field, value)
        
        return (None, None)
    
    def _handleAnalyze(self, objectType: str, message: str, domainId: str, unitId: str) -> Dict:
        """Analyze operation - get object and analyze comprehensively"""
        # Emit thought: Starting analysis
        self._emit_thought('thought', f"Analyzing {objectType}...")
        
        # CRITICAL: Check if VeriniceTool is available and authenticated
        if not self.veriniceTool:
            self._emit_thought('error', "ISMS client not available")
            return self._error(get_error_message('connection', 'isms_client_not_available'))
        
        # Ensure authentication before proceeding
        if not self.veriniceTool._ensureAuthenticated():
            self._emit_thought('error', "ISMS client not available")
            return self._error(get_error_message('connection', 'isms_init_failed', error='ISMS client not available'))
        
        # Resolve object ID
        objectId = self._resolveToId(objectType, message, domainId)
        if not objectId:
            return self._error(get_error_message('validation', 'missing_params_analyze', objectType=objectType))
        
        result = self.veriniceTool.getObject(objectType, domainId, objectId)
        if not result.get('success'):
            error_detail = self._extract_error_details(result)
            return self._error(f"Could not find {objectType}: {error_detail}")
        
        object_data = result.get('data', {})
        if not isinstance(object_data, dict):
            return self._error(f"Invalid data returned for {objectType}")
        
        # Build comprehensive analysis
        name = object_data.get('name', 'Unknown')
        description = object_data.get('description', '')
        subType = object_data.get('subType', '')
        status = object_data.get('status', '')
        
        relationships_info = ""
        if objectType == 'scope':
            # List all assets and check which are linked to this scope
            assets_result = self.veriniceTool.listObjects('asset', domainId)
            if assets_result.get('success'):
                objects = assets_result.get('objects', {})
                items = objects.get('items', []) if isinstance(objects, dict) else (objects if isinstance(objects, list) else [])
                linked_assets = []
                for asset in items:
                    if isinstance(asset, dict):
                        parts = asset.get('parts', [])
                        members = asset.get('members', [])
                        scope_refs = parts + members
                        for ref in scope_refs:
                            if isinstance(ref, dict) and (ref.get('id') == objectId or ref.get('resourceId') == objectId):
                                linked_assets.append(asset.get('name', 'N/A'))
                
                if linked_assets:
                    relationships_info = f"\n\n**Linked Assets ({len(linked_assets)}):**\n"
                    for asset_name in linked_assets[:10]:  # Show first 10
                        relationships_info += f"• {asset_name}\n"
                    if len(linked_assets) > 10:
                        relationships_info += f"... and {len(linked_assets) - 10} more\n"
        
        # Build analysis text
        analysis = f"**Analysis of {name}**\n\n"
        analysis += f"**Type:** {objectType.capitalize()}\n"
        if subType:
            analysis += f"**SubType:** {subType}\n"
        if status:
            analysis += f"**Status:** {status}\n"
        if description:
            analysis += f"\n**Description:**\n{description}\n"
        analysis += relationships_info
        
        # Emit thought: Analysis complete
        self._emit_thought('complete', f"Analysis of {objectType} '{name}' completed")
        
        return self._success(analysis)
    
    def _handleCompare(self, objectType: str, message: str, domainId: str, unitId: str) -> Dict:
        """Compare operation - compare two objects using MCP compare tool"""
        # Emit thought: Starting comparison
        self._emit_thought('thought', f"Comparing {objectType} objects...")
        
        # CRITICAL: Check if VeriniceTool is available and authenticated
        if not self.veriniceTool:
            self._emit_thought('error', "ISMS client not available")
            return self._error(get_error_message('connection', 'isms_client_not_available'))
        
        # Ensure authentication before proceeding
        if not self.veriniceTool._ensureAuthenticated():
            self._emit_thought('error', "ISMS client not available")
            return self._error(get_error_message('connection', 'isms_init_failed', error='ISMS client not available'))
        
        # Extract two object names from message
        # Pattern: "compare X and Y" or "compare X Y" or "compare 'X' and 'Y'"
        patterns = [
            r'compare\s+["\']?([^"\']+)["\']?\s+and\s+["\']?([^"\']+)["\']?',
            r'compare\s+["\']?([^"\']+)["\']?\s+["\']?([^"\']+)["\']?',
            r'compare\s+(\S+)\s+and\s+(\S+)',
            r'compare\s+(\S+)\s+(\S+)',
        ]
        
        object1_name = None
        object2_name = None
        
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                object1_name = match.group(1).strip()
                object2_name = match.group(2).strip()
                break
        
        if not object1_name or not object2_name:
            return self._error(get_error_message('validation', 'comparison_requires_two'))
        
        # Use MCP compare tool
        try:
            from mcp.tools.compare import compare_objects
            result = compare_objects(
                object1_name=object1_name,
                object2_name=object2_name,
                object1_type=objectType,
                object2_type=objectType,
                verinice_tool=self.veriniceTool,
                llm_tool=self.llmTool,
                state=self.state
            )
            
            if result.get('success'):
                comparison_text = result.get('text', 'Comparison completed')
                self._emit_thought('complete', f"Comparison of {object1_name} and {object2_name} completed")
                
                # Store comparison in state for context questions
                if hasattr(self, 'state'):
                    # Parse diff count from text if possible
                    diff_count = comparison_text.count('\n- ')
                    self.state['_last_comparison'] = {
                        'obj1': object1_name,
                        'obj2': object2_name,
                        'diff_count': diff_count or 'several',
                        'timestamp': time.time()
                    }
                
                return self._success(comparison_text)
            else:
                error_text = result.get('text', 'Comparison failed')
                return self._error(error_text)
        except ImportError:
            return self._error("Compare tool not available")
        except Exception as e:
            logger.error(f"Compare operation failed: {e}", exc_info=True)
            return self._error(f"Comparison failed: {str(e)}")
    
    # ==================== HELPER METHODS ====================
    
    def _getDefaults(self) -> tuple:
        """Get default domain/unit with caching"""
        if self._domainCache and self._unitCache:
            return self._domainCache, self._unitCache
        
        unitsResult = self.veriniceTool.listUnits()
        if unitsResult.get('success'):
            units = unitsResult.get('units', [])
            if units and len(units) > 0:
                unit = units[0]
                self._unitCache = unit.get('id')
                
                domains = unit.get('domains', [])
                if domains and len(domains) > 0:
                    self._domainCache = domains[0].get('id') if isinstance(domains[0], dict) else domains[0]
        
        # Fallback to first domain if no unit domain or no units
        if not self._domainCache:
            domainsResult = self.veriniceTool.listDomains()
            if domainsResult.get('success') and domainsResult.get('domains'):
                self._domainCache = domainsResult['domains'][0].get('id')
        
        # If still no unit but we have domains, try to get unit from domains
        if not self._unitCache and self._domainCache:
            # Try listing units again (might have been a transient error)
            unitsResult = self.veriniceTool.listUnits()
            if unitsResult.get('success') and unitsResult.get('units'):
                unit = unitsResult['units'][0]
                self._unitCache = unit.get('id')
        
        return self._domainCache, self._unitCache
    
    def _extractSimpleFormat(self, message: str, objectType: str) -> Optional[Dict]:
        """
        Extract from simple format with support for quoted strings:
        - "create {objectType} {name} {abbreviation} {description}"
        - "create {objectType} \"name with spaces\" \"abbr\" \"description with spaces\""
        - "create {objectType} name_with_underscores abbr description"
        
        Examples:
        - create scope "scope test" "scp2" "scope description"
        - create person "john doe" "DPO" "dpo officer"
        - create scope scope_test scp2 scope_description
        - creat scope "SCOPE TEST" "SA-1" "SCOPE TESTING"  (typo "creat" supported)
        """
        # Support "creat" typo
        createPattern = r'(?:create|creat|new|add)'
        
        # First try: All quoted format with subtype (supports spaces)
        # Pattern: create {objectType} "name" "abbreviation" "description" "subtype"
        quotedWithSubTypePattern = rf'{createPattern}\s+{objectType}\s+"([^"]+)"\s+"([^"]+)"\s+"([^"]+)"\s+"([^"]+)"'
        quotedWithSubTypeMatch = re.search(quotedWithSubTypePattern, message, re.IGNORECASE)
        if quotedWithSubTypeMatch:
            return {
                'name': quotedWithSubTypeMatch.group(1).strip(),
                'abbreviation': quotedWithSubTypeMatch.group(2).strip(),
                'description': quotedWithSubTypeMatch.group(3).strip(),
                'subType': quotedWithSubTypeMatch.group(4).strip()
            }
        
        # Second try: All quoted format without subtype (supports spaces)
        # Pattern: create {objectType} "name" "abbreviation" "description"
        quotedPattern = rf'{createPattern}\s+{objectType}\s+"([^"]+)"\s+"([^"]+)"\s+"([^"]+)"'
        quotedMatch = re.search(quotedPattern, message, re.IGNORECASE)
        if quotedMatch:
            return {
                'name': quotedMatch.group(1).strip(),
                'abbreviation': quotedMatch.group(2).strip(),
                'description': quotedMatch.group(3).strip()
            }
        
        # Third try: Quoted name and description, unquoted abbreviation (with hyphens)
        # Pattern: create {objectType} "name" ABBR-1 "description"
        quotedNameDescPattern = rf'{createPattern}\s+{objectType}\s+"([^"]+)"\s+([A-Za-z0-9_-]+?)\s+"([^"]+)"'
        quotedNameDescMatch = re.search(quotedNameDescPattern, message, re.IGNORECASE)
        if quotedNameDescMatch:
            return {
                'name': quotedNameDescMatch.group(1).strip(),
                'abbreviation': quotedNameDescMatch.group(2).strip(),
                'description': quotedNameDescMatch.group(3).strip()
            }
        
        # Fourth try: Quoted name and abbreviation, unquoted description
        quotedNamePattern = rf'{createPattern}\s+{objectType}\s+"([^"]+)"\s+"([^"]+)"\s+(.+?)(?:\s+subType|\s+status|$)'
        quotedNameMatch = re.search(quotedNamePattern, message, re.IGNORECASE)
        if quotedNameMatch:
            desc = quotedNameMatch.group(3).strip().strip('"').strip("'")
            return {
                'name': quotedNameMatch.group(1).strip(),
                'abbreviation': quotedNameMatch.group(2).strip(),
                'description': desc
            }
        
        # Fifth try: Quoted name only, unquoted abbreviation and description
        # Pattern: create {objectType} "name" ABBR description text
        quotedNameUnquotedPattern = rf'{createPattern}\s+{objectType}\s+"([^"]+)"\s+([A-Za-z0-9_-]+?)\s+(.+?)(?:\s+subType|\s+status|$)'
        quotedNameUnquotedMatch = re.search(quotedNameUnquotedPattern, message, re.IGNORECASE)
        if quotedNameUnquotedMatch:
            desc = quotedNameUnquotedMatch.group(3).strip().strip('"').strip("'")
            return {
                'name': quotedNameUnquotedMatch.group(1).strip(),
                'abbreviation': quotedNameUnquotedMatch.group(2).strip(),
                'description': desc
            }
        
        # Sixth try: Standard format without quotes (underscores converted to spaces)
        # Pattern: create {objectType} {name} {abbreviation} {description}
        # Name can have spaces/underscores, abbreviation is short (1-20 chars), description is rest
        # Use non-greedy matching and ensure abbreviation doesn't contain spaces
        pattern = rf'{createPattern}\s+{objectType}\s+([A-Za-z0-9_\s-]+?)\s+([A-Za-z0-9_-]{{1,20}})\s+(.+?)(?:\s+subType|\s+status|$)'
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            name = match.group(1).strip().replace('_', ' ')  # Convert underscores to spaces
            abbreviation = match.group(2).strip()
            description = match.group(3).strip()
            return {
                'name': name,
                'abbreviation': abbreviation,
                'description': description
            }
        
        # Seventh try: "create {objectType} {name} {abbreviation}" (no description)
        pattern2 = rf'{createPattern}\s+{objectType}\s+([A-Za-z0-9_\s-]+?)\s+([A-Za-z0-9_-]{{1,20}})(?:\s+subType|\s+status|$)'
        match2 = re.search(pattern2, message, re.IGNORECASE)
        if match2:
            name = match2.group(1).strip().replace('_', ' ')
            abbreviation = match2.group(2).strip()
            return {
                'name': name,
                'abbreviation': abbreviation,
                'description': ''
            }
        
        return None
    
    def _extractName(self, message: str, objectType: str) -> Optional[str]:
        """Extract object name from message - enhanced patterns"""
        # Also handle: "Create a new Scope named 'Project Phoenix' and immediately link it..."
        # Also handle: "Create a new Incident named 'Phishing Attempt Jan-24'. Then, find..."
        quoted_patterns = [
            rf'(?:create|creat|new|add)\s+(?:a\s+)?(?:new\s+)?(?:person|persons|people)\s+["\']([^"\']+)["\'](?:\s*\.|$)',  # "create person 'John'." or "create person 'John'"
            rf'(?:create|creat|new|add)\s+(?:a\s+)?(?:new\s+)?(?:person|persons|people)\s+["\']([^"\']+)["\']',  # Fallback
            # Pattern for "Create a new Scope named 'Project Phoenix' and immediately link it..."
            rf'(?:create|creat|new|add)\s+(?:a\s+)?(?:new\s+)?{objectType}\s+(?:named|called)\s+["\']([^"\']+)["\'](?:\s+and\s+(?:immediately\s+)?(?:link|connect)|$)',
            # Pattern for "Create a new Incident named 'Phishing Attempt Jan-24'. Then, find..."
            rf'(?:create|creat|new|add)\s+(?:a\s+)?(?:new\s+)?{objectType}\s+(?:named|called)\s+["\']([^"\']+)["\']\s*[\.\,]\s*then',
            rf'(?:create|creat|new|add)\s+(?:a\s+)?{objectType}\s+["\']([^"\']+)["\']',  # Generic quoted name
        ]
        
        for pattern in quoted_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                if name:
                    return name
        
        # CRITICAL: Handle "add [name] in our isms person list" pattern FIRST
        # Pattern: "add Toom in our isms person list" -> extract "Toom"
        if objectType.lower() == 'person':
            add_name_patterns = [
                rf'(?:create|creat|new|add)\s+([A-Za-z0-9_\s-]+?)\s+in\s+(?:our|the)\s+(?:isms|system)\s+(?:person|persons|people)\s+list',  # "add Toom in our isms person list"
                rf'(?:create|creat|new|add)\s+([A-Za-z0-9_\s-]+?)\s+in\s+(?:our|the)\s+(?:isms|system)',  # "add Toom in our isms"
                rf'(?:create|creat|new|add)\s+([A-Za-z0-9_\s-]+?)\s+to\s+(?:our|the)\s+(?:person|persons|people)\s+list',  # "add Toom to our person list"
            ]
            for pattern in add_name_patterns:
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    name = match.group(1).strip()
                    # Stop at "and set" or "and" if present
                    if ' and ' in name.lower():
                        name = name.split(' and ')[0].strip()
                    if name and len(name) > 0:
                        return name
        
        # Handle unquoted names - CRITICAL: Stop at "in our isms", "list", "and set", etc.
        patterns = [
            rf'(?:create|creat|new|add)\s+{objectType}\s+([A-Za-z0-9_\s-]+?)(?:\s+in\s+(?:our|the)\s+(?:isms|system)|\s+list|\s+and\s+set|\s+description|\s+abbreviation|\s+subType|\s+status|$)',  # "create scope MyScope" or "add person Toom list"
            rf'{objectType}\s+(?:called|named)\s+([A-Za-z0-9_\s-]+)',     # "scope called MyScope"
            r'(?:name|called|named)\s+([A-Za-z0-9_\s-]+)',               # "name MyScope"
            rf'{objectType}\s+([A-Za-z0-9_\s-]+?)(?:\s+description|\s+abbreviation|\s+subType|\s+status|$)',  # "scope MyScope"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                name = re.sub(r'\s+(in|for|with|using|to|the|description|abbreviation|subType|status|list|and|set).*$', '', name, flags=re.IGNORECASE).strip()
                if name:
                    return name
        return None
    
    def _extractAbbreviation(self, message: str) -> Optional[str]:
        """Extract abbreviation from message"""
        patterns = [
            r'abbreviation[:\s]+([A-Za-z0-9_-]{1,10})',
            r'abbrev[:\s]+([A-Za-z0-9_-]{1,10})',
            r'abbr[:\s]+([A-Za-z0-9_-]{1,10})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                abbrev = match.group(1).strip()
                if abbrev:
                    return abbrev
        return None
    
    def _extractDescription(self, message: str) -> Optional[str]:
        """Extract description from message"""
        patterns = [
            r'description[:\s]+(.+?)(?:\s+subType|\s+status|$)',
            r'desc[:\s]+(.+?)(?:\s+subType|\s+status|$)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                desc = match.group(1).strip().strip('"').strip("'")
                if desc:
                    return desc
        return None
    
    def _extractSubType(self, message: str, objectType: str) -> Optional[str]:
        """Extract subType from message"""
        # Pattern 1: "assign his role to 'DPO'" or "assign her role to 'DPO'"
        assign_role_pattern = r'assign\s+(?:his|her|their|its)\s+role\s+to\s+["\']?([^"\']+)["\']?'
        match = re.search(assign_role_pattern, message, re.IGNORECASE)
        if match:
            subType = match.group(1).strip()
            if subType:
                return subType
        
        # Pattern 1.5: "set his role to DPO" or "set her role to DPO"
        set_role_pattern = r'set\s+(?:his|her|their|its)\s+role\s+to\s+([A-Za-z0-9_\s-]+?)(?:\s|$|and|,|\.)'
        match = re.search(set_role_pattern, message, re.IGNORECASE)
        if match:
            subType = match.group(1).strip()
            if subType:
                return subType
        
        # Pattern 2: "as DPO" or "as Data Protection Officer"
        as_pattern = r'as\s+([A-Za-z0-9_\s-]+)'
        match = re.search(as_pattern, message, re.IGNORECASE)
        if match:
            subType = match.group(1).strip()
            if subType:
                return subType
        
        # Pattern 3: "for {subtype} subtypes" or "for {subtype}" (for any object type)
        # Examples: "create asset Firewall for Application subtypes", "create asset Firewall for IT-System"
        for_subtype_patterns = [
            r'for\s+([A-Za-z0-9_\s-]+?)\s+subtypes?\s*$',  # "for Application subtypes"
            r'for\s+(?:the\s+)?([A-Za-z0-9_\s-]+?)(?:\s+subtypes?)?\s*$',  # "for Application" or "for the Application"
        ]
        
        for pattern in for_subtype_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                potential_subtype = match.group(1).strip()
                # Skip common words that aren't subtypes
                skip_words = ['the', 'our', 'isms', 'system', 'domain', 'unit', 'role']
                if potential_subtype.lower() not in skip_words and len(potential_subtype) > 1:
                    return potential_subtype
        
        # Pattern 3.5: "for DPO" or "for the DPO role" (person-specific, but also check for other types)
        if objectType.lower() == 'person':
            for_patterns = [
                r'for\s+(?:the\s+)?([A-Z][A-Za-z0-9_\s-]+?)(?:\s+role)?\s*$',
                r'for\s+(?:the\s+)?([A-Z]{2,})(?:\s+role)?\s*$',
            ]
            for pattern in for_patterns:
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    potential_subtype = match.group(1).strip()
                    person_subtype_keywords = [
                        'data protection officer', 'dpo', 'data protection',
                        'security officer', 'cio', 'cto', 'cfo', 'ciso',
                        'chief information officer', 'chief technology officer',
                        'chief financial officer', 'chief information security officer'
                    ]
                    potential_lower = potential_subtype.lower()
                    for keyword in person_subtype_keywords:
                        if keyword in potential_lower or potential_lower in keyword:
                            return potential_subtype
        
        # Pattern 4: Standard patterns
        patterns = [
            r'subType[:\s]+([A-Za-z0-9_\s-]+)',
            r'subtype[:\s]+([A-Za-z0-9_\s-]+)',
            r'type[:\s]+([A-Za-z0-9_\s-]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                subType = match.group(1).strip()
                if subType:
                    return subType
        return None
    
    def _getSubTypesInfo(self, domainId: str, objectType: str) -> Dict:
        """Get subTypes information for an object type in a domain"""
        try:
            result = self.veriniceTool.getDomainSubTypes(domainId, objectType)
            if result.get('success'):
                return {
                    'subTypes': result.get('subTypes', []),
                    'count': result.get('count', 0)
                }
        except Exception:
            pass
        return {'subTypes': [], 'count': 0}
    
    def _determineSubType(self, objectType: str, name: str, abbreviation: str, description: str, domainId: str) -> Optional[str]:
        """
        Determine subtype using simple pattern matching and interactive selection.
        Simple approach: Pattern matching first, then ask user if needed.
        """
        subTypesInfo = self._getSubTypesInfo(domainId, objectType)
        availableSubTypes = subTypesInfo.get('subTypes', [])
        
        # If no subtypes available, return None
        if not availableSubTypes:
            return None
        
        # If only one subtype, use it
        if len(availableSubTypes) == 1:
            if len(availableSubTypes) > 0:
                return availableSubTypes[0]
            return None
        
        # Try pattern matching
        inferred = self._inferSubTypeFromPattern(objectType, name, abbreviation, description, availableSubTypes)
        if inferred:
            return inferred
        
        # Pattern matching failed - return None to trigger user prompt in _handleCreate
        return None
    
    def _inferSubTypeFromPattern(self, objectType: str, name: str, abbreviation: str, description: str, availableSubTypes: List[str]) -> Optional[str]:
        """
        Infer subtype from patterns in name, abbreviation, or description.
        Simple keyword matching - no LLM needed.
        """
        if not availableSubTypes:
            return None
        
        # Normalize inputs for matching
        name_lower = (name or '').lower().strip()
        abbr_lower = (abbreviation or '').lower().strip()
        desc_lower = (description or '').lower().strip()
        combined_text = f"{name_lower} {abbr_lower} {desc_lower}"
        
        # Helper to normalize subtype names (remove prefixes like AST_, PER_, etc.)
        def normalize_subtype(st: str) -> str:
            st_clean = st.lower().replace('ast_', '').replace('per_', '').replace('_', ' ').replace('-', ' ')
            return st_clean.strip()
        
        # Try to match each available subtype
        for subType in availableSubTypes:
            subType_lower = subType.lower()
            subType_normalized = normalize_subtype(subType)
            
            # 1. Check if description itself is exactly a subtype name (exact match)
            if desc_lower == subType_lower or desc_lower == subType_normalized:
                return subType
            
            # 2. Check if description contains subtype name (with plural/singular handling)
            # "Datatypes" should match "AST_Datatype" or "Datatype"
            desc_words = desc_lower.split()
            for word in desc_words:
                # Exact match
                if word == subType_lower or word == subType_normalized:
                    return subType
                # Singular/plural match (e.g., "datatypes" matches "datatype")
                if word.rstrip('s') == subType_normalized.rstrip('s') or subType_normalized.rstrip('s') == word.rstrip('s'):
                    return subType
                # Contains match (e.g., "datatypes" contains "datatype")
                if word in subType_normalized or subType_normalized in word:
                    return subType
            
            # 3. Direct match in combined text
            if subType_lower in combined_text or subType_normalized in combined_text:
                return subType
            
            # 4. Pattern mappings for common subtypes
            patterns = {
                'person': {
                    'data protection officer': ['dpo', 'data protection', 'privacy officer', 'gdpr officer'],
                    'person': ['person', 'employee', 'staff', 'user']
                },
                'asset': {
                    'it-systems': ['it system', 'server', 'infrastructure', 'network', 'system'],
                    'it-system': ['it system', 'server', 'infrastructure', 'network', 'system'],
                    'applications': ['application', 'app', 'software', 'program'],
                    'application': ['application', 'app', 'software', 'program'],
                    'datatypes': ['data type', 'data', 'information', 'dataset', 'datatypes'],
                    'datatype': ['data type', 'data', 'information', 'dataset', 'datatypes']
                }
            }
            
            type_patterns = patterns.get(objectType.lower(), {})
            
            # Pattern match
            if subType_normalized in type_patterns:
                keywords = type_patterns[subType_normalized]
                for keyword in keywords:
                    if keyword in combined_text:
                        return subType
            
            # 5. Partial match (subtype name contains abbreviation or vice versa)
            if abbr_lower and (abbr_lower in subType_lower or subType_lower in abbr_lower):
                return subType
        
        return None
    
    def _matchSubType(self, providedSubType: str, availableSubTypes: List[str]) -> Optional[str]:
        """
        Match a user-provided subtype string against available subtypes.
        Handles variations like "Data protection officer" → "PER_DataProtectionOfficer"
        """
        if not availableSubTypes or not providedSubType:
            return None
        
        provided_lower = providedSubType.lower().strip()
        
        # Helper to normalize subtype names (remove prefixes like AST_, PER_, SCP_, CTL_, etc.)
        def normalize_subtype(st: str) -> str:
            st_lower = st.lower()
            prefixes = ['ast_', 'per_', 'scp_', 'ctl_', 'pro_', 'scn_', 'inc_', 'doc_']
            for prefix in prefixes:
                if st_lower.startswith(prefix):
                    st_lower = st_lower[len(prefix):]
                    break
            # Replace underscores and hyphens with spaces
            st_clean = st_lower.replace('_', ' ').replace('-', ' ')
            return st_clean.strip()
        
        # Try to match each available subtype
        for subType in availableSubTypes:
            subType_lower = subType.lower()
            subType_normalized = normalize_subtype(subType)
            
            # 1. Exact match (case-insensitive)
            if provided_lower == subType_lower or provided_lower == subType_normalized:
                return subType
            
            # 2. Normalized match (remove spaces, underscores, hyphens)
            provided_normalized = provided_lower.replace(' ', '').replace('_', '').replace('-', '')
            subType_normalized_no_spaces = subType_normalized.replace(' ', '').replace('_', '').replace('-', '')
            if provided_normalized == subType_normalized_no_spaces:
                return subType
            
            # 3. Word-by-word matching (e.g., "data protection officer" matches "dataprotectionofficer")
            provided_words = provided_lower.split()
            subType_words = subType_normalized.split()
            
            if all(word in subType_normalized for word in provided_words):
                return subType
            
            if all(word in provided_lower for word in subType_words):
                return subType
            
            # 4. Contains match (e.g., "data protection officer" contains "dataprotectionofficer")
            if provided_lower in subType_normalized or subType_normalized in provided_lower:
                return subType
            
            # 5. Pattern-based matching for common variations
            patterns = {
                'data protection officer': ['dpo', 'data protection', 'privacy officer', 'gdpr officer', 'dataprotectionofficer'],
                'dataprotectionofficer': ['dpo', 'data protection', 'privacy officer', 'gdpr officer', 'data protection officer'],
                'person': ['person', 'employee', 'staff', 'user'],
                'it-system': ['it system', 'server', 'infrastructure', 'network', 'system', 'it-systems'],
                'it-systems': ['it system', 'server', 'infrastructure', 'network', 'system', 'it-system'],
                'application': ['application', 'app', 'software', 'program'],
                'datatype': ['data type', 'data', 'information', 'dataset', 'datatypes'],
                'datatypes': ['data type', 'data', 'information', 'dataset', 'datatype'],
                'controller': ['controller', 'controllers', 'controllership', 'controllerships'],
                'controllers': ['controller', 'controllers', 'controllership', 'controllerships']
            }
            
            if subType_normalized in patterns:
                keywords = patterns[subType_normalized]
                for keyword in keywords:
                    if keyword in provided_lower or provided_lower in keyword:
                        return subType
        
        return None
    
    def _resolveToId(self, objectType: str, message: str, domainId: str) -> Optional[str]:
        """
        Resolve name or ID to object ID - single, simple method
        
        1. Check if message has UUID
        2. If not, extract name
        3. List objects and find by name (try default domain first, then all domains)
        4. Return ID or None
        """
        uuidMatch = re.search(r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})', message, re.IGNORECASE)
        if uuidMatch:
            return uuidMatch.group(1)
        
        # Extract name from message
        # CRITICAL: Handle quoted names FIRST (e.g., "Update the asset 'Main Firewall'. Change...")
        # For update commands, stop at field name (description, status, etc.)
        # For get/delete commands, capture everything after object type
        updateFieldKeywords = ['description', 'status', 'subtype', 'subType', 'name', 'abbreviation', 'abbr']
        
        patterns = [
            # CRITICAL: Handle "Update the asset 'Main Firewall'. Change its description..."
            # Pattern must match period/comma after quote, then space, then "Change" keyword
            rf'(?:update|change|modify|edit|set)\s+(?:the\s+)?{objectType}\s+["\']([^"\']+)["\']\s*[\.\,]\s+(?:change|set|update|description|confidentiality|status|name|abbreviation|subtype|subType|and|to)',
            # Pattern with period/comma after quote: "Update the asset 'Main_Firewall'."
            rf'(?:update|change|modify|edit|set)\s+(?:the\s+)?{objectType}\s+["\']([^"\']+)["\']\s*[\.\,]',
            # Pattern without punctuation after quote (but may have space and then text)
            rf'(?:update|change|modify|edit|set)\s+(?:the\s+)?{objectType}\s+["\']([^"\']+)["\'](?:\s|\.|,|$)',
            # CRITICAL: Handle role assignment patterns: "set role for the DPO for the person Ruby"
            # Extract name after "for the person" or "for person" - must be more specific to avoid matching wrong "for the"
            # Pattern: "set role for the X for the person Ruby" or "add in the X for the person Tommy"
            # Use non-greedy match to get the LAST "for the person" in the message
            rf'(?:set|add|assign).*?for\s+(?:the\s+)?person\s+["\']?([^"\']+)["\']?(?:\s|$|\.|,)',
            # Get/delete with quoted names
            rf'(?:get|view|show|delete|remove|analyze)\s+(?:the\s+)?{objectType}\s+["\']([^"\']+)["\']',
            rf'(?:update|change|modify|edit|set)\s+{objectType}\s+([A-Za-z0-9_\s-]+?)(?:\s+(?:{"|".join(updateFieldKeywords)}))',
            # Get/delete command: "get asset Name" - capture everything
            rf'(?:get|view|show|delete|remove|analyze)\s+{objectType}\s+(.+)',
            # Generic: "asset Name"
            rf'{objectType}\s+([A-Za-z0-9_\s-]+)',
        ]
        
        if objectType.lower() == 'person':
            # Pattern for "for the person X" - must come after other patterns to avoid false matches
            patterns.insert(-2, rf'for\s+(?:the\s+)?person\s+["\']?([^"\']+)["\']?(?:\s|$|\.|,)')
        
        name = None
        for pattern in patterns:
            if pattern is None:
                continue
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                # Clean up - remove common trailing words that indicate field names
                name = re.sub(r'\s+(description|status|subtype|subType|name|abbreviation|abbr|field|value|to|is|as).*$', '', name, flags=re.IGNORECASE).strip()
                if name:
                    break
        
        if not name:
            return None
        
        # Helper function to search in a specific domain
        def searchInDomain(dId: str) -> Optional[str]:
            if not self.veriniceTool:
                return None
            listResult = self.veriniceTool.listObjects(objectType, dId)
            if not listResult.get('success'):
                return None
            
            objects = listResult.get('objects', {})
            items = objects.get('items', []) if isinstance(objects, dict) else (objects if isinstance(objects, list) else [])
            
            # Find by name (exact match first, then fuzzy)
            for item in items:
                itemName = item.get('name', '').strip()
                if not itemName:
                    continue
                
                itemName_clean = itemName.strip("'\"")
                name_clean = name.strip("'\"")
                
                # Exact match (case-insensitive, ignoring quotes)
                if itemName_clean.lower() == name_clean.lower():
                    return item.get('id') or item.get('resourceId')
                
                # Also try exact match with original names (in case quotes are part of the name)
                if itemName.lower() == name.lower():
                    return item.get('id') or item.get('resourceId')
                
                # Fuzzy match (substring) - but be more lenient
                # Also handle cases where spaces might be replaced with underscores or hyphens
                name_normalized = name_clean.lower().replace('_', ' ').replace('-', ' ').strip()
                item_name_normalized = itemName_clean.lower().replace('_', ' ').replace('-', ' ').strip()
                
                if name_normalized == item_name_normalized:
                    return item.get('id') or item.get('resourceId')
                if name_normalized in item_name_normalized or item_name_normalized in name_normalized:
                    return item.get('id') or item.get('resourceId')
                
                # Also try matching with underscores/hyphens
                name_underscore = name_clean.lower().replace(' ', '_')
                name_hyphen = name_clean.lower().replace(' ', '-')
                item_underscore = itemName_clean.lower().replace(' ', '_')
                item_hyphen = itemName_clean.lower().replace(' ', '-')
                
                if name_underscore == item_underscore or name_hyphen == item_hyphen:
                    return item.get('id') or item.get('resourceId')
                if item_underscore == name_underscore or item_hyphen == name_hyphen:
                    return item.get('id') or item.get('resourceId')
                
                # Word-by-word matching (handles "Main Firewall" vs "Main_Firewall" or partial matches)
                name_words = set(name_normalized.split())
                item_words = set(item_name_normalized.split())
                if name_words and item_words:
                    if name_words.issubset(item_words) or item_words.issubset(name_words):
                        return item.get('id') or item.get('resourceId')
                    # If most words match (80% threshold), consider it a match
                    intersection = name_words & item_words
                    if intersection:
                        match_ratio = len(intersection) / max(len(name_words), len(item_words))
                        if match_ratio >= 0.8:
                            return item.get('id') or item.get('resourceId')
                        # Lower threshold for partial matches (e.g., "Main" in "Main Firewall")
                        if len(intersection) >= min(len(name_words), len(item_words)):
                            return item.get('id') or item.get('resourceId')
            
            return None
        
        # Try default domain first (most common case) with retries
        max_retries = 3
        delay_seconds = 2
        
        logger.error(f"[_resolveToId] DEBUG: Resolving '{name}' (type: {objectType}) in domain '{domainId}'")
        
        if domainId:
            for attempt in range(max_retries):
                result = searchInDomain(domainId)
                if result:
                    logger.info(f"[_resolveToId] Found '{name}' in default domain: {result}")
                    return result
                logger.error(f"[_resolveToId] DEBUG: Object '{name}' not found in domain '{domainId}' (attempt {attempt + 1}/{max_retries}).")
                # DEBUG: List what was found to see why it didn't match
                listResult = self.veriniceTool.listObjects(objectType, domainId)
                if listResult.get('success'):
                    found_names = [o.get('name') for o in listResult.get('objects', {}).get('items', [])]
                    logger.error(f"[_resolveToId] DEBUG: Available objects in domain: {found_names}")
                
                time.sleep(delay_seconds)
        
        # If not found in domain, try searching in the unit (if available)
        # Some objects might be created at unit level
        _, unitId = self._getDefaults()
        if unitId:
            logger.info(f"[_resolveToId] Searching in unit '{unitId}' for '{name}'")
            listResult = self.veriniceTool.listObjects(objectType, None, unitId=unitId)
            if listResult.get('success'):
                objects = listResult.get('objects', {})
                items = objects.get('items', []) if isinstance(objects, dict) else (objects if isinstance(objects, list) else [])
                
                # Reuse search logic (copy-paste for now, could be refactored)
                for item in items:
                    itemName = item.get('name', '').strip()
                    if not itemName:
                        continue
                    
                    itemName_clean = itemName.strip("'\"")
                    name_clean = name.strip("'\"")
                    
                    # Exact/Fuzzy matching logic identical to searchInDomain
                    if itemName_clean.lower() == name_clean.lower():
                        return item.get('id') or item.get('resourceId')
                    if itemName.lower() == name.lower():
                        return item.get('id') or item.get('resourceId')
                    
                    name_normalized = name_clean.lower().replace('_', ' ').replace('-', ' ').strip()
                    item_name_normalized = itemName_clean.lower().replace('_', ' ').replace('-', ' ').strip()
                    
                    if name_normalized == item_name_normalized:
                        return item.get('id') or item.get('resourceId')
                    if name_normalized in item_name_normalized or item_name_normalized in name_normalized:
                        return item.get('id') or item.get('resourceId')
        
        # If not found in default domain after retries, search all domains
        # This handles cases where objects are in different domains or domain cache is stale
        logger.info(f"[_resolveToId] Searching all domains for '{name}'")
        domainsResult = self.veriniceTool.listDomains()
        if domainsResult.get('success') and domainsResult.get('domains'):
            domains = domainsResult['domains']
            # Search all domains, including the default one again (in case it wasn't searched above)
            for domain in domains:
                dId = domain.get('id') if isinstance(domain, dict) else domain
                if dId:
                    # Don't skip default domain - search it again if it wasn't found first time
                    # (handles cases where domainId was None or search failed)
                    result = searchInDomain(dId)
                    if result:
                        return result
        
        return None
    
    # ==================== RESPONSE HELPERS ====================
    
    def _success(self, result: Any) -> Dict:
        """Success response"""
        return {
            'status': 'success',
            'result': result,
            'type': 'tool_result'
        }
    
    def _extract_error_details(self, result: Dict) -> str:
        """Extract specific error details from API response"""
        # Try multiple error fields in order of specificity
        error = result.get('error') or result.get('message') or result.get('text')
        
        # If error is a dict, extract message from it
        if isinstance(error, dict):
            error = error.get('message') or error.get('error') or error.get('detail') or str(error)
        
        if not error:
            error_data = result.get('data', {})
            if isinstance(error_data, dict):
                # Try common error message fields
                error = (error_data.get('message') or 
                        error_data.get('error') or 
                        error_data.get('detail') or
                        error_data.get('errorMessage') or
                        error_data.get('error_description'))
        
        if not error:
            exception = result.get('exception')
            if exception:
                error = str(exception)
        
        if not error:
            status_code = result.get('status_code')
            if status_code:
                if status_code == 404:
                    error = "Object not found - the requested item doesn't exist"
                elif status_code == 400:
                    error = "Invalid request - please check your input parameters"
                elif status_code == 401:
                    error = "Authentication failed - please check your credentials"
                elif status_code == 403:
                    error = "Permission denied - you don't have access to this resource"
                elif status_code == 409:
                    error = "Conflict - object may already exist or there's a naming conflict"
                elif status_code == 422:
                    error = "Validation failed - required fields are missing or invalid"
                elif status_code == 500:
                    error = "Server error - Verinice backend encountered an issue"
                else:
                    error = f"HTTP {status_code} error occurred"
        
        # If error contains server response, try to parse JSON
        if error and ('Server response:' in error or 'response' in error.lower()):
            # Try to extract JSON error message
            json_match = re.search(r'\{[^}]+\}', error)
            if json_match:
                try:
                    json_data = json.loads(json_match.group())
                    if isinstance(json_data, dict):
                        json_error = json_data.get('message') or json_data.get('error') or json_data.get('detail')
                        if json_error:
                            error = json_error
                except (json.JSONDecodeError, ValueError, KeyError):
                    pass
        
        # Clean up error message - remove generic prefixes
        if error:
            error = re.sub(r'^(Error|Exception|Failed):\s*', '', error, flags=re.IGNORECASE)
            error = error.strip()
        
        return error or "Operation failed - no error details available"
    
    def _error(self, message: str) -> Dict:
        """Error response"""
        return {
            'status': 'error',
            'result': message,
            'type': 'error'
        }
