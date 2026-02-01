"""Intelligent Intent Classifier - uses LLM to understand user intent instead of pattern matching"""
from typing import Dict, List, Any, Optional, Tuple
import re
import json


class IntentClassifier:
    """Classifies user intents intelligently using LLM with pattern fallback"""
    
    def __init__(self, llmTool=None):
        """
        Args:
            llmTool: LLM tool for intelligent classification (optional)
        """
        self.llmTool = llmTool
        self.cache = {}  # Cache classifications
        self.confidence_threshold = 0.7  # Minimum confidence for LLM classification
    
    def classify(self, query: str, context: Optional[Dict] = None, 
                 intentTypes: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Classify user query intent
        
        Args:
            query: User query
            context: Optional context (conversation history, etc.)
            intentTypes: List of possible intent types to consider
            
        Returns:
            Dict with 'intent', 'confidence', 'entities', 'reasoning'
        """
        queryLower = query.lower().strip()
        
        cacheKey = f"{queryLower}_{hash(str(context))}"
        if cacheKey in self.cache:
            return self.cache[cacheKey]
        
        # Use LLM for classification (primary method)
        if self.llmTool:
            try:
                result = self._llmBasedClassification(query, context, intentTypes)
                # Cache result
                self.cache[cacheKey] = result
                return result
            except Exception:
                # Only fallback to pattern if LLM completely fails
                pass
        
        # Fallback: pattern-based only when LLM unavailable
        result = self._patternBasedClassification(query, context, intentTypes)
        self.cache[cacheKey] = result
        return result
    
    def _patternBasedClassification(self, query: str, context: Optional[Dict], 
                                   intentTypes: Optional[List[str]]) -> Dict[str, Any]:
        """Fast pattern-based classification"""
        queryLower = query.lower()
        intent = 'unknown'
        confidence = 0.5
        entities = {}
        reasoning = "Pattern-based classification"
        
        # Verinice intents
        if any(word in queryLower for word in ['create', 'new', 'add', 'make']) and not any(q in queryLower for q in ['what', 'how', 'why']):
                intent = 'verinice_create'
                confidence = 0.7
        
        elif any(word in queryLower for word in ['list', 'show', 'display', 'get all']):
            intent = 'verinice_list'
            confidence = 0.7
        
        # Capability queries
        elif any(phrase in queryLower for phrase in ['what can', 'can you', 'show capabilities', 'help', 'what do you do']):
            intent = 'show_capabilities'
            confidence = 0.9
        
        return {
            'intent': intent,
            'confidence': confidence,
            'entities': entities,
            'reasoning': reasoning,
            'method': 'pattern'
        }
    
    def _llmBasedClassification(self, query: str, context: Optional[Dict], 
                               intentTypes: Optional[List[str]]) -> Dict[str, Any]:
        """LLM-powered intent classification"""
        if not self.llmTool:
            return {'intent': 'unknown', 'confidence': 0, 'method': 'llm_unavailable'}
        
        try:
            # Build context string
            contextStr = ""
            if context:
                if context.get('conversationHistory'):
                    contextStr += f"Recent conversation: {str(context['conversationHistory'][-3:])}\n"
            
            # Build intent types list
            if not intentTypes:
                intentTypes = [
                    
                    'verinice_create',   # Create Verinice object
                    'verinice_list',     # List Verinice objects
                    'verinice_get',      # Get Verinice object details
                    'verinice_update',   # Update Verinice object
                    'verinice_delete',   # Delete Verinice object
                    'show_capabilities', # Show what agent can do
                    'general_question',  # General question/chat
                    'unknown'            # Unknown intent
                ]
            
            prompt = f"""You are an expert at classifying user queries into specific intent categories for an ISMS compliance assistant.

TASK: Classify the user query into one of these intent types: {', '.join(intentTypes)}

User Query: "{query}"

Context:
{contextStr if contextStr else 'No additional context'}

AVAILABLE INTENTS:
- verinice_create: User wants to CREATE a Verinice object (explicit create command like "create scope", "create asset")
- verinice_list: User wants to list Verinice objects (e.g., "list scopes", "show assets")
- verinice_get: User wants to get/view details of a specific Verinice object
- verinice_update: User wants to update/modify a Verinice object
- verinice_delete: User wants to delete a Verinice object
- show_capabilities: User wants to know what the agent can do (e.g., "what can you do", "show capabilities")
- general_question: General question or chat that doesn't fit other categories
- unknown: Cannot determine intent

IMPORTANT RULES:
1. If user explicitly says "create X", classify as 'verinice_create'
4. Questions starting with "what", "how", "why" are usually analysis/queries, NOT creation commands
5. Commands with action verbs (create, list, delete, update) should match their respective intent types
6. Be precise: distinguish between "list" (verinice_list) and "get/view" (verinice_get) operations

EXAMPLES:

CREATE INTENT:
- "create scope MyScope" → {{"intent": "verinice_create", "confidence": 0.95, "entities": {{"objectType": "scope", "name": "MyScope"}}, "reasoning": "Explicit create command for scope"}}
- "can you create scope MyScope" → {{"intent": "verinice_create", "confidence": 0.9, "entities": {{"objectType": "scope", "name": "MyScope"}}, "reasoning": "Polite create request"}}
- "I need to create an asset called Server1" → {{"intent": "verinice_create", "confidence": 0.9, "entities": {{"objectType": "asset", "name": "Server1"}}, "reasoning": "Conversational create request"}}
- "please create control A.8.1.1" → {{"intent": "verinice_create", "confidence": 0.95, "entities": {{"objectType": "control", "name": "A.8.1.1"}}, "reasoning": "Polite create command"}}
- "make a new scope named BLUETEAM" → {{"intent": "verinice_create", "confidence": 0.85, "entities": {{"objectType": "scope", "name": "BLUETEAM"}}, "reasoning": "Alternative phrasing for create"}}
- "Create a new person 'John'.assign his role to 'DPO'" → {{"intent": "verinice_create", "confidence": 0.9, "entities": {{"objectType": "person", "name": "John", "role": "DPO"}}, "reasoning": "Create person with role"}}
- "add a person 'Kyaw Kyaw' and set his role to DPO" → {{"intent": "verinice_create", "confidence": 0.9, "entities": {{"objectType": "person", "name": "Kyaw Kyaw", "role": "DPO"}}, "reasoning": "Add person with role, conversational"}}

LIST INTENT:
- "list all assets" → {{"intent": "verinice_list", "confidence": 0.9, "entities": {{"objectType": "asset"}}, "reasoning": "List operation for assets"}}
- "show me all scopes" → {{"intent": "verinice_list", "confidence": 0.9, "entities": {{"objectType": "scope"}}, "reasoning": "Show is equivalent to list"}}
- "what scopes do we have" → {{"intent": "verinice_list", "confidence": 0.85, "entities": {{"objectType": "scope"}}, "reasoning": "Question form of list request"}}
- "display all controls" → {{"intent": "verinice_list", "confidence": 0.9, "entities": {{"objectType": "control"}}, "reasoning": "Display is equivalent to list"}}
- "can you list the assets" → {{"intent": "verinice_list", "confidence": 0.9, "entities": {{"objectType": "asset"}}, "reasoning": "Polite list request"}}

GET/VIEW INTENT:
- "get scope SCOPE1" → {{"intent": "verinice_get", "confidence": 0.95, "entities": {{"objectType": "scope", "name": "SCOPE1"}}, "reasoning": "Get specific object"}}
- "show me SCOPE1" → {{"intent": "verinice_get", "confidence": 0.9, "entities": {{"objectType": "scope", "name": "SCOPE1"}}, "reasoning": "Show specific object"}}
- "what is SCOPE1" → {{"intent": "verinice_get", "confidence": 0.85, "entities": {{"objectType": "scope", "name": "SCOPE1"}}, "reasoning": "Question about specific object"}}
- "view Desktop asset" → {{"intent": "verinice_get", "confidence": 0.9, "entities": {{"objectType": "asset", "name": "Desktop"}}, "reasoning": "View specific object"}}

UPDATE INTENT:
- "update scope SCOPE1" → {{"intent": "verinice_update", "confidence": 0.95, "entities": {{"objectType": "scope", "name": "SCOPE1"}}, "reasoning": "Update command"}}
- "modify Desktop asset" → {{"intent": "verinice_update", "confidence": 0.9, "entities": {{"objectType": "asset", "name": "Desktop"}}, "reasoning": "Modify is equivalent to update"}}
- "change SCOPE1 description" → {{"intent": "verinice_update", "confidence": 0.9, "entities": {{"objectType": "scope", "name": "SCOPE1"}}, "reasoning": "Change is equivalent to update"}}
- "set role for the Data protection officer for the person Ruby" → {{"intent": "verinice_update", "confidence": 0.9, "entities": {{"objectType": "person", "name": "Ruby", "role": "Data Protection Officer"}}, "reasoning": "Set role for a person"}}
- "change Ruby's role to CISO" → {{"intent": "verinice_update", "confidence": 0.9, "entities": {{"objectType": "person", "name": "Ruby", "role": "CISO"}}, "reasoning": "Change role for a person"}}

DELETE INTENT:
- "delete scope SCOPE1" → {{"intent": "verinice_delete", "confidence": 0.95, "entities": {{"objectType": "scope", "name": "SCOPE1"}}, "reasoning": "Delete command"}}
- "remove Desktop asset" → {{"intent": "verinice_delete", "confidence": 0.9, "entities": {{"objectType": "asset", "name": "Desktop"}}, "reasoning": "Remove is equivalent to delete"}}

CAPABILITIES INTENT:
- "what can you do?" → {{"intent": "show_capabilities", "confidence": 0.95, "entities": {{}}, "reasoning": "User asking about agent capabilities"}}
- "show capabilities" → {{"intent": "show_capabilities", "confidence": 0.95, "entities": {{}}, "reasoning": "Direct capabilities request"}}
- "what are your features" → {{"intent": "show_capabilities", "confidence": 0.9, "entities": {{}}, "reasoning": "Alternative phrasing for capabilities"}}
- "help" → {{"intent": "show_capabilities", "confidence": 0.8, "entities": {{}}, "reasoning": "Help request often means show capabilities"}}

GENERAL QUESTION:
- "how do I create a scope?" → {{"intent": "general_question", "confidence": 0.8, "entities": {{}}, "reasoning": "Question about how to do something, not a direct command"}}
- "what is ISO 27001?" → {{"intent": "general_question", "confidence": 0.9, "entities": {{}}, "reasoning": "Knowledge question"}}
- "explain risk assessment" → {{"intent": "general_question", "confidence": 0.9, "entities": {{}}, "reasoning": "Explanation request"}}

BAD EXAMPLES (what NOT to do):
- "create scope MyScope" → ❌ WRONG: {{"intent": "general_question", "confidence": 0.5, "entities": {{}}, "reasoning": "User wants to create something"}}
  ✅ CORRECT: {{"intent": "verinice_create", "confidence": 0.95, "entities": {{"objectType": "scope", "name": "MyScope"}}, "reasoning": "Explicit create command"}}
- "show me the scopes" → ❌ WRONG: {{"intent": "verinice_get", "confidence": 0.6, "entities": {{"objectType": "scope"}}, "reasoning": "User wants to see scopes"}}
  ✅ CORRECT: {{"intent": "verinice_list", "confidence": 0.9, "entities": {{"objectType": "scope"}}, "reasoning": "Show me is equivalent to list operation"}}
- "what is SCOPE1" → ❌ WRONG: {{"intent": "general_question", "confidence": 0.7, "entities": {{}}, "reasoning": "Question about something"}}
  ✅ CORRECT: {{"intent": "verinice_get", "confidence": 0.85, "entities": {{"objectType": "scope", "name": "SCOPE1"}}, "reasoning": "Question about specific object"}}
- "list assets" → ❌ WRONG: {{"intent": "unknown", "confidence": 0.3, "entities": {{}}, "reasoning": "Unclear intent"}}
  ✅ CORRECT: {{"intent": "verinice_list", "confidence": 0.9, "entities": {{"objectType": "asset"}}, "reasoning": "List operation for assets"}}

OUTPUT FORMAT (respond ONLY with valid JSON, no explanations, no markdown):
{{
    "intent": "intent_name",
    "confidence": 0.0-1.0,
    "entities": {{"key": "value"}},
    "reasoning": "brief explanation"
}}
"""
            
            # Use JSON mode for structured output
            response = self.llmTool.generate(prompt, maxTokens=300, response_format="json_object")
            
            # Parse JSON response (should be clean JSON with JSON mode)
            try:
                result = json.loads(response)
                result['method'] = 'llm'
                return result
            except json.JSONDecodeError:
                # Fallback: try regex extraction if JSON mode didn't work
                jsonMatch = re.search(r'\{[^}]+\}', response, re.DOTALL)
                if jsonMatch:
                    result = json.loads(jsonMatch.group(0))
                    result['method'] = 'llm'
                    return result
            
            # Fallback: extract intent from text
            return self._extractIntentFromText(response, query)
            
        except Exception as e:
            # Fallback to pattern-based
            return self._patternBasedClassification(query, context, intentTypes)
    
    def _extractIntentFromText(self, text: str, query: str) -> Dict[str, Any]:
        """Extract intent from LLM text response"""
        textLower = text.lower()
        
        intent = 'unknown'
        confidence = 0.5
        
        if 'verinice' in textLower:
            intent = 'verinice_create'
            confidence = 0.7
        elif 'create' in textLower:
            intent = 'verinice_create'
            confidence = 0.6
        elif 'list' in textLower:
            intent = 'verinice_list'
            confidence = 0.6
        
        return {
            'intent': intent,
            'confidence': confidence,
            'entities': {},
            'reasoning': f"Extracted from LLM response: {text[:100]}",
            'method': 'llm_fallback'
        }
    
    def isVeriniceOperation(self, query: str, context: Optional[Dict] = None) -> bool:
        """Check if query is a Verinice operation"""
        classification = self.classify(query, context)
        intent = classification.get('intent', '')
        return intent.startswith('verinice_') and classification.get('confidence', 0) > 0.6
    
    def getIntent(self, query: str, context: Optional[Dict] = None) -> str:
        """Get intent name (shortcut method)"""
        return self.classify(query, context).get('intent', 'unknown')
    
    def clearCache(self):
        """Clear classification cache"""
        self.cache.clear()

