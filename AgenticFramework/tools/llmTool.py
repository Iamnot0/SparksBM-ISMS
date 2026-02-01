"""LLM integration - Gemini API"""
import os
import json
import re
from pathlib import Path
from typing import Dict, Optional, List, Any
from dotenv import load_dotenv

# Load .env from AgenticFramework directory (explicit path)
try:
    _agenticFrameworkDir = Path(__file__).parent.parent
    _envFile = _agenticFrameworkDir / '.env'
    if _envFile.exists() and _envFile.is_file():
        try:
            load_dotenv(_envFile, override=True)
        except Exception as e:
            logger.warning(f"Could not read .env from AgenticFramework dir: {e}")
            _projectRoot = _agenticFrameworkDir.parent
            _envFileProject = _projectRoot / '.env'
            if _envFileProject.exists() and _envFileProject.is_file():
                try:
                    load_dotenv(_envFileProject, override=False)
                except Exception:
                    load_dotenv(override=False)
            else:
                load_dotenv(override=False)
    else:
        _projectRoot = _agenticFrameworkDir.parent
        _envFileProject = _projectRoot / '.env'
        if _envFileProject.exists() and _envFileProject.is_file():
            try:
                load_dotenv(_envFileProject, override=False)
            except Exception:
                load_dotenv(override=False)
        else:
            load_dotenv(override=False)
except Exception as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"Could not load .env from explicit path: {e}")
    load_dotenv(override=False)

# Try to import Google Gemini
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None


class LLMTool:
    """Wrapper for Gemini LLM provider"""
    
    def __init__(self, provider='gemini'):
        """
        Args:
            provider: 'gemini' (only supported provider)
        """
        self.provider = 'gemini'
        self.conversationHistory = []
        self.geminiApiKey = os.getenv('GEMINI_API_KEY', '')
        
        # Model configuration
        self.primaryModel = os.getenv('GEMINI_MODEL_PRIMARY', os.getenv('GEMINI_MODEL', 'gemini-2.5-flash'))
        self.secondaryModel = os.getenv('GEMINI_MODEL_SECONDARY', 'gemini-1.5-flash')
        self.geminiModel = self.primaryModel
        
        self._setup_gemini()
    
    def _setup_gemini(self):
        """Setup Gemini client"""
        if not GEMINI_AVAILABLE:
            raise RuntimeError("Google Generative AI library not installed. Run: pip install google-generativeai")
        
        if not self.geminiApiKey:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        
        try:
            genai.configure(api_key=self.geminiApiKey)
            self.geminiClient = genai.GenerativeModel(self.geminiModel)
        except Exception as e:
            raise RuntimeError(f"Gemini setup failed: {e}")
    
    def generate(self, prompt: str, systemPrompt: str = "", maxTokens: int = 512, provider: Optional[str] = None, retryOnRateLimit: bool = True, response_format: Optional[str] = None) -> str:
        """
        Generate text response from Gemini LLM
        
        Args:
            prompt: User prompt
            systemPrompt: System instructions
            maxTokens: Max tokens to generate
            provider: Ignored (always uses Gemini)
            retryOnRateLimit: Whether to retry on rate limit errors
            response_format: Optional response format ("json_object" for structured JSON output)
            
        Returns:
            Generated text
        """
        return self._generate_gemini(prompt, systemPrompt, maxTokens, retryOnRateLimit, response_format)
    
    def _generate_gemini(self, prompt: str, systemPrompt: str, maxTokens: int, retryOnRateLimit: bool, response_format: Optional[str] = None) -> str:
        """Generate using Gemini API"""
        import time
        
        def isRateLimitError(error: Exception) -> bool:
            """Check if error is a rate limit error"""
            errorStr = str(error).lower()
            return '429' in errorStr or 'quota' in errorStr or 'rate limit' in errorStr or 'too many requests' in errorStr or 'exhausted' in errorStr
        
        maxRetries = 3 if retryOnRateLimit else 1
        for attempt in range(maxRetries):
            try:
                # Build full prompt with system prompt
                full_prompt = prompt
                if systemPrompt:
                    full_prompt = f"{systemPrompt}\n\n{prompt}"
                
                # Configure generation parameters
                generation_config = {
                    "max_output_tokens": maxTokens,
                    "temperature": 0.7
                }
                
                # For JSON mode, add instruction to return JSON
                if response_format == "json_object":
                    full_prompt = f"{full_prompt}\n\nRespond with valid JSON only, no markdown, no explanations."
                
                # Generate content
                response = self.geminiClient.generate_content(
                    full_prompt,
                    generation_config=genai.types.GenerationConfig(**generation_config)
                )
                
                # Extract response text
                try:
                    result = response.text.strip()
                except AttributeError:
                    if hasattr(response, 'candidates') and response.candidates:
                        candidate = response.candidates[0]
                        if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts') and candidate.content.parts:
                            result = candidate.content.parts[0].text.strip()
                        else:
                            raise RuntimeError("Gemini response has no valid content")
                    else:
                        raise RuntimeError("Gemini response has no valid content")
                
                # For JSON mode, try to extract JSON if wrapped
                if response_format == "json_object":
                    # Try to extract JSON from response
                    json_match = re.search(r'\{[^}]+\}', result, re.DOTALL)
                    if json_match:
                        result = json_match.group(0)
                
                self.conversationHistory.append({
                    'provider': 'gemini',
                    'prompt': prompt,
                    'response': result,
                    'response_format': response_format
                })
                return result
            except Exception as e:
                errorMsg = str(e)
                if isRateLimitError(e) and attempt < maxRetries - 1:
                    waitTime = 2 ** attempt
                    time.sleep(waitTime)
                    continue
                raise RuntimeError(f"Gemini generation failed: {errorMsg}")
        
        raise RuntimeError("Gemini generation failed after retries")
    
    def analyze(self, data: Any, analysisType: str = "summary", provider: Optional[str] = None) -> str:
        """
        Analyze data using Gemini LLM
        
        Args:
            data: Data to analyze (dict, list, str)
            analysisType: Type of analysis (summary, extract, validate, etc.)
            provider: Ignored (always uses Gemini)
            
        Returns:
            Analysis result as string
        """
        prompt = f"Analyze the following data ({analysisType}):\n\n{data}"
        return self.generate(prompt, provider=provider)
    
    def extractEntities(self, text: str, entityTypes: List[str], provider: Optional[str] = None) -> Dict:
        """
        Extract entities from text using Gemini LLM
        
        Args:
            text: Text to extract from
            entityTypes: List of entity types to find
            provider: Ignored (always uses Gemini)
            
        Returns:
            Dict with extracted entities
        """
        prompt = f"Extract the following entity types from the text: {', '.join(entityTypes)}\n\nText:\n{text}\n\nReturn as JSON."
        response = self.generate(prompt, provider=provider, response_format="json_object")
        
        # Try to parse JSON from response
        try:
            if '```json' in response:
                jsonStr = response.split('```json')[1].split('```')[0].strip()
            elif '```' in response:
                jsonStr = response.split('```')[1].split('```')[0].strip()
            else:
                jsonStr = response.strip()
            
            return json.loads(jsonStr)
        except (json.JSONDecodeError, ValueError, KeyError, IndexError):
            return {'raw': response, 'entities': []}
    
    def getHistory(self) -> List[Dict]:
        """Get conversation history"""
        return self.conversationHistory.copy()
    
    def getAvailableProviders(self) -> List[str]:
        """Get list of available LLM providers"""
        return ['gemini']
