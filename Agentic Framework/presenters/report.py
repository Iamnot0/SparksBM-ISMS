"""Report presenter - formats report generation results"""
from typing import Any, Dict, Optional
from .base import BasePresenter


class ReportPresenter(BasePresenter):
    """Presents report generation results"""
    
    def present(self, data: Any, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Present report generation result
        
        Expected input format:
        {
            'success': True,
            'reportId': 'inventory-of-assets',
            'reportName': 'Inventory of Assets',
            'format': 'pdf',
            'data': base64_encoded_pdf,  # optional
            'size': 12345  # optional
        }
        """
        if not data.get('success'):
            return {
                'type': 'error',
                'content': data.get('error', 'Failed to generate report')
            }
        
        report_id = data.get('reportId', 'Report')
        report_name = data.get('reportName') or report_id.replace('-', ' ').title()
        
        result = {
            'type': 'report',
            'content': f"Generated the {report_name} report. PDF is ready for download.",
            'reportId': report_id,
            'reportName': report_name,
            'format': data.get('format', 'pdf')
        }
        
        # Include PDF data if available
        if 'data' in data:
            result['data'] = data['data']
        if 'size' in data:
            result['size'] = data['size']
        
        return result

