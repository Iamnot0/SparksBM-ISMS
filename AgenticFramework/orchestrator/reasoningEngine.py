"""
Reasoning Engine - Abstract Interface for LLM Integration

This module provides a vendor-independent interface for reasoning engines.
It allows the system to use different LLM providers (Gemini, etc.)
without changing the core application logic.

Architecture:
- ReasoningEngine: Abstract base class defining the interface
- GeminiReasoningEngine: Gemini API implementation
- FallbackReasoningEngine: Graceful degradation when LLM unavailable

Usage:
    engine = GeminiReasoningEngine()
    response = engine.reason("What is ISMS?", context={...})
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional, Any, List
import os
import re
from dotenv import load_dotenv
from pathlib import Path

# Try to import Google Gemini
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None

# Load environment variables
_agenticFrameworkDir = Path(__file__).parent.parent
_envFile = _agenticFrameworkDir / '.env'
if _envFile.exists():
    load_dotenv(_envFile)
else:
    load_dotenv()


class ReasoningEngine(ABC):
    """
    Abstract base class for reasoning engines.
    
    All reasoning engine implementations must inherit from this class
    and implement the reason() method.
    """
    
    @abstractmethod
    def reason(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Process a query and return a reasoned response.
        
        Args:
            query: The user's question or command
            context: Optional context information (conversation history, documents, etc.)
            
        Returns:
            str: The reasoning engine's response
            
        Raises:
            Exception: If reasoning fails
        """
        pass
    
    @abstractmethod
    def isAvailable(self) -> bool:
        """
        Check if the reasoning engine is available and ready to use.
        
        Returns:
            bool: True if engine is available, False otherwise
        """
        pass


