"""
Live Routing Log Checker - API Endpoint

Add this to your NotebookLLM API to expose routing logs via HTTP endpoint.

Usage:
1. Add this code to NotebookLLM/api/routers/chat.py or create a new router file
2. Access via: GET http://localhost:8000/api/routing-logs
3. Returns JSON with routing statistics and recent logs
"""

from fastapi import APIRouter
from typing import Dict, List

router = APIRouter(prefix="/api", tags=["monitoring"])


@router.get("/routing-logs")
async def get_routing_logs() -> Dict:
    """
    Get routing logs from the live agent instance
    
    Returns:
        Dict with routing statistics and recent logs
    """
    try:
        # Import agent bridge to access live agent
        from integration.agentBridge import agent_instance
        
        if not agent_instance:
            return {
                "status": "error",
                "message": "Agent not initialized",
                "logs": []
            }
        
        routing_log = agent_instance.getRoutingLog()
        
        if len(routing_log) == 0:
            return {
                "status": "success",
                "message": "No messages processed yet",
                "total": 0,
                "matches": 0,
                "mismatches": 0,
                "match_rate": 0,
                "logs": []
            }
        
        # Calculate statistics
        total = len(routing_log)
        matches = sum(1 for e in routing_log if e.get('match', False))
        mismatches = [e for e in routing_log if not e.get('match', False)]
        match_rate = (matches / total * 100) if total > 0 else 0
        
        recent_logs = routing_log[-20:] if len(routing_log) >= 20 else routing_log
        
        return {
            "status": "success",
            "message": f"Retrieved {total} routing decisions",
            "total": total,
            "matches": matches,
            "mismatches": len(mismatches),
            "match_rate": round(match_rate, 1),
            "recent_logs": recent_logs,
            "mismatch_details": mismatches[:10]  # First 10 mismatches
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "logs": []
        }


@router.post("/routing-logs/clear")
async def clear_routing_logs() -> Dict:
    """Clear routing logs (use after validation)"""
    try:
        from integration.agentBridge import agent_instance
        
        if not agent_instance:
            return {"status": "error", "message": "Agent not initialized"}
        
        agent_instance.clearRoutingLog()
        
        return {
            "status": "success",
            "message": "Routing logs cleared"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


# To use this, add to your main.py:
# from routers.monitoring import router as monitoring_router
# app.include_router(monitoring_router)
