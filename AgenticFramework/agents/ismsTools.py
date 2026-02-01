"""
ISMS Tools Wrapper - Standardizes VeriniceTool methods for ISMSAgent

Phase 5: Progressive Agentic Architecture

This module provides wrapper functions that standardize VeriniceTool methods
for use by ISMSAgent. All tools return consistent format:
{
    'success': bool,
    'message'|'text': str,
    'data': dict (optional)
}
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def create_isms_tools(verinice_tool):
    """
    Create and register all ISMS tools for ISMSAgent.
    
    Args:
        verinice_tool: VeriniceTool instance
    
    Returns:
        Dict of tool_name -> tool_dict for registration
    """
    tools = {}
    
    # ==================== CRUD OPERATIONS ====================
    
    def list_objects(objectType: str, domainId: str = None, unitId: str = None) -> Dict:
        """List ISMS objects (scopes, assets, controls, etc.)"""
        result = verinice_tool.listObjects(objectType, domainId, unitId=unitId)
        if result.get('success'):
            objects = result.get('objects', {}).get('items', [])
            count = len(objects)
            return {
                'success': True,
                'message': f"Found {count} {objectType}(s)",
                'data': result
            }
        return {
            'success': False,
            'message': result.get('error', 'Failed to list objects')
        }
    
    def get_object(objectType: str, domainId: str, objectId: str) -> Dict:
        """Get a specific ISMS object by ID"""
        result = verinice_tool.getObject(objectType, domainId, objectId)
        if result.get('success'):
            obj = result.get('object', {})
            return {
                'success': True,
                'message': f"Retrieved {objectType}: {obj.get('name', 'N/A')}",
                'data': result
            }
        return {
            'success': False,
            'message': result.get('error', 'Failed to get object')
        }
    
    def create_object(objectType: str, domainId: str, unitId: str, name: str,
                     subType: str = None, description: str = "", abbreviation: str = None) -> Dict:
        """Create a new ISMS object"""
        result = verinice_tool.createObject(
            objectType, domainId, unitId, name,
            subType=subType, description=description, abbreviation=abbreviation
        )
        if result.get('success'):
            return {
                'success': True,
                'message': f"Created {objectType}: {name}",
                'data': result
            }
        return {
            'success': False,
            'message': result.get('error', 'Failed to create object')
        }
    
    def update_object(objectType: str, domainId: str, objectId: str, **kwargs) -> Dict:
        """Update an ISMS object"""
        result = verinice_tool.updateObject(objectType, domainId, objectId, **kwargs)
        if result.get('success'):
            return {
                'success': True,
                'message': f"Updated {objectType}",
                'data': result
            }
        return {
            'success': False,
            'message': result.get('error', 'Failed to update object')
        }
    
    def delete_object(objectType: str, domainId: str, objectId: str) -> Dict:
        """Delete an ISMS object"""
        result = verinice_tool.deleteObject(objectType, domainId, objectId)
        if result.get('success'):
            return {
                'success': True,
                'message': f"Deleted {objectType}",
                'data': result
            }
        return {
            'success': False,
            'message': result.get('error', 'Failed to delete object')
        }
    
    # ==================== DOMAIN & UNIT OPERATIONS ====================
    
    def list_domains() -> Dict:
        """List all domains"""
        result = verinice_tool.listDomains()
        if result.get('success'):
            domains = result.get('domains', [])
            return {
                'success': True,
                'message': f"Found {len(domains)} domain(s)",
                'data': result
            }
        return {
            'success': False,
            'message': result.get('error', 'Failed to list domains')
        }
    
    def list_units() -> Dict:
        """List all units"""
        result = verinice_tool.listUnits()
        if result.get('success'):
            units = result.get('units', [])
            return {
                'success': True,
                'message': f"Found {len(units)} unit(s)",
                'data': result
            }
        return {
            'success': False,
            'message': result.get('error', 'Failed to list units')
        }
    
    def get_domain(domainId: str) -> Dict:
        """Get domain details"""
        result = verinice_tool.getDomain(domainId)
        if result.get('success'):
            return {
                'success': True,
                'message': f"Retrieved domain: {result.get('domain', {}).get('name', 'N/A')}",
                'data': result
            }
        return {
            'success': False,
            'message': result.get('error', 'Failed to get domain')
        }
    
    def get_unit(unitId: str) -> Dict:
        """Get unit details"""
        result = verinice_tool.getUnit(unitId)
        if result.get('success'):
            return {
                'success': True,
                'message': f"Retrieved unit: {result.get('unit', {}).get('name', 'N/A')}",
                'data': result
            }
        return {
            'success': False,
            'message': result.get('error', 'Failed to get unit')
        }
    
    # ==================== REPORT OPERATIONS ====================
    
    def list_reports(domainId: str = None) -> Dict:
        """List available reports"""
        result = verinice_tool.listReports(domainId)
        if result.get('success'):
            reports = result.get('reports', [])
            return {
                'success': True,
                'message': f"Found {len(reports)} report(s)",
                'data': result
            }
        return {
            'success': False,
            'message': result.get('error', 'Failed to list reports')
        }
    
    def generate_report(reportId: str, domainId: str = None, params: Dict = None) -> Dict:
        """Generate a report"""
        result = verinice_tool.generateReport(reportId, domainId, params)
        if result.get('success'):
            return {
                'success': True,
                'message': f"Generated report: {reportId}",
                'data': result
            }
        return {
            'success': False,
            'message': result.get('error', 'Failed to generate report')
        }
    
    def get_valid_subtypes(domainId: str, objectType: str) -> Dict:
        """Get valid subtypes for an object type"""
        result = verinice_tool.getValidSubTypes(domainId, objectType)
        if result.get('success'):
            subtypes = result.get('subTypes', [])
            return {
                'success': True,
                'message': f"Found {len(subtypes)} subtype(s) for {objectType}",
                'data': result
            }
        return {
            'success': False,
            'message': result.get('error', 'Failed to get subtypes')
        }
    
    # ==================== RECONCILIATION OPERATIONS ====================
    
    def compare_objects(objectType: str, objectId1: str, objectId2: str, domainId: str) -> Dict:
        """Compare two ISMS objects"""
        result = verinice_tool.compareObjects(objectType, objectId1, objectId2, domainId)
        if result.get('success'):
            diff_count = len(result.get('differences', []))
            return {
                'success': True,
                'message': f"Comparison complete: {diff_count} difference(s) found",
                'data': result
            }
        return {
            'success': False,
            'message': result.get('error', 'Failed to compare objects')
        }
    
    def compare_domains(domainId1: str, domainId2: str, objectType: str = None) -> Dict:
        """Compare two domains"""
        result = verinice_tool.compareDomains(domainId1, domainId2, objectType)
        if result.get('success'):
            return {
                'success': True,
                'message': "Domain comparison complete",
                'data': result
            }
        return {
            'success': False,
            'message': result.get('error', 'Failed to compare domains')
        }
    
    def find_differences(objectType: str, domainId: str, filters: Dict = None) -> Dict:
        """Find objects with differences or anomalies"""
        result = verinice_tool.findDifferences(objectType, domainId, filters)
        if result.get('success'):
            anomaly_count = result.get('count', 0)
            return {
                'success': True,
                'message': f"Found {anomaly_count} object(s) with issues",
                'data': result
            }
        return {
            'success': False,
            'message': result.get('error', 'Failed to find differences')
        }
    
    # Register all tools
    tools = {
        'list_objects': {
            'func': list_objects,
            'description': 'List ISMS objects (scopes, assets, controls, processes, persons, scenarios, incidents, documents). Args: objectType (str), domainId (str, optional), unitId (str, optional)',
            'parameters': {
                'type': 'object',
                'properties': {
                    'objectType': {'type': 'string', 'description': 'Object type (scope, asset, control, etc.)'},
                    'domainId': {'type': 'string', 'description': 'Domain ID (optional)'},
                    'unitId': {'type': 'string', 'description': 'Unit ID (optional, for scopes)'}
                },
                'required': ['objectType']
            }
        },
        'get_object': {
            'func': get_object,
            'description': 'Get a specific ISMS object by ID. Args: objectType, domainId, objectId',
            'parameters': {
                'type': 'object',
                'properties': {
                    'objectType': {'type': 'string'},
                    'domainId': {'type': 'string'},
                    'objectId': {'type': 'string'}
                },
                'required': ['objectType', 'domainId', 'objectId']
            }
        },
        'create_object': {
            'func': create_object,
            'description': 'Create a new ISMS object. Args: objectType, domainId, unitId, name, subType (optional), description (optional), abbreviation (optional)',
            'parameters': {
                'type': 'object',
                'properties': {
                    'objectType': {'type': 'string'},
                    'domainId': {'type': 'string'},
                    'unitId': {'type': 'string'},
                    'name': {'type': 'string'},
                    'subType': {'type': 'string'},
                    'description': {'type': 'string'},
                    'abbreviation': {'type': 'string'}
                },
                'required': ['objectType', 'domainId', 'unitId', 'name']
            }
        },
        'update_object': {
            'func': update_object,
            'description': 'Update an ISMS object. Can update fields like name, description, subType, abbreviation. For person objects, can also update the "role" field. Args: objectType, domainId, objectId, and fields to update (e.g., name, description, role, subType, etc.)',
            'parameters': {
                'type': 'object',
                'properties': {
                    'objectType': {'type': 'string', 'description': 'Type of the object to update (e.g., "person", "asset", "scope")'},
                    'domainId': {'type': 'string', 'description': 'The ID of the domain the object belongs to'},
                    'objectId': {'type': 'string', 'description': 'The ID of the object to update'},
                    'name': {'type': 'string', 'description': 'New name for the object (optional)'},
                    'description': {'type': 'string', 'description': 'New description for the object (optional)'},
                    'subType': {'type': 'string', 'description': 'New subType for the object (optional)'},
                    'abbreviation': {'type': 'string', 'description': 'New abbreviation for the object (optional)'},
                    'role': {'type': 'string', 'description': 'New role for a person object (e.g., "DPO", "CISO") (optional)'}
                },
                'required': ['objectType', 'domainId', 'objectId']
            }
        },
        'delete_object': {
            'func': delete_object,
            'description': 'Delete an ISMS object. Args: objectType, domainId, objectId',
            'parameters': {
                'type': 'object',
                'properties': {
                    'objectType': {'type': 'string'},
                    'domainId': {'type': 'string'},
                    'objectId': {'type': 'string'}
                },
                'required': ['objectType', 'domainId', 'objectId']
            }
        },
        'list_domains': {
            'func': list_domains,
            'description': 'List all domains',
            'parameters': {'type': 'object', 'properties': {}}
        },
        'list_units': {
            'func': list_units,
            'description': 'List all units',
            'parameters': {'type': 'object', 'properties': {}}
        },
        'get_domain': {
            'func': get_domain,
            'description': 'Get domain details. Args: domainId',
            'parameters': {
                'type': 'object',
                'properties': {
                    'domainId': {'type': 'string'}
                },
                'required': ['domainId']
            }
        },
        'get_unit': {
            'func': get_unit,
            'description': 'Get unit details. Args: unitId',
            'parameters': {
                'type': 'object',
                'properties': {
                    'unitId': {'type': 'string'}
                },
                'required': ['unitId']
            }
        },
        'list_reports': {
            'func': list_reports,
            'description': 'List available reports. Args: domainId (optional)',
            'parameters': {
                'type': 'object',
                'properties': {
                    'domainId': {'type': 'string'}
                }
            }
        },
        'generate_report': {
            'func': generate_report,
            'description': 'Generate a report. Args: reportId, domainId (optional), params (optional)',
            'parameters': {
                'type': 'object',
                'properties': {
                    'reportId': {'type': 'string'},
                    'domainId': {'type': 'string'},
                    'params': {'type': 'object'}
                },
                'required': ['reportId']
            }
        },
        'get_valid_subtypes': {
            'func': get_valid_subtypes,
            'description': 'Get valid subtypes for an object type. Args: domainId, objectType',
            'parameters': {
                'type': 'object',
                'properties': {
                    'domainId': {'type': 'string'},
                    'objectType': {'type': 'string'}
                },
                'required': ['domainId', 'objectType']
            }
        },
        'compare_objects': {
            'func': compare_objects,
            'description': 'Compare two ISMS objects and find differences. Args: objectType, objectId1, objectId2, domainId',
            'parameters': {
                'type': 'object',
                'properties': {
                    'objectType': {'type': 'string'},
                    'objectId1': {'type': 'string'},
                    'objectId2': {'type': 'string'},
                    'domainId': {'type': 'string'}
                },
                'required': ['objectType', 'objectId1', 'objectId2', 'domainId']
            }
        },
        'compare_domains': {
            'func': compare_domains,
            'description': 'Compare two domains and find differences. Args: domainId1, domainId2, objectType (optional)',
            'parameters': {
                'type': 'object',
                'properties': {
                    'domainId1': {'type': 'string'},
                    'domainId2': {'type': 'string'},
                    'objectType': {'type': 'string'}
                },
                'required': ['domainId1', 'domainId2']
            }
        },
        'find_differences': {
            'func': find_differences,
            'description': 'Find objects with differences or anomalies. Args: objectType, domainId, filters (optional)',
            'parameters': {
                'type': 'object',
                'properties': {
                    'objectType': {'type': 'string'},
                    'domainId': {'type': 'string'},
                    'filters': {'type': 'object'}
                },
                'required': ['objectType', 'domainId']
            }
        }
    }
    
    return tools


def register_isms_tools(agent, verinice_tool):
    """
    Register all ISMS tools with an ISMSAgent.
    
    Args:
        agent: ISMSAgent instance
        verinice_tool: VeriniceTool instance
    """
    tools = create_isms_tools(verinice_tool)
    
    for tool_name, tool_info in tools.items():
        agent.register_tool(
            name=tool_name,
            func=tool_info['func'],
            description=tool_info['description'],
            parameters=tool_info['parameters']
        )
    
    logger.info(f"Registered {len(tools)} ISMS tools with agent")
