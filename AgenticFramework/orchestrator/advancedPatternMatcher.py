"""
Advanced Pattern Matcher - LLM-free intent understanding

Handles complex prompts:
- ISMS reconciliation and comparison
- Safety-critical operations
- Multi-step operations
- Constraint extraction
"""

import re
from typing import Dict, Optional, List, Tuple
import logging

logger = logging.getLogger(__name__)


class AdvancedPatternMatcher:
    """Advanced pattern matching for complex prompts without LLM"""
    
    def __init__(self):
        self.patterns = self._load_patterns()
    
    def _load_patterns(self) -> Dict:
        """Load pattern definitions"""
        return {
            # ISMS reconciliation patterns
            'isms_reconciliation': {
                'keywords': ['compare', 'reconcile', 'reconciliation', 'difference', 'drift', 'gap', 'discrepancy'],
                'object_patterns': [
                    r"['\"]([A-Za-z0-9_\s-]+)['\"]",  # Quoted object names
                    r'\b([A-Z][A-Za-z0-9_\s-]+)\b',  # Capitalized names (SCOPE1, Production)
                ],
                'domain_keywords': ['domain', 'scope', 'environment', 'production', 'staging', 'dr'],
                'comparison_phrases': ['vs', 'versus', 'against', 'and', 'with'],
            },
            
            # Safety-critical operations
            'safety_operations': {
                'dangerous_keywords': [
                    'delete all', 'remove all', 'clean up', 'wipe', 'drop', 'truncate', 'destroy',
                    'erase all', 'clear all', 'purge', 'format', 'reset all', 'nuke', 'kill all'
                ],
                'protected_paths': [
                    'root', '/', '../', '..\\', 'config', 'secrets', 'password', 'credential',
                    '.env', '.git', 'node_modules', 'vendor', '__pycache__', '.venv',
                    'system', 'etc', 'usr', 'var', 'home', 'windows', 'system32'
                ],
                'bulk_operations': [
                    'all files', 'all data', 'everything', 'entire', 'whole',
                    'entire directory', 'whole folder', 'all directories', 'all folders'
                ],
                'confirmation_triggers': ['just do it', 'proceed', 'go ahead', 'execute', 'run it', 'do it now'],
            },
            
            # Multi-step operations
            'multi_step': {
                'connectors': ['then', 'and', 'after', 'next', 'also', 'while', 'during'],
                'sequence_markers': ['first', 'second', 'step 1', 'step 2', 'phase', 'stage'],
            },
            
            # Constraint extraction
            'constraints': {
                'preservation': ['preserve', 'maintain', 'keep', 'don\'t change', 'do not modify'],
                'requirements': ['must', 'should', 'required', 'critical', 'important', 'ensure'],
                'prohibitions': ['do not', 'don\'t', 'avoid', 'never', 'skip', 'ignore'],
            },
        }
    
    def detect_intent(self, message: str) -> Dict:
        """
        Detect intent from message using advanced pattern matching.
        
        Returns:
            Dict with:
            - intent: str (isms_reconciliation, safety_check, multi_step, etc.)
            - confidence: float (0.0-1.0)
            - entities: Dict (extracted parameters)
            - requires_llm: bool (whether LLM is needed for full understanding)
        """
        message_lower = message.lower().strip()
        original_message = message
        
        # IMPORTANT: Check safety FIRST (highest priority)
        safety_intent = self._detect_safety_operation(original_message, message_lower)
        if safety_intent:
            return safety_intent
        
        # (ISMS reconciliation uses "and" but is not multi-step)
        isms_intent = self._detect_isms_reconciliation(original_message, message_lower)
        if isms_intent and isms_intent.get('confidence', 0) >= 0.6:
            return isms_intent
        
        has_multi_step_indicators = self._has_multi_step_indicators(message_lower)
        
        if has_multi_step_indicators:
            multi_intent = self._detect_multi_step(original_message, message_lower)
            if multi_intent:
                step_count = multi_intent.get('entities', {}).get('step_count', 0)
                if step_count >= 2:
                    # If we found 2+ steps, prioritize multi-step
                    return multi_intent
        
        # Re-check ISMS reconciliation with lower threshold (if not caught above)
        if isms_intent:
            return isms_intent
        
        # Final check: multi-step with lower threshold
        if has_multi_step_indicators:
            multi_intent = self._detect_multi_step(original_message, message_lower)
            if multi_intent:
                return multi_intent
        
        # Default: unknown intent
        return {
            'intent': 'unknown',
            'confidence': 0.3,
            'entities': {},
            'requires_llm': True,
            'reasoning': 'No matching patterns found'
        }
    
    def _detect_isms_reconciliation(self, original: str, message_lower: str) -> Optional[Dict]:
        """Detect ISMS reconciliation/comparison requests"""
        patterns = self.patterns['isms_reconciliation']
        
        has_keyword = any(keyword in message_lower for keyword in patterns['keywords'])
        # Also check for "find gaps" which is a common reconciliation pattern
        has_gap_keyword = 'gap' in message_lower and ('find' in message_lower or 'between' in message_lower)
        
        if not (has_keyword or has_gap_keyword):
            return None
        
        # Extract object names
        objects = self._extract_object_names(original, message_lower)
        
        domains = self._extract_domains(message_lower)
        
        # If "reconcile" keyword is present, it's definitely reconciliation
        if 'reconcile' in message_lower:
            confidence = 0.7
            if len(objects) >= 2:
                confidence += 0.15
        # If "gap" or "find gaps" is present, it's gap analysis
        elif 'gap' in message_lower:
            confidence = 0.7
            if len(domains) >= 2 or len(objects) >= 2:
                confidence += 0.15
        else:
            # Regular comparison
            confidence = 0.6
            if len(objects) >= 2:
                confidence += 0.2
            if domains:
                confidence += 0.1
        
        return {
            'intent': 'isms_reconciliation',
            'confidence': min(confidence, 1.0),
            'entities': {
                'objects': objects,
                'domains': domains,
                'comparison_type': self._extract_comparison_type(message_lower)
            },
            'requires_llm': len(objects) < 2 or 'gap analysis' in message_lower or 'remediation' in message_lower,
            'reasoning': f'Detected ISMS reconciliation: {len(objects)} objects, {len(domains)} domains'
        }
    
    def _detect_safety_operation(self, original: str, message_lower: str) -> Optional[Dict]:
        """Detect safety-critical operations"""
        patterns = self.patterns['safety_operations']
        
        has_dangerous = any(keyword in message_lower for keyword in patterns['dangerous_keywords'])
        has_bulk = any(keyword in message_lower for keyword in patterns['bulk_operations'])
        has_protected = any(path in message_lower for path in patterns['protected_paths'])
        
        if not (has_dangerous or (has_bulk and has_protected)):
            return None
        
        # Extract target path/scope
        target = self._extract_path_or_scope(original, message_lower)
        
        return {
            'intent': 'safety_check',
            'confidence': 0.9,
            'entities': {
                'operation': 'dangerous',
                'target': target,
                'is_bulk': has_bulk,
                'is_protected_path': has_protected
            },
            'requires_llm': False,  # Safety checks should be immediate
            'reasoning': 'Detected potentially dangerous operation - requires safety check',
            'action': 'block' if has_protected else 'confirm'
        }
    
    def _has_multi_step_indicators(self, message_lower: str) -> bool:
        """Quick check if message has multi-step indicators"""
        patterns = self.patterns['multi_step']
        has_connector = any(connector in message_lower for connector in patterns['connectors'])
        has_sequence = any(marker in message_lower for marker in patterns['sequence_markers'])
        
        # Exclude ISMS reconciliation patterns (they use "and" but aren't multi-step)
        isms_keywords = ['reconcile', 'compare', 'reconciliation', 'gap', 'difference', 'drift']
        if any(keyword in message_lower for keyword in isms_keywords):
            # If it's an ISMS operation, don't treat "and" as multi-step connector
            return has_sequence  # Only sequence markers, not "and"
        
        return has_connector or has_sequence
    
    def _detect_multi_step(self, original: str, message_lower: str) -> Optional[Dict]:
        """Detect multi-step operations"""
        patterns = self.patterns['multi_step']
        
        # Exclude single UPDATE operations with multiple fields
        # Pattern: "update X. Change Y and set Z" should be treated as single UPDATE, not multi-step
        if message_lower.startswith('update '):
            update_field_keywords = ['change', 'set', 'update', 'description', 'confidentiality', 'status', 'availability', 'integrity']
            # If the message contains "update" followed by field keywords, it's likely a single UPDATE
            if any(keyword in message_lower for keyword in update_field_keywords):
                # Only exclude if it's clearly a field update pattern, not "update X then update Y"
                if ' then ' not in message_lower and '. then ' not in message_lower:
                    # This is a single UPDATE operation with multiple fields
                    return None
        
        # Exclude single CREATE operations with field modifications
        # Pattern: "Create a Controller named 'X' and mark its status as 'Y'" should be treated as single CREATE, not multi-step
        if message_lower.startswith('create '):
            # Check if it's a single CREATE with field modifications (status, note, description, etc.)
            create_field_keywords = ['mark', 'set', 'add', 'note', 'status', 'description', 'confidentiality', 'saying']
            # If the message contains "create" followed by field keywords, it's likely a single CREATE
            if any(keyword in message_lower for keyword in create_field_keywords):
                # Only exclude if it's clearly a field modification pattern, not "create X then create Y"
                if ' then ' not in message_lower and '. then ' not in message_lower:
                    # Also handle "Add a note" pattern and "Add a note saying..."
                    and_pattern = r'\s+and\s+(?:mark|set|add|note|status|description)'
                    add_pattern = r'\s+add\s+(?:a\s+)?note\s+(?:saying)?'
                    if re.search(and_pattern, message_lower) or re.search(add_pattern, message_lower):
                        # This is a single CREATE operation with multiple fields
                        return None
        
        has_connector = any(connector in message_lower for connector in patterns['connectors'])
        has_sequence = any(marker in message_lower for marker in patterns['sequence_markers'])
        
        if not (has_connector or has_sequence):
            return None
        
        # Extract steps
        steps = self._extract_steps(original, message_lower)
        
        # If we found steps, this is definitely multi-step
        if len(steps) >= 2:
            confidence = 0.85 if len(steps) == 2 else 0.9
            return {
                'intent': 'multi_step',
                'confidence': confidence,
                'entities': {
                    'steps': steps,
                    'step_count': len(steps)
                },
                'requires_llm': len(steps) > 3,  # Complex multi-step needs LLM
                'reasoning': f'Detected multi-step operation with {len(steps)} steps',
                'already_checked': True
            }
        
        # If connectors found but steps not extracted well, try one more time with simpler extraction
        if (has_connector or has_sequence) and len(steps) < 2:
            # Try simple "then" split as last resort
            if 'then' in message_lower:
                parts = message_lower.split('then', 1)
                if len(parts) == 2:
                    step1 = parts[0].strip()
                    step2 = parts[1].strip()
                    # Clean up
                    step1 = re.sub(r'[,\.;]+$', '', step1)
                    step2 = re.sub(r'^[,\.;]+\s*', '', step2)
                    if len(step1) > 5 and len(step2) > 5:
                        steps = [step1, step2]
                        return {
                            'intent': 'multi_step',
                            'confidence': 0.75,
                            'entities': {
                                'steps': steps,
                                'step_count': len(steps)
                            },
                            'requires_llm': False,
                            'reasoning': f'Detected multi-step operation with {len(steps)} steps (simple extraction)',
                            'already_checked': True
                        }
        
        # If connectors found but steps not extracted, try additional extraction methods
        if (has_connector or has_sequence) and len(steps) < 2:
            # Try splitting on common separators
            separators = [', then', '. then', '; then', ', and', '. and', ', next', '. next']
            for sep in separators:
                if sep in message_lower:
                    parts = message_lower.split(sep, 1)
                    if len(parts) == 2:
                        step1 = parts[0].strip()
                        step2 = parts[1].strip()
                        # Clean up
                        step1 = re.sub(r'[,\.;]+$', '', step1)
                        step2 = re.sub(r'^[,\.;]+\s*', '', step2)
                        if len(step1) > 5 and len(step2) > 5:
                            steps = [step1, step2]
                            return {
                                'intent': 'multi_step',
                                'confidence': 0.7,
                                'entities': {
                                    'steps': steps,
                                    'step_count': len(steps)
                                },
                                'requires_llm': False,
                                'reasoning': f'Detected multi-step operation with {len(steps)} steps (separator extraction)',
                                'already_checked': True
                            }
            
            # Try splitting on "and" if it's not an ISMS operation
            if 'and' in message_lower and len(steps) < 2:
                isms_keywords = ['reconcile', 'compare', 'reconciliation', 'gap', 'difference', 'drift']
                if not any(keyword in message_lower for keyword in isms_keywords):
                    # Split on "and" but only if both parts are substantial
                    parts = re.split(r'\s+and\s+', message_lower, 1)
                    if len(parts) == 2:
                        step1 = parts[0].strip()
                        step2 = parts[1].strip()
                        # Make sure both parts are verbs/actions, not just nouns
                        action_verbs = ['create', 'convert', 'run', 'execute', 'deploy', 'test', 'build', 'link', 'add', 'remove', 'delete', 'update']
                        if any(verb in step1 for verb in action_verbs) and any(verb in step2 for verb in action_verbs):
                            if len(step1) > 5 and len(step2) > 5:
                                steps = [step1, step2]
                                return {
                                    'intent': 'multi_step',
                                    'confidence': 0.7,
                                    'entities': {
                                        'steps': steps,
                                        'step_count': len(steps)
                                    },
                                    'requires_llm': False,
                                    'reasoning': f'Detected multi-step operation with {len(steps)} steps (and-separated)',
                                    'already_checked': True
                                }
        
        # If we still can't extract steps but have strong indicators, return None
        # This allows other handlers to try
        # Only return multi-step if we successfully extracted at least 2 steps
        if len(steps) < 2:
            return None
        
        return None
    
    # ==================== HELPER METHODS ====================
    
    def _extract_language(self, message_lower: str, prepositions: List[str]) -> Optional[str]:
        """Extract programming language from message"""
        lang_map = {
            'python': 'python', 'py': 'python', 'python3': 'python', 'python2': 'python',
            'javascript': 'javascript', 'js': 'javascript', 'node': 'javascript', 'nodejs': 'javascript',
            'php': 'php', 'php8': 'php', 'php7': 'php',
            'java': 'java',
            'typescript': 'typescript', 'ts': 'typescript',
            'go': 'go', 'golang': 'go',
            'rust': 'rust', 'rs': 'rust',
            'ruby': 'ruby', 'rb': 'ruby',
            'c++': 'cpp', 'cpp': 'cpp', 'cplusplus': 'cpp',
            'c#': 'csharp', 'csharp': 'csharp', 'cs': 'csharp',
            'swift': 'swift',
            'kotlin': 'kotlin',
            'scala': 'scala',
            'r': 'r',
            'matlab': 'matlab'
        }
        
        # Also check for version numbers (e.g., "PHP 8.2", "Python 3.12")
        version_pattern = r'((?:python|php|java|javascript|js|typescript|ts)\s*[\d\.]+)'
        version_match = re.search(version_pattern, message_lower, re.IGNORECASE)
        if version_match:
            lang_with_version = version_match.group(1).lower()
            # Extract base language
            for lang_key in lang_map.keys():
                if lang_key in lang_with_version:
                    return lang_map[lang_key]
        
        for prep in prepositions:
            pattern = rf'{prep}\s+({"|".join(lang_map.keys())})'
            match = re.search(pattern, message_lower)
            if match:
                lang = match.group(1)
                return lang_map.get(lang, lang)
        
        # Try direct language mention without preposition
        for lang_key, lang_value in lang_map.items():
            if lang_key in message_lower:
                return lang_value
        
        return None
    
    def _extract_constraints(self, original: str, message_lower: str) -> List[str]:
        """Extract constraints from message"""
        constraints = []
        patterns = self.patterns['constraints']
        
        # Extract preservation constraints (improved patterns)
        for keyword in patterns['preservation']:
            # Pattern 1: "preserve X"
            pattern1 = rf'{keyword}\s+([^,\.;]+?)(?:\s|,|\.|;|$)'
            matches = re.findall(pattern1, message_lower)
            constraints.extend([f'preserve: {m.strip()}' for m in matches])
            
            # Pattern 2: "preserving X" (gerund form)
            pattern2 = rf'preserving\s+([^,\.;]+?)(?:\s|,|\.|;|$)'
            matches = re.findall(pattern2, message_lower)
            constraints.extend([f'preserve: {m.strip()}' for m in matches])
        
        # Extract requirements (improved patterns)
        for keyword in patterns['requirements']:
            pattern = rf'{keyword}\s+([^,\.;]+?)(?:\s|,|\.|;|$)'
            matches = re.findall(pattern, message_lower)
            constraints.extend([f'required: {m.strip()}' for m in matches])
        
        # Extract prohibitions (improved patterns)
        for keyword in patterns['prohibitions']:
            pattern = rf'{keyword}\s+([^,\.;]+?)(?:\s|,|\.|;|$)'
            matches = re.findall(pattern, message_lower)
            constraints.extend([f'prohibited: {m.strip()}' for m in matches])
        
        # Extract technical constraints (e.g., "using Fibers", "with strict typing")
        tech_patterns = [
            r'using\s+([A-Za-z0-9_\s-]+?)(?:\s|,|\.|;|$)',
            r'with\s+([A-Za-z0-9_\s-]+?)(?:\s|,|\.|;|$)',
            r'maintaining\s+([A-Za-z0-9_\s-]+?)(?:\s|,|\.|;|$)',
            r'ensuring\s+([A-Za-z0-9_\s-]+?)(?:\s|,|\.|;|$)',
        ]
        for pattern in tech_patterns:
            matches = re.findall(pattern, message_lower)
            constraints.extend([f'technical: {m.strip()}' for m in matches if len(m.strip()) < 50])
        
        return constraints
    
    def _extract_object_names(self, original: str, message_lower: str) -> List[str]:
        """Extract ISMS object names"""
        objects = []
        
        # Pattern 1: Quoted names
        quoted = re.findall(r"['\"]([A-Za-z0-9_\s-]+)['\"]", original)
        objects.extend(quoted)
        
        # Pattern 2: Capitalized names (likely object names)
        capitalized = re.findall(r'\b([A-Z][A-Za-z0-9_\s-]{2,})\b', original)
        # Filter out common words
        common_words = {'The', 'This', 'That', 'These', 'Those', 'Production', 'Staging'}
        objects.extend([obj for obj in capitalized if obj not in common_words])
        
        return list(set(objects))  # Remove duplicates
    
    def _extract_domains(self, message_lower: str) -> List[str]:
        """Extract domain/environment names"""
        domains = []
        domain_keywords = ['production', 'staging', 'development', 'dr', 'disaster recovery', 'test']
        
        for keyword in domain_keywords:
            if keyword in message_lower:
                domains.append(keyword)
        
        return domains
    
    def _extract_comparison_type(self, message_lower: str) -> str:
        """Extract type of comparison"""
        if 'gap' in message_lower or 'missing' in message_lower:
            return 'gap_analysis'
        elif 'drift' in message_lower or 'difference' in message_lower:
            return 'drift_detection'
        elif 'reconcile' in message_lower:
            return 'reconciliation'
        else:
            return 'comparison'
    
    def _extract_path_or_scope(self, original: str, message_lower: str) -> Optional[str]:
        """Extract file path or scope from dangerous operation"""
        # Pattern 1: Quoted paths
        quoted_pattern = r"['\"]([^'\"]+)['\"]"
        match = re.search(quoted_pattern, original)
        if match:
            return match.group(1)
        
        # Pattern 2: Paths with directory separators
        path_pattern = r'([A-Za-z0-9_\-\.]+/[A-Za-z0-9_\-\./]*)'
        match = re.search(path_pattern, original)
        if match:
            return match.group(1)
        
        # Pattern 3: Directory mentions ("in the X directory", "from X folder")
        dir_pattern = r'(?:in|from|to|at)\s+(?:the\s+)?([A-Za-z0-9_\-\./]+)\s+(?:directory|folder|path)'
        match = re.search(dir_pattern, message_lower)
        if match:
            return match.group(1)
        
        # Pattern 4: Simple directory names after "in" or "from"
        simple_dir_pattern = r'(?:in|from)\s+([A-Za-z0-9_\-]+/?)'
        match = re.search(simple_dir_pattern, message_lower)
        if match:
            return match.group(1)
        
        return None
    
    def _extract_steps(self, original: str, message_lower: str) -> List[str]:
        """Extract individual steps from multi-step operation"""
        steps = []
        
        # Pattern 1: Explicit step numbering ("Step 1:", "Step 2:", etc.)
        # Improved pattern to capture full step content
        step_pattern = r'(?:step\s*\d+|first|second|third|fourth|fifth|finally|last)[:\.]?\s*([^,\.]+?)(?:\s*(?:,|\.|$|then|and|next|step))'
        step_matches = re.findall(step_pattern, message_lower, re.IGNORECASE)
        if step_matches:
            steps = [step.strip() for step in step_matches if step.strip() and len(step.strip()) > 3]
            if len(steps) >= 2:
                return steps
        
        # Pattern 2: Split by period followed by lowercase (sentence boundary)
        # Handles: "Create person 'John'.assign his role to 'DPO'"
        period_pattern = r'\.\s*([a-z])'  # Period followed by lowercase (new sentence)
        period_matches = list(re.finditer(period_pattern, message_lower))
        if len(period_matches) >= 1:
            # Split at periods, but keep the period with the first part
            parts = re.split(r'\.\s+(?=[a-z])', original)
            if len(parts) >= 2:
                # Clean up each part
                cleaned_parts = []
                for i, part in enumerate(parts):
                    part = part.strip()
                    if part:
                        # If not the last part, add period back
                        if i < len(parts) - 1 and not part.endswith('.'):
                            part += '.'
                        cleaned_parts.append(part)
                if len(cleaned_parts) >= 2:
                    return cleaned_parts
        
        # Pattern 3: Split by connectors (then, and, after, next, also)
        # CRITICAL: Use original message to preserve case and quotes, but match on lowercase
        connectors = ['then', 'and', 'after', 'next', 'also', 'finally']
        # More sophisticated splitting that preserves context
        connector_pattern = r'\s+(?:' + '|'.join(connectors) + r')\s+'
        # Find connector positions in lowercase, but extract from original
        parts_lower = re.split(connector_pattern, message_lower)
        
        if len(parts_lower) > 1:
            # Extract corresponding parts from original message
            cleaned_parts = []
            current_pos = 0
            for i, part_lower in enumerate(parts_lower):
                part_lower = part_lower.strip()
                if not part_lower:
                    continue
                
                # Find this part in the original message (case-insensitive)
                # Search from current position
                search_text = original[current_pos:].lower()
                part_start = search_text.find(part_lower)
                if part_start >= 0:
                    # Extract from original message
                    actual_start = current_pos + part_start
                    actual_end = actual_start + len(part_lower)
                    part = original[actual_start:actual_end]
                    current_pos = actual_end
                else:
                    # Fallback: use lowercase version
                    part = part_lower
                
                part = part.strip()
                part = re.sub(r'^(?:first|second|third|then|and|next|also|finally)[:\.]?\s*', '', part, flags=re.IGNORECASE)
                part = re.sub(r'[,\.;]+$', '', part)
                if part and len(part) > 3:  # Filter out very short fragments
                    cleaned_parts.append(part)
            
            if len(cleaned_parts) >= 2:
                steps = cleaned_parts
        
        # Pattern 3: Period-separated commands (e.g., "Create person 'John'.assign his role to 'DPO'")
        # CRITICAL: Extract from original to preserve case and quotes
        if not steps or len(steps) < 2:
            # Look for patterns like "do X. assign Y" or "X. then Y" (period followed by action)
            # Pattern: sentence ending with period, followed by lowercase action word
            period_sep_pattern = r'([^\.]+\.)\s*([a-z][^\.]+?)(?:\.|$)'
            match = re.search(period_sep_pattern, message_lower)
            if match:
                # Extract from original using match positions
                step1_start = match.start(1)
                step1_end = match.end(1)
                step2_start = match.start(2)
                step2_end = match.end(2)
                step1 = original[step1_start:step1_end].strip()
                step2 = original[step2_start:step2_end].strip()
                step1 = step1.rstrip('.')
                if len(step1) > 3 and len(step2) > 3:
                    steps = [step1, step2]
        
        # Pattern 4: Sequential commands separated by punctuation with connectors
        # CRITICAL: Extract from original to preserve case and quotes
        if not steps or len(steps) < 2:
            # Look for patterns like "do X. Then do Y." or "X, then Y"
            sequential_pattern = r'([^,\.]+?)(?:[,\.]\s*(?:then|and|next|after|also)\s+)([^,\.]+)'
            match = re.search(sequential_pattern, message_lower)
            if match:
                # Extract from original using match positions
                step1_start = match.start(1)
                step1_end = match.end(1)
                step2_start = match.start(2)
                step2_end = match.end(2)
                step1 = original[step1_start:step1_end].strip()
                step2 = original[step2_start:step2_end].strip()
                if len(step1) > 3 and len(step2) > 3:
                    steps = [step1, step2]
        
        # Pattern 4: Commands with "then" in the middle (e.g., "convert X to Y, then run Z")
        # CRITICAL: Extract from original to preserve case and quotes
        if not steps or len(steps) < 2:
            # Look for "X, then Y" pattern more aggressively (with or without comma)
            then_patterns = [
                r'(.+?),\s*then\s+(.+)',  # With comma
                r'(.+?)\s+then\s+(.+)',   # Without comma
            ]
            for pattern in then_patterns:
                match = re.search(pattern, message_lower)
                if match:
                    # Extract from original using match positions
                    step1_start = match.start(1)
                    step1_end = match.end(1)
                    step2_start = match.start(2)
                    step2_end = match.end(2)
                    step1 = original[step1_start:step1_end].strip()
                    step2 = original[step2_start:step2_end].strip()
                    step1 = re.sub(r'[,\.;]+$', '', step1)
                    # Make sure both parts are substantial
                    if len(step1) > 5 and len(step2) > 5:
                        steps = [step1, step2]
                        break
        
        # Pattern 5: "X to Y, then Z"
        # CRITICAL: Extract from original to preserve case and quotes
        if not steps or len(steps) < 2:
            # Pattern: "convert/transform X to Y, then do Z"
            # More flexible: match anything before "to/into X, then Y"
            transform_then_pattern = r'(.+?\s+(?:to|into)\s+[^,]+?),\s*then\s+(.+)'
            match = re.search(transform_then_pattern, message_lower)
            if match:
                # Extract from original using match positions
                step1_start = match.start(1)
                step1_end = match.end(1)
                step2_start = match.start(2)
                step2_end = match.end(2)
                step1 = original[step1_start:step1_end].strip()
                step2 = original[step2_start:step2_end].strip()
                step1 = re.sub(r'[,\.;]+$', '', step1)
                if len(step1) > 5 and len(step2) > 5:
                    steps = [step1, step2]
        
        # Pattern 6: Direct "then" splitting (fallback)
        # CRITICAL: Extract from original to preserve case and quotes
        if not steps or len(steps) < 2:
            # Simple split on "then" - most reliable
            if 'then' in message_lower:
                # Find "then" in original (case-insensitive)
                then_match = re.search(r'\s+then\s+', original, re.IGNORECASE)
                if then_match:
                    step1 = original[:then_match.start()].strip()
                    step2 = original[then_match.end():].strip()
                    # Clean up
                    step1 = re.sub(r'[,\.;]+$', '', step1)
                    step2 = re.sub(r'^[,\.;]+\s*', '', step2)
                    if len(step1) > 5 and len(step2) > 5:
                        steps = [step1, step2]
        
        return steps
    
    def get_route_suggestion(self, intent_result: Dict) -> Dict:
        """
        Suggest routing based on detected intent.
        
        Returns:
            Dict with route, handler, and confidence
        """
        intent = intent_result.get('intent')
        entities = intent_result.get('entities', {})
        requires_llm = intent_result.get('requires_llm', True)
        
        if intent == 'isms_reconciliation':
            return {
                'route': 'isms_reconciliation',
                'handler': '_handleISMSReconciliation',
                'data': {
                    'objects': entities.get('objects', []),
                    'domains': entities.get('domains', []),
                    'comparison_type': entities.get('comparison_type', 'comparison')
                },
                'confidence': intent_result.get('confidence', 0.7),
                'requires_llm': requires_llm
            }
        
        elif intent == 'safety_check':
            return {
                'route': 'safety_check',
                'handler': '_handleSafetyCheck',
                'data': {
                    'operation': entities.get('operation'),
                    'target': entities.get('target'),
                    'is_bulk': entities.get('is_bulk', False),
                    'is_protected_path': entities.get('is_protected_path', False),
                    'action': intent_result.get('action', 'confirm')
                },
                'confidence': 1.0,  # High confidence for safety
                'requires_llm': False
            }
        
        elif intent == 'multi_step':
            return {
                'route': 'multi_step',
                'handler': '_handleMultiStep',
                'data': {
                    'steps': entities.get('steps', []),
                    'step_count': entities.get('step_count', 0)
                },
                'confidence': intent_result.get('confidence', 0.7),
                'requires_llm': requires_llm
            }
        
        elif intent == 'multi_step':
            return {
                'route': 'multi_step',
                'handler': '_handleMultiStep',
                'data': {
                    'steps': entities.get('steps', []),
                    'step_count': entities.get('step_count', 0)
                },
                'confidence': intent_result.get('confidence', 0.7),
                'requires_llm': requires_llm
            }
        
        return {
            'route': 'unknown',
            'handler': None,
            'data': {},
            'confidence': 0.3,
            'requires_llm': True
        }
