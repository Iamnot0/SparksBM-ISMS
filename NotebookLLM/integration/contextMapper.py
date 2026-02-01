"""Context mapper - converts ISMS objects to agent-readable context"""
from typing import List, Dict, Any, Optional
import sys
import os

_currentDir = os.path.dirname(os.path.abspath(__file__))
_scriptsPath = os.path.join(_currentDir, '..', '..', 'SparksbmISMS', 'scripts')
if os.path.exists(_scriptsPath) and _scriptsPath not in sys.path:
    sys.path.insert(0, _scriptsPath)

try:
    from sparksbmMgmt import SparksBMClient, API_URL
    ISMS_AVAILABLE = True
except ImportError:
    ISMS_AVAILABLE = False
    SparksBMClient = None
    API_URL = "http://localhost:8070"


class ContextMapper:
    """Maps ISMS objects to agent context"""
    
    def __init__(self):
        self.client = None
        if ISMS_AVAILABLE:
            try:
                self.client = SparksBMClient()
            except Exception:
                pass
    
    def buildContext(self, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Build context from ISMS object sources
        
        Returns:
            Dict with context string and metadata
        """
        if not sources:
            return {
                'context': "",
                'activeSources': []
            }
        
        contextParts = []
        
        for source in sources:
            sourceId = source.get('id')
            sourceType = source.get('type')
            domainId = source.get('domainId')
            
            if not sourceId or not sourceType or not domainId:
                continue
            
            # Fetch object details
            objectData = self._fetchObject(sourceType, domainId, sourceId)
            if objectData:
                contextParts.append(self._formatObject(objectData, sourceType))
        
        contextStr = "\n\n".join(contextParts) if contextParts else ""
        
        return {
            'context': contextStr,
            'activeSources': sources
        }
    
    def _fetchObject(self, objectType: str, domainId: str, objectId: str) -> Optional[Dict]:
        """Fetch object from ISMS API"""
        if not self.client or not self.client.accessToken:
            return None
        
        try:
            objectTypeMap = {
                "scope": "scopes",
                "asset": "assets",
                "control": "controls",
                "process": "processes",
                "person": "persons",
                "scenario": "scenarios",
                "incident": "incidents",
                "document": "documents"
            }
            
            plural = objectTypeMap.get(objectType.lower())
            if not plural:
                return None
            
            url = f"{API_URL}/domains/{domainId}/{plural}/{objectId}"
            response = self.client.makeRequest('GET', url)
            response.raise_for_status()
            
            return response.json()
            
        except Exception:
            return None
    
    def _formatObject(self, objectData: Dict, objectType: str) -> str:
        """Format object data for agent context"""
        name = objectData.get('name', 'Unknown')
        objId = objectData.get('id', '')
        description = objectData.get('description', '')
        subType = objectData.get('subType', '')
        
        parts = [f"{objectType.capitalize()}: {name}"]
        
        if objId:
            parts.append(f"ID: {objId}")
        
        if subType:
            parts.append(f"SubType: {subType}")
        
        if description:
            parts.append(f"Description: {description[:200]}")
        
        for key in ['status', 'priority', 'riskLevel']:
            if key in objectData:
                parts.append(f"{key}: {objectData[key]}")
        
        return "\n".join(parts)
    
