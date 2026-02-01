"""List presenter - formats list data"""
from typing import Any, Dict, Optional, List
from .base import BasePresenter


class ListPresenter(BasePresenter):
    """Presents list data as structured format"""
    
    def present(self, data: Any, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Present list data
        
        Expected input format:
        {
            'items': [...],  # or 'data': [...]
            'title': 'Available reports',  # optional
            'item_format': 'name'  # optional, how to format each item
        }
        """
        items = data.get('items') or data.get('data') or data.get('list') or []
        if isinstance(items, dict) and 'items' in items:
            items = items['items']
        
        if not items:
            return {
                'type': 'text',
                'content': data.get('title', 'No items found') or 'No items found'
            }
        
        # Format items
        formatted_items = []
        item_format = data.get('item_format', 'name')
        
        for item in items:
            if isinstance(item, dict):
                # Try to extract name/title
                name = item.get('name') or item.get('title') or item.get('id', 'Unknown')
                formatted_items.append({
                    'name': name,
                    'description': item.get('description', '') or '—'
                })
            elif isinstance(item, str):
                formatted_items.append({'name': item})
            else:
                formatted_items.append({'name': str(item)})
        
        # If it's a simple list of names, return as table
        if all('description' not in item or not item.get('description') or item.get('description') == '—' for item in formatted_items):
            return {
                'type': 'table',
                'title': data.get('title', 'List'),
                'columns': ['Name'],
                'data': formatted_items,
                'total': len(formatted_items)
            }
        
        # Otherwise return as table with name and description
        return {
            'type': 'table',
            'title': data.get('title', 'List'),
            'columns': ['Name', 'Description'],
            'data': formatted_items,
            'total': len(formatted_items)
        }

