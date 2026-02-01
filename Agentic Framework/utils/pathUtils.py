"""Path resolution utilities"""
import os
import sys
from typing import Optional


def find_sparksbm_scripts_path() -> Optional[str]:
    """
    Find the SparksBM ISMS scripts directory.
    
    Tries in order:
    1. SPARKSBM_SCRIPTS_PATH environment variable
    2. Relative path from Agentic Framework (../../SparksbmISMS/scripts)
    3. Returns None if not found
    
    Returns:
        Absolute path to scripts directory, or None if not found
    """
    from config.settings import Settings
    
    # Try environment variable first
    if Settings.SPARKSBM_SCRIPTS_PATH:
        abs_path = os.path.abspath(Settings.SPARKSBM_SCRIPTS_PATH)
        if os.path.exists(abs_path):
            return abs_path
    
    # Try relative path from Agentic Framework
    current_dir = os.path.dirname(os.path.abspath(__file__))
    relative_path = os.path.join(current_dir, '..', '..', 'SparksbmISMS', 'scripts')
    abs_path = os.path.abspath(relative_path)
    
    if os.path.exists(abs_path):
        return abs_path
    
    return None


def add_to_python_path(path: str) -> bool:
    """
    Add a path to sys.path if it exists and isn't already there.
    
    Args:
        path: Path to add
        
    Returns:
        True if path was added, False otherwise
    """
    if not path or not os.path.exists(path):
        return False
    
    abs_path = os.path.abspath(path)
    if abs_path not in sys.path:
        sys.path.insert(0, abs_path)
        return True
    
    return False
