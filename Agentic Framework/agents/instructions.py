"""
Agent Instructions and Pattern Definitions

This module loads patterns from multiple JSON files and provides them
as constants for backward compatibility. System prompts remain here.
"""

import json
from pathlib import Path
from typing import Dict, List

# ==================== LOAD JSON FILES ====================

def _loadJSONFile(filename: str) -> Dict:
    """Load JSON file from utils directory"""
    try:
        jsonPath = Path(__file__).parent.parent / 'utils' / filename
        with open(jsonPath, 'r') as f:
            return json.load(f)
    except Exception:
        # Fallback to empty structure if file missing
        return {}

# Load all instruction files
_ISMS_INSTRUCTIONS = _loadJSONFile('ismsInstructions.json')
_COMMON_INSTRUCTIONS = _loadJSONFile('commonInstructions.json')
_ERRORS_BASE = _loadJSONFile('errorsBase.json')

# ==================== ISMS PATTERNS ====================
_verinice = _ISMS_INSTRUCTIONS.get('verinice', {})
VERINICE_OBJECT_TYPES = _verinice.get('object_types', [])

# Operation keywords (for pattern matching)
_op_keywords = _verinice.get('operation_keywords', {})
VERINICE_CREATE_KEYWORDS = _op_keywords.get('create', ['create', 'new', 'add', 'make'])
VERINICE_LIST_KEYWORDS = _op_keywords.get('list', ['list', 'show', 'display'])
VERINICE_GET_KEYWORDS = _op_keywords.get('get', ['get', 'view'])
VERINICE_UPDATE_KEYWORDS = _op_keywords.get('update', ['update', 'edit', 'modify'])
VERINICE_DELETE_KEYWORDS = _op_keywords.get('delete', ['delete', 'remove'])
VERINICE_ANALYZE_KEYWORDS = _op_keywords.get('analyze', ['analyze'])

# Question filters
_question_filters = _verinice.get('question_filters', {})
VERINICE_QUESTION_STARTERS = _question_filters.get('question_starters', ['how do', 'how can', 'how to', 'what is', 'what are'])
VERINICE_QUESTION_WORDS = _question_filters.get('question_words', ['how', 'what', 'why'])

# Conversational patterns
_conv_patterns = _verinice.get('conversational_patterns', {})
VERINICE_CONVERSATIONAL_LIST = _conv_patterns.get('list_prompts', [])
VERINICE_SUBTYPE_QUERIES = _conv_patterns.get('subtype_queries', [])

# Subtype mappings (subtype name -> object type)
VERINICE_SUBTYPE_MAPPINGS = _verinice.get('subtype_mappings', {})

# Report patterns
_report_patterns = _verinice.get('report_patterns', {})
VERINICE_REPORT_KEYWORDS = _report_patterns.get('keywords', ['generate', 'create', 'make', 'get'])
VERINICE_REPORT_TYPES = _report_patterns.get('types', ['inventory', 'risk', 'statement'])
VERINICE_REPORT_TYPE_MAPPINGS = _report_patterns.get('type_mappings', {})

# Typo corrections
VERINICE_TYPO_CORRECTIONS = _verinice.get('typo_corrections', {})

# Legacy operation patterns (kept for backward compatibility - may be removed later)
_legacy_ops = _verinice.get('legacy_operations', {})
VERINICE_CREATE_PATTERNS = _legacy_ops.get('create', [])
VERINICE_LIST_PATTERNS = _legacy_ops.get('list', [])
VERINICE_VIEW_PATTERNS = _legacy_ops.get('view', [])
VERINICE_UPDATE_PATTERNS = _legacy_ops.get('update', [])
VERINICE_DELETE_PATTERNS = _legacy_ops.get('delete', [])
VERINICE_REPORT_PATTERNS = _legacy_ops.get('report', [])
VERINICE_ANALYZE_PATTERNS = _legacy_ops.get('analyze', [])
VERINICE_DOMAIN_PATTERNS = _legacy_ops.get('domain', [])


# ==================== COMMON PATTERNS ====================
_conv = _COMMON_INSTRUCTIONS.get('conversational', {})
GREETING_PATTERN = _conv.get('greeting_regex', r'^(hey|hi|hello).*$')
THANKS_PATTERN = _conv.get('thanks_regex', r'^(thanks|thank\s*you).*$')
AFFIRMATIVE_PATTERNS = _conv.get('affirmative', ['yes', 'ok'])
FOLLOW_UP_PATTERNS = _conv.get('follow_up', [])

