"""
MCP (Micro-Agentic Protocol) Server

Provides LLM-based intent understanding and tool execution for complex ISMS operations
that require reasoning beyond simple pattern matching.

Operations handled by MCP:
- Linking objects (link, unlink, connect, associate)
- Analysis operations (analyze, understand, assess)
- Natural language queries (complex questions about ISMS data)

CRUD operations remain in ISMSCoordinator (fast, reliable, pattern-based).
"""

from .server import MCPServer

__all__ = ['MCPServer']
