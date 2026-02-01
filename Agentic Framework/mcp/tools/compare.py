"""
MCP Comparison Tool - Compares ISMS objects

Compares two ISMS objects and identifies differences:
- Object properties
- Relationships
- Compliance status
- Risk associations
"""

from typing import Dict, Optional
import logging
from agents.instructions import get_error_message

logger = logging.getLogger(__name__)


def compare_objects(
    object1_name: str,
    object2_name: str,
    object1_type: Optional[str] = None,
    object2_type: Optional[str] = None,
    verinice_tool=None,
    llm_tool=None,
    state: Dict = None
) -> Dict:
    """
    Compare two ISMS objects.
    
    Args:
        object1_name: Name of first object
        object2_name: Name of second object
        object1_type: Optional type of first object
        object2_type: Optional type of second object
        verinice_tool: VeriniceTool instance
        llm_tool: LLMTool instance for generating comparison text
        state: Agent state dictionary
    
    Returns:
        Dict with comparison results:
        {
            'success': bool,
            'text': str,  # Natural language comparison
            'data': dict  # Structured comparison data
        }
    """
    if not verinice_tool:
        return {
            'success': False,
            'text': get_error_message('connection', 'verinice_tool_not_available'),
            'data': {}
        }
    
    try:
        # Step 1: Resolve both objects
        domain_id, unit_id = _get_defaults(verinice_tool, state)
        
        obj1_id, obj1_type = _resolve_object_id(
            object1_name, object1_type, verinice_tool, domain_id, unit_id
        )
        obj2_id, obj2_type = _resolve_object_id(
            object2_name, object2_type, verinice_tool, domain_id, unit_id
        )
        
        if not obj1_id:
            return {
                'success': False,
                'text': get_error_message('not_found', 'object_not_found_compare', objectName=object1_name),
                'data': {}
            }
        
        if not obj2_id:
            return {
                'success': False,
                'text': get_error_message('not_found', 'object_not_found_compare', objectName=object2_name),
                'data': {}
            }
        
        # Both objects must be same type for comparison
        if obj1_type != obj2_type:
            return {
                'success': False,
                'text': get_error_message('not_found', 'cannot_compare_different_types', type1=obj1_type, type2=obj2_type),
                'data': {}
            }
        
        # Step 2: Get both objects
        obj1_result = verinice_tool.getObject(obj1_type, domain_id, obj1_id)
        obj2_result = verinice_tool.getObject(obj2_type, domain_id, obj2_id)
        
        if not obj1_result.get('success'):
            return {
                'success': False,
                'text': get_error_message('mcp', 'retrieve_object_failed', objectType=obj1_type, objectName=object1_name, error=obj1_result.get('error', 'Unknown error')),
                'data': {}
            }
        
        if not obj2_result.get('success'):
            return {
                'success': False,
                'text': get_error_message('mcp', 'retrieve_object_failed', objectType=obj2_type, objectName=object2_name, error=obj2_result.get('error', 'Unknown error')),
                'data': {}
            }
        
        obj1_data = obj1_result.get('data') or obj1_result.get('object', {})
        obj2_data = obj2_result.get('data') or obj2_result.get('object', {})
        
        # Step 3: Use VeriniceTool's compareObjects if available
        compare_result = verinice_tool.compareObjects(obj1_type, obj1_id, obj2_id, domain_id)
        
        # Step 4: Generate natural language comparison
        if llm_tool:
            comparison_text = _generate_comparison_text(
                obj1_data, obj2_data, obj1_type, compare_result, llm_tool
            )
        else:
            comparison_text = _format_structured_comparison(obj1_data, obj2_data, obj1_type, compare_result)
        
        return {
            'success': True,
            'text': comparison_text,
            'data': {
                'object1': obj1_data,
                'object2': obj2_data,
                'type': obj1_type,
                'comparison': compare_result
            }
        }
        
    except Exception as e:
        logger.error(f"Error comparing objects: {e}", exc_info=True)
        return {
            'success': False,
            'text': f"Error comparing objects: {str(e)}",
            'data': {}
        }


