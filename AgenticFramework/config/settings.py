"""Configuration and settings management"""
import os
from pathlib import Path
from typing import Dict
from dotenv import load_dotenv

# Load .env from AgenticFramework directory (explicit path)
try:
    _agenticFrameworkDir = Path(__file__).parent.parent
    _envFile = _agenticFrameworkDir / '.env'
    if _envFile.exists() and _envFile.is_file():
        try:
            load_dotenv(_envFile, override=False)
        except (PermissionError, OSError) as e:
            # Permission denied or other file access error - try project root
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
        # Try project root
        _projectRoot = _agenticFrameworkDir.parent
        _envFileProject = _projectRoot / '.env'
        if _envFileProject.exists() and _envFileProject.is_file():
            try:
                load_dotenv(_envFileProject, override=False)
            except Exception:
                load_dotenv(override=False)
        else:
            # Fallback to default behavior
            load_dotenv(override=False)
except Exception as e:
    # If path resolution fails, just use default
    load_dotenv(override=False)


class Settings:
    """Centralized configuration"""
    
    # LLM Configuration - Gemini
    LLM_BACKEND = os.getenv('LLM_BACKEND', 'gemini')
    LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'gemini')
    LLM_MODEL = os.getenv('LLM_MODEL', 'gemini-2.5-flash')
    LLM_MAX_TOKENS = int(os.getenv('LLM_MAX_TOKENS', '512'))
    
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
    GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
    
    # Verinice (optional)
    VERINICE_ENABLED = os.getenv('VERINICE_ENABLED', 'true').lower() == 'true'
    VERINICE_API_URL = os.getenv('VERINICE_API_URL', 'http://localhost:8070')
    SPARKSBM_SCRIPTS_PATH = os.getenv('SPARKSBM_SCRIPTS_PATH', '')
    
    # Output directory
    OUTPUT_DIR = os.getenv('OUTPUT_DIR', 'output')
    
    # Memory settings
    MAX_MEMORY_HISTORY = int(os.getenv('MAX_MEMORY_HISTORY', '1000'))
    
    @classmethod
    def getAvailableGeminiModels(cls) -> Dict[str, str]:
        """Get list of available Gemini models with descriptions"""
        return {
            'gemini-2.5-flash': 'Fast and cost-effective (RECOMMENDED)',
            'gemini-1.5-flash': 'Fast and efficient',
            'gemini-1.5-pro': 'Most capable model',
        }
    
    @classmethod
    def getLLMConfig(cls) -> Dict:
        """Get LLM configuration dict"""
        return {
            'backend': cls.LLM_BACKEND,
            'provider': cls.LLM_PROVIDER,
            'model': cls.LLM_MODEL,
            'max_tokens': cls.LLM_MAX_TOKENS,
            'gemini_model': cls.GEMINI_MODEL,
            'gemini_available_models': cls.getAvailableGeminiModels()
        }
    
    @classmethod
    def validate(cls) -> Dict:
        """Validate configuration"""
        errors = []
        warnings = []
        
        if not cls.GEMINI_API_KEY:
            errors.append("GEMINI_API_KEY required")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