class GeminiReasoningEngine(ReasoningEngine):
    """
    Gemini API reasoning engine.
    
    This implementation uses Google Gemini API.
    It provides cloud-based reasoning capabilities with API key authentication.
    
    Features:
    - Cloud-based execution (accessible from anywhere)
    - API key authentication
    - Fast response times
    - Free tier available
    
    Configuration:
    - Default model: gemini-2.5-flash (from env or default)
    - API key: GEMINI_API_KEY environment variable (required)
    """
    
    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = 60,
        temperature: float = 0.7,
        max_tokens: int = 250,
        response_mode: str = "concise"
    ):
        """
        Initialize Gemini API reasoning engine.
        
        Args:
            model: Gemini model name (default: gemini-2.5-flash, from env or default)
            api_key: API key for authentication (default: from GEMINI_API_KEY env)
            timeout: Request timeout in seconds (default: 60)
            temperature: Sampling temperature 0.0-1.0 (default: 0.7)
            max_tokens: Maximum tokens to generate (default: 250 for concise mode)
            response_mode: Response style - "concise" (default), "normal", or "detailed"
        """
        if not GEMINI_AVAILABLE:
            raise RuntimeError("Google Generative AI library not installed. Run: pip install google-generativeai")
        
        # Default to gemini-2.5-flash
        self.model_name = model or os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
        self.api_key = api_key or os.getenv('GEMINI_API_KEY', '')
        self.timeout = timeout
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.response_mode = response_mode  # concise | normal | detailed
        self._is_available_cache = None
        self.geminiClient = None
        
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is required. Set it in environment variables or pass as api_key parameter.")
        
        # Configure Gemini
        try:
            genai.configure(api_key=self.api_key)
            self.geminiClient = genai.GenerativeModel(self.model_name)
        except Exception as e:
            raise RuntimeError(f"Gemini setup failed: {e}")
    
    def reason(self, query: str, context: Optional[Dict[str, Any]] = None, system_prompt: Optional[str] = None, response_mode: Optional[str] = None) -> str:
        """
        Process a query using Gemini API and return a response.
        
        Args:
            query: The user's question or command
            context: Optional context (conversation history, documents, etc.)
            system_prompt: Optional system prompt to guide the LLM
            response_mode: Override default response mode ("concise", "normal", "detailed")
            
        Returns:
            str: The model's response (truncated if exceeds limits)
            
        Raises:
            Exception: If Gemini API call fails
        """
        if not self.isAvailable():
            raise Exception("Gemini API is not available. Please check your API key and network connection.")
        
        # Use provided mode or default
        mode = response_mode or self.response_mode
        
        # DEBUG: Log mode and question type
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[ReasoningEngine] Query: {query[:50]}... | Mode: {mode} | QuestionType: {self._detectQuestionType(query)}")
        
        # Detect question type for appropriate prompt
        question_type = self._detectQuestionType(query)
        
        # Build prompt with question-type aware system prompt
        enhanced_system_prompt = self._getSystemPromptForMode(mode, question_type, system_prompt)
        
        # Build full prompt with context
        full_prompt = self._buildPrompt(query, context, enhanced_system_prompt)
        
        # Adjust max_tokens based on mode if default is used
        effective_max_tokens = self.max_tokens
        if self.max_tokens == 250:  # Default value
            mode_limits = {
                "concise": 300,  # Increased to prevent cut-off responses
                "normal": 300,
                "detailed": 600
            }
            effective_max_tokens = mode_limits.get(mode, 250)
        
        try:
            response = self.geminiClient.generate_content(
                full_prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=effective_max_tokens,
                    temperature=self.temperature
                )
            )
            
            # Extract response text
            try:
                response_text = response.text.strip()
            except (AttributeError, ValueError) as textError:
                # Fallback to manual extraction
                if hasattr(response, 'candidates') and response.candidates:
                    candidate = response.candidates[0]
                    finish_reason = getattr(candidate, 'finish_reason', None)
                    if finish_reason == 2:  # SAFETY - content blocked
                        raise RuntimeError("Content was blocked by safety filters. Please rephrase your request.")
                    elif hasattr(candidate, 'content') and hasattr(candidate.content, 'parts') and candidate.content.parts:
                        response_text = candidate.content.parts[0].text.strip()
                    else:
                        raise RuntimeError(f"Gemini response has no valid content. Finish reason: {finish_reason}")
                else:
                    raise RuntimeError(f"Gemini response has no valid content: {textError}")
            
            # DEBUG: Log raw response length
            raw_word_count = len(response_text.split())
            logger.info(f"[ReasoningEngine] Raw response: {raw_word_count} words, Mode: {mode}")
            
            # Apply safety truncation and markdown stripping
            response_text = self._truncateResponse(response_text, mode)
            
            # DEBUG: Log after truncation
            truncated_word_count = len(response_text.split())
            has_md_before = '**' in response_text or '#' in response_text or '•' in response_text
            logger.info(f"[ReasoningEngine] After truncate: {truncated_word_count} words, Has markdown: {has_md_before}")
            
            # Final safety check: ALWAYS strip markdown for concise mode (no exceptions)
            if mode == "concise":
                # Multiple passes of aggressive markdown removal
                for _ in range(3):  # Multiple passes to catch nested/edge cases
                    response_text = response_text.replace('**', '').replace('*', '')
                    response_text = response_text.replace('#', '').replace('•', '-').replace('`', '')
                    response_text = response_text.replace('__', '').replace('_', ' ')
                    response_text = re.sub(r'\*\*[^*]*\*\*', '', response_text)
                    response_text = re.sub(r'^#+\s+', '', response_text, flags=re.MULTILINE)
                    response_text = re.sub(r'^\s*[•\-\*]\s+', '', response_text, flags=re.MULTILINE)
                # Clean up whitespace
                response_text = re.sub(r'\s+', ' ', response_text)  # Multiple spaces to single
                response_text = re.sub(r'\n\s*\n+', '\n', response_text)  # Multiple newlines
                response_text = response_text.strip()
                
                # Verify no markdown remains - if it does, strip one more time
                if '**' in response_text or '#' in response_text or '•' in response_text:
                    response_text = response_text.replace('**', '').replace('*', '').replace('#', '').replace('•', '')
                    response_text = re.sub(r'\s+', ' ', response_text).strip()
            
            # DEBUG: Log final response
            final_word_count = len(response_text.split())
            has_md_final = '**' in response_text or '#' in response_text or '•' in response_text
            logger.info(f"[ReasoningEngine] Final response: {final_word_count} words, Has markdown: {has_md_final}")
            
            return response_text
            
        except Exception as e:
            error_msg = str(e).lower()
            error_str = str(e)
            
            if "quota" in error_msg or "429" in error_str or "rate limit" in error_msg or "exhausted" in error_msg:
                raise Exception(
                    "Gemini API daily quota exceeded. "
                    "You have reached your daily request limit. "
                    "Please wait 24 hours or upgrade your API plan. "
                    "Both gemini-cli and SparksBM share the same API quota."
                )
            
            if "401" in error_str or "403" in error_str or "invalid api key" in error_msg or "authentication" in error_msg:
                raise Exception(
                    "Gemini API authentication failed. "
                    "Please check your GEMINI_API_KEY environment variable."
                )
            
            if "blocked" in error_msg or "safety" in error_msg:
                raise Exception("Content was blocked by Gemini safety filters. Please rephrase your request.")
            
            if "timeout" in error_msg or "connection" in error_msg or "network" in error_msg:
                raise Exception(f"Network error connecting to Gemini API: {error_str}")
            
            if "location" in error_msg and "not supported" in error_msg:
                raise Exception(
                    "Gemini API is not available in your current location. "
                    "Google restricts API access in certain regions (e.g., EU, UK, China). "
                    "Please check Google's supported regions or use a VPN."
                )
            
            # Generic error
            raise Exception(f"Gemini API request failed: {error_str}")
    
    def isAvailable(self) -> bool:
        """
        Check if Gemini API is available and accessible.
        
        Returns:
            bool: True if Gemini API is available, False otherwise
        """
        # Basic validation: API key must be present and client initialized
        if not self.api_key or not self.geminiClient:
            return False
        
        # Use cached result if available (valid for 5 minutes)
        # For cloud API, we assume it's available if API key is set and client is initialized
        # Actual availability will be tested on first request
        return True
    
    def _detectQuestionType(self, query: str) -> str:
        """
        Detect question type to apply appropriate prompt style.
        
        Returns:
            str: Question type - "capabilities", "knowledge", "analysis", "howto", "general"
        """
        query_lower = query.lower().strip()
        
        # Capabilities questions
        if any(phrase in query_lower for phrase in ["what can you", "what do you", "what are your", "your capabilities", "what can", "help me with"]):
            return "capabilities"
        
        # How-to questions
        if any(phrase in query_lower for phrase in ["how do", "how can", "how to", "how should", "steps to", "way to"]):
            return "howto"
        
        # Knowledge questions (what is, what are, explain, define)
        if any(phrase in query_lower for phrase in ["what is", "what are", "what does", "explain", "define", "tell me about", "describe"]):
            return "knowledge"
        
        # Analysis questions
        if any(phrase in query_lower for phrase in ["analyze", "analysis", "summarize", "summary", "main points", "key points"]):
            return "analysis"
        
        return "general"
    
    def _getSystemPromptForMode(self, mode: str, question_type: str, base_prompt: Optional[str] = None) -> str:
        """
        Generate appropriate system prompt based on response mode and question type.
        
        Args:
            mode: Response mode ("concise", "normal", "detailed")
            question_type: Question type ("capabilities", "knowledge", "analysis", "howto", "general")
            base_prompt: Optional base prompt to enhance
            
        Returns:
            str: Complete system prompt with constraints
        """
        # CRITICAL: Put response constraints FIRST so they take priority
        prompt_parts = []
        
        # Mode-specific constraints (MUST BE FIRST)
        if mode == "concise":
            prompt_parts.append("=== CRITICAL: YOU MUST FOLLOW THESE RULES ===")
            prompt_parts.append("1. Maximum 150 words.")
            prompt_parts.append("2. ABSOLUTELY NO markdown: no **bold**, no # headers, no bullet points (•), no lists, no code blocks.")
            prompt_parts.append("3. Write in plain text sentences only. Use commas and periods, not formatting.")
            prompt_parts.append("4. NO introductions like 'Here is...' or 'Let me explain...'. Start directly with the answer.")
            prompt_parts.append("5. NO conclusions or summaries. Just answer the question.")
            prompt_parts.append("6. If you use formatting, your response is WRONG. Plain text only.")
            prompt_parts.append("=== END RULES ===")
            prompt_parts.append("")
        elif mode == "normal":
            prompt_parts.append("RESPONSE RULES:")
            prompt_parts.append("- Maximum 250 words.")
            prompt_parts.append("- Use minimal formatting.")
        elif mode == "detailed":
            prompt_parts.append("RESPONSE RULES:")
            prompt_parts.append("- Maximum 500 words.")
            prompt_parts.append("- You may use formatting if helpful.")
        
        # Question-type specific guidance
        if question_type == "capabilities":
            prompt_parts.append("- List 3-5 capabilities in one short paragraph (no bullets, no formatting).")
        elif question_type == "knowledge":
            prompt_parts.append("- Answer in 2-3 sentences. Be precise and factual. No formatting.")
        elif question_type == "howto":
            prompt_parts.append("- Provide brief step-by-step instructions in plain text. No numbering unless essential.")
        elif question_type == "analysis":
            prompt_parts.append("- Focus on key insights in 2-3 sentences. Be concise.")
        
        prompt_parts.append("")
        
        if base_prompt:
            prompt_parts.append(base_prompt)
        
        return "\n".join(prompt_parts)
    
    def _stripMarkdown(self, text: str) -> str:
        """
        Remove markdown formatting from text.
        
        Args:
            text: Text that may contain markdown
            
        Returns:
            str: Plain text with markdown removed
        """
        text = re.sub(r'\*\*([^*\n]+)\*\*', r'\1', text)
        text = re.sub(r'\*([^*\n]+)\*', r'\1', text)
        text = re.sub(r'__([^_\n]+)__', r'\1', text)
        text = re.sub(r'_([^_\n]+)_', r'\1', text)
        
        text = re.sub(r'^#+\s+(.+)$', r'\1', text, flags=re.MULTILINE)
        
        text = re.sub(r'^[\s]*[•\-\*]\s+', '', text, flags=re.MULTILINE)
        
        text = re.sub(r'```[^`]*```', '', text, flags=re.DOTALL)
        text = re.sub(r'`([^`\n]+)`', r'\1', text)
        
        text = re.sub(r'^\d+[\.\)]\s+', '', text, flags=re.MULTILINE)
        
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            line = re.sub(r'^\s*\*\*([^*]+)\*\*\s*$', r'\1', line)
            if ':' in line and len(line.strip()) < 50:
                line = re.sub(r'^\s*\*\*?([^*:]+):\*\*?\s*$', r'\1:', line)
            cleaned_lines.append(line)
        text = '\n'.join(cleaned_lines)
        
        # Clean up extra whitespace
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)  # Multiple newlines
        text = re.sub(r'  +', ' ', text)  # Multiple spaces
        text = re.sub(r'^\s+', '', text, flags=re.MULTILINE)  # Leading spaces on lines
        text = text.strip()
        
        return text
    
    def _truncateResponse(self, response: str, mode: str) -> str:
        """
        Safety net: Strip markdown and truncate response if it exceeds reasonable limits.
        
        Args:
            response: The response text
            mode: Response mode to determine limit
            
        Returns:
            str: Cleaned and truncated response if needed
        """
        # ALWAYS strip markdown formatting for concise mode (safety net)
        if mode == "concise":
            response = self._stripMarkdown(response)
            # Strip again if markdown still present (more aggressive)
            if '**' in response or '#' in response or '•' in response:
                # More aggressive stripping
                response = response.replace('**', '').replace('*', '').replace('#', '').replace('•', '-').replace('`', '')
                # Clean up any double spaces or formatting artifacts
                response = re.sub(r'\s+', ' ', response)
                response = re.sub(r'\n\s*\n+', '\n', response)
        
        # Word limits by mode (strict)
        word_limits = {
            "concise": 80,  # Strict limit for concise mode
            "normal": 300,
            "detailed": 600
        }
        
        limit = word_limits.get(mode, 300)
        words = response.split()
        
        if len(words) > limit:
            # Truncate at sentence boundary if possible
            truncated = " ".join(words[:limit])
            # Try to end at sentence
            last_period = truncated.rfind('.')
            last_exclamation = truncated.rfind('!')
            last_question = truncated.rfind('?')
            last_sentence = max(last_period, last_exclamation, last_question)
            
            if last_sentence > limit * 0.7:  # If we found a sentence end reasonably close
                return truncated[:last_sentence + 1]
            else:
                return truncated + "..."
        
        return response
    
    def _buildPrompt(self, query: str, context: Optional[Dict[str, Any]] = None, system_prompt: Optional[str] = None) -> str:
        """
        Build full prompt string for Gemini API.
        
        Args:
            query: The user's question
            context: Optional context information
            system_prompt: Optional system prompt
            
        Returns:
            str: Full prompt string
        """
        parts = []
        
        if system_prompt:
            parts.append(system_prompt)
        elif context and "system" in context:
            parts.append(str(context["system"]))
        
        if context and "documents" in context and context["documents"]:
            doc_context = "Relevant Documents:\n"
            for doc in context["documents"][:2]:  # Top 2 documents
                doc_context += f"- {doc}\n"
            parts.append(doc_context)
        
        if context and "history" in context and context["history"]:
            history_text = "Previous conversation:\n"
            for msg in context["history"][-5:]:  # Last 5 messages for context
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role in ["user", "assistant"]:
                    history_text += f"{role.capitalize()}: {content}\n"
            parts.append(history_text)
        
        parts.append(f"User: {query}")
        
        return "\n\n".join(parts)
    
    def __repr__(self) -> str:
        """String representation of the engine."""
        api_key_display = f"***{self.api_key[-4:]}" if self.api_key and len(self.api_key) > 4 else "***"
        return f"GeminiReasoningEngine(model={self.model_name}, api_key={api_key_display})"


