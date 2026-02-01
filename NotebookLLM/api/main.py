"""FastAPI main application"""
import sys
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

_currentDir = os.path.dirname(os.path.abspath(__file__))
_parentDir = os.path.dirname(_currentDir)
if _parentDir not in sys.path:
    sys.path.insert(0, _parentDir)

# Load environment variables from config file before importing routers
# This must be done before CORS configuration
_configDir = Path(_parentDir) / "config"
_configFile = _configDir / "notebookllm.env"
if _configFile.exists():
    with open(_configFile, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())

# Import routers after environment is loaded
from api.routers import chat  # noqa: E402

app = FastAPI(
    title="NotebookLLM API",
    description="API bridge for NotebookLLM agent integration",
    version="1.0.0"
)

# Eager initialization of AgentBridge to avoid first-request delay
@app.on_event("startup")
async def startup_event():
    """Initialize agent bridge on startup instead of first request"""
    try:
        from api.services.agentService import AgentService
        _ = AgentService()
    except Exception:
        pass

# CORS middleware - must be added before routes
# Allow common localhost origins for development
cors_origins_str = os.getenv("CORS_ORIGINS", "http://localhost:3002,http://localhost:3000,http://localhost:3001,http://127.0.0.1:3002,http://127.0.0.1:3001,http://127.0.0.1:3000")
cors_origins = [origin.strip() for origin in cors_origins_str.split(",") if origin.strip()]

additional_origins = [
    "http://localhost:3000",
    "http://localhost:3001", 
    "http://localhost:3002",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    "http://127.0.0.1:3002",
]
for origin in additional_origins:
    if origin not in cors_origins:
        cors_origins.append(origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Include routers
app.include_router(chat.router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "NotebookLLM API", "status": "running"}


@app.get("/health")
async def health():
    """Health check"""
    return {"status": "healthy"}
