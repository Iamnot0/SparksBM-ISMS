"""Smart response formatter - formats agent responses intelligently"""
from typing import Dict, Any, List, Optional
import json


class ResponseFormatter:
    """Formats agent responses in a user-friendly, intelligent way"""
    
    @staticmethod
    def format(result: Any, resultType: str = 'chat_response', context: Optional[Dict] = None) -> Any:
        """
        Intelligently format any result based on its type and content
        
        Args:
            result: The result to format (dict, list, string, etc.)
            resultType: Type of result ('tool_result', 'chat_response', 'error', etc.)
            context: Optional context about the operation
            
        Returns:
            Formatted result - can be string for chat or dict for structured data (tables)
        """
        if resultType == 'error':
            return ResponseFormatter._formatError(result, context)
        
        if resultType == 'tool_result':
            formatted = ResponseFormatter._formatToolResult(result, context)
            # If result is structured data (table/object_detail), return dict, not string
            if isinstance(formatted, dict) and formatted.get('type') in ['table', 'object_detail']:
                return formatted
            # If result is formatted text (from presenter), return the content
            if isinstance(formatted, dict) and formatted.get('type') == 'text':
                return formatted.get('content', str(formatted))
            return formatted
        
        if isinstance(result, dict) and result.get('type') in ['table', 'object_detail']:
            return result
        
        if isinstance(result, dict) and result.get('type') == 'text':
            return result.get('content', str(result))
        
        if isinstance(result, dict):
            return ResponseFormatter._formatDict(result, context)
        
        if isinstance(result, list):
            return ResponseFormatter._formatList(result, context)
        
        if isinstance(result, str):
            if result.strip().startswith('{') and '"type"' in result and '"table"' in result:
                try:
                    parsed = json.loads(result)
                    if parsed.get('type') in ['table', 'object_detail']:
                        return parsed
                except:
                    pass
            return ResponseFormatter._formatString(result, context)
        
        return str(result)
    
    @staticmethod
    def _formatError(error: Any, context: Optional[Dict] = None) -> str:
        """Format error messages in a user-friendly way"""
        if isinstance(error, dict):
            errorMsg = error.get('error') or error.get('result') or error.get('message') or str(error)
        else:
            errorMsg = str(error)
        
        # Clean up common error patterns
        if "FileNotFoundError" in errorMsg:
            return "**File Not Found**\n\nI couldn't find the file you specified. Please check the file path and try again."
        
        if "PermissionError" in errorMsg:
            return "**Permission Denied**\n\nI don't have permission to access this file. Please check file permissions."
        
        if "KeyError" in errorMsg:
            return "**Missing Information**\n\nSome required information is missing. Please provide all necessary details."
        
        if "ValueError" in errorMsg:
            return f"**Invalid Value**\n\n{errorMsg.split('ValueError:')[-1].strip()}"
        
        if "TypeError" in errorMsg:
            return "**Type Error**\n\nThere was a type mismatch. Please check your input format."
        
        # Only format LLM/API errors if they're actually LLM/API related errors
        # Don't mask other errors that happen to contain "LLM" or "API" in the message
        if ("LLM" in errorMsg or "API" in errorMsg) and (
            "llm" in errorMsg.lower() or 
            "api" in errorMsg.lower() or
            "quota" in errorMsg.lower() or 
            "429" in errorMsg or
            "404" in errorMsg or
            "not found" in errorMsg.lower() or
            "service" in errorMsg.lower() or
            "unavailable" in errorMsg.lower()
        ):
            if "quota" in errorMsg.lower() or "429" in errorMsg:
                return "I've reached a service limit. Please try again in a few moments, or check your API settings.\n\nBasic operations like listing assets and scopes still work."
            if "404" in errorMsg or "not found" in errorMsg.lower():
                return "The advanced service is temporarily unavailable.\n\nYou can still:\n• List and view your ISMS objects\n• Create new objects\n\nTry again in a moment."
            # For other LLM/API errors, show the actual error but in a user-friendly way
            # Extract the meaningful part of the error
            if "LLM" in errorMsg or "llm" in errorMsg.lower():
                if "not configured" in errorMsg.lower() or "not available" in errorMsg.lower():
                    return "LLM service is not configured. Please check your API settings."
                return f"LLM service error: {errorMsg.split('LLM')[-1].split('API')[0].strip()[:100]}"
            if "API" in errorMsg or "api" in errorMsg.lower():
                if "not configured" in errorMsg.lower() or "not available" in errorMsg.lower():
                    return "API service is not configured. Please check your API settings."
                return f"API service error: {errorMsg.split('API')[-1].strip()[:100]}"
        
        # Preserve actual error messages for debugging - don't mask everything
        
        # Generic error formatting - remove error prefixes and clean up
        errorMsg = errorMsg.replace("Error:", "").replace("error:", "").replace("❌", "").strip()
        if len(errorMsg) > 200:
            errorMsg = errorMsg[:200] + "..."
        
        return errorMsg
    
    @staticmethod
    def _formatToolResult(result: Any, context: Optional[Dict] = None) -> str:
        """Format tool execution results intelligently"""
        if isinstance(result, dict):
            if result.get('type') == 'text':
                return result.get('content', str(result))
            
            if result.get('type') == 'table':
                return result  # Return structured data, not formatted text
            
            if result.get('type') == 'object_detail':
                return result  # Return structured data, not formatted text
            
            if 'status' in result:
                status = result.get('status')
                if status == 'success':
                    data = result.get('result') or result.get('data') or result
                    # If data is structured (table/object_detail), return as-is
                    if isinstance(data, dict) and data.get('type') in ['table', 'object_detail']:
                        return data
                    return ResponseFormatter._formatSuccessData(data, result.get('type'))
                elif status == 'error':
                    return ResponseFormatter._formatError(result.get('error') or result)
            
            
            # Verinice object results
            if 'objects' in result or 'items' in result:
                return ResponseFormatter._formatVeriniceObjects(result)
            
            # List/array results
            if 'list' in result or isinstance(result.get('data'), list):
                return ResponseFormatter._formatList(result.get('data') or result.get('list') or [], context)
            
            # Generic dict - format as key-value pairs
            return ResponseFormatter._formatDict(result, context)
        
        if isinstance(result, list):
            return ResponseFormatter._formatList(result, context)
        
        return str(result) if result else "Operation completed successfully"
    
    @staticmethod
    def _formatVeriniceObjects(data: Dict) -> str:
        """Format Verinice object lists"""
        output = []
        objects = data.get('objects') or data.get('items') or data.get('data') or []
        
        if not objects:
            return "📋 **No objects found**"
        
        objectType = data.get('objectType', 'objects').title()
        output.append(f"📋 **{objectType} Found: {len(objects)}**\n")
        
        # Show first 10 items with details
        for i, obj in enumerate(objects[:10], 1):
            if isinstance(obj, dict):
                name = obj.get('name') or obj.get('title') or obj.get('id', 'Unknown')
                objId = obj.get('id', '')
                output.append(f"{i}. **{name}**")
                if objId and objId != name:
                    output.append(f"   ID: `{objId[:20]}...`" if len(objId) > 20 else f"   ID: `{objId}`")
            else:
                output.append(f"{i}. {obj}")
        
        if len(objects) > 10:
            output.append(f"\n... and {len(objects) - 10} more")
        
        return "\n".join(output)
    
    @staticmethod
    def _formatList(items: List, context: Optional[Dict] = None) -> str:
        """Format list data"""
        if not items:
            return "📋 **Empty list**"
        
        if len(items) == 1:
            return f"📋 **1 item**\n\n• {ResponseFormatter._formatItem(items[0])}"
        
        output = [f"📋 **{len(items)} items**\n"]
        
        for i, item in enumerate(items[:20], 1):
            formatted = ResponseFormatter._formatItem(item)
            output.append(f"{i}. {formatted}")
        
        if len(items) > 20:
            output.append(f"\n... and {len(items) - 20} more items")
        
        return "\n".join(output)
    
    @staticmethod
    def _formatItem(item: Any) -> str:
        """Format a single item"""
        if isinstance(item, dict):
            # Try to find a name/title field
            name = item.get('name') or item.get('title') or item.get('id')
            if name:
                return f"**{name}**"
            # Show first few key-value pairs
            pairs = list(item.items())[:3]
            return ", ".join([f"{k}: {v}" for k, v in pairs])
        return str(item)
    
    @staticmethod
    def _formatDict(data: Dict, context: Optional[Dict] = None) -> str:
        """Format dictionary data"""
        output = []
        
        if 'status' in data and data['status'] == 'success':
            result = data.get('result') or data.get('data')
            if result:
                return ResponseFormatter.format(result, data.get('type', 'tool_result'), context)
        
        # Format as key-value pairs
        for key, value in list(data.items())[:15]:
            if key in ['status', 'type']:
                continue
            
            formattedValue = ResponseFormatter._formatValue(value)
            output.append(f"**{key}:** {formattedValue}")
        
        if len(data) > 15:
            output.append(f"\n... and {len(data) - 15} more fields")
        
        return "\n".join(output) if output else "✅ Operation completed"
    
    @staticmethod
    def _formatValue(value: Any) -> str:
        """Format a single value"""
        if isinstance(value, list):
            if len(value) <= 3:
                return ", ".join([str(v) for v in value])
            return f"{len(value)} items"
        if isinstance(value, dict):
            return f"{{ {len(value)} fields }}"
        if isinstance(value, str) and len(value) > 100:
            return value[:100] + "..."
        return str(value)
    
    @staticmethod
    def _formatString(text: str, context: Optional[Dict] = None) -> str:
        """Format string responses"""
        if any(marker in text for marker in ['**', '`', '#', '*', '-']):
            return text
        
        if text.strip().startswith('{') or text.strip().startswith('['):
            try:
                parsed = json.loads(text)
                return ResponseFormatter.format(parsed, 'tool_result', context)
            except:
                pass
        
        # Return as-is if it looks like a natural response
        return text
    
    @staticmethod
    def _formatSuccessData(data: Any, dataType: Optional[str] = None) -> str:
        """Format successful operation data"""
        if isinstance(data, dict):
            return ResponseFormatter._formatDict(data)
        
        if isinstance(data, list):
            return ResponseFormatter._formatList(data)
        
        # Don't add success banner - let the actual result speak
        return str(data) if data else ""