class FallbackReasoningEngine(ReasoningEngine):
    """
    Fallback reasoning engine that returns helpful messages when no LLM is available.
    
    This engine is used when Gemini or other LLM services are not available.
    It provides graceful degradation by returning informative messages instead
    of failing silently.
    """
    
    def reason(self, query: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Return a helpful fallback message with context-aware suggestions.
        """
        query_lower = query.lower()
        
        suggestions = []
        if 'create' in query_lower:
            suggestions.append("- 'create scope MyScope'")
            suggestions.append("- 'create asset Server1'")
        if 'list' in query_lower or 'show' in query_lower:
            suggestions.append("- 'list scopes'")
            suggestions.append("- 'list assets'")
        if 'update' in query_lower:
            suggestions.append("- 'update scope MyScope NewName'")
        if 'delete' in query_lower:
            suggestions.append("- 'delete scope MyScope'")
            
        if not suggestions:
            suggestions = [
                "- 'list scopes'",
                "- 'create asset MyAsset'",
                "- 'help'"
            ]
            
        suggestion_str = "\n".join(suggestions)
        
        return (
            "I'm currently operating in offline mode (LLM unavailable). "
            "I can still perform basic ISMS operations using specific commands:\n\n"
            f"{suggestion_str}\n\n"
            "Please try using one of these exact command formats."
        )
    
    def isAvailable(self) -> bool:
        """
        Fallback engine is always available.
        
        Returns:
            bool: Always True
        """
        return True
    
    def __repr__(self) -> str:
        """String representation of the engine."""
        return "FallbackReasoningEngine()"


def createReasoningEngine(preferredEngine: str = "gemini") -> ReasoningEngine:
    """
    Factory function to create a reasoning engine.
    
    This function attempts to create the preferred engine and falls back
    to the FallbackReasoningEngine if the preferred engine is not available.
    
    Args:
        preferredEngine: Engine type to create ("gemini", "fallback")
        
    Returns:
        ReasoningEngine: An instance of a reasoning engine
        
    Example:
        engine = createReasoningEngine("gemini")
        if engine.isAvailable():
            response = engine.reason("What is ISMS?")
    """
    if preferredEngine.lower() == "gemini":
        try:
            engine = GeminiReasoningEngine()
            if engine.isAvailable():
                return engine
            else:
                print("⚠️  Gemini API not available, using fallback engine")
                return FallbackReasoningEngine()
        except ValueError as e:
            # API key missing
            print(f"⚠️  {e}")
            print("⚠️  Using fallback engine")
            return FallbackReasoningEngine()
        except Exception as e:
            print(f"⚠️  Failed to initialize Gemini API: {e}")
            print("⚠️  Using fallback engine")
            return FallbackReasoningEngine()
    
    elif preferredEngine.lower() == "fallback":
        return FallbackReasoningEngine()
    
    else:
        raise ValueError(f"Unknown reasoning engine: {preferredEngine}")


# Example usage
if __name__ == "__main__":
    print("=== Reasoning Engine Test ===\n")
    
    engine = createReasoningEngine("gemini")
    print(f"Engine: {engine}")
    print(f"Available: {engine.isAvailable()}\n")
    
    if engine.isAvailable():
        # Test 1: Simple query
        print("Test 1: Simple Query")
        try:
            response = engine.reason("What is ISMS in one sentence?")
            print(f"Response: {response}\n")
        except Exception as e:
            print(f"Error: {e}\n")
        
        # Test 2: Query with context
        print("Test 2: Query with Context")
        try:
            context = {
                "system": "You are an ISMS expert assistant.",
                "history": [
                    {"role": "user", "content": "What is a scope?"},
                    {"role": "assistant", "content": "A scope defines the boundaries of an ISMS."}
                ]
            }
            response = engine.reason("How do I create one?", context)
            print(f"Response: {response}\n")
        except Exception as e:
            print(f"Error: {e}\n")
    else:
        print("⚠️  Gemini API not available.")
        print("⚠️  Please set GEMINI_API_KEY environment variable.")
