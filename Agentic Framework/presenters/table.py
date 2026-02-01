"""Table presenter - formats tabular data"""
from typing import Any, Dict, Optional
from .base import BasePresenter


class TablePresenter(BasePresenter):
    """Presents tabular data as structured table format"""
    
    def present(self, data: Any, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Present tabular data with pagination, column prioritization, and smart truncation
        
        Expected input format:
        {
            'items': [...],  # or 'data': [...]
            'columns': ['Name', 'Description'],  # optional, will infer
            'essential_columns': ['Name', 'SubType'],  # optional, for column prioritization
            'title': 'I found 2 scopes',  # optional
            'total': 2,  # optional
            'page': 1,  # optional, for pagination
            'page_size': 15  # optional, default 15
        }
        """
        items = data.get('items') or data.get('data') or data.get('objects', {}).get('items', []) or []
        if isinstance(items, dict) and 'items' in items:
            items = items['items']
        
        if not items:
            return {
                'type': 'text',
                'content': data.get('title', 'No data found') or 'No data found'
            }
        
        total_count = len(items)
        page = data.get('page', 1)
        page_size = data.get('page_size', 15)
        use_essential_columns = data.get('use_essential_columns', True)
        essential_columns = data.get('essential_columns', [])
        
        # Extract columns if not provided
        all_columns = data.get('columns')
        if not all_columns and items:
            # Infer columns from first item
            first_item = items[0] if isinstance(items, list) else {}
            if isinstance(first_item, dict):
                all_columns = list(first_item.keys())
                # Capitalize column names
                all_columns = [col.replace('_', ' ').title() for col in all_columns]
        
        # Show ALL items - no truncation
        # If pagination is requested, use pagination
        start_idx = 0
        end_idx = total_count
        
        if page > 1 or data.get('force_pagination', False):
            # Pagination mode: show page_size items per page
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            display_items = items[start_idx:end_idx]
            truncation_message = None
        else:
            # Show all items - no truncation
            display_items = items
            truncation_message = None
        
        # Column prioritization: Use essential columns by default if available
        if use_essential_columns and essential_columns and all_columns:
            # Use essential columns, but ensure they exist in all_columns
            columns = [col for col in essential_columns if col in all_columns]
            if not columns:
                columns = all_columns  # Fallback to all columns if essential not found
        else:
            columns = all_columns or []
        
        # If only one column (e.g., just "Name"), format as simple list instead of table
        if len(columns) == 1 and len(display_items) > 0:
            single_col = columns[0]
            single_col_key = single_col.lower().replace(' ', '_')
            
            # Build simple list format
            list_items = []
            for item in display_items:
                if isinstance(item, dict):
                    value = None
                    if single_col_key == 'subtype':
                        value = item.get('subType') or item.get('subtype')
                    elif single_col_key == 'name':
                        value = item.get('name') or item.get('title')
                    else:
                        value = (
                            item.get(single_col_key) or 
                            item.get(single_col) or 
                            item.get(single_col_key.replace('_', '')) or
                            item.get(single_col.lower())
                        )
                    if value:
                        list_items.append(str(value))
                else:
                    list_items.append(str(item))
            
            # Return as simple text list with conversational prefix
            if list_items:
                title = data.get('title', '')
                if title:
                    # Use the title as prefix (e.g., "I found these Scopes in our ISMS:")
                    content = f"{title}\n\n" + '\n'.join(list_items)
                else:
                    # Fallback to simple list
                    content = '\n'.join(list_items)
                
                return {
                    'type': 'text',
                    'content': content
                }
        
        # Build table data structure
        table_data = []
        for item in display_items:
            if isinstance(item, dict):
                row = {}
                for col in columns or []:
                    col_key = col.lower().replace(' ', '_')
                    # Try multiple key formats (including camelCase variations)
                    value = None
                    if col_key == 'subtype':
                        value = item.get('subType') or item.get('subtype')
                    elif col_key == 'abbreviation':
                        value = item.get('abbreviation')
                    elif col_key == 'designator':
                        value = item.get('designator')
                    else:
                        value = (
                            item.get(col_key) or 
                            item.get(col) or 
                            item.get(col_key.replace('_', '')) or
                            item.get(col.lower())
                        )
                    
                    row[col] = str(value) if value is not None else '—'
                table_data.append(row)
            else:
                # Simple value
                table_data.append({columns[0] if columns else 'Value': str(item)})
        
        # Format as table structure for proper HTML rendering
        title = data.get('title', 'Data')
        
        # Build pagination info
        total_pages = (total_count + page_size - 1) // page_size if page_size > 0 else 1
        pagination_info = None
        if total_count > page_size and not truncation_message:
            pagination_info = {
                'current_page': page,
                'total_pages': total_pages,
                'page_size': page_size,
                'showing': f"Showing {start_idx + 1}-{min(end_idx, total_count)} of {total_count}",
                'has_next': page < total_pages,
                'has_previous': page > 1
            }
        
        # Return structured table data for frontend rendering
        result = {
            'type': 'table',
            'title': title,
            'columns': columns or [],
            'data': table_data,
            'total': total_count,
            'all_columns': all_columns,  # Store all columns for expansion
            'essential_columns': essential_columns,
            'show_expand': use_essential_columns and essential_columns and len(all_columns or []) > len(columns)
        }
        
        if truncation_message:
            result['truncation_message'] = truncation_message
        if pagination_info:
            result['pagination'] = pagination_info
        
        return result

