"""Text presenter - formats text responses with proper structure"""
from typing import Any, Dict, Optional
from .base import BasePresenter


class TextPresenter(BasePresenter):
    """Presents text responses with proper formatting and structure"""
    
    def present(self, data: Any, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Present text data with proper formatting
        
        Expected input format:
        - String: Plain text
        - Dict with 'content' or 'text': Text content
        - Dict with 'title' and 'sections': Structured text
        """
        if isinstance(data, str):
            formatted = self._formatText(data)
            return {
                'type': 'text',
                'content': formatted
            }
        
        if isinstance(data, dict):
            # If already formatted
            if data.get('type') == 'text':
                return data
            
            # Structured text with title and sections
            if 'title' in data or 'sections' in data:
                formatted = self._formatStructuredText(data)
                return {
                    'type': 'text',
                    'content': formatted
                }
            
            # Content or text field
            if 'content' in data or 'text' in data:
                text = data.get('content') or data.get('text', '')
                formatted = self._formatText(text)
                return {
                    'type': 'text',
                    'content': formatted
                }
        
        # Fallback: convert to string
        formatted = self._formatText(str(data))
        return {
            'type': 'text',
            'content': formatted
        }
    
    def _formatText(self, text: str) -> str:
        """Format plain text with proper line breaks and spacing"""
        if not text:
            return ''
        
        lines = text.split('\n')
        formatted_lines = []
        prev_empty = False
        
        for line in lines:
            line = line.strip()
            
            # Skip multiple consecutive empty lines
            if not line:
                if not prev_empty:
                    formatted_lines.append('')
                    prev_empty = True
                continue
            
            prev_empty = False
            
            # Format markdown-style headers
            if line.startswith('**') and line.endswith('**'):
                # Bold header
                formatted_lines.append(line)
            elif line.startswith('#'):
                # Markdown header
                formatted_lines.append(line)
            elif line.startswith('- ') or line.startswith('* '):
                # Bullet point
                formatted_lines.append(f"  {line}")
            elif line.startswith(('1. ', '2. ', '3. ', '4. ', '5. ', '6. ', '7. ', '8. ', '9. ')):
                # Numbered list
                formatted_lines.append(f"  {line}")
            elif ':' in line and len(line.split(':')) == 2:
                # Key-value pair
                formatted_lines.append(f"  {line}")
            else:
                formatted_lines.append(line)
        
        return '\n'.join(formatted_lines)
    
    def _formatStructuredText(self, data: Dict) -> str:
        """Format structured text with title and sections"""
        lines = []
        
        if 'title' in data:
            title = data['title']
            if not title.startswith('**'):
                title = f"**{title}**"
            lines.append(title)
            lines.append('')
        
        if 'sections' in data:
            sections = data['sections']
            if isinstance(sections, list):
                for section in sections:
                    if isinstance(section, dict):
                        # Section with title and content
                        if 'title' in section:
                            lines.append(f"**{section['title']}**")
                        if 'content' in section:
                            content = section['content']
                            if isinstance(content, list):
                                for item in content:
                                    lines.append(f"  • {item}")
                            else:
                                lines.append(f"  {content}")
                        lines.append('')
                    elif isinstance(section, str):
                        lines.append(section)
                        lines.append('')
            elif isinstance(sections, dict):
                for key, value in sections.items():
                    lines.append(f"**{key}**:")
                    if isinstance(value, list):
                        for item in value:
                            lines.append(f"  • {item}")
                    else:
                        lines.append(f"  {value}")
                    lines.append('')
        
        if 'content' in data:
            content = data['content']
            if isinstance(content, list):
                for item in content:
                    lines.append(f"  • {item}")
            else:
                lines.append(content)
        
        return '\n'.join(lines)

