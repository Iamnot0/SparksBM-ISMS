"""
MCP Analyze Tool - Analyzes ISMS objects and their relationships

Provides comprehensive analysis of ISMS objects including:
- Object details and properties
- Relationships and dependencies
- Compliance status
- Risk associations
"""

from typing import Dict, Optional
import logging
from agents.instructions import get_error_message

logger = logging.getLogger(__name__)


def analyze_object(
    object_name: str,
    object_type: Optional[str] = None,
    verinice_tool=None,
    llm_tool=None,
    state: Dict = None
) -> Dict:
    """
    Analyze an ISMS object comprehensively.
    
    Args:
        object_name: Name of the object to analyze (e.g., "SCOPE1")
        object_type: Optional object type (scope, asset, control, etc.)
        verinice_tool: VeriniceTool instance
        llm_tool: LLMTool instance for generating analysis
        state: Agent state dictionary
    
    Returns:
        Dict with analysis results:
        {
            'success': bool,
            'text': str,  # Natural language analysis
            'data': dict  # Structured analysis data
        }
    """
    if not verinice_tool:
        return {
            'success': False,
            'text': get_error_message('connection', 'verinice_tool_not_available'),
            'data': {}
        }
    
    try:
        # Step 1: Resolve object name to ID and type
        domain_id, unit_id = _get_defaults(verinice_tool, state)
        
        # Try to find the object
        object_id, detected_type = _resolve_object_id(
            object_name, 
            object_type, 
            verinice_tool, 
            domain_id, 
            unit_id
        )
        
        if not object_id:
            return {
                'success': False,
                'text': get_error_message('not_found', 'object_not_found_analyze', objectType=object_type or 'object', objectName=object_name),
                'data': {}
            }
        
        # Step 2: Get object details
        # Note: getObject signature is (objectType, domainId, objectId)
        result = verinice_tool.getObject(detected_type, domain_id, object_id)
        
        if not result.get('success'):
            return {
                'success': False,
                'text': get_error_message('mcp', 'retrieve_object_failed', objectType=detected_type, objectName=object_name, error=result.get('error', 'Unknown error')),
                'data': {}
            }
        
        object_data = result.get('data') or result.get('object', {})
        
        # Step 3: Get relationships (what's linked to this object)
        relationships = _get_relationships(object_id, detected_type, verinice_tool, domain_id)
        
        # Step 4: Build comprehensive analysis
        analysis_data = {
            'object': object_data,
            'type': detected_type,
            'relationships': relationships,
            'summary': _build_summary(object_data, detected_type, relationships)
        }
        
        # Step 5: Generate natural language analysis using LLM if available
        if llm_tool:
            analysis_text = _generate_analysis_text(
                object_data, 
                detected_type, 
                relationships, 
                llm_tool
            )
        else:
            # Fallback to structured analysis
            analysis_text = _format_structured_analysis(analysis_data)
        
        return {
            'success': True,
            'text': analysis_text,
            'data': analysis_data
        }
        
    except Exception as e:
        logger.error(f"Error analyzing object: {e}", exc_info=True)
        return {
            'success': False,
            'text': f"Error analyzing object: {str(e)}",
            'data': {}
        }


# ==================== HELPER FUNCTIONS ====================

def _get_defaults(verinice_tool, state: Dict = None) -> tuple:
    """Get default domain and unit IDs"""
    try:
        if state and state.get('defaultDomainId'):
            domain_id = state.get('defaultDomainId')
        else:
            domains_result = verinice_tool.listDomains()
            if domains_result.get('success') and domains_result.get('domains'):
                domain_id = domains_result['domains'][0].get('id')
            else:
                domain_id = None
        
        if state and state.get('defaultUnitId'):
            unit_id = state.get('defaultUnitId')
        else:
            units_result = verinice_tool.listUnits()
            if units_result.get('success') and units_result.get('units'):
                unit_id = units_result['units'][0].get('id')
            else:
                unit_id = None
        
        return domain_id, unit_id
    except Exception:
        return None, None


def _resolve_object_id(
    object_name: str,
    object_type: Optional[str],
    verinice_tool,
    domain_id: Optional[str],
    unit_id: Optional[str]
) -> tuple:
    """
    Resolve object name to ID and type.
    
    Returns:
        Tuple of (object_id, object_type) or (None, None)
    """
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


def _get_relationships(
    object_id: str,
    object_type: str,
    verinice_tool,
    domain_id: Optional[str]
) -> Dict:
    """Get relationships for an object"""
    relationships = {
        'linked_objects': [],
        'linked_scopes': [],
        'linked_assets': [],
        'linked_controls': []
    }
    
    # For scopes, get linked assets/controls
    if object_type == 'scope':
        assets_result = verinice_tool.listObjects('asset', domain_id)
        if assets_result.get('success'):
            objects = assets_result.get('objects', {})
            items = objects.get('items', []) if isinstance(objects, dict) else (objects if isinstance(objects, list) else [])
            for asset in items:
                parts = asset.get('parts', [])
                members = asset.get('members', [])
                scope_refs = parts + members
                for ref in scope_refs:
                    if isinstance(ref, dict) and (ref.get('id') == object_id or ref.get('resourceId') == object_id):
                        relationships['linked_assets'].append({
                            'name': asset.get('name'),
                            'id': asset.get('id') or asset.get('resourceId'),
                            'subType': asset.get('subType')
                        })
    
    return relationships