# Legacy list patterns (kept for backward compatibility)
GREETING_PATTERNS = ['hey', 'hi', 'hello', 'yo', 'sup', 'whats up', 'greetings', 'good morning', 'good afternoon', 'good evening', 'hi there', 'hello there']
AGENT_NAME_GREETING_PATTERNS = ['hey sparksbm', 'hi sparksbm', 'hello sparksbm', 'hey intelligent', 'hi intelligent', 'hello intelligent']
THANKS_PATTERNS = ['thanks', 'thank you', 'thx', 'ty', 'appreciate it', 'thanks a lot', 'thank you so much']

_cap = _COMMON_INSTRUCTIONS.get('capabilities', {})
CAPABILITY_SHOW_PATTERNS = _cap.get('show_patterns', [])
CAPABILITY_QUERY_PATTERNS = _cap.get('query_patterns', [])

_sys = _COMMON_INSTRUCTIONS.get('system_queries', {})
LLM_STATUS_PATTERNS = _sys.get('llm_status', [])
STATE_HISTORY_PATTERNS = _sys.get('state_history', [])
WORKFLOW_TEST_PATTERNS = _sys.get('workflow_test', [])
SYSTEM_FLOW_PATTERNS = _sys.get('system_flow', [])
AGENT_MANAGE_PATTERNS = _sys.get('agent_management', [])

ACTION_VERB_PATTERNS = _COMMON_INSTRUCTIONS.get('action_verbs', {})

TYPO_VARIATIONS = _COMMON_INSTRUCTIONS.get('typo_variations', {})

_knowledge = _COMMON_INSTRUCTIONS.get('knowledge_questions', {})
KNOWLEDGE_QUESTION_STARTERS = _knowledge.get('question_starters', ['what', 'how', 'why'])
KNOWLEDGE_QUESTION_PHRASES = _knowledge.get('question_phrases', ['how do', 'what is'])
KNOWLEDGE_WHAT_PATTERNS = _knowledge.get('what_patterns', ['what', 'explain', 'define'])
KNOWLEDGE_HOW_TO_CREATE_PATTERNS = _knowledge.get('how_to_create_patterns', ['how', 'do i'])

_constants = _COMMON_INSTRUCTIONS.get('constants', {})
FUZZY_MATCH_MIN_WORD_LENGTH = _constants.get('fuzzy_match_min_word_length', 2)

# ==================== ERROR MESSAGES ====================
def get_error_message(category: str, key: str, **kwargs) -> str:
    """
    Get error message from errorsBase.json with variable substitution.
    
    Args:
        category: Error category (validation, not_found, operation_failed, connection, data, user_guidance)
        key: Error key within category
        **kwargs: Variables to substitute in the message template
    
    Returns:
        Formatted error message with variables substituted
    
    Example:
        get_error_message('validation', 'missing_name', objectType='scope')
        # Returns: "What name for the scope?\n\nExample: create scope MyName..."
    """
    category_errors = _ERRORS_BASE.get(category, {})
    template = category_errors.get(key, f"Error: {category}.{key}")
    
    # Substitute variables in template
    try:
        return template.format(**kwargs)
    except KeyError as e:
        # If variable missing, return template as-is
        return template

# ==================== SYSTEM PROMPT (Kept in Python) ====================
DETAILED_SYSTEM_PROMPT = """You are SparksBM Intelligent, a professional ISMS compliance assistant integrated with Verinice.

Your Core Capabilities:
1. ISO 27001, ISO 22301, and NIS-2 compliance guidance
2. Verinice ISMS platform operations (scopes, assets, controls, processes, persons, scenarios, incidents, documents)
3. Risk management and control implementation advice

Communication Standards:
- Be professional, friendly, and approachable
- Use clear, concise language with actionable guidance
- Use ISMS terminology correctly
- Provide context and examples when helpful
- One action per response, one question maximum

Critical Rules:
- NEVER expose internal tool names, tool calls, or execution steps
- ALWAYS narrate actions as if you performed them directly
- Rewrite errors as calm, user-facing explanations with next steps
- NO system wording like "service issue", "tool error", "operation failed"
- End responses with guidance or clear next steps when appropriate

Your Expertise:
- You understand the full lifecycle of ISMS objects
- You can explain relationships between scopes, assets, controls, and risks
- You provide practical implementation guidance
- You adapt your responses based on user expertise level

Remember: Users see you as an intelligent assistant, not a system executing commands."""