# ==================== HELPER FUNCTIONS ====================

def _get_defaults(verinice_tool, state: Dict = None) -> tuple:
    """Get default domain and unit IDs"""
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
    return None, None


def _resolve_object_id(
    object_name: str,
    object_type: Optional[str],
    verinice_tool,
    domain_id: Optional[str],
    unit_id: Optional[str]
) -> tuple:
    """Resolve object name to ID and type"""
    # If type is provided, search in that type
    if object_type:
        result = verinice_tool.listObjects(object_type, domain_id, unitId=unit_id)
        if result.get('success'):
            objects = result.get('objects', {})
            items = objects.get('items', []) if isinstance(objects, dict) else (objects if isinstance(objects, list) else [])
            for obj in items:
                if obj.get('name', '').upper() == object_name.upper():
                    return obj.get('id') or obj.get('resourceId'), object_type
    
    # Try common object types
    common_types = ['scope', 'asset', 'control', 'process', 'person', 'document', 'scenario']
    
    for obj_type in common_types:
        result = verinice_tool.listObjects(obj_type, domain_id, unitId=unit_id)
        if result.get('success'):
            objects = result.get('objects', {})
            items = objects.get('items', []) if isinstance(objects, dict) else (objects if isinstance(objects, list) else [])
            for obj in items:
                if obj.get('name', '') and obj.get('name', '').upper() == object_name.upper():
                    return obj.get('id') or obj.get('resourceId'), obj_type
    
    return None, None


def _generate_comparison_text(
    obj1_data: Dict,
    obj2_data: Dict,
    object_type: str,
    compare_result: Dict,
    llm_tool
) -> str:
    """Generate natural language comparison using LLM"""
    try:
        differences = compare_result.get('differences', [])
        diff_count = len(differences)
        
        prompt = f"""Compare these two {object_type} objects from an ISMS:

Object 1: {obj1_data.get('name', 'Unknown')}
- Description: {obj1_data.get('description', 'N/A')}
- Abbreviation: {obj1_data.get('abbreviation', 'N/A')}
- Properties: {str(obj1_data)[:500]}

Object 2: {obj2_data.get('name', 'Unknown')}
- Description: {obj2_data.get('description', 'N/A')}
- Abbreviation: {obj2_data.get('abbreviation', 'N/A')}
- Properties: {str(obj2_data)[:500]}

Differences found: {diff_count}
{differences[:5] if differences else 'No differences detected'}

Provide a clear, professional comparison highlighting:
1. Key similarities
2. Key differences
3. Compliance implications
4. Recommendations (if any)

Be concise (3-4 paragraphs max)."""

        response = llm_tool.generate(
            prompt=prompt,
            systemPrompt="You are an expert ISMS compliance analyst. Provide clear, professional comparisons.",
            maxTokens=600
        )
        
        if response:
            return response.strip()
    except Exception as e:
        logger.warning(f"LLM comparison generation failed: {e}")
    
    return _format_structured_comparison(obj1_data, obj2_data, object_type, compare_result)


def _format_structured_comparison(
    obj1_data: Dict,
    obj2_data: Dict,
    object_type: str,
    compare_result: Dict
) -> str:
    """Format structured comparison as text"""
    obj1_name = obj1_data.get('name', 'Unknown')
    obj2_name = obj2_data.get('name', 'Unknown')
    differences = compare_result.get('differences', [])
    
    text = f"Comparison: {obj1_name} vs {obj2_name}\n\n"
    text += f"Type: {object_type}\n"
    text += f"Differences found: {len(differences)}\n\n"
    
    if differences:
        text += "Key Differences:\n"
        for diff in differences[:10]:  # Limit to first 10
            text += f"- {diff}\n"
    else:
        text += "No significant differences found.\n"
    
    return text
