"""
ISMS Coordinator - Phase 4 Refactoring

Coordinates all ISMS operations including CRUD, reports, and follow-ups.

Status: ISOLATION BUILD - NOT CONNECTED TO PRODUCTION
Feature Flag: _useIsmsCoordinator = False (when integrated)
"""

from typing import Dict, Optional, List, Any
import re
from agents.instructions import (
    get_error_message,
    VERINICE_OBJECT_TYPES,
    VERINICE_CREATE_KEYWORDS,
    VERINICE_LIST_KEYWORDS,
    VERINICE_GET_KEYWORDS,
    VERINICE_UPDATE_KEYWORDS,
    VERINICE_DELETE_KEYWORDS,
    VERINICE_SUBTYPE_MAPPINGS,
    VERINICE_TYPO_CORRECTIONS
)


class ISMSCoordinator:
    """
    Coordinates all ISMS operations with clean separation of concerns.
    
    Replaces ISMSHandler with a coordinator pattern.
    Handles CRUD operations, report generation, and follow-ups.
    """
    
    def __init__(self, state: Dict, tools: Dict, contextManager=None):
        """
        Initialize ISMS Coordinator with explicit dependencies.
        
        Args:
            state: Agent state dictionary (passed by reference)
            tools: Dictionary of available tools
            contextManager: Optional context manager for session data
        
        Example:
            tools = {
                'veriniceTool': veriniceTool,
                'llmTool': llmTool  # optional
            }
            coordinator = ISMSCoordinator(agent.state, tools)
        """
        self.state = state
        self.veriniceTool = tools.get('veriniceTool')
        self.llmTool = tools.get('llmTool')
        self.contextManager = contextManager
        
        # Internal handler (lazy initialization)
        self._ismsHandler = None
        
        # Caches (from ISMSHandler)
        self._domainCache = None
        self._unitCache = None
    
    def _getCreateKeywordsPattern(self) -> str:
        """Build regex pattern for create keywords from JSON config"""
        return '|'.join(re.escape(kw) for kw in VERINICE_CREATE_KEYWORDS)
    
    # ==================== PUBLIC INTERFACE ====================
    
    def handleOperation(self, operation: str, objectType: str, message: str) -> Dict:
        """
        Handle ISMS CRUD operations (main entry point).
        
        Replaces ISMSHandler.execute()
        
        Args:
            operation: Operation type (create, list, get, update, delete)
            objectType: ISMS object type (asset, scope, person, etc.)
            message: User's original message
        
        Returns:
            Dict with response data:
            {
                'type': 'success' | 'error',
                'text': str,  # Response message
                'data': dict  # Optional operation results
            }
        
        Examples:
            # Create operation
            result = coordinator.handleOperation('create', 'asset', 'create asset MyAsset')
            
            # List operation
            result = coordinator.handleOperation('list', 'scopes', 'list scopes')
            
            # Get operation
            result = coordinator.handleOperation('get', 'asset', 'get asset MyAsset')
        
        Raises:
            None - returns error dict instead
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
            'analyze': self._handleAnalyze
        }
        
        handler = handlers.get(operation)
        if not handler:
            return self._error(get_error_message('validation', 'unknown_operation', operation=operation))
        
        return handler(objectType, message, domainId, unitId)
    
    def handleReportGeneration(self, command: Dict, message: str) -> Dict:
        """
        Handle report generation requests.
        
        Lists available scopes and stores pending state for user selection.
        
        Args:
            command: Dict with reportType (e.g., {'reportType': 'inventory-of-assets'})
            message: User's original message
        
        Returns:
            Dict with response:
            {
                'type': 'text',
                'text': str,  # List of scopes for selection
                'data': {
                    'pendingReportGeneration': {
                        'reportType': str,
                        'scopes': list
                    }
                }
            }
        
        Side Effects:
            Sets self.state['pendingReportGeneration']
        
        Example:
            command = {'reportType': 'inventory-of-assets'}
            result = coordinator.handleReportGeneration(command, message)
        """
        # TODO: Implement (port from MainAgent._handleReportGeneration)
        # For now, return placeholder
        return self._error(get_error_message('implementation', 'report_generation_not_implemented'))
    
    def handleReportFollowUp(self, message: str) -> Dict:
        """
        Handle report generation follow-up (scope selection).
        
        Processes user's scope selection and generates the report.
        
        Args:
            message: User's scope selection (e.g., "1" or "MyScope")
        
        Returns:
            Dict with report data:
            {
                'type': 'report',
                'text': str,  # Success message
                'report': {
                    'format': 'pdf',
                    'data': str,  # Base64 encoded PDF
                    'reportType': str,
                    'scope': str
                }
            }
        
        Side Effects:
            Clears self.state['pendingReportGeneration']
        
        Prerequisites:
            Must have self.state['pendingReportGeneration'] set
        
        Raises:
            Returns error dict if:
            - No pending report generation
            - Invalid scope selection
            - Report generation fails
        """
        # TODO: Implement (port from MainAgent._handleReportGenerationFollowUp)
        # For now, return placeholder
        return self._error(get_error_message('implementation', 'report_followup_not_implemented'))
    
    def handleSubtypeFollowUp(self, message: str) -> Optional[Dict]:
        """
        Handle subtype selection follow-up.
        
        Completes pending creation operations that require subtype selection.
        
        Args:
            message: User's subtype selection (e.g., "2" or "AST_IT-System")
        
        Returns:
            Dict with creation result if pending operation exists:
            {
                'type': 'success',
                'text': str,  # Success message
                'data': dict  # Created object data
            }
            
            None if no pending subtype selection
        
        Side Effects:
            Clears self.state['_pendingSubtypeSelection']
        
        Prerequisites:
            Must have self.state['_pendingSubtypeSelection'] set
        
        Example:
            # After create operation prompts for subtype
            result = coordinator.handleSubtypeFollowUp("2")
        """
        # TODO: Implement (port from MainAgent._handleSubtypeFollowUp)
        # For now, return None (no pending operation)
        return None
    
    # ==================== INTERNAL METHODS ====================
    # These methods will be ported from ISMSHandler
    
    def _getHandler(self):
        """
        Lazy initialize ISMSHandler (internal).
        
        Returns existing handler or creates new one if needed.
        """
        # TODO: Implement lazy initialization
        pass
    
    def _getDefaults(self):
        """
        Get default domain and unit (with caching).
        
        Returns:
            Tuple[str, str]: (domainId, unitId)
        
        Note:
            Uses instance variable caching to avoid repeated API calls.
            Cache is cleared on initialization.
        """
        # Return cached values if available
        if self._domainCache and self._unitCache:
            return self._domainCache, self._unitCache
        
        unitsResult = self.veriniceTool.listUnits()
        if unitsResult.get('success'):
            units = unitsResult.get('units', [])
            if units and len(units) > 0:
                unit = units[0]
                self._unitCache = unit.get('id')
                
                domains = unit.get('domains', [])
                if domains:
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
    
    def _handleCreate(self, objectType: str, message: str, domainId: str, unitId: str, preDetectedSubType: Optional[str] = None) -> Dict:
        """
        Create operation handler (internal).
        
        Most complex handler - extracts parameters, handles subtypes, creates object.
        
        Args:
            objectType: Type of object to create
            message: User's message
            domainId: Domain ID
            unitId: Unit ID
            preDetectedSubType: Optional subtype detected by router (e.g., "Controllers" from "create Controllers named X")
        
        Returns:
            Dict with creation result
        """
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
                
                # If we got name, proceed with creation (subtype can be None and will be handled later)
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
                        # Store created object info in state
                        created_id = result.get('id')
                        if created_id:
                            key = f"{objectType}_{name}"
                            if '_created_objects' not in self.state:
                                self.state['_created_objects'] = {}
                            self.state['_created_objects'][key] = {
                                'id': created_id,
                                'name': name,
                                'type': objectType,
                                'subType': subType
                            }
                        subtype_msg = f" with subtype '{subType}'" if subType else ""
                        return self._success(f"Created {objectType} '{name}'{subtype_msg}")
                    else:
                        return self._error(get_error_message('operation_failed', 'create', objectType=objectType, error=result.get('error', 'Unknown error')))
        
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
            # Normal flow: Try simple format first
            simpleFormat = self._extractSimpleFormat(message, objectType)
            if simpleFormat:
                name = simpleFormat['name']
                abbreviation = simpleFormat.get('abbreviation')
                description = simpleFormat.get('description', '')
                subType = simpleFormat.get('subType')
            else:
                # Fallback to keyword extraction
                name = self._extractName(message, objectType)
                if not name:
                    return self._error(get_error_message('validation', 'what_name_for_object', objectType=objectType))
                abbreviation = self._extractAbbreviation(message)
                description = self._extractDescription(message) or ""
                subType = self._extractSubType(message, objectType)
        
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
        
        # If subType not provided, try to infer or auto-select
        if not subType:
            subTypesInfo = self._getSubTypesInfo(domainId, objectType)
            availableSubTypes = subTypesInfo.get('subTypes', [])
            
            if not availableSubTypes:
                pass  # No subtypes, proceed without
            elif len(availableSubTypes) == 1:
                subType = availableSubTypes[0]  # Only one option
            else:
                # Try pattern matching
                inferred = self._inferSubTypeFromPattern(objectType, name, abbreviation, description, availableSubTypes)
                if inferred:
                    subType = inferred
                else:
                    # Auto-select first subtype for consistency
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
            # Store created object info in state for quick lookup (helps with UPDATE/DELETE immediately after CREATE)
            objectId = result.get('objectId') or result.get('data', {}).get('resourceId') or result.get('data', {}).get('id')
            if objectId and name:
                # Store in state for quick resolution
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
            if objectId:
                info += f" (ID: {objectId[:8]}...)"
            return self._success(info)
        
        return self._error(get_error_message('operation_failed', 'create', objectType=objectType, error=result.get('error', 'Unknown error')))
    
    def _handleList(self, objectType: str, message: str, domainId: str, unitId: str) -> Dict:
        """
        List operation handler (internal).
        
        Supports subtype filtering: list assets subType AST_IT-System
        
        Args:
            objectType: Type of object to list
            message: User's message (may contain subtype filter)
            domainId: Domain ID
            unitId: Unit ID
        
        Returns:
            Dict with list results (filtered by subtype if specified)
        """
        # Extract subtype filter from message if present
        subtypeFilter = self._extractSubType(message, objectType)
        
        # Helper function to filter items by subtype
        def filterBySubtype(items: List[Dict], subtype: Optional[str]) -> List[Dict]:
            """Filter items by subtype if subtype filter is provided"""
            if not subtype:
                return items
            # Normalize subtype for comparison
            subtype_lower = subtype.lower().strip()
            filtered = []
            for item in items:
                item_subtype = item.get('subType') or item.get('subtype', '')
                if item_subtype:
                    # Try exact match
                    if item_subtype.lower() == subtype_lower:
                        filtered.append(item)
                    # Try matching without prefix (e.g., "IT-System" matches "AST_IT-System")
                    elif subtype_lower.replace('ast_', '').replace('per_', '') in item_subtype.lower():
                        filtered.append(item)
                    # Try reverse (item subtype without prefix matches filter)
                    elif item_subtype.lower().replace('ast_', '').replace('per_', '') == subtype_lower:
                        filtered.append(item)
            return filtered if filtered else items  # Return all if no matches (might be wrong filter)
        
        # Special handling for scopes - can be listed without domain
        if objectType == 'scope' and not domainId:
            if unitId:
                result = self.veriniceTool.listObjects(objectType, None, unitId=unitId)
                if result.get('success'):
                    # Apply subtype filter if specified
                    if subtypeFilter:
                        objects = result.get('objects', {})
                        items = objects.get('items', []) if isinstance(objects, dict) else (objects if isinstance(objects, list) else [])
                        filtered_items = filterBySubtype(items, subtypeFilter)
                        if isinstance(objects, dict):
                            objects['items'] = filtered_items
                        else:
                            result['objects'] = filtered_items
                    result['objectType'] = objectType
                    formatted = self._formatResult('listVeriniceObjects', result)
                    return self._success(formatted)
                return self._error(get_error_message('operation_failed', 'list_scopes', error=result.get('error', 'Unknown error')))
            else:
                # No unit - try to get units
                unitsResult = self.veriniceTool.listUnits()
                if not unitsResult.get('success'):
                    errorMsg = unitsResult.get('error', 'Unknown error')
                    if 'not available' in errorMsg.lower() or 'authentication' in errorMsg.lower() or 'connection' in errorMsg.lower():
                        return self._error(get_error_message('connection', 'isms_unavailable', error=errorMsg))
                    # Fallback to domains
                    domainsResult = self.veriniceTool.listDomains()
                    if domainsResult.get('success') and domainsResult.get('domains'):
                        domainId = domainsResult['domains'][0].get('id')
                        result = self.veriniceTool.listObjects(objectType, domainId)
                        if result.get('success'):
                            result['objectType'] = objectType
                            formatted = self._formatResult('listVeriniceObjects', result)
                            return self._success(formatted)
                        return self._error(get_error_message('operation_failed', 'list_scopes', error=result.get('error', 'Unknown error')))
                    return self._error(get_error_message('operation_failed', 'list_units', error=errorMsg))
                
                units = unitsResult.get('units')
                if not units or (isinstance(units, list) and len(units) == 0):
                    # No units - try domains fallback
                    domainsResult = self.veriniceTool.listDomains()
                    if domainsResult.get('success') and domainsResult.get('domains'):
                        domainId = domainsResult['domains'][0].get('id')
                        result = self.veriniceTool.listObjects(objectType, domainId)
                        if result.get('success'):
                            result['objectType'] = objectType
                            formatted = self._formatResult('listVeriniceObjects', result)
                            return self._success(formatted)
                        return self._error(get_error_message('operation_failed', 'list_scopes', error=result.get('error', 'Unknown error')))
                    return self._error(get_error_message('not_found', 'unit'))
                
                # Use first unit
                firstUnit = units[0]
                unitId = firstUnit.get('id')
                if not unitId:
                    return self._error(get_error_message('not_found', 'unit_missing_id'))
                
                result = self.veriniceTool.listObjects(objectType, None, unitId=unitId)
                if result.get('success'):
                    result['objectType'] = objectType
                    formatted = self._formatResult('listVeriniceObjects', result)
                    return self._success(formatted)
                return self._error(get_error_message('operation_failed', 'list_scopes', error=result.get('error', 'Unknown error')))
        
        # Standard list with domain
        # CRITICAL: If no domainId provided, or the domain-specific query returns
        # no items, try ALL domains so we don't miss objects that live outside
        # the default domain (e.g., assets created in other domains).
        def _aggregate_from_all_domains() -> Dict:
            domainsResult = self.veriniceTool.listDomains()
            if not (domainsResult.get('success') and domainsResult.get('domains')):
                # Make message context-aware
                object_type_singular = self._getSingularForm(objectType)
                return self._error(get_error_message('operation_failed', 'list_no_domain', objectType=objectType))
            
            all_items = []
            domains = domainsResult.get('domains', [])
            for d in domains:
                d_id = d.get('id') if isinstance(d, dict) else d
                if not d_id:
                    continue
                res = self.veriniceTool.listObjects(objectType, d_id)
                if not res.get('success'):
                    continue
                objects = res.get('objects', {})
                items = objects.get('items', []) if isinstance(objects, dict) else (objects if isinstance(objects, list) else [])
                all_items.extend(items)
            
            if not all_items:
                # Return a success response with a clear "no objects" message
                # Make it context-aware based on the requested object type
                object_type_singular = self._getSingularForm(objectType)
                # Generate example name based on object type
                example_name = f"{object_type_singular.capitalize()}Name"
                return self._success(f"No {objectType} found in any domain. Try: 'create {object_type_singular} {example_name}' to create one.")
            
            seen_ids = set()
            unique_items = []
            for item in all_items:
                item_id = item.get('id') or item.get('resourceId')
                if item_id and item_id not in seen_ids:
                    seen_ids.add(item_id)
                    unique_items.append(item)
            
            # Apply subtype filter if specified
            if subtypeFilter:
                unique_items = filterBySubtype(unique_items, subtypeFilter)
            
            aggregated_result = {
                'success': True,
                'objects': {'items': unique_items},
                'objectType': objectType
            }
            formatted = self._formatResult('listVeriniceObjects', aggregated_result)
            return self._success(formatted)
        
        # If no domain specified, aggregate across all domains
        if not domainId:
            return _aggregate_from_all_domains()
        
        # Try listing in the given domain first
        result = self.veriniceTool.listObjects(objectType, domainId)
        if result.get('success'):
            objects = result.get('objects', {})
            items = objects.get('items', []) if isinstance(objects, dict) else (objects if isinstance(objects, list) else [])
            
            # Apply subtype filter if specified
            if subtypeFilter:
                items = filterBySubtype(items, subtypeFilter)
                if isinstance(objects, dict):
                    objects['items'] = items
                else:
                    result['objects'] = items
            
            if not items:
                # Domain-specific query returned no items; fall back to all domains
                return _aggregate_from_all_domains()
            
            result['objectType'] = objectType
            formatted = self._formatResult('listVeriniceObjects', result)
            return self._success(formatted)
        
        return self._error(get_error_message('operation_failed', 'list_objects', objectType=objectType, error=result.get('error', 'Unknown error')))
    
    def _handleGet(self, objectType: str, message: str, domainId: str, unitId: str) -> Dict:
        """
        Get operation handler (internal).
        
        Finds object by name or ID and retrieves details.
        
        Args:
            objectType: Type of object
            message: User's message
            domainId: Domain ID
            unitId: Unit ID (unused but kept for consistency)
        
        Returns:
            Dict with object details
        """
        objectId, foundDomainId = self._resolveToId(objectType, message, domainId)
        if not objectId:
            return self._error(get_error_message('validation', 'missing_params', objectType=objectType))
        
        # Use the domain where the object was actually found
        actualDomainId = foundDomainId if foundDomainId else domainId
        result = self.veriniceTool.getObject(objectType, actualDomainId, objectId)
        if result.get('success'):
            formatted = self._formatResult('getVeriniceObject', result)
            return self._success(formatted)
        return self._error(get_error_message('not_found', 'object', objectType=objectType, error=result.get('error', 'Unknown error')))
    
    def _handleDelete(self, objectType: str, message: str, domainId: str, unitId: str) -> Dict:
        """
        Delete operation handler (internal).
        
        Args:
            objectType: Type of object
            message: User's message
            domainId: Domain ID
            unitId: Unit ID (unused but kept for consistency)
        
        Returns:
            Dict with deletion result
        """
        # Debug: Print what we're trying to resolve
        print(f"[DEBUG DELETE] Resolving {objectType} from message: '{message[:100]}' with domainId: {domainId}")
        objectId, foundDomainId = self._resolveToId(objectType, message, domainId)
        print(f"[DEBUG DELETE] Resolved to: objectId={objectId}, foundDomainId={foundDomainId}")
        if not objectId:
            return self._error(get_error_message('validation', 'missing_params_delete', objectType=objectType))
        
        # Use the domain where the object was actually found
        actualDomainId = foundDomainId if foundDomainId else domainId
        result = self.veriniceTool.deleteObject(objectType, actualDomainId, objectId)
        if result.get('success'):
            return self._success(f"Deleted {objectType} successfully")
        return self._error(get_error_message('operation_failed', 'delete', objectType=objectType, error=result.get('error', 'Unknown error')))
    
    def _handleUpdate(self, objectType: str, message: str, domainId: str, unitId: str) -> Dict:
        """
        Update operation handler (internal).
        
        UPDATE can change:
        - Object names: "update asset OldName to NewName"
        - Descriptions: "update asset X. Change its description to 'New description'"
        - Other properties: "update asset X. Set its confidentiality to 'High'"
        - Multiple fields: "update asset X. Change description to 'Y' and set confidentiality to 'High'"
        
        Args:
            objectType: Type of object
            message: User's message
            domainId: Domain ID
            unitId: Unit ID (unused but kept for consistency)
        
        Returns:
            Dict with update result
        """
        # Debug: Print what we're trying to resolve
        print(f"[DEBUG UPDATE] Resolving {objectType} from message: '{message[:100]}' with domainId: {domainId}")
        # For UPDATE, pass the full message to _resolveToId so it can extract the name
        objectId, foundDomainId = self._resolveToId(objectType, message, domainId)
        print(f"[DEBUG UPDATE] Resolved to: objectId={objectId}, foundDomainId={foundDomainId}")
        if not objectId:
            # Try to extract name manually for better error message
            import re
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
        
        # Use the domain where the object was actually found
        actualDomainId = foundDomainId if foundDomainId else domainId
        
        # Extract all fields to update
        updateData = {}
        updatedFields = []
        
        # 1. Extract new name (if specified)
        newName = self._extractNewNameFromUpdate(message, objectType)
        if newName:
            updateData['name'] = newName
            updatedFields.append(f"name to '{newName}'")
        
        # 2. Extract description (if specified)
        description = self._extractDescriptionFromUpdate(message)
        if description:
            updateData['description'] = description
            updatedFields.append(f"description to '{description}'")
        
        # 3. Extract other properties (confidentiality, status, subtype, etc.)
        otherProps = self._extractPropertiesFromUpdate(message)
        if otherProps:
            # If subtype is being updated, validate and match it
            if 'subType' in otherProps:
                subType = otherProps['subType']
                subTypesInfo = self._getSubTypesInfo(actualDomainId, objectType)
                availableSubTypes = subTypesInfo.get('subTypes', [])
                if availableSubTypes:
                    if subType not in availableSubTypes:
                        # Try intelligent matching
                        matched = self._matchSubType(subType, availableSubTypes)
                        if matched:
                            otherProps['subType'] = matched
                        else:
                            return self._error(get_error_message('validation', 'invalid_subtype', subType=subType, available=', '.join(availableSubTypes[:5])))
            
            updateData.update(otherProps)
            for key, value in otherProps.items():
                updatedFields.append(f"{key} to '{value}'")
        
        if not updateData:
            return self._error(get_error_message('validation', 'what_should_be_updated', objectType=objectType))
        
        oldName = None
        if 'name' in updateData:
            oldName = self._extractName(message, objectType)
            print(f"[DEBUG UPDATE] Old name: '{oldName}', New name: '{newName}'")
        
        result = self.veriniceTool.updateObject(objectType, actualDomainId, objectId, updateData)
        if result.get('success'):
            if 'name' in updateData and oldName:
                if '_created_objects' not in self.state:
                    self.state['_created_objects'] = {}
                
                # Normalize function for cache keys
                def normalize_key(n: str) -> str:
                    return n.lower().replace('_', ' ').replace('-', ' ').strip()
                
                old_key = f"{objectType}:{normalize_key(oldName)}"
                cached_info = self.state['_created_objects'].pop(old_key, None)
                if cached_info:
                    print(f"[DEBUG UPDATE] Removed old cache entry: {old_key}")
                
                new_key = f"{objectType}:{normalize_key(newName)}"
                self.state['_created_objects'][new_key] = {
                    'objectId': objectId,
                    'domainId': actualDomainId,
                    'objectType': objectType,
                    'name': newName
                }
                print(f"[DEBUG UPDATE] ✅ Updated state cache: {old_key} -> {new_key}")
            
            # Build success message
            if len(updatedFields) == 1:
                successMsg = f"Updated {objectType} {updatedFields[0]}"
            else:
                successMsg = f"Updated {objectType}:\n" + "\n".join(f"- {field}" for field in updatedFields)
            
            return self._success(successMsg)
        return self._error(get_error_message('operation_failed', 'update', error=result.get('error', 'Unknown error')))
    
    def _extractNewNameFromUpdate(self, message: str, objectType: str) -> Optional[str]:
        """
        Extract new name from update message.
        
        Handles name changes in update operations.
        Patterns:
        - "update asset OldName to NewName"
        - "update asset OldName NewName"
        - "update asset OldName name NewName"
        - "update asset OldName rename NewName"
        - "update asset OldName. Change name to NewName"
        
        Note: Returns None if no name change is specified (allows description/property-only updates)
        
        Args:
            message: User's message
            objectType: Type of object
        
        Returns:
            New name or None (if no name change)
        """
        messageLower = message.lower()
        
        # Pattern 1: "update asset OldName to NewName" (simple "to" pattern)
        # But only if "to" is followed by a name, not "change" or "set"
        pattern1 = rf'update\s+{objectType}\s+[A-Za-z0-9_\s\'-]+\s+to\s+([A-Za-z0-9_\s\'-]+?)(?:\s*\.|,|\s+and|\s+change|\s+set|$)'
        match = re.search(pattern1, message, re.IGNORECASE)
        if match:
            newName = match.group(1).strip().strip("'\"")
            if newName.lower() not in ['change', 'set', 'update'] and len(newName) > 0:
                newName = re.sub(r'\s+(in|for|with|using|the|description|abbreviation|subType|status|change|set).*$', '', newName, flags=re.IGNORECASE).strip()
                if newName:
                    return newName
        
        # Pattern 2: "update asset OldName NewName" (two names after objectType)
        # But be careful - if second word is "change" or "set", it's not a name
        pattern2 = rf'update\s+{objectType}\s+([A-Za-z0-9_\s\'-]+?)\s+([A-Za-z0-9_\s\'-]+?)(?:\s*\.|,|\s+and|\s+change|\s+set|$)'
        match = re.search(pattern2, message, re.IGNORECASE)
        if match:
            oldName = match.group(1).strip().strip("'\"")
            potentialNewName = match.group(2).strip().strip("'\"")
            # If potentialNewName doesn't look like a keyword, it's the new name
            keywords = ['name', 'rename', 'to', 'as', 'description', 'abbreviation', 'subType', 'status', 'change', 'set', 'update']
            if potentialNewName.lower() not in keywords and len(potentialNewName) > 0:
                potentialNewName = re.sub(r'\s+(in|for|with|using|the|description|abbreviation|subType|status|change|set).*$', '', potentialNewName, flags=re.IGNORECASE).strip()
                if potentialNewName:
                    return potentialNewName
        
        # Pattern 3: "update asset OldName name NewName" or "update asset OldName rename NewName"
        pattern3 = rf'update\s+{objectType}\s+[A-Za-z0-9_\s\'-]+\s+(?:name|rename)\s+(?:to\s+)?([A-Za-z0-9_\s\'-]+?)(?:\s*\.|,|\s+and|\s+change|\s+set|$)'
        match = re.search(pattern3, message, re.IGNORECASE)
        if match:
            newName = match.group(1).strip().strip("'\"")
            newName = re.sub(r'\s+(in|for|with|using|the|description|abbreviation|subType|status).*$', '', newName, flags=re.IGNORECASE).strip()
            if newName:
                return newName
        
        return None
    
    def _extractDescriptionFromUpdate(self, message: str) -> Optional[str]:
        """
        Extract description from update message.
        
        Handles patterns like:
        - "Change its description to 'X'"
        - "Change description to 'X'"
        - "Set description to 'X'"
        - "Update description to 'X'"
        
        Args:
            message: User's message
        
        Returns:
            Extracted description or None
        """
        patterns = [
            r"(?:change|set|update)\s+(?:its\s+)?description\s+to\s+['\"]?([^'\"]+)['\"]?",
            r"description\s+(?:is|to|should be|will be)\s+['\"]?([^'\"]+)['\"]?",
            r"description[:\s]+['\"]?([^'\"]+)['\"]?(?:\s+and|\s+set|$)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                desc = match.group(1).strip().strip('"').strip("'")
                if desc:
                    return desc
        return None
    
    def _extractPropertiesFromUpdate(self, message: str) -> Dict[str, str]:
        """
        Extract other properties from update message (confidentiality, status, etc.).
        
        Handles patterns like:
        - "Set its confidentiality to 'High'"
        - "Set confidentiality to 'High'"
        - "Change status to 'Active'"
        
        Args:
            message: User's message
        
        Returns:
            Dict with property names and values
        """
        properties = {}
        message_lower = message.lower()
        
        # Common property patterns
        property_patterns = [
            (r"(?:set|change|update)\s+(?:its\s+)?confidentiality\s+to\s+['\"]?([^'\"]+)['\"]?", 'confidentiality'),
            (r"(?:set|change|update)\s+(?:its\s+)?status\s+to\s+['\"]?([^'\"]+)['\"]?", 'status'),
            (r"(?:set|change|update)\s+(?:its\s+)?availability\s+to\s+['\"]?([^'\"]+)['\"]?", 'availability'),
            (r"(?:set|change|update)\s+(?:its\s+)?integrity\s+to\s+['\"]?([^'\"]+)['\"]?", 'integrity'),
            (r"confidentiality\s+(?:is|to|should be|will be)\s+['\"]?([^'\"]+)['\"]?", 'confidentiality'),
            (r"status\s+(?:is|to|should be|will be)\s+['\"]?([^'\"]+)['\"]?", 'status'),
            # Subtype patterns
            (r"(?:set|change|update)\s+(?:its\s+)?subtype\s+to\s+['\"]?([^'\"]+)['\"]?", 'subType'),
            (r"(?:set|change|update)\s+(?:its\s+)?subType\s+to\s+['\"]?([^'\"]+)['\"]?", 'subType'),
            (r"subtype\s+(?:is|to|should be|will be)\s+['\"]?([^'\"]+)['\"]?", 'subType'),
            (r"subType\s+(?:is|to|should be|will be)\s+['\"]?([^'\"]+)['\"]?", 'subType'),
        ]
        
        for pattern, prop_name in property_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                value = match.group(1).strip().strip('"').strip("'")
                if value:
                    properties[prop_name] = value
        
        return properties
    
    def _handleAnalyze(self, objectType: str, message: str, domainId: str, unitId: str) -> Dict:
        """
        Analyze operation handler (internal).
        
        Args:
            objectType: Type of object
            message: User's message
            domainId: Domain ID
            unitId: Unit ID (unused but kept for consistency)
        
        Returns:
            Dict with analysis result
        """
        objectId, foundDomainId = self._resolveToId(objectType, message, domainId)
        if not objectId:
            return self._error(get_error_message('validation', 'missing_params_analyze', objectType=objectType))
        
        # Use the domain where the object was actually found
        actualDomainId = foundDomainId if foundDomainId else domainId
        result = self.veriniceTool.analyzeObject(objectType, actualDomainId, objectId)
        if result.get('success'):
            formatted = self._formatResult('analyzeVeriniceObject', result)
            return self._success(formatted)
        return self._error(get_error_message('operation_failed', 'analyze', error=result.get('error', 'Unknown error')))
    
    # ========== HELPER METHODS ==========
    
    def _getSingularForm(self, objectType: str) -> str:
        """
        Get singular form of object type for messages.
        
        Args:
            objectType: Plural or singular object type (e.g., 'scopes', 'assets', 'scope')
        
        Returns:
            Singular form (e.g., 'scope', 'asset', 'person')
        """
        if objectType == 'processes':
            return 'process'
        elif objectType == 'scopes':
            return 'scope'
        elif objectType == 'assets':
            return 'asset'
        elif objectType == 'persons':
            return 'person'
        elif objectType == 'controls':
            return 'control'
        elif objectType == 'documents':
            return 'document'
        elif objectType == 'incidents':
            return 'incident'
        elif objectType == 'scenarios':
            return 'scenario'
        
        # Default: remove trailing 's' if present
        if objectType.endswith('s'):
            return objectType[:-1]
        return objectType
    
    # ========== PARSING METHODS (from ISMSHandler) ==========
    
    def _extractName(self, message: str, objectType: str) -> Optional[str]:
        """
        Extract object name from message - enhanced patterns for natural language.
        
        Handles variations like:
        - "create scope in our isms, and named it SCOPE1"
        - "create scope named SCOPE1"
        - "create scope called SCOPE1"
        - "create scope SCOPE1 in our isms"
        - "create scope SCOPE1"
        
        Args:
            message: User's message
            objectType: Type of object (asset, scope, etc.)
        
        Returns:
            Extracted name or None
        """
        message_lower = message.lower()
        
        # Common phrases to skip (not part of the name)
        skip_phrases = [
            'in our isms', 'in the isms', 'in our system', 'in the system',
            'in our', 'in the', 'for our', 'for the', 'with our', 'with the',
            'and named it', 'and called it', 'and name it', 'and call it',
            'named it', 'called it', 'name it', 'call it'
        ]
        
        # Pattern 0: Handle "create a new Data Protection Officer 'John'" - extract 'John' as name
        # This must come BEFORE other patterns to avoid extracting "Data Protection Officer" as the name
        if objectType.lower() == 'person':
            # Build create keywords pattern from JSON config
            create_keywords_pattern = self._getCreateKeywordsPattern()
            dpo_pattern = rf'(?:{create_keywords_pattern})\s+(?:a\s+)?(?:new\s+)?(?:Data\s+Protection\s+Officer|DPO|Security\s+Officer)\s+["\']([^"\']+)["\']'
            match = re.search(dpo_pattern, message, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                if name and len(name) > 0:
                    return name
        
        # Pattern 0.5: Handle "Create a \"Controller\" named 'MFA for VPN'" - CRITICAL: Check this BEFORE generic patterns
        # This must come before Pattern 1 to ensure Controller pattern matches
        # NOTE: "Controller" is a subtype of scope, not control, but we check for both objectType == 'scope' and 'control'
        # because the router might route it as either depending on detection order
        if objectType.lower() in ['scope', 'control']:
            create_keywords_pattern = self._getCreateKeywordsPattern()
            controller_patterns = [
                rf'(?:{create_keywords_pattern})\s+(?:a\s+)?["\']controller["\']\s+(?:named|called|name|call)\s+["\']([^"\']+)["\']',  # "Create a \"Controller\" named 'X'"
                rf'(?:{create_keywords_pattern})\s+(?:a\s+)?["\']?controller["\']?\s+(?:named|called|name|call)\s+["\']([^"\']+)["\']',  # Fallback with optional quotes
            ]
            for pattern in controller_patterns:
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    name = match.group(1).strip()
                    if name and len(name) > 0:
                        return name
        
        # Pattern 1: Explicit naming patterns (highest priority)
        # "create scope named SCOPE1" or "create scope called SCOPE1" or "create person named 'Sarah Connor'"
        # Also handle "Create a \"Controller\" named 'MFA for VPN'" - CRITICAL: Handle both "Controller" and "control"
        # Special case: If objectType is "control", also match "Controller" in the message
        object_type_pattern = objectType
        if objectType.lower() == 'control':
            # Match both "control" and "Controller" (quoted or unquoted)
            object_type_pattern = r'(?:control|["\']?controller["\']?)'
        
        # Build create keywords pattern from JSON config
        create_keywords_pattern = self._getCreateKeywordsPattern()
        
        quoted_patterns = [
            rf'(?:{create_keywords_pattern})\s+(?:a\s+)?{object_type_pattern}\s+(?:in\s+(?:our|the)\s+(?:isms|system))?\s*(?:,?\s*and\s+)?(?:named|called|name|call)\s+(?:it\s+)?["\']([^"\']+)["\']',  # "create control named 'X'" or "create \"Controller\" named 'X'"
            rf'(?:{create_keywords_pattern})\s+{object_type_pattern}\s+(?:in\s+(?:our|the)\s+(?:isms|system))?\s*(?:,?\s*and\s+)?(?:named|called|name|call)\s+["\']([^"\']+)["\']',  # Fallback
            rf'(?:{create_keywords_pattern})\s+(?:a\s+)?{object_type_pattern}\s+(?:in\s+(?:our|the)\s+(?:isms|system))?\s*(?:,?\s*and\s+)?(?:named|called|name|call)\s+(?:it\s+)?["\']([^"\']+)["\']',  # With optional quotes around objectType
        ]
        for pattern in quoted_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                if name and len(name) > 0:
                    return name
        
        # Build create keywords pattern from JSON config
        create_keywords_pattern = self._getCreateKeywordsPattern()
        
        explicit_patterns = [
            # Pattern for "Create a new Incident named 'Phishing Attempt Jan-24'"
            # Also handle: "Create a new Incident named 'Phishing Attempt Jan-24'. Then, find..."
            rf'(?:{create_keywords_pattern})\s+(?:a\s+)?(?:new\s+)?{objectType}\s+(?:named|called|name|call)\s+["\']([^"\']+)["\'](?:\s*[\.\,]?\s*then|\s*\.|$)',
            rf'(?:{create_keywords_pattern})\s+(?:a\s+)?(?:new\s+)?{objectType}\s+(?:named|called|name|call)\s+["\']([^"\']+)["\']',
            rf'(?:{create_keywords_pattern})\s+{objectType}\s+(?:in\s+(?:our|the)\s+(?:isms|system))?\s*(?:,?\s*and\s+)?(?:named|called|name|call)\s+(?:it\s+)?([A-Za-z0-9_\s-]+?)(?:\s*,\s*|$|description|abbreviation|subType|status)',
            rf'(?:{create_keywords_pattern})\s+{objectType}\s+(?:in\s+(?:our|the)\s+(?:isms|system))?\s*(?:,?\s*and\s+)?(?:named|called|name|call)\s+([A-Za-z0-9_\s-]+?)(?:\s*,\s*|$|description|abbreviation|subType|status)',
        ]
        
        for pattern in explicit_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                # Clean up the name
                name = re.sub(r'\s+(description|abbreviation|subType|status|in|for|with|using|to|the).*$', '', name, flags=re.IGNORECASE).strip()
                if name and len(name) > 0:
                    # Skip if it's just a skip phrase
                    if name.lower() not in [p.replace(' ', '_') for p in skip_phrases]:
                        return name
        
        # Pattern 2: Direct name after object type (before skip phrases)
        # "create scope SCOPE1 in our isms" or "create scope SCOPE1" or "create person 'Sarah Connor'"
        # Also handle "Create a \"Controller\" 'MFA for VPN'" (without "named")
        # Special case: If objectType is "control", also match "Controller"
        if objectType.lower() == 'control':
            object_type_pattern = r'(?:control|["\']?controller["\']?)'
        else:
            object_type_pattern = objectType
        
        # CRITICAL: Handle plural forms (e.g., "create assets 'name'")
        # Pattern: "create assets 'Data Type 01' in the Datatypes assets"
        object_type_pattern_plural = objectType
        if objectType.lower() == 'asset':
            object_type_pattern_plural = r'(?:asset|assets)'
        elif objectType.lower() == 'scope':
            object_type_pattern_plural = r'(?:scope|scopes)'
        elif objectType.lower() == 'control':
            object_type_pattern_plural = r'(?:control|controls|["\']?controller["\']?)'
        elif objectType.lower() == 'person':
            object_type_pattern_plural = r'(?:person|persons|people)'
        elif objectType.lower() == 'process':
            object_type_pattern_plural = r'(?:process|processes)'
        
        # Build create keywords pattern from JSON config
        create_keywords_pattern = self._getCreateKeywordsPattern()
        
        quoted_direct_patterns = [
            # Pattern for "create assets 'name' in the [subtype] assets" - extract name only
            rf'(?:{create_keywords_pattern})\s+{object_type_pattern_plural}\s+["\']([^"\']+)["\']\s+in\s+the\s+[A-Za-z0-9_\s-]+\s+{object_type_pattern_plural}',  # "create assets 'X' in the Y assets"
            # Standard pattern: "create asset 'X'" or "create assets 'X'" - handle period-separated commands
            # Match up to period or "assign" keyword to handle "create person 'John'.assign his role to 'DPO'"
            rf'(?:{create_keywords_pattern})\s+(?:a\s+)?(?:new\s+)?{object_type_pattern_plural}\s+["\']([^"\']+)["\'](?:\s*\.|$)',  # "create person 'John'." or "create person 'John'"
            rf'(?:{create_keywords_pattern})\s+(?:a\s+)?(?:new\s+)?{object_type_pattern_plural}\s+["\']([^"\']+)["\'](?:\s+assign|\s+\.)',  # "create person 'John' assign" or "create person 'John'."
            rf'(?:{create_keywords_pattern})\s+{objectType}\s+["\']([^"\']+)["\']',  # Fallback
        ]
        for pattern in quoted_direct_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                if name and len(name) > 0:
                    return name
        
        # Build create keywords pattern from JSON config
        create_keywords_pattern = self._getCreateKeywordsPattern()
        
        direct_patterns = [
            rf'(?:{create_keywords_pattern})\s+{objectType}\s+([A-Za-z0-9_\s-]+?)(?:\s+(?:in\s+(?:our|the)\s+(?:isms|system)|for\s+(?:our|the)|with\s+(?:our|the)|description|abbreviation|subType|status|$))',
            rf'(?:{create_keywords_pattern})\s+{objectType}\s+([A-Za-z0-9_\s-]+?)(?:\s|,|$|description|abbreviation|subType|status)',
        ]
        
        for pattern in direct_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                name_lower = name.lower()
                for skip_phrase in skip_phrases:
                    if skip_phrase in name_lower:
                        # Extract name before the skip phrase
                        idx = name_lower.find(skip_phrase)
                        name = name[:idx].strip()
                        break
                
                name = re.sub(r'\s+(description|abbreviation|subType|status|in|for|with|using|to|the).*$', '', name, flags=re.IGNORECASE).strip()
                
                # Skip single words that are likely not names (like "in", "our", "the")
                if name and len(name) > 0:
                    skip_words = ['in', 'our', 'the', 'and', 'named', 'called', 'name', 'call', 'it', 'isms', 'system']
                    if name.lower() not in skip_words and len(name) > 1:
                        return name
        
        # Pattern 3: Fallback - object type followed by name
        # "scope SCOPE1" or "scope called SCOPE1"
        fallback_patterns = [
            rf'{objectType}\s+(?:called|named)\s+(?:it\s+)?([A-Za-z0-9_\s-]+?)(?:\s|,|$|description|abbreviation|subType|status)',
            rf'{objectType}\s+([A-Za-z0-9_\s-]+?)(?:\s+(?:in\s+(?:our|the)\s+(?:isms|system)|description|abbreviation|subType|status|$))',
        ]
        
        for pattern in fallback_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                # Clean up
                name = re.sub(r'\s+(description|abbreviation|subType|status|in|for|with|using|to|the).*$', '', name, flags=re.IGNORECASE).strip()
                if name and len(name) > 0:
                    skip_words = ['in', 'our', 'the', 'and', 'named', 'called', 'name', 'call', 'it', 'isms', 'system']
                    if name.lower() not in skip_words and len(name) > 1:
                        return name
        
        return None
    
    def _extractAbbreviation(self, message: str) -> Optional[str]:
        """
        Extract abbreviation from message.
        
        Args:
            message: User's message
        
        Returns:
            Extracted abbreviation or None
        """
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
        """
        Extract description from message.
        
        Args:
            message: User's message
        
        Returns:
            Extracted description or None
        """
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
    
    def _extractDescriptionFromUpdate(self, message: str) -> Optional[str]:
        """
        Extract description from update message.
        
        Handles patterns like:
        - "Change its description to 'X'"
        - "Change description to 'X'"
        - "Set description to 'X'"
        - "Update description to 'X'"
        
        Args:
            message: User's message
        
        Returns:
            Extracted description or None
        """
        patterns = [
            r"(?:change|set|update)\s+(?:its\s+)?description\s+to\s+['\"]?([^'\"]+)['\"]?",
            r"description\s+(?:is|to|should be|will be)\s+['\"]?([^'\"]+)['\"]?",
            r"description[:\s]+['\"]?([^'\"]+)['\"]?(?:\s+and|\s+set|$)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                desc = match.group(1).strip().strip('"').strip("'")
                if desc:
                    return desc
        return None
    
    def _extractPropertiesFromUpdate(self, message: str) -> Dict[str, str]:
        """
        Extract other properties from update message (confidentiality, status, etc.).
        
        Handles patterns like:
        - "Set its confidentiality to 'High'"
        - "Set confidentiality to 'High'"
        - "Change status to 'Active'"
        
        Args:
            message: User's message
        
        Returns:
            Dict with property names and values
        """
        properties = {}
        message_lower = message.lower()
        
        # Common property patterns
        property_patterns = [
            (r"(?:set|change|update)\s+(?:its\s+)?confidentiality\s+to\s+['\"]?([^'\"]+)['\"]?", 'confidentiality'),
            (r"(?:set|change|update)\s+(?:its\s+)?status\s+to\s+['\"]?([^'\"]+)['\"]?", 'status'),
            (r"(?:set|change|update)\s+(?:its\s+)?availability\s+to\s+['\"]?([^'\"]+)['\"]?", 'availability'),
            (r"(?:set|change|update)\s+(?:its\s+)?integrity\s+to\s+['\"]?([^'\"]+)['\"]?", 'integrity'),
            (r"confidentiality\s+(?:is|to|should be|will be)\s+['\"]?([^'\"]+)['\"]?", 'confidentiality'),
            (r"status\s+(?:is|to|should be|will be)\s+['\"]?([^'\"]+)['\"]?", 'status'),
            # Subtype patterns
            (r"(?:set|change|update)\s+(?:its\s+)?subtype\s+to\s+['\"]?([^'\"]+)['\"]?", 'subType'),
            (r"(?:set|change|update)\s+(?:its\s+)?subType\s+to\s+['\"]?([^'\"]+)['\"]?", 'subType'),
            (r"subtype\s+(?:is|to|should be|will be)\s+['\"]?([^'\"]+)['\"]?", 'subType'),
            (r"subType\s+(?:is|to|should be|will be)\s+['\"]?([^'\"]+)['\"]?", 'subType'),
        ]
        
        for pattern, prop_name in property_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                value = match.group(1).strip().strip('"').strip("'")
                if value:
                    properties[prop_name] = value
        
        return properties
    
    def _extractSubType(self, message: str, objectType: str) -> Optional[str]:
        """
        Extract subtype from message.
        
        Supports patterns like:
        - "create a Data Protection Officer 'John'" -> extracts "Data Protection Officer"
        - "create person 'John' subtype DPO" -> extracts "DPO"
        - "create a DPO named 'John'" -> extracts "DPO"
        
        Args:
            message: User's message
            objectType: Type of object
        
        Returns:
            Extracted subtype or None
        """
        # Pattern 1: "create a new Data Protection Officer 'John'" or "create a DPO 'John'"
        # Extract subtype before the quoted name - this handles "create a new Data Protection Officer 'John'"
        # CRITICAL: Only extract if objectType is 'person', otherwise it might be a different object type
        if objectType.lower() == 'person':
            create_keywords_pattern = self._getCreateKeywordsPattern()
            subtype_before_name_patterns = [
                rf'(?:{create_keywords_pattern})\s+(?:a\s+)?(?:new\s+)?([A-Z][A-Za-z\s-]+?)\s+["\']',  # "create a new Data Protection Officer 'John'"
                rf'(?:{create_keywords_pattern})\s+(?:a\s+)?([A-Z]{2,})\s+["\']',  # "create a DPO 'John'"
            ]
            for pattern in subtype_before_name_patterns:
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    potential_subtype = match.group(1).strip()
                    if potential_subtype.lower() not in ['person', 'persons', 'people']:
                        # Common person subtypes - check if it matches
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
        
        # Pattern 2: "for [subtype]" or "for the [subtype] role" patterns
        # Examples: "create person John for DPO", "create person 'John' for the DPO role", "create person 'John' for Data Protection Officers role"
        if objectType.lower() == 'person':
            for_subtype_patterns = [
                r'for\s+(?:the\s+)?([A-Z][A-Za-z0-9_\s-]+?)(?:\s+role)?\s*$',  # "for DPO" or "for the DPO role"
                r'for\s+(?:the\s+)?([A-Z]{2,})(?:\s+role)?\s*$',  # "for DPO" (acronym)
                r'for\s+(?:the\s+)?([A-Za-z\s-]+?)\s+role\s*$',  # "for Data Protection Officers role"
            ]
            for pattern in for_subtype_patterns:
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
        
        # Pattern 3: Explicit subtype keyword
        patterns = [
            r'subType[:\s]+([A-Za-z0-9_\s-]+)',
            r'subtype[:\s]+([A-Za-z0-9_\s-]+)',
            r'type[:\s]+([A-Za-z0-9_\s-]+)',
            r'as\s+([A-Za-z0-9_\s-]+)',  # "create person 'John' as DPO"
            r'assign\s+(?:his|her|their|its)\s+role\s+to\s+["\']?([^"\']+)["\']?',  # "assign his role to 'DPO'"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                subType = match.group(1).strip()
                if subType:
                    return subType
        
        # Pattern 3: "create assets 'name' in the [subtype] assets" - extract subtype from "in the [subtype] assets"
        # Example: "create assets 'Data Type 01' in the Datatypes assets" -> extract "Datatypes"
        if objectType.lower() == 'asset':
            create_keywords_pattern = self._getCreateKeywordsPattern()
            subtype_in_pattern = rf'(?:{create_keywords_pattern})\s+(?:asset|assets)\s+["\']([^"\']+)["\']\s+in\s+the\s+([A-Za-z0-9_\s-]+?)\s+(?:asset|assets)'
            match = re.search(subtype_in_pattern, message, re.IGNORECASE)
            if match:
                subtype = match.group(2).strip()
                if subtype:
                    return subtype
        
        return None
    
    def _extractSimpleFormat(self, message: str, objectType: str) -> Optional[Dict]:
        """
        Parse 'create {type} {name} {abbr} {desc}' format.
        
        Supports multiple formats:
        - Quoted strings: create asset "name with spaces" "ABBR" "description"
        - Underscores: create asset name_with_underscores ABBR description
        - Mixed formats
        - "Create a \"Controller\" named 'X'" (special case for Controller)
        
        Args:
            message: User's message
            objectType: Type of object
        
        Returns:
            Dict with extracted fields or None
        """
        # Use create keywords from JSON config
        createPattern = self._getCreateKeywordsPattern()
        
        # CRITICAL: Handle "Create a \"Controller\" named 'X'" pattern FIRST (before any other patterns)
        # Pattern: "Create a \"Controller\" named 'MFA for VPN'"
        # This pattern works regardless of objectType - if message has "Controller", handle it specially
        if 'controller' in message.lower():
            create_keywords_pattern = self._getCreateKeywordsPattern()
            controller_named_patterns = [
                rf'(?:{create_keywords_pattern})\s+(?:a\s+)?["\']controller["\']\s+(?:named|called|name|call)\s+["\']([^"\']+)["\']',  # "Create a \"Controller\" named 'X'"
                rf'(?:{create_keywords_pattern})\s+(?:a\s+)?["\']?controller["\']?\s+(?:named|called|name|call)\s+["\']([^"\']+)["\']',  # Fallback with optional quotes
            ]
            for pattern in controller_named_patterns:
                controller_match = re.search(pattern, message, re.IGNORECASE)
                if controller_match:
                    name = controller_match.group(1).strip()
                    if name:
                        # Try to extract other fields if present
                        abbreviation = self._extractAbbreviation(message) or ""
                        description = self._extractDescription(message) or ""
                        return {
                            'name': name,
                            'abbreviation': abbreviation,
                            'description': description
                        }
        
        # Pattern 1: All quoted with subtype
        quotedWithSubTypePattern = rf'{createPattern}\s+{objectType}\s+"([^"]+)"\s+"([^"]+)"\s+"([^"]+)"\s+"([^"]+)"'
        quotedWithSubTypeMatch = re.search(quotedWithSubTypePattern, message, re.IGNORECASE)
        if quotedWithSubTypeMatch:
            return {
                'name': quotedWithSubTypeMatch.group(1).strip(),
                'abbreviation': quotedWithSubTypeMatch.group(2).strip(),
                'description': quotedWithSubTypeMatch.group(3).strip(),
                'subType': quotedWithSubTypeMatch.group(4).strip()
            }
        
        # Pattern 2: All quoted without subtype
        # CRITICAL: Only match if objectType matches (not "Controller" when objectType is "control")
        # Skip this pattern for "control" type if message contains "Controller" - let Controller-specific patterns handle it
        if not (objectType.lower() == 'control' and 'controller' in message.lower()):
            quotedPattern = rf'{createPattern}\s+{objectType}\s+"([^"]+)"\s+"([^"]+)"\s+"([^"]+)"'
            quotedMatch = re.search(quotedPattern, message, re.IGNORECASE)
            if quotedMatch:
                return {
                    'name': quotedMatch.group(1).strip(),
                    'abbreviation': quotedMatch.group(2).strip(),
                    'description': quotedMatch.group(3).strip()
                }
        
        # Pattern 3: Quoted name and description, unquoted abbreviation
        quotedNameDescPattern = rf'{createPattern}\s+{objectType}\s+"([^"]+)"\s+([A-Za-z0-9_-]+?)\s+"([^"]+)"'
        quotedNameDescMatch = re.search(quotedNameDescPattern, message, re.IGNORECASE)
        if quotedNameDescMatch:
            return {
                'name': quotedNameDescMatch.group(1).strip(),
                'abbreviation': quotedNameDescMatch.group(2).strip(),
                'description': quotedNameDescMatch.group(3).strip()
            }
        
        # Pattern 4: Quoted name and abbreviation, unquoted description
        quotedNamePattern = rf'{createPattern}\s+{objectType}\s+"([^"]+)"\s+"([^"]+)"\s+(.+?)(?:\s+subType|\s+status|$)'
        quotedNameMatch = re.search(quotedNamePattern, message, re.IGNORECASE)
        if quotedNameMatch:
            desc = quotedNameMatch.group(3).strip().strip('"').strip("'")
            return {
                'name': quotedNameMatch.group(1).strip(),
                'abbreviation': quotedNameMatch.group(2).strip(),
                'description': desc
            }
        
        # Pattern 5: Quoted name only, unquoted abbreviation and description
        quotedNameUnquotedPattern = rf'{createPattern}\s+{objectType}\s+"([^"]+)"\s+([A-Za-z0-9_-]+?)\s+(.+?)(?:\s+subType|\s+status|$)'
        quotedNameUnquotedMatch = re.search(quotedNameUnquotedPattern, message, re.IGNORECASE)
        if quotedNameUnquotedMatch:
            desc = quotedNameUnquotedMatch.group(3).strip().strip('"').strip("'")
            return {
                'name': quotedNameUnquotedMatch.group(1).strip(),
                'abbreviation': quotedNameUnquotedMatch.group(2).strip(),
                'description': desc
            }
        
        # Pattern 6: Standard format without quotes (underscores converted to spaces)
        # Skip if it contains natural language phrases that indicate named/called patterns
        skip_natural_language = re.search(r'(?:in\s+(?:our|the)\s+(?:isms|system)|named|called|name\s+it|call\s+it)', message, re.IGNORECASE)
        if not skip_natural_language:
            pattern = rf'{createPattern}\s+{objectType}\s+([A-Za-z0-9_\s-]+?)\s+([A-Za-z0-9_-]{{1,20}})\s+(.+?)(?:\s+subType|\s+status|$)'
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                name = match.group(1).strip().replace('_', ' ')
                abbreviation = match.group(2).strip()
                description = match.group(3).strip()
                # Skip if name looks like a skip phrase
                skip_words = ['in', 'our', 'the', 'and', 'named', 'called', 'name', 'call', 'it', 'isms', 'system']
                if name.lower() not in skip_words:
                    return {
                        'name': name,
                        'abbreviation': abbreviation,
                        'description': description
                    }
        
        # Pattern 7: Name and abbreviation only (no description)
        # Skip if it contains natural language phrases
        if not skip_natural_language:
            pattern2 = rf'{createPattern}\s+{objectType}\s+([A-Za-z0-9_\s-]+?)\s+([A-Za-z0-9_-]{{1,20}})(?:\s+subType|\s+status|$)'
            match2 = re.search(pattern2, message, re.IGNORECASE)
            if match2:
                name = match2.group(1).strip().replace('_', ' ')
                abbreviation = match2.group(2).strip()
                # Skip if name looks like a skip phrase
                skip_words = ['in', 'our', 'the', 'and', 'named', 'called', 'name', 'call', 'it', 'isms', 'system']
                if name.lower() not in skip_words:
                    return {
                        'name': name,
                        'abbreviation': abbreviation,
                        'description': ''
                    }
        
        return None
    
    def _parseSubtypeSelection(self, message: str, availableSubTypes: List[str]) -> Optional[str]:
        """
        Parse user's subtype selection.
        
        Handles both number selection (e.g., "2") and name selection (e.g., "AST_IT-System").
        
        Args:
            message: User input
            availableSubTypes: List of valid subtype names
        
        Returns:
            Selected subtype name or None
        """
        # TODO: Port from MainAgent._parseSubtypeSelection
        pass
    
    # ========== RESOLUTION METHODS (from ISMSHandler) ==========
    
    def _resolveToId(self, objectType: str, nameOrId: str, domainId: str) -> tuple:
        """
        Resolve object name to ID and domain.
        
        Checks if message contains UUID, otherwise searches by name.
        Returns both the object ID and the domain ID where it was found.
        
        Args:
            objectType: Type of object
            nameOrId: Message containing name or ID
            domainId: Domain ID to search in (default domain)
        
        Returns:
            Tuple of (objectId, foundDomainId) or (None, None)
            If objectId is found, foundDomainId is the domain where it was found
        """
        uuidMatch = re.search(r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})', nameOrId, re.IGNORECASE)
        if uuidMatch:
            # For UUID, use the provided domainId (or search all domains if None)
            objectId = uuidMatch.group(1)
            if domainId:
                return (objectId, domainId)
            # If no domainId, try to find which domain contains this object
            domainsResult = self.veriniceTool.listDomains()
            if domainsResult.get('success') and domainsResult.get('domains'):
                for domain in domainsResult['domains']:
                    dId = domain.get('id') if isinstance(domain, dict) else domain
                    if dId:
                        # Try to get the object to verify it exists in this domain
                        testResult = self.veriniceTool.getObject(objectType, dId, objectId)
                        if testResult.get('success'):
                            return (objectId, dId)
            return (objectId, domainId)  # Fallback to provided domainId
        
        # Extract name from message
        # First, try to extract quoted names (handles "Update the asset 'Main_Firewall'" or "create 'Ascope' scope")
        # CRITICAL: Handle both single and double quotes, and handle period/comma/space after quote
        # Build create keywords pattern from JSON config
        create_keywords_pattern = self._getCreateKeywordsPattern()
        
        quoted_patterns = [
            # CRITICAL: Handle "Update the asset 'Main Firewall'. Change its description..." 
            # Pattern must match period/comma after quote, then space, then "Change" keyword
            # This MUST be first to catch this specific pattern before simpler patterns
            rf'(?:update|change|modify|edit|set)\s+(?:the\s+)?{objectType}\s+["\']([^"\']+)["\']\s*[\.\,]\s+(?:change|set|update|description|confidentiality|status|name|abbreviation|subtype|subType|and|to)',
            # Pattern with period/comma after quote: "Update the asset 'Main_Firewall'."
            rf'(?:update|change|modify|edit|set)\s+(?:the\s+)?{objectType}\s+["\']([^"\']+)["\']\s*[\.\,]',
            rf'(?:get|view|show|delete|remove|analyze)\s+(?:the\s+)?{objectType}\s+["\']([^"\']+)["\']\s*[\.\,]',
            # Pattern for CREATE: "create 'Ascope' scope" or "create scope 'Ascope'"
            rf'(?:{create_keywords_pattern})\s+["\']([^"\']+)["\']\s+{objectType}',
            rf'(?:{create_keywords_pattern})\s+{objectType}\s+["\']([^"\']+)["\']',
            # Pattern without punctuation after quote (but may have space and then text)
            rf'(?:update|change|modify|edit|set)\s+(?:the\s+)?{objectType}\s+["\']([^"\']+)["\'](?:\s|\.|,|$)',
            rf'(?:get|view|show|delete|remove|analyze)\s+(?:the\s+)?{objectType}\s+["\']([^"\']+)["\'](?:\s|\.|,|$)',
            rf'(?:the\s+)?{objectType}\s+["\']([^"\']+)["\']',
        ]
        
        name = None
        for pattern in quoted_patterns:
            match = re.search(pattern, nameOrId, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                if name:
                    break
        
        # If no quoted name found, try unquoted patterns
        if not name:
            updateFieldKeywords = ['description', 'status', 'subtype', 'subType', 'name', 'abbreviation', 'abbr']
            
            patterns = [
                rf'(?:update|change|modify|edit|set)\s+(?:the\s+)?{objectType}\s+([A-Za-z0-9_\s-]+?)(?:\s+(?:{"|".join(updateFieldKeywords)})|\.|$)',
                rf'(?:get|view|show|delete|remove|analyze)\s+(?:the\s+)?{objectType}\s+([A-Za-z0-9_\s-]+?)(?:\s|$|\.)',
                rf'(?:the\s+)?{objectType}\s+([A-Za-z0-9_\s-]+?)(?:\s|$|\.)',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, nameOrId, re.IGNORECASE)
                if match:
                    name = match.group(1).strip()
                    name = re.sub(r'\s+(description|status|subtype|subType|name|abbreviation|abbr|field|value|to|is|as|change|set).*$', '', name, flags=re.IGNORECASE).strip()
                    if name:
                        break
        
        if not name:
            print(f"[DEBUG _resolveToId] No name extracted from message: '{nameOrId[:100]}'")
            return (None, None)
        
        print(f"[DEBUG _resolveToId] Extracted name: '{name}' for {objectType}, searching in domainId: {domainId}")
        
        # First, check state cache for recently created objects (helps with immediate UPDATE/DELETE after CREATE)
        if '_created_objects' in self.state:
            normalized_search_key = f"{objectType}:{name.lower().replace('_', ' ').replace('-', ' ').strip()}"
            cached = self.state['_created_objects'].get(normalized_search_key)
            if cached:
                cached_objectId = cached.get('objectId')
                cached_domainId = cached.get('domainId')
                if cached_objectId and cached_domainId:
                    print(f"[DEBUG _resolveToId] ✅ Found in state cache: {cached_objectId} in domain {cached_domainId}")
                    return (cached_objectId, cached_domainId)
        
        # Helper to search in a specific domain
        def searchInDomain(dId: str) -> tuple:
            if not dId:
                return (None, None)
            listResult = self.veriniceTool.listObjects(objectType, dId)
            if not listResult.get('success'):
                print(f"[DEBUG _resolveToId] listObjects failed for {objectType} in domain {dId}: {listResult.get('error', 'Unknown error')}")
                return (None, None)
            
            objects = listResult.get('objects', {})
            items = objects.get('items', []) if isinstance(objects, dict) else (objects if isinstance(objects, list) else [])
            
            print(f"[DEBUG _resolveToId] Searching {len(items)} {objectType}(s) in domain {dId} for name '{name}'")
            
            # Debug: Show first few item names to see what we're searching through
            if items:
                sample_names = [item.get('name', 'NO_NAME')[:30] for item in items[:5]]
                print(f"[DEBUG _resolveToId] Sample item names in domain: {sample_names}")
            else:
                print(f"[DEBUG _resolveToId] WARNING: No items returned from listObjects for {objectType} in domain {dId}")
            
            # Normalize name for comparison (handle underscores/spaces/hyphens)
            def normalize_name(n: str) -> str:
                """Normalize name by replacing underscores/hyphens with spaces and lowercasing"""
                if not n:
                    return ''
                return n.replace('_', ' ').replace('-', ' ').lower().strip()
            
            normalized_search_name = normalize_name(name)
            print(f"[DEBUG _resolveToId] Normalized search name: '{normalized_search_name}'")
            
            for item in items:
                itemName = item.get('name', '').strip()
                if not itemName:
                    # Try alternative name fields
                    itemName = item.get('title', '') or item.get('displayName', '') or ''
                    if not itemName:
                        continue
                
                normalized_item_name = normalize_name(itemName)
                
                # Exact match (case-insensitive, space/underscore/hyphen agnostic)
                if normalized_item_name == normalized_search_name:
                    objectId = item.get('id') or item.get('resourceId') or item.get('uuid')
                    print(f"[DEBUG _resolveToId] ✅ Found exact match: '{itemName}' -> {objectId} in domain {dId}")
                    return (objectId, dId) if objectId else (None, None)
                
                # Fuzzy match (substring, space/underscore/hyphen agnostic)
                if normalized_search_name in normalized_item_name or normalized_item_name in normalized_search_name:
                    objectId = item.get('id') or item.get('resourceId') or item.get('uuid')
                    print(f"[DEBUG _resolveToId] ✅ Found fuzzy match: '{itemName}' -> {objectId} in domain {dId}")
                    return (objectId, dId) if objectId else (None, None)
                
                # Also try matching without normalization (for backwards compatibility)
                if itemName.lower() == name.lower():
                    objectId = item.get('id') or item.get('resourceId') or item.get('uuid')
                    print(f"[DEBUG _resolveToId] ✅ Found exact match (non-normalized): '{itemName}' -> {objectId} in domain {dId}")
                    return (objectId, dId) if objectId else (None, None)
            
            print(f"[DEBUG _resolveToId] ❌ No match found in domain {dId} (searched {len(items)} items)")
            return (None, None)
        
        # Try default domain first (if provided)
        if domainId:
            objectId, foundDomainId = searchInDomain(domainId)
            if objectId:
                print(f"[DEBUG _resolveToId] Found in default domain {domainId}")
                return (objectId, foundDomainId)
        
        # Search all domains if not found in default domain (or if domainId is None)
        print(f"[DEBUG _resolveToId] Searching all domains for '{name}'")
        domainsResult = self.veriniceTool.listDomains()
        if domainsResult.get('success') and domainsResult.get('domains'):
            domains = domainsResult['domains']
            searched_domains = set()
            if domainId:
                searched_domains.add(domainId)
            
            for domain in domains:
                dId = domain.get('id') if isinstance(domain, dict) else domain
                if dId and dId not in searched_domains:
                    objectId, foundDomainId = searchInDomain(dId)
                    if objectId:
                        print(f"[DEBUG _resolveToId] Found in domain {dId}")
                        return (objectId, foundDomainId)
                    searched_domains.add(dId)
        
        print(f"[DEBUG _resolveToId] Object '{name}' not found in any domain")
        return (None, None)
    
    def _getSubTypesInfo(self, domainId: str, objectType: str) -> Dict:
        """
        Get available subtypes for object type.
        
        Args:
            domainId: Domain ID
            objectType: Type of object
        
        Returns:
            Dict with subtypes and count
        """
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
    
    def _matchSubType(self, providedSubType: str, availableSubTypes: List[str]) -> Optional[str]:
        """
        Intelligently match provided subtype to available options.
        
        Handles variations like:
        - "Data Protection Officer" → "PER_DataProtectionOfficer" or "PER_DPO"
        - "DPO" → "PER_DataProtectionOfficer" or "PER_DPO"
        - "Data protection officer" → "PER_DataProtectionOfficer"
        
        Args:
            providedSubType: User-provided subtype string
            availableSubTypes: List of valid subtypes
        
        Returns:
            Matched subtype or None
        """
        if not availableSubTypes or not providedSubType:
            return None
        
        provided_lower = providedSubType.lower().strip()
        
        def normalize_subtype(st: str) -> str:
            """Remove common prefixes and normalize"""
            prefixes = ['scp_', 'ast_', 'per_', 'ctl_', 'pro_', 'inc_', 'doc_', 'scn_']
            st_lower = st.lower()
            for prefix in prefixes:
                if st_lower.startswith(prefix):
                    st = st[len(prefix):]
                    break
            st_clean = st.lower().replace('_', ' ').replace('-', ' ')
            return st_clean.strip()
        
        def dashboard_to_technical(dashboard_name: str, available_subtypes: List[str]) -> Optional[str]:
            """Convert dashboard-friendly name to technical subtype"""
            dashboard_lower = dashboard_name.lower().strip()
            
            # Mapping dashboard names to technical subtypes
            dashboard_mapping = {
                'scopes': 'SCP_Scope',
                'processors': 'SCP_Processor',
                'controllers': 'SCP_Controller',
                'joint controllerships': 'SCP_JointController',
                'joint controllership': 'SCP_JointController',
                'responsible body': 'SCP_ResponsibleBody',
                
                'datatypes': 'AST_Datatype',
                'datatype': 'AST_Datatype',
                'it-systems': 'AST_IT-System',
                'it-system': 'AST_IT-System',
                'it systems': 'AST_IT-System',
                'applications': 'AST_Application',
                'application': 'AST_Application',
                
                'persons': 'PER_Person',
                'person': 'PER_Person',
                'data protection officers': 'PER_DataProtectionOfficer',
                'data protection officer': 'PER_DataProtectionOfficer',
                'dpo': 'PER_DataProtectionOfficer',
                
                'toms': 'CTL_TOM',
                'tom': 'CTL_TOM',
                
                'data protection impact assessment': 'PRO_DPIA',
                'data protection impact': 'PRO_DPIA',
                'dpia': 'PRO_DPIA',
                'data transfers': 'PRO_DataTransfer',
                'data transfer': 'PRO_DataTransfer',
                'data processings': 'PRO_DataProcessing',
                'data processing': 'PRO_DataProcessing',
                
                'data privacy incidents': 'INC_Incident',
                'data privacy incident': 'INC_Incident',
                
                'contracts': 'DOC_Contract',
                'contract': 'DOC_Contract',
                'documents': 'DOC_Document',
                'document': 'DOC_Document',
            }
            
            if dashboard_lower in dashboard_mapping:
                technical = dashboard_mapping[dashboard_lower]
                if technical in available_subtypes:
                    return technical
            
            # Try fuzzy matching with available subtypes
            for subtype in available_subtypes:
                normalized = normalize_subtype(subtype)
                if dashboard_lower == normalized or dashboard_lower in normalized or normalized in dashboard_lower:
                    return subtype
            
            return None
        
        # CRITICAL: First try dashboard-to-technical mapping
        # User might provide dashboard-friendly names like "Controllers", "Datatypes", "Data protection officers"
        dashboard_to_tech = dashboard_to_technical(providedSubType, availableSubTypes)
        if dashboard_to_tech:
            return dashboard_to_tech
        
        # Special handling for DPO/Data Protection Officer
        dpo_variations = ['dpo', 'data protection officer', 'data protection', 'data protection officers']
        is_dpo = any(variant in provided_lower for variant in dpo_variations)
        if is_dpo:
            # Look for DPO-related subtypes
            for subtype in availableSubTypes:
                subtype_lower = subtype.lower()
                if 'dpo' in subtype_lower or 'dataprotection' in subtype_lower or 'data_protection' in subtype_lower:
                    return subtype
        
        for subType in availableSubTypes:
            subType_lower = subType.lower()
            subType_normalized = normalize_subtype(subType)
            
            # Exact match
            if provided_lower == subType_lower or provided_lower == subType_normalized:
                return subType
            
            # Normalized match (remove spaces, underscores, hyphens)
            provided_normalized = provided_lower.replace(' ', '').replace('_', '').replace('-', '')
            subType_normalized_no_spaces = subType_normalized.replace(' ', '').replace('_', '').replace('-', '')
            if provided_normalized == subType_normalized_no_spaces:
                return subType
            
            # Word-by-word matching
            provided_words = provided_lower.split()
            subType_words = subType_normalized.split()
            
            if all(word in subType_normalized for word in provided_words):
                return subType
            
            if all(word in provided_lower for word in subType_words):
                return subType
            
            # Contains match
            if provided_lower in subType_normalized or subType_normalized in provided_lower:
                return subType
            
            # Pattern-based matching
            patterns = {
                'data protection officer': ['dpo', 'data protection', 'privacy officer', 'gdpr officer', 'dataprotectionofficer'],
                'dataprotectionofficer': ['dpo', 'data protection', 'privacy officer', 'gdpr officer', 'data protection officer'],
                'person': ['person', 'employee', 'staff', 'user'],
                'it-system': ['it system', 'server', 'infrastructure', 'network', 'system', 'it-systems'],
                'it-systems': ['it system', 'server', 'infrastructure', 'network', 'system', 'it-system'],
                'application': ['application', 'app', 'software', 'program'],
                'datatype': ['data type', 'data', 'information', 'dataset', 'datatypes'],
                'datatypes': ['data type', 'data', 'information', 'dataset', 'datatype']
            }
            
            if subType_normalized in patterns:
                keywords = patterns[subType_normalized]
                for keyword in keywords:
                    if keyword in provided_lower or provided_lower in keyword:
                        return subType
        
        return None
    
    def _inferSubTypeFromPattern(self, objectType: str, name: str, 
                                 abbreviation: str, description: str,
                                 availableSubTypes: List[str]) -> Optional[str]:
        """
        Infer subtype from patterns in name/abbreviation/description.
        
        Simple keyword matching - no LLM needed.
        
        Args:
            objectType: Type of object
            name: Object name
            abbreviation: Object abbreviation
            description: Object description
            availableSubTypes: List of valid subtypes
        
        Returns:
            Inferred subtype or None
        """
        if not availableSubTypes:
            return None
        
        # Normalize inputs
        name_lower = (name or '').lower().strip()
        abbr_lower = (abbreviation or '').lower().strip()
        desc_lower = (description or '').lower().strip()
        combined_text = f"{name_lower} {abbr_lower} {desc_lower}"
        
        def normalize_subtype(st: str) -> str:
            """Remove common prefixes"""
            st_clean = st.lower().replace('ast_', '').replace('per_', '').replace('_', ' ').replace('-', ' ')
            return st_clean.strip()
        
        for subType in availableSubTypes:
            subType_lower = subType.lower()
            subType_normalized = normalize_subtype(subType)
            
            # Exact match in description
            if desc_lower == subType_lower or desc_lower == subType_normalized:
                return subType
            
            desc_words = desc_lower.split()
            for word in desc_words:
                if word == subType_lower or word == subType_normalized:
                    return subType
                if word.rstrip('s') == subType_normalized.rstrip('s') or subType_normalized.rstrip('s') == word.rstrip('s'):
                    return subType
                if word in subType_normalized or subType_normalized in word:
                    return subType
            
            # Direct match in combined text
            if subType_lower in combined_text or subType_normalized in combined_text:
                return subType
            
            # Pattern mappings
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
            if subType_normalized in type_patterns:
                keywords = type_patterns[subType_normalized]
                for keyword in keywords:
                    if keyword in combined_text:
                        return subType
            
            # Partial match
            if abbr_lower and (abbr_lower in subType_lower or subType_lower in abbr_lower):
                return subType
        
        return None
    
    # ========== UTILITY METHODS (from ISMSHandler) ==========
    
    def _success(self, message: str, data: Any = None) -> Dict:
        """
        Format success response.
        
        Args:
            message: Success message text
            data: Optional additional data
        
        Returns:
            Dict with success response format
        """
        return {
            'type': 'success',
            'text': message,
            'data': data
        }
    
    def _error(self, message: str) -> Dict:
        """
        Format error response.
        
        Args:
            message: Error message text
        
        Returns:
            Dict with error response format
        """
        return {
            'type': 'error',
            'text': message
        }
    
    def _formatResult(self, operation: str, result: Any) -> str:
        """
        Format Verinice result for display.
        
        This is a simplified formatter. The full MainAgent formatter
        will be used when integrated, but this provides basic formatting
        for testing.
        
        Args:
            operation: Operation type (e.g., 'listVeriniceObjects')
            result: Raw result from Verinice tool
        
        Returns:
            Formatted string for display
        """
        # For now, return simple formatted result
        # This will be replaced with proper MainAgent formatter during integration
        if isinstance(result, dict):
            if operation == 'listVeriniceObjects':
                objects = result.get('objects', {})
                items = objects.get('items', []) if isinstance(objects, dict) else (objects if isinstance(objects, list) else [])
                objectType = result.get('objectType', 'objects')
                
                if not items:
                    return f"No {objectType}s found."
                
                formatted = f"Found {len(items)} {objectType}(s):\n\n"
                for i, item in enumerate(items[:20], 1):  # Limit to 20 items
                    name = item.get('name', 'N/A')
                    itemId = item.get('id') or item.get('resourceId', 'N/A')
                    formatted += f"{i}. {name} (ID: {itemId})\n"
                
                if len(items) > 20:
                    formatted += f"\n... and {len(items) - 20} more items"
                
                return formatted
            
            elif operation == 'getVeriniceObject':
                obj = result.get('object', result)
                name = obj.get('name', 'N/A')
                objId = obj.get('id') or obj.get('resourceId', 'N/A')
                objType = obj.get('type', 'object')
                
                formatted = f"**{objType.upper()}: {name}**\n\n"
                formatted += f"ID: {objId}\n"
                
                if 'description' in obj:
                    formatted += f"Description: {obj['description']}\n"
                if 'abbreviation' in obj:
                    formatted += f"Abbreviation: {obj['abbreviation']}\n"
                if 'status' in obj:
                    formatted += f"Status: {obj['status']}\n"
                if 'subType' in obj:
                    formatted += f"SubType: {obj['subType']}\n"
                
                return formatted
        
        # Fallback: convert to string
        return str(result)


# ==================== USAGE EXAMPLE ====================

def example_usage():
    """
    Example of how ISMSCoordinator will be used in MainAgent.
    
    This is for documentation only - not actual integration.
    """
    
    # In MainAgent.__init__:
    # self._ismsCoordinator = None
    # self._useIsmsCoordinator = False  # Feature flag
    
    # In MainAgent (when integrated):
    def _getIsmsCoordinator(agent):
        """Lazy initialize ISMS Coordinator"""
        if not agent._ismsCoordinator:
            tools = {
                'veriniceTool': agent._veriniceTool,
                'llmTool': agent._llmTool
            }
            agent._ismsCoordinator = ISMSCoordinator(
                agent.state,
                tools,
                agent.contextManager
            )
        return agent._ismsCoordinator
    
    # Example calls:
    # coordinator = agent._getIsmsCoordinator()
    
    # CRUD operation:
    # result = coordinator.handleOperation('create', 'asset', message)
    
    # Report generation:
    # result = coordinator.handleReportGeneration(command, message)
    
    # Follow-up handling:
    # result = coordinator.handleReportFollowUp(message)
    # result = coordinator.handleSubtypeFollowUp(message)


# ==================== TESTING NOTES ====================

"""
Shadow Testing Strategy (Phase 4):

1. Build this coordinator in isolation (CURRENT PHASE)
2. When Phase 3 monitoring ends (Jan 17):
   - Connect to MainAgent with feature flag False
   - Run old ISMSHandler AND new ISMSCoordinator in parallel
   - Log both results for comparison
   - Validate 100% match rate
3. Deploy when confident (flip flag to True)
4. Monitor for 2 weeks
5. Remove old ISMSHandler code

Feature Flag Location:
    mainAgent.py: self._useIsmsCoordinator = False

Shadow Testing Code:
    if self._useIsmsCoordinator:
        new_result = self._ismsCoordinator.handleOperation(...)
        return new_result
    else:
        old_result = self._ismsHandler.execute(...)
        return old_result

Validation:
    - All ISMS operations must work identically
    - State management must be preserved
    - Follow-ups must work correctly
    - Report generation must work end-to-end
"""
