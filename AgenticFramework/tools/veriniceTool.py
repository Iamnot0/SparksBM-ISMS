"""Verinice ISMS integration tools - CRUD operations for all object types"""
import sys
import os
from typing import Dict, List, Optional, Any
from agents.instructions import get_error_message

# Import path utilities and settings
from utils.pathUtils import find_sparksbm_scripts_path, add_to_python_path
from config.settings import Settings

SPARKSBM_SCRIPTS_PATH = find_sparksbm_scripts_path()
if SPARKSBM_SCRIPTS_PATH:
    add_to_python_path(SPARKSBM_SCRIPTS_PATH)

try:
    from sparksbmMgmt import SparksBMClient, SparksBMObjectManager, SparksBMUnitManager, SparksBMDomainManager, API_URL
    VERINICE_AVAILABLE = True
    # Use API_URL from sparksbmMgmt if available, otherwise use Settings
    if not API_URL or API_URL == "http://localhost:8070":
        API_URL = Settings.VERINICE_API_URL
except ImportError:
    VERINICE_AVAILABLE = False
    SparksBMClient = None  # type: ignore
    SparksBMObjectManager = None  # type: ignore
    SparksBMUnitManager = None  # type: ignore
    SparksBMDomainManager = None  # type: ignore
    API_URL = Settings.VERINICE_API_URL