def _build_summary(object_data: Dict, object_type: str, relationships: Dict) -> Dict:
    """Build summary of object analysis"""
    return {
        'name': object_data.get('name', 'N/A'),
        'type': object_type,
        'subType': object_data.get('subType', 'N/A'),
        'status': object_data.get('status', 'N/A'),
        'description': object_data.get('description', ''),
        'linked_count': len(relationships.get('linked_assets', [])) + len(relationships.get('linked_controls', [])),
        'has_relationships': len(relationships.get('linked_assets', [])) > 0 or len(relationships.get('linked_controls', [])) > 0
    }


def _generate_analysis_text(
    object_data: Dict,
    object_type: str,
    relationships: Dict,
    llm_tool
) -> str:
    """Generate natural language analysis using LLM"""
    try:
        summary = _build_summary(object_data, object_type, relationships)
        
        prompt = f"""You are an ISMS compliance expert. Analyze this ISMS object and provide a comprehensive, natural analysis.

TASK: Analyze the following ISMS object and provide a professional, insightful analysis suitable for a data protection officer or compliance manager.

Object Details:
- Name: {summary['name']}
- Type: {summary['type']}
- SubType: {summary['subType']}
- Status: {summary['status']}
- Description: {summary['description'] or 'No description provided'}

Relationships:
- Linked Assets: {len(relationships.get('linked_assets', []))}
- Linked Controls: {len(relationships.get('linked_controls', []))}

ANALYSIS REQUIREMENTS:
1. Summarize what this object is and its purpose in the ISMS
2. Explain its current status and key properties
3. Describe its relationships and dependencies with other ISMS objects
4. Provide insights about compliance implications (ISO 27001, GDPR, etc.)
5. Be concise (3-4 paragraphs max)
6. Use professional but accessible language

EXAMPLES OF GOOD ANALYSIS:

Example 1 (Scope):
"SCOPE1 is a critical scope within the ISMS framework, currently in 'Active' status. This scope encompasses the organization's primary IT infrastructure and serves as the foundation for risk assessment and control implementation. It is linked to 15 assets and 8 controls, indicating a well-integrated security posture. From a compliance perspective, this scope aligns with ISO 27001 requirements for scope definition and demonstrates proper asset-control mapping, which is essential for effective risk management."

Example 2 (Asset):
"The Desktop asset is an IT-System type asset currently operational. This asset represents a critical endpoint in the organization's infrastructure and is linked to SCOPE1, indicating it's within the primary security boundary. With 3 linked controls, this asset has appropriate security measures in place. Compliance-wise, this asset should be regularly assessed for vulnerabilities and maintained according to the organization's asset management policy to meet ISO 27001 A.8.1.1 requirements."

BAD EXAMPLES (what NOT to do):
- ❌ WRONG: "This is a scope. It has some assets. It's important for security." (Too generic, no specifics, no compliance context)
- ❌ WRONG: "SCOPE1 exists in the system. You can link assets to it." (Not an analysis, just instructions)
- ❌ WRONG: "I cannot analyze this object because I don't have enough information." (Should use available data, even if limited)
- ✅ CORRECT: Provide specific details about status, relationships, compliance implications, and actionable insights

Now analyze the provided object:"""

        response = llm_tool.generate(
            prompt=prompt,
            systemPrompt="You are an expert ISMS compliance analyst. Provide clear, professional analysis.",
            maxTokens=500
        )
        
        if response:
            return response.strip()
    except Exception as e:
        logger.warning(f"LLM analysis generation failed: {e}")
    
    # Fallback to structured format
    return _format_structured_analysis({
        'object': object_data,
        'type': object_type,
        'relationships': relationships,
        'summary': summary
    })


def _format_structured_analysis(analysis_data: Dict) -> str:
    """Format analysis as structured text (fallback)"""
    summary = analysis_data.get('summary', {})
    relationships = analysis_data.get('relationships', {})
    
    text = f"**Analysis of {summary.get('name', 'Object')}**\n\n"
    text += f"**Type:** {summary.get('type', 'N/A')}\n"
    text += f"**SubType:** {summary.get('subType', 'N/A')}\n"
    text += f"**Status:** {summary.get('status', 'N/A')}\n\n"
    
    if summary.get('description'):
        text += f"**Description:** {summary['description']}\n\n"
    
    text += f"**Relationships:**\n"
    text += f"- Linked Assets: {len(relationships.get('linked_assets', []))}\n"
    text += f"- Linked Controls: {len(relationships.get('linked_controls', []))}\n"
    
    if relationships.get('linked_assets'):
        text += "\n**Linked Assets:**\n"
        for asset in relationships['linked_assets'][:5]:  # Limit to 5
            text += f"- {asset.get('name')} ({asset.get('subType')})\n"
    
    return text
