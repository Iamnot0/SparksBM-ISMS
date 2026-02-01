"""
MCP Tools - Complex ISMS operations requiring LLM reasoning

These tools use LLM for intent understanding and VeriniceTool for actual operations.
"""

from .linking import link_objects, unlink_objects
from .analyze import analyze_object
from .compare import compare_objects

__all__ = ['link_objects', 'unlink_objects', 'analyze_object', 'compare_objects']