class VeriniceTool:
    """Tools for interacting with Verinice ISMS - Full CRUD operations"""
    
    # Object type mappings
    OBJECT_TYPES = {
        "scope": "scopes",
        "asset": "assets",
        "control": "controls",
        "process": "processes",
        "person": "persons",
        "scenario": "scenarios",
        "incident": "incidents",
        "document": "documents"
    }
    
    def __init__(self):
        """Initialize Verinice tool with SparksBM client"""
        self.client = None
        self.objectManager = None
        self.unitManager = None
        self.domainManager = None
        
        if VERINICE_AVAILABLE:
            # Retry authentication up to 3 times with delays
            import time
            max_retries = 3
            retry_delay = 2  # seconds
            
            for attempt in range(max_retries):
                try:
                    # Suppress print output during initialization
                    import io
                    import contextlib
                    f = io.StringIO()
                    with contextlib.redirect_stdout(f):
                        self.client = SparksBMClient()
                    if self.client and self.client.accessToken:
                        self.objectManager = SparksBMObjectManager(self.client)
                        self.unitManager = SparksBMUnitManager(self.client)
                        if SparksBMDomainManager:
                            self.domainManager = SparksBMDomainManager(self.client)
                        break  # Success, exit retry loop
                    else:
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay)
                except Exception as e:
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                    else:
                        self.client = None
    
    def _checkClient(self) -> bool:
        """Check if client is available - tries to ensure authentication"""
        return self._ensureAuthenticated()
    
    def _ensureAuthenticated(self) -> bool:
        """Ensure client is authenticated, refresh token if expired"""
        # If client doesn't exist, try to initialize it
        if not self.client and VERINICE_AVAILABLE:
            try:
                import io
                import contextlib
                f = io.StringIO()
                with contextlib.redirect_stdout(f):
                    self.client = SparksBMClient()
                if self.client and self.client.accessToken:
                    # Ensure ObjectManager is created
                    if not self.objectManager:
                        self.objectManager = SparksBMObjectManager(self.client)
                    if not self.unitManager:
                        self.unitManager = SparksBMUnitManager(self.client)
                    if SparksBMDomainManager and not self.domainManager:
                        self.domainManager = SparksBMDomainManager(self.client)
            except Exception:
                pass
        
        # If client exists but ObjectManager doesn't, create it
        if self.client and self.client.accessToken and not self.objectManager:
            try:
                    self.objectManager = SparksBMObjectManager(self.client)
                    self.unitManager = SparksBMUnitManager(self.client)
                    if SparksBMDomainManager:
                        self.domainManager = SparksBMDomainManager(self.client)
            except Exception:
                pass
        
        if not self.client:
            return False
        
        if not self.client.accessToken:
            # Try to re-authenticate
            if hasattr(self.client, 'getAccessToken'):
                try:
                    self.client.getAccessToken()
                except Exception:
                    return False
            return self.client.accessToken is not None
        
        # Token exists, but might be expired - test it
        try:
            # Use session to make request (has auth headers)
            response = self.client.session.get(f"{self.client.apiUrl}/domains", timeout=5)
            if response.status_code == 401:
                # Token expired, re-authenticate
                if hasattr(self.client, 'getAccessToken'):
                    try:
                        self.client.getAccessToken()
                        return self.client.accessToken is not None
                    except Exception:
                        return False
                return False
            return True
        except Exception as e:
            # Network error or other issue
            return False
    
    # ==================== CREATE OPERATIONS ====================
    
    def createObject(self, objectType: str, domainId: str, unitId: str, 
                    name: str, subType: Optional[str] = None,
                    description: str = "", abbreviation: Optional[str] = None) -> Dict:
        """
        Create an object in Verinice
        
        Args:
            objectType: Type of object (scope, asset, control, process, person, scenario, incident, document)
            domainId: Domain ID
            unitId: Unit ID
            name: Object name
            subType: Optional subType (will use first available if not provided)
            description: Optional description
        
        Returns:
            Dict with success status and data or error
        """
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': get_error_message('connection', 'isms_client_not_available_detailed')
            }
        
        if not self.objectManager:
            return {'success': False, 'error': get_error_message('connection', 'isms_object_manager_not_initialized')}
        
        try:
            result = self.objectManager.createObject(
                object_type=objectType,
                name=name,
                domain_id=domainId,
                unit_id=unitId,
                description=description,
                sub_type=subType,
                abbreviation=abbreviation,
                unit_manager=self.unitManager
            )
            
            if result:
                # Use the name parameter we passed, not from result (result doesn't have name)
                return {
                    'success': True,
                    'data': result,
                    'objectId': result.get('resourceId') or result.get('id'),
                    'objectType': objectType,
                    'objectName': name  # Use the name parameter passed to createObject
                }
            else:
                return {'success': False, 'error': get_error_message('operation_failed', 'create_object_exception', error='Failed to create object using SparksBMObjectManager. It returned no data.')}
        except Exception as e:
            errorMsg = str(e)
            # Try to extract more details from the exception
            serverResponse = None
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                serverResponse = e.response.text
                errorMsg += f"\n   Server response: {serverResponse[:300]}"
            elif hasattr(e, 'args') and isinstance(e.args, tuple) and len(e.args) > 0:
                # FIX: Safe access to e.args[0]
                first_arg = e.args[0] if len(e.args) > 0 else None
                if first_arg:
                    errorMsg += f"\n   Details: {str(first_arg)[:300]}"
            
            if '500' in errorMsg or 'Internal Server Error' in errorMsg:
                errorMsg += "\n   [Note: This is a Verinice backend error, not an agent issue]"
                errorMsg += "\n   Check Verinice backend logs for detailed error information"
            
            return {'success': False, 'error': get_error_message('operation_failed', 'create_object_exception', error=errorMsg)}
    
    # ==================== READ OPERATIONS ====================
    
    def listObjects(self, objectType: str, domainId: Optional[str] = None, filters: Optional[Dict] = None, unitId: Optional[str] = None) -> Dict:
        """
        List objects of a specific type in a domain or unit
        
        Args:
            objectType: Type of object (scope, asset, control, process, person, scenario, incident, document)
            domainId: Domain ID (optional for scopes - can list at unit level)
            filters: Optional filters (subType, status, etc. - passed as query parameters)
            unitId: Unit ID (optional, used for scopes when domainId is not available)
        
        Returns:
            Dict with success status and list of objects
        """
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': get_error_message('connection', 'isms_client_not_available_detailed')
            }
        
        if not self.objectManager:
            return {'success': False, 'error': get_error_message('connection', 'isms_object_manager_not_initialized')}
        
        plural = self.OBJECT_TYPES.get(objectType.lower())
        if not plural:
            return {
                'success': False,
                'error': get_error_message('validation', 'unknown_object_type', objectType=objectType, availableTypes=', '.join(self.OBJECT_TYPES.keys()))
            }
        
        try:
            # For scopes, can list at unit level if no domain
            if objectType.lower() == 'scope' and not domainId:
                if unitId:
                    # List scopes at unit level
                    url = f"{API_URL}/units/{unitId}/scopes"
                else:
                    # Try to get unit first
                    unitsResult = self.listUnits()
                    units = unitsResult.get('units', [])
                    # SAFE: Check if units is a list and has elements before indexing
                    if unitsResult.get('success') and isinstance(units, list) and len(units) > 0:
                        unitId = units[0].get('id')
                        url = f"{API_URL}/units/{unitId}/scopes"
                    else:
                        return {'success': False, 'error': get_error_message('not_found', 'no_unit_available')}
            elif domainId:
                # Use direct API call to support filters
                url = f"{API_URL}/domains/{domainId}/{plural}"
            else:
                return {'success': False, 'error': get_error_message('not_found', 'domain_or_unit_required')}
            params = {}
            if filters:
                for key, value in filters.items():
                    if value is not None:
                        params[key] = value
            
            # CRITICAL: Request all items by setting a large page size
            # Verinice API defaults to 20 items per page, so we need to explicitly request more
            # Using size=10000 to get all items (adjust if you have more than 10k objects)
            if 'size' not in params:
                params['size'] = 10000  # Request up to 10,000 items
            
            response = self.client.makeRequest('GET', url, params=params if params else None)
            response.raise_for_status()
            
            objects = response.json()
            
            if isinstance(objects, dict):
                if 'items' in objects:
                    # Keep the dict structure with 'items' key
                    objects = objects
                elif 'content' in objects:
                    objects = {'items': objects['content']}
                else:
                    # Convert to standard format
                    objects = {'items': []}
            elif isinstance(objects, list):
                # Convert list to standard format
                objects = {'items': objects}
            else:
                objects = {'items': []}
            
            items = objects.get('items', []) if isinstance(objects, dict) else []
            return {
                'success': True,
                'count': len(items),
                'objects': objects,  # Keep as dict with 'items' key for consistency
                'objectType': objectType,
                'domainId': domainId
            }
        except Exception as e:
            errorMsg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                errorMsg = f'HTTP {e.response.status_code}: {e.response.text[:200]}'
            return {'success': False, 'error': get_error_message('operation_failed', 'list_objects_exception', error=errorMsg)}
    
    def getObject(self, objectType: str, domainId: str, objectId: str) -> Dict:
        """
        Get a specific object by ID - backend uses top-level /{plural}/{uuid} endpoint
        
        Args:
            objectType: Type of object (scope, asset, control, process, person, scenario, incident, document)
            domainId: Domain ID (not used for GET - kept for compatibility)
            objectId: Object ID
        
        Returns:
            Dict with success status and object data
        """
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': get_error_message('connection', 'isms_client_not_available_detailed')
            }
        
        plural = self.OBJECT_TYPES.get(objectType.lower())
        if not plural:
            return {
                'success': False, 
                'error': f'Unknown object type: {objectType}. Available types: {", ".join(self.OBJECT_TYPES.keys())}'
            }
        
        try:
            # Backend uses top-level endpoint: /{plural}/{uuid}
            url = f"{API_URL}/{plural}/{objectId}"
            response = self.client.makeRequest('GET', url)
            response.raise_for_status()
            
            objectData = response.json()
            return {
                'success': True,
                'data': objectData,
                'objectId': objectId,
                'objectType': objectType,
                'domainId': domainId
            }
        except Exception as e:
            errorMsg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                status_code = e.response.status_code
                if status_code == 404:
                    errorMsg = f'{objectType} not found'
                elif status_code == 403:
                    errorMsg = f'Access forbidden: You may not have permission to view this {objectType}'
                else:
                    error_text = e.response.text[:300] if hasattr(e.response, 'text') else str(e.response.content[:300])
                    errorMsg = f'HTTP {status_code}: {error_text}'
            return {'success': False, 'error': get_error_message('operation_failed', 'get_object', objectType=objectType, error=errorMsg)}
    
    # ==================== UPDATE OPERATIONS ====================
    
    def updateObject(self, objectType: str, domainId: str, objectId: str, 
                    data: Dict = None, **kwargs) -> Dict:
        """
        Update an object - properly handles PUT by getting full object first
        
        Args:
            objectType: Type of object
            domainId: Domain ID
            objectId: Object ID
            data: Dictionary of fields to update
        
        Returns:
            Dict with success status and updated object data
        """
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': get_error_message('connection', 'isms_client_not_available_detailed')
            }
        
        plural = self.OBJECT_TYPES.get(objectType.lower())
        if not plural:
            return {'success': False, 'error': f'Unknown object type: {objectType}'}
        
        try:
            # Step 1: GET the current object from domain-specific endpoint
            # FIX: For UPDATE, we need the InDomain view, not the top-level view
            # Use domain-specific GET endpoint: /domains/{domainId}/{plural}/{uuid}
            plural = self.OBJECT_TYPES.get(objectType.lower())
            if not plural:
                return {'success': False, 'error': f'Unknown object type: {objectType}'}
            
            inDomainUrl = f"{API_URL}/domains/{domainId}/{plural}/{objectId}"
            inDomainResponse = self.client.makeRequest('GET', inDomainUrl)
            inDomainResponse.raise_for_status()
            
            etag = inDomainResponse.headers.get('ETag') or inDomainResponse.headers.get('etag')
            
            # Step 2: Use full object from InDomain GET, update only specified fields
            # InDomain PUT requires complete object with all nested structures
            fullObject = inDomainResponse.json()
            if not isinstance(fullObject, dict):
                return {'success': False, 'error': get_error_message('validation', 'invalid_object_data')}
            
            fullObject = fullObject.copy()
            
            # FIX: InDomain GET already returns object with subType/status at top level
            # No need to extract from domains dict - the InDomain endpoint already does this
            
            # FIX: Merge user's updates into full object
            if data:
                for key, value in data.items():
                    fullObject[key] = value
            if kwargs:
                for key, value in kwargs.items():
                    fullObject[key] = value
            
            # FIX: Remove frontend-only fields (matching frontend behavior)
            # Frontend deletes these before sending to backend
            if 'createdAt' in fullObject:
                del fullObject['createdAt']
            if 'updatedAt' in fullObject:
                del fullObject['updatedAt']
            if 'displayName' in fullObject:
                del fullObject['displayName']
            

            
            # FIX: Remove read-only fields that backend rejects
            # BUT: FullScopeInDomainDto requires 'id' field, so keep it!
            readOnlyFields = ['_self', 'type', 'resourceId']
            for field in readOnlyFields:
                fullObject.pop(field, None)
            
            # FIX: Ensure 'id' is present (required by FullScopeInDomainDto)
            if 'id' not in fullObject:
                fullObject['id'] = objectId
            
            # FIX: CRITICAL - Validate and ensure all required fields are present
            # Backend requires: owner (@NotNull), subType (@NotNull, min=1), status (@NotNull, min=1)
            
            # 1. Ensure owner is present and in correct format {targetUri: "..."}
            if 'owner' in fullObject:
                owner = fullObject['owner']
                if isinstance(owner, dict):
                    target_uri = owner.get('targetUri')
                    if not target_uri and 'id' in owner:
                        target_uri = f'{API_URL}/units/{owner["id"]}'
                    if target_uri:
                        fullObject['owner'] = {'targetUri': target_uri}
                    elif 'id' in owner:
                        fullObject['owner'] = {'targetUri': f'{API_URL}/units/{owner["id"]}'}
                    else:
                        # Invalid owner structure - try to get from unitId if available
                        print(f"[UPDATE DEBUG] WARNING: Invalid owner structure: {owner}")
            else:
                # Owner is REQUIRED - try to get from unitId or fail
                print(f"[UPDATE DEBUG] ERROR: No owner field found in object!")
                # Try to get unitId from context (if available)
                # For now, return error - owner is mandatory
                return {'success': False, 'error': get_error_message('validation', 'cannot_update_missing_owner')}
            
            # 2. Ensure subType is present and valid (required, min length 1)
            if 'subType' not in fullObject or not fullObject.get('subType'):
                print(f"[UPDATE DEBUG] ERROR: subType is missing or empty!")
                return {'success': False, 'error': get_error_message('validation', 'cannot_update_missing_subtype')}
            
            # 3. Ensure status is present and valid (required, min length 1)
            if 'status' not in fullObject or not fullObject.get('status'):
                print(f"[UPDATE DEBUG] ERROR: status is missing or empty!")
                return {'success': False, 'error': get_error_message('validation', 'cannot_update_missing_status')}
            
            # 4. Keep 'domains' dict if it has content (backend might need it for validation)
            # Only remove if it's truly empty
            if 'domains' in fullObject:
                if isinstance(fullObject['domains'], dict) and len(fullObject['domains']) == 0:
                    del fullObject['domains']
            
            # 5. Validate ETag is present (required by backend)
            if not etag:
                print(f"[UPDATE DEBUG] WARNING: ETag is missing from GET response!")
                # ETag is required by backend, but let's try without it first
                # If it fails, we'll get a clear error message
            
            # Step 3: PUT the complete updated object
            # Backend InDomain controller requires ALL fields: /domains/{domainId}/{plural}/{uuid}
            url = f"{API_URL}/domains/{domainId}/{plural}/{objectId}"
            
            # DEBUG: Log what we're sending (detailed)
            import json as json_module
            print(f"[UPDATE DEBUG] Sending PUT to: {url}")
            print(f"[UPDATE DEBUG] Payload keys ({len(fullObject)}): {list(fullObject.keys())}")
            print(f"[UPDATE DEBUG] Payload JSON: {json_module.dumps(fullObject, indent=2, default=str)[:1000]}")
            
            headers = {}
            if etag:
                headers['If-Match'] = etag
            else:
                # ETag is required - return error before sending
                return {
                    'success': False,
                    'error': get_error_message('validation', 'cannot_update_missing_etag')
                }
            
            response = self.client.makeRequest('PUT', url, json=fullObject, headers=headers)
            
            print(f"[UPDATE DEBUG] Response status: {response.status_code}")
            print(f"[UPDATE DEBUG] Response: {response.text[:300]}")
            
            # FIX: Better error handling for 400/412 errors with detailed logging
            if response.status_code == 400:
                try:
                    error_detail = response.json()
                    # Log full error for debugging
                    import json as json_module
                    print(f"[UPDATE DEBUG] HTTP 400 Error Detail: {json_module.dumps(error_detail, indent=2)}")
                    print(f"[UPDATE DEBUG] Payload sent had {len(fullObject)} keys: {list(fullObject.keys())}")
                    return {
                        'success': False,
                        'error': get_error_message('validation', 'backend_validation_error', errorDetail=str(error_detail))
                    }
                except Exception:
                    error_text = response.text[:500]
                    print(f"[UPDATE DEBUG] HTTP 400 Error Text: {error_text}")
                    print(f"[UPDATE DEBUG] Payload sent had {len(fullObject)} keys: {list(fullObject.keys())}")
                    return {
                        'success': False,
                        'error': f'HTTP 400: {error_text}'
                    }
            elif response.status_code == 412:
                return {
                    'success': False,
                    'error': get_error_message('validation', 'precondition_failed')
                }
            
            response.raise_for_status()
            
            updatedData = response.json()
            return {
                'success': True,
                'data': updatedData,
                'objectId': objectId,
                'objectType': objectType
            }
        except Exception as e:
            errorMsg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code == 404:
                    errorMsg = f'{objectType} not found'
                else:
                    errorMsg = f'HTTP {e.response.status_code}: {e.response.text[:200]}'
            return {'success': False, 'error': get_error_message('operation_failed', 'update_object_exception', error=errorMsg)}
    
    # ==================== DELETE OPERATIONS ====================
    
    def deleteObject(self, objectType: str, domainId: str, objectId: str) -> Dict:
        """
        Delete an object - backend uses top-level /{plural}/{uuid} endpoint for ALL objects
        
        Args:
            objectType: Type of object
            domainId: Domain ID (not used for DELETE - kept for compatibility)
            objectId: Object ID
        
        Returns:
            Dict with success status
        """
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': get_error_message('connection', 'isms_client_not_available_detailed')
            }
        
        plural = self.OBJECT_TYPES.get(objectType.lower())
        if not plural:
            return {'success': False, 'error': f'Unknown object type: {objectType}'}
        
        try:
            # Backend uses top-level endpoint for DELETE: /{plural}/{uuid}
            # This applies to ALL object types (scopes, assets, controls, etc.)
            url = f"{API_URL}/{plural}/{objectId}"
            response = self.client.makeRequest('DELETE', url)
            
            if response.status_code in [200, 204]:
                return {
                    'success': True,
                    'message': f'Deleted {objectType} successfully',
                    'objectId': objectId,
                    'objectType': objectType
                }
            else:
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}: {response.text[:200]}'
                }
        except Exception as e:
            errorMsg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code == 404:
                    errorMsg = f'{objectType} not found'
                else:
                    errorMsg = f'HTTP {e.response.status_code}: {e.response.text[:200]}'
            return {'success': False, 'error': get_error_message('operation_failed', 'delete_object_exception', error=errorMsg)}
    
    # ==================== REPORT OPERATIONS ====================
    
    def listReports(self, domainId: Optional[str] = None) -> Dict:
        """
        List available reports for a domain (or all reports if domainId not provided)
        
        Args:
            domainId: Optional Domain ID (for filtering, but reports are global)
        
        Returns:
            Dict with success status and list of reports
        """
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': get_error_message('connection', 'isms_client_not_available_detailed')
            }
        
        try:
            # Use direct API call since reports endpoint is global
            url = f"{API_URL}/api/reporting/reports"
            response = self.client.makeRequest('GET', url)
            response.raise_for_status()
            
            reports = response.json()
            if isinstance(reports, dict):
                # Convert dict of reports to list format
                reports_list = []
                for report_id, report_data in reports.items():
                    report_entry = {
                        'id': report_id,
                        **report_data
                    }
                    reports_list.append(report_entry)
                reports = reports_list
            
            return {
                'success': True,
                'count': len(reports),
                'reports': reports,
                'domainId': domainId
            }
        except Exception as e:
            errorMsg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                errorMsg = f'HTTP {e.response.status_code}: {e.response.text[:200]}'
            return {'success': False, 'error': get_error_message('operation_failed', 'list_reports', error=errorMsg)}
    
    def generateReport(self, reportId: str, domainId: Optional[str] = None, params: Optional[Dict] = None) -> Dict:
        """
        Generate a report
        
        Args:
            reportId: Report ID (e.g., 'inventory-of-assets', 'risk-assessment', 'statement-of-applicability')
            domainId: Optional Domain ID (for context, but reports are generated globally)
            params: Optional report parameters (outputType, language, targets, timeZone)
        
        Returns:
            Dict with success status and report data/URL
        """
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': get_error_message('connection', 'isms_client_not_available_detailed')
            }
        
        try:
            # Report generation endpoint matches frontend expectation
            url = f"{API_URL}/api/reporting/reports/{reportId}"
            payload = params or {}
            payload['outputType'] = payload.get('outputType', 'application/pdf')
            payload['language'] = payload.get('language', 'en')
            payload['targets'] = payload.get('targets', [])
            payload['timeZone'] = payload.get('timeZone', 'UTC')
            
            # Make POST request - expect binary PDF response
            response = self.client.makeRequest('POST', url, json=payload)
            response.raise_for_status()
            
            content_type = response.headers.get('Content-Type', '')
            # FIX: Safe access to response.content
            content_preview = response.content[:4] if hasattr(response, 'content') and isinstance(response.content, bytes) and len(response.content) >= 4 else b''
            if 'application/pdf' in content_type or 'pdf' in content_type.lower() or content_preview == b'%PDF':
                # Return PDF data as base64 for transmission
                import base64
                pdf_data = response.content
                pdf_base64 = base64.b64encode(pdf_data).decode('utf-8')
                return {
                    'success': True,
                    'reportId': reportId,
                    'domainId': domainId,
                    'format': 'pdf',
                    'data': pdf_base64,
                    'size': len(pdf_data),
                    'message': f'Report "{reportId}" generated successfully ({len(pdf_data)} bytes). PDF data available in base64 format.'
                }
            else:
                # Try JSON response
                try:
                    result = response.json()
                    return {
                        'success': True,
                        'data': result,
                        'reportId': reportId,
                        'domainId': domainId
                    }
                except Exception:
                    # Return raw response
                    # FIX: Safe access to response content
                    response_text = response.text[:500] if hasattr(response, 'text') else ''
                    if not response_text and hasattr(response, 'content'):
                        response_text = str(response.content[:500]) if isinstance(response.content, bytes) else str(response.content)[:500]
                    return {
                        'success': True,
                        'data': response_text,
                        'reportId': reportId,
                        'domainId': domainId,
                        'message': 'Report generated but response format is not PDF or JSON'
                    }
        except Exception as e:
            errorMsg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                status_code = e.response.status_code
                error_text = e.response.text[:300] if hasattr(e.response, 'text') else str(e.response.content[:300])
                errorMsg = f'HTTP {status_code}: {error_text}'
                if status_code == 404:
                    errorMsg += f'\n   Report ID "{reportId}" not found. Available reports: inventory-of-assets, risk-assessment, statement-of-applicability'
            return {'success': False, 'error': get_error_message('operation_failed', 'generate_report', error=errorMsg)}
    
    # ==================== ANALYSIS OPERATIONS ====================
    
    # ==================== HELPER METHODS ====================
    
    def getValidSubTypes(self, domainId: str, objectType: str) -> Dict:
        """
        Get valid subTypes for an object type in a domain
        
        Args:
            domainId: Domain ID
            objectType: Type of object
        
        Returns:
            Dict with success status and list of valid subTypes
        """
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': get_error_message('connection', 'isms_client_not_available_detailed')
            }
        
        if not self.objectManager:
            return {'success': False, 'error': get_error_message('connection', 'isms_object_manager_not_initialized')}
        
        try:
            subTypes = self.objectManager.getValidSubTypes(domainId, objectType)
            return {
                'success': True,
                'subTypes': subTypes,
                'objectType': objectType,
                'domainId': domainId
            }
        except Exception as e:
            return {'success': False, 'error': get_error_message('operation_failed', 'get_subtypes', error=str(e))}
    
    def listDomains(self) -> Dict:
        """List all available domains"""
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': get_error_message('connection', 'isms_client_not_available_detailed')
            }
        
        try:
            from sparksbmMgmt import SparksBMDomainManager
            domainManager = SparksBMDomainManager(self.client)
            domains = domainManager.listDomains()
            return {
                'success': True,
                'count': len(domains),
                'domains': domains
            }
        except Exception as e:
            return {'success': False, 'error': get_error_message('operation_failed', 'list_domains', error=str(e))}
    
    def listUnits(self) -> Dict:
        """List all available units"""
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': get_error_message('connection', 'isms_client_not_available_detailed')
            }
        
        if not self.unitManager:
            return {'success': False, 'error': get_error_message('connection', 'isms_unit_manager_not_initialized')}
        
        try:
            units = self.unitManager.listUnits()
            return {
                'success': True,
                'count': len(units),
                'units': units
            }
        except Exception as e:
            return {'success': False, 'error': get_error_message('operation_failed', 'list_units_exception', error=str(e))}
    
    # ==================== DOMAIN MANAGEMENT ====================
    
    def createDomain(self, templateId: str) -> Dict:
        """Create domain from template"""
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': get_error_message('connection', 'isms_client_not_available_detailed')
            }
        
        if not self.domainManager:
            return {'success': False, 'error': get_error_message('connection', 'isms_domain_manager_not_initialized')}
        
        try:
            # createDomainFromTemplate returns bool, not domain object
            success = self.domainManager.createDomainFromTemplate(templateId)
            if success:
                # Fetch the newly created domain by listing all domains and finding the latest
                # or by template ID (domains created from same template might have similar names)
                domains = self.domainManager.listDomains()
                if domains:
                    # Find domain created from this template (most recent or matching template)
                    # For now, return success with template info
                    return {
                        'success': True,
                        'message': f'Domain created successfully from template {templateId}',
                        'templateId': templateId,
                        'totalDomains': len(domains)
                    }
                return {
                    'success': True,
                    'message': f'Domain created successfully from template {templateId}',
                    'templateId': templateId
                }
            return {'success': False, 'error': get_error_message('operation_failed', 'create_domain')}
        except Exception as e:
            return {'success': False, 'error': get_error_message('operation_failed', 'create_domain', error=str(e))}
    
    def deleteDomain(self, domainId: str) -> Dict:
        """Delete a domain"""
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': get_error_message('connection', 'isms_client_not_available_detailed')
            }
        
        if not self.domainManager:
            return {'success': False, 'error': get_error_message('connection', 'isms_domain_manager_not_initialized')}
        
        try:
            result = self.domainManager.deleteDomain(domainId)
            return {
                'success': result,
                'domainId': domainId
            }
        except Exception as e:
            return {'success': False, 'error': get_error_message('operation_failed', 'delete_domain', error=str(e))}
    
    def getDomainTemplates(self) -> Dict:
        """Get available domain templates"""
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': get_error_message('connection', 'isms_client_not_available_detailed')
            }
        
        if not self.domainManager:
            return {'success': False, 'error': get_error_message('connection', 'isms_domain_manager_not_initialized')}
        
        try:
            templates = self.domainManager.getDomainTemplates()
            return {
                'success': True,
                'count': len(templates),
                'templates': templates
            }
        except Exception as e:
            return {'success': False, 'error': get_error_message('operation_failed', 'get_templates', error=str(e))}
    
    def getDomainSubTypes(self, domainId: str, objectType: str = None) -> Dict:
        """Get subtypes for a domain (all types or specific type)"""
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': get_error_message('connection', 'isms_client_not_available_detailed')
            }
        
        if not self.objectManager:
            return {'success': False, 'error': get_error_message('connection', 'isms_object_manager_not_initialized')}
        
        try:
            if objectType:
                subtypes = self.objectManager.getValidSubTypes(domainId, objectType)
                return {
                    'success': True,
                    'objectType': objectType,
                    'subTypes': subtypes,
                    'count': len(subtypes)
                }
            else:
                object_types = ['scope', 'asset', 'control', 'process', 'person', 'scenario', 'incident', 'document']
                all_subtypes = {}
                for obj_type in object_types:
                    subtypes = self.objectManager.getValidSubTypes(domainId, obj_type)
                    if subtypes:
                        all_subtypes[obj_type] = subtypes
                return {
                    'success': True,
                    'subTypes': all_subtypes,
                    'totalCount': sum(len(v) for v in all_subtypes.values())
                }
        except Exception as e:
            return {'success': False, 'error': get_error_message('operation_failed', 'get_subtypes', error=str(e))}
    
    # ==================== UNIT MANAGEMENT ====================
    
    def createUnit(self, name: str, description: str = "", domainIds: List[str] = None) -> Dict:
        """Create a new unit"""
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': get_error_message('connection', 'isms_client_not_available_detailed')
            }
        
        if not self.unitManager:
            return {'success': False, 'error': get_error_message('connection', 'isms_unit_manager_not_initialized')}
        
        try:
            result = self.unitManager.createUnit(name, description, domainIds)
            if result:
                return {
                    'success': True,
                    'unitId': result.get('id'),
                    'unit': result
                }
            return {'success': False, 'error': get_error_message('operation_failed', 'create_unit')}
        except Exception as e:
            return {'success': False, 'error': get_error_message('operation_failed', 'create_unit', error=str(e))}
    
    # ==================== RISK DEFINITIONS ====================
    
    def listRiskDefinitions(self, domainId: str) -> Dict:
        """List risk definitions in a domain"""
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': get_error_message('connection', 'isms_client_not_available_detailed')
            }
        
        if not self.objectManager:
            return {'success': False, 'error': get_error_message('connection', 'isms_object_manager_not_initialized')}
        
        try:
            risk_defs = self.objectManager.listRiskDefinitions(domainId)
            return {
                'success': True,
                'count': len(risk_defs),
                'riskDefinitions': risk_defs,
                'domainId': domainId
            }
        except Exception as e:
            return {'success': False, 'error': get_error_message('operation_failed', 'list_risk_definitions', error=str(e))}
    
    # ==================== PROFILE MANAGEMENT ====================
    
    def listProfiles(self, domainId: str) -> Dict:
        """List profiles in a domain"""
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': get_error_message('connection', 'isms_client_not_available_detailed')
            }
        
        if not self.domainManager:
            return {'success': False, 'error': get_error_message('connection', 'isms_domain_manager_not_initialized')}
        
        try:
            profiles = self.domainManager.listProfiles(domainId)
            return {
                'success': True,
                'count': len(profiles),
                'profiles': profiles,
                'domainId': domainId
            }
        except Exception as e:
            return {'success': False, 'error': get_error_message('operation_failed', 'list_profiles', error=str(e))}
    
    def getDomain(self, domainId: str) -> Dict:
        """Get detailed information about a domain"""
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': get_error_message('connection', 'isms_client_not_available_detailed')
            }
        
        try:
            response = self.client.makeRequest('GET', f"{API_URL}/domains/{domainId}")
            response.raise_for_status()
            domain = response.json()
            return {
                'success': True,
                'domain': domain,
                'domainId': domainId
            }
        except Exception as e:
            errorMsg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                status_code = e.response.status_code
                if status_code == 404:
                    errorMsg = f'Domain {domainId} not found'
                else:
                    error_text = e.response.text[:300] if hasattr(e.response, 'text') else str(e.response.content[:300])
                    errorMsg = f'HTTP {status_code}: {error_text}'
            return {'success': False, 'error': get_error_message('operation_failed', 'get_domain', error=errorMsg)}
    
    def getUnit(self, unitId: str) -> Dict:
        """Get detailed information about a unit"""
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': get_error_message('connection', 'isms_client_not_available_detailed')
            }
        
        if not self.unitManager:
            return {'success': False, 'error': get_error_message('connection', 'isms_unit_manager_not_initialized')}
        
        try:
            response = self.client.makeRequest('GET', f"{API_URL}/units/{unitId}")
            response.raise_for_status()
            unit = response.json()
            return {
                'success': True,
                'unit': unit,
                'unitId': unitId
            }
        except Exception as e:
            errorMsg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                status_code = e.response.status_code
                if status_code == 404:
                    errorMsg = f'Unit {unitId} not found'
                else:
                    error_text = e.response.text[:300] if hasattr(e.response, 'text') else str(e.response.content[:300])
                    errorMsg = f'HTTP {status_code}: {error_text}'
            return {'success': False, 'error': get_error_message('operation_failed', 'get_unit', error=errorMsg)}
    
    def listCatalogItems(self, domainId: str) -> Dict:
        """List catalog items in a domain"""
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': get_error_message('connection', 'isms_client_not_available_detailed')
            }
        
        if not self.objectManager:
            return {'success': False, 'error': get_error_message('connection', 'isms_object_manager_not_initialized')}
        
        try:
            catalog_items = self.objectManager.listCatalogItems(domainId)
            return {
                'success': True,
                'count': len(catalog_items),
                'catalogItems': catalog_items,
                'domainId': domainId
            }
        except Exception as e:
            return {'success': False, 'error': get_error_message('operation_failed', 'list_catalog_items', error=str(e))}
    
    
    # ==================== RECONCILIATION OPERATIONS ====================
    
    def compareObjects(self, objectType: str, objectId1: str, objectId2: str, domainId: str) -> Dict:
        """
        Compare two ISMS objects and find differences.
        
        Args:
            objectType: Type of objects to compare (asset, control, etc.)
            objectId1: First object ID
            objectId2: Second object ID
            domainId: Domain ID
        
        Returns:
            Dict with comparison results:
            {
                'success': bool,
                'differences': [
                    {'field': str, 'value1': any, 'value2': any}
                ],
                'similarities': [list of similar fields],
                'summary': str
            }
        """
        if not self._ensureAuthenticated():
            return {
                'success': False, 
                'error': get_error_message('connection', 'isms_client_not_available')
            }
        
        try:
            obj1_result = self.getObject(objectType, domainId, objectId1)
            obj2_result = self.getObject(objectType, domainId, objectId2)
            
            if not obj1_result.get('success'):
                return {'success': False, 'error': get_error_message('operation_failed', 'get_source_object', error=obj1_result.get("error"))}
            if not obj2_result.get('success'):
                return {'success': False, 'error': get_error_message('operation_failed', 'get_target_object', error=obj2_result.get("error"))}
            
            # FIX: getObject returns 'data', not 'object'
            obj1 = obj1_result.get('data', {})
            obj2 = obj2_result.get('data', {})
            
            # Compare fields
            differences = []
            similarities = []
            
            all_keys = set(obj1.keys()) | set(obj2.keys())
            
            for key in all_keys:
                val1 = obj1.get(key)
                val2 = obj2.get(key)
                
                # Skip internal fields
                if key in ['id', 'resourceId', 'version', 'created', 'modified']:
                    continue
                
                if val1 != val2:
                    differences.append({
                        'field': key,
                        'value1': val1,
                        'value2': val2
                    })
                else:
                    similarities.append(key)
            
            summary = f"Found {len(differences)} differences and {len(similarities)} similarities"
            
            return {
                'success': True,
                'differences': differences,
                'similarities': similarities,
                'summary': summary,
                'object1': {'id': objectId1, 'name': obj1.get('name', 'N/A')},
                'object2': {'id': objectId2, 'name': obj2.get('name', 'N/A')}
            }
        except Exception as e:
            return {'success': False, 'error': get_error_message('operation_failed', 'compare_objects', error=str(e))}
    
    def compareDomains(self, domainId1: str, domainId2: str, objectType: str = None) -> Dict:
        """
        Compare two domains and find differences in objects.
        
        Args:
            domainId1: First domain ID
            domainId2: Second domain ID
            objectType: Optional - compare only this object type (e.g., 'asset')
        
        Returns:
            Dict with comparison results:
            {
                'success': bool,
                'domain1': {'id': str, 'name': str, 'counts': dict},
                'domain2': {'id': str, 'name': str, 'counts': dict},
                'differences': {
                    'objectType': {
                        'only_in_domain1': [list],
                        'only_in_domain2': [list],
                        'common': [list]
                    }
                },
                'summary': str
            }
        """
        if not self._ensureAuthenticated():
            return {
                'success': False,
                'error': get_error_message('connection', 'isms_client_not_available')
            }
        
        try:
            domain1 = self.getDomain(domainId1)
            domain2 = self.getDomain(domainId2)
            
            if not domain1.get('success'):
                return {'success': False, 'error': get_error_message('operation_failed', 'get_domain', error=domain1.get("error"))}
            if not domain2.get('success'):
                return {'success': False, 'error': get_error_message('operation_failed', 'get_domain', error=domain2.get("error"))}
            
            domain1_info = domain1.get('domain', {})
            domain2_info = domain2.get('domain', {})
            
            # Object types to compare
            object_types = [objectType] if objectType else ['asset', 'control', 'process', 'scope']
            
            differences = {}
            domain1_counts = {}
            domain2_counts = {}
            
            for obj_type in object_types:
                # List objects in each domain
                list1 = self.listObjects(obj_type, domainId1)
                list2 = self.listObjects(obj_type, domainId2)
                
                if not list1.get('success') or not list2.get('success'):
                    continue
                
                # FIX: Safe access to items lists
                objects1 = list1.get('objects', {})
                objects2 = list2.get('objects', {})
                items1 = objects1.get('items', []) if isinstance(objects1, dict) else []
                items2 = objects2.get('items', []) if isinstance(objects2, dict) else []
                
                # Ensure items are lists before iterating
                if not isinstance(items1, list):
                    items1 = []
                if not isinstance(items2, list):
                    items2 = []
                
                ids1 = {item.get('id') or item.get('resourceId'): item.get('name', 'N/A') for item in items1 if isinstance(item, dict)}
                ids2 = {item.get('id') or item.get('resourceId'): item.get('name', 'N/A') for item in items2 if isinstance(item, dict)}
                
                domain1_counts[obj_type] = len(ids1)
                domain2_counts[obj_type] = len(ids2)
                
                # Find differences
                only_in_1 = {id: name for id, name in ids1.items() if id not in ids2}
                only_in_2 = {id: name for id, name in ids2.items() if id not in ids1}
                common = {id: name for id, name in ids1.items() if id in ids2}
                
                differences[obj_type] = {
                    'only_in_domain1': [{'id': id, 'name': name} for id, name in only_in_1.items()],
                    'only_in_domain2': [{'id': id, 'name': name} for id, name in only_in_2.items()],
                    'common': [{'id': id, 'name': name} for id, name in common.items()]
                }
            
            summary = f"Domain comparison: {domain1_info.get('name', domainId1)} vs {domain2_info.get('name', domainId2)}"
            
            return {
                'success': True,
                'domain1': {
                    'id': domainId1,
                    'name': domain1_info.get('name', 'N/A'),
                    'counts': domain1_counts
                },
                'domain2': {
                    'id': domainId2,
                    'name': domain2_info.get('name', 'N/A'),
                    'counts': domain2_counts
                },
                'differences': differences,
                'summary': summary
            }
        except Exception as e:
            return {'success': False, 'error': get_error_message('operation_failed', 'compare_domains', error=str(e))}
    
    def findDifferences(self, objectType: str, domainId: str, filters: Dict = None) -> Dict:
        """
        Find objects with specific differences or anomalies.
        
        Args:
            objectType: Type of objects to analyze
            domainId: Domain ID
            filters: Optional filters (e.g., {'missing_description': True, 'missing_abbreviation': True})
        
        Returns:
            Dict with objects that have differences/anomalies
        """
        if not self._ensureAuthenticated():
            return {
                'success': False,
                'error': get_error_message('connection', 'isms_client_not_available')
            }
        
        try:
            # List all objects
            list_result = self.listObjects(objectType, domainId, filters)
            if not list_result.get('success'):
                return list_result
            
            # FIX: Safe access to items list
            objects_dict = list_result.get('objects', {})
            items = objects_dict.get('items', []) if isinstance(objects_dict, dict) else []
            if not isinstance(items, list):
                items = []
            
            anomalies = []
            
            # FIX: Safe access to filters dict
            check_missing_description = filters.get('missing_description', False) if isinstance(filters, dict) else True
            check_missing_abbreviation = filters.get('missing_abbreviation', False) if isinstance(filters, dict) else True
            
            for item in items:
                # FIX: Ensure item is a dict before accessing
                if not isinstance(item, dict):
                    continue
                
                issues = []
                
                if check_missing_description and not item.get('description'):
                    issues.append('missing_description')
                
                if check_missing_abbreviation and not item.get('abbreviation'):
                    issues.append('missing_abbreviation')
                
                if issues:
                    anomalies.append({
                        'id': item.get('id') or item.get('resourceId'),
                        'name': item.get('name', 'N/A'),
                        'issues': issues
                    })
            
            return {
                'success': True,
                'objectType': objectType,
                'total': len(items),
                'anomalies': anomalies,
                'count': len(anomalies)
            }
        except Exception as e:
            return {'success': False, 'error': get_error_message('operation_failed', 'find_differences', error=str(e))}
