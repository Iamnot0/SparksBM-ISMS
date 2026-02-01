"""Enhanced context manager - handles multiple documents, conversation flow, and relationships"""
from typing import Dict, List, Any, Optional
from datetime import datetime


class EnhancedContextManager:
    """Manages context for multiple documents, conversations, and relationships"""
    
    def __init__(self):
        self.documents: Dict[str, Dict[str, Any]] = {}  # docId -> document data
        self.conversation: List[Dict[str, Any]] = []  # Full conversation history
        self.relationships: Dict[str, List[str]] = {}  # docId -> [related docIds]
        self.metadata: Dict[str, Dict[str, Any]] = {}  # docId -> metadata
        self.maxConversationHistory = 50  # Keep last 50 messages
    
    def addDocument(self, docId: str, data: Dict[str, Any], fileName: str, 
                   docType: str, metadata: Optional[Dict] = None) -> bool:
        """
        Add a document to context
        
        Args:
            docId: Unique document identifier
            data: Document data
            fileName: Original file name
            docType: Document type
            metadata: Optional metadata (size, etc.)
            
        Returns:
            True if added successfully
        """
        self.documents[docId] = {
            'data': data,
            'fileName': fileName,
            'type': docType,
            'addedAt': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        
        # Store metadata separately for quick access
        self.metadata[docId] = {
            'fileName': fileName,
            'type': docType,
            'addedAt': datetime.now().isoformat(),
            'size': len(str(data))
        }
        
        return True
    
    def getDocument(self, docId: str) -> Optional[Dict[str, Any]]:
        """Get document by ID"""
        return self.documents.get(docId)
    
    def getAllDocuments(self) -> Dict[str, Dict[str, Any]]:
        """Get all documents"""
        return self.documents.copy()
    
    def getDocumentMetadata(self, docId: str) -> Optional[Dict[str, Any]]:
        """Get document metadata"""
        return self.metadata.get(docId)
    
    def listDocuments(self) -> List[Dict[str, Any]]:
        """List all documents with metadata"""
        return [
            {
                'id': docId,
                **self.metadata[docId]
            }
            for docId in self.metadata.keys()
        ]
    
    def findDocumentByName(self, fileName: str) -> Optional[str]:
        """Find document ID by file name"""
        for docId, meta in self.metadata.items():
            if meta['fileName'].lower() == fileName.lower():
                return docId
        return None
    
    def findDocumentsByType(self, docType: str) -> List[str]:
        """Find all document IDs of a specific type"""
        return [
            docId for docId, meta in self.metadata.items()
            if meta['type'] == docType
        ]
    
    def addToConversation(self, role: str, content: str, metadata: Optional[Dict] = None):
        """Add message to conversation history"""
        self.conversation.append({
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat(),
            'metadata': metadata or {}
        })
        
        # Keep conversation manageable
        if len(self.conversation) > self.maxConversationHistory:
            self.conversation = self.conversation[-self.maxConversationHistory:]
    
    def getConversationContext(self, limit: int = 10) -> str:
        """Get recent conversation context for LLM"""
        recent = self.conversation[-limit:] if len(self.conversation) > limit else self.conversation
        
        context = []
        for msg in recent:
            context.append(f"{msg['role'].upper()}: {msg['content']}")
        
        return "\n".join(context)
    
    def addRelationship(self, docId1: str, docId2: str, relationshipType: str = "related"):
        """Add relationship between two documents"""
        if docId1 not in self.relationships:
            self.relationships[docId1] = []
        
        if docId2 not in self.relationships:
            self.relationships[docId2] = []
        
        # Store bidirectional relationship
        if docId2 not in self.relationships[docId1]:
            self.relationships[docId1].append({
                'docId': docId2,
                'type': relationshipType,
                'createdAt': datetime.now().isoformat()
            })
        
        if docId1 not in self.relationships[docId2]:
            self.relationships[docId2].append({
                'docId': docId1,
                'type': relationshipType,
                'createdAt': datetime.now().isoformat()
            })
    
    def getRelatedDocuments(self, docId: str) -> List[str]:
        """Get related document IDs"""
        return [rel['docId'] for rel in self.relationships.get(docId, [])]
    
    def buildContextForLLM(self, query: str, includeDocuments: Optional[List[str]] = None) -> str:
        """
        Build comprehensive context string for LLM
        
        Args:
            query: Current user query
            includeDocuments: Specific document IDs to include (None = all)
            
        Returns:
            Formatted context string
        """
        contextParts = []
        
        convContext = self.getConversationContext(limit=5)
        if convContext:
            contextParts.append("=== Recent Conversation ===")
            contextParts.append(convContext)
            contextParts.append("")
        
        docIds = includeDocuments if includeDocuments else list(self.documents.keys())
        
        if docIds:
            contextParts.append("=== Available Documents ===")
            for docId in docIds:
                if docId in self.documents:
                    doc = self.documents[docId]
                    meta = self.metadata.get(docId, {})
                    
                    contextParts.append(f"\nDocument: {meta.get('fileName', 'Unknown')} (ID: {docId})")
                    contextParts.append(f"Type: {meta.get('type', 'unknown')}")
                    contextParts.append("")
        
        if self.relationships:
            contextParts.append("=== Document Relationships ===")
            for docId, rels in self.relationships.items():
                if docId in self.metadata:
                    docName = self.metadata[docId]['fileName']
                    relatedNames = [
                        self.metadata.get(rel['docId'], {}).get('fileName', 'Unknown')
                        for rel in rels
                        if rel['docId'] in self.metadata
                    ]
                    if relatedNames:
                        contextParts.append(f"{docName} is related to: {', '.join(relatedNames)}")
            contextParts.append("")
        
        return "\n".join(contextParts)
    
    
    def removeDocument(self, docId: str) -> bool:
        """Remove document from context"""
        if docId in self.documents:
            del self.documents[docId]
        if docId in self.metadata:
            del self.metadata[docId]
        if docId in self.relationships:
            for otherDocId, rels in self.relationships.items():
                self.relationships[otherDocId] = [
                    rel for rel in rels if rel['docId'] != docId
                ]
            del self.relationships[docId]
        return True
    
    def getSummary(self) -> Dict[str, Any]:
        """Get summary of current context"""
        return {
            'documentCount': len(self.documents),
            'conversationLength': len(self.conversation),
            'relationshipCount': sum(len(rels) for rels in self.relationships.values()),
            'documents': [
                {
                    'id': docId,
                    'name': meta['fileName'],
                    'type': meta['type']
                }
                for docId, meta in self.metadata.items()
            ]
        }
    
    def validateContext(self) -> Dict[str, Any]:
        """
        Validate context health and return validation results.
        
        Returns:
            Dict with validation status, issues, and recommendations
        """
        issues = []
        warnings = []
        
        # Check conversation history size
        if len(self.conversation) > self.maxConversationHistory * 0.9:
            warnings.append(f"Conversation history is at {len(self.conversation)}/{self.maxConversationHistory} messages. Consider summarization.")
        
        # Check for orphaned relationships
        for docId, rels in self.relationships.items():
            if docId not in self.documents:
                issues.append(f"Orphaned relationship: document {docId} referenced but not in documents")
            for rel in rels:
                if rel['docId'] not in self.documents:
                    issues.append(f"Orphaned relationship: related document {rel['docId']} not found")
        
        # Check for documents without metadata
        for docId in self.documents:
            if docId not in self.metadata:
                warnings.append(f"Document {docId} missing metadata")
        
        # Check conversation quality
        if len(self.conversation) > 0:
            recent_messages = self.conversation[-10:]
            empty_messages = sum(1 for msg in recent_messages if not msg.get('content', '').strip())
            if empty_messages > 0:
                warnings.append(f"Found {empty_messages} empty messages in recent conversation")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'documentCount': len(self.documents),
            'conversationLength': len(self.conversation),
            'relationshipCount': sum(len(rels) for rels in self.relationships.values())
        }
    
    def summarizeConversation(self, maxMessages: int = 20) -> str:
        """
        Create a concise summary of conversation history.
        
        Args:
            maxMessages: Maximum number of recent messages to include in summary
            
        Returns:
            Summarized conversation context
        """
        if not self.conversation:
            return "No conversation history available."
        
        recent = self.conversation[-maxMessages:] if len(self.conversation) > maxMessages else self.conversation
        
        # Group by role and extract key points
        user_messages = [msg['content'] for msg in recent if msg.get('role') == 'user']
        assistant_messages = [msg['content'] for msg in recent if msg.get('role') == 'assistant']
        
        summary_parts = []
        summary_parts.append(f"Conversation Summary ({len(recent)} recent messages):")
        summary_parts.append(f"- User messages: {len(user_messages)}")
        summary_parts.append(f"- Assistant messages: {len(assistant_messages)}")
        
        if user_messages:
            # Extract key topics from user messages (first 3-5 words of each)
            key_topics = []
            for msg in user_messages[-5:]:  # Last 5 user messages
                words = msg.split()[:5]
                if words:
                    key_topics.append(' '.join(words))
            if key_topics:
                summary_parts.append(f"- Recent topics: {', '.join(key_topics)}")
        
        return "\n".join(summary_parts)
    
    def getContextHealth(self) -> Dict[str, Any]:
        """
        Get overall context health metrics.
        
        Returns:
            Dict with health metrics and status
        """
        validation = self.validateContext()
        
        # Calculate health score (0-100)
        health_score = 100
        if validation['issues']:
            health_score -= len(validation['issues']) * 20
        if validation['warnings']:
            health_score -= len(validation['warnings']) * 5
        health_score = max(0, min(100, health_score))
        
        # Determine health status
        if health_score >= 80:
            status = "healthy"
        elif health_score >= 60:
            status = "degraded"
        else:
            status = "unhealthy"
        
        return {
            'status': status,
            'score': health_score,
            'validation': validation,
            'metrics': {
                'documents': len(self.documents),
                'conversation_messages': len(self.conversation),
                'relationships': sum(len(rels) for rels in self.relationships.values()),
                'conversation_utilization': f"{len(self.conversation)}/{self.maxConversationHistory}"
            }
        }

