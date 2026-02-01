#!/bin/bash
# NotebookLLM Start Script
# Starts both API and Frontend servers

set -e
set +o pipefail  # Don't exit on pipe failures

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Configuration
CONFIG_DIR="$SCRIPT_DIR/config"
CONFIG_FILE="$CONFIG_DIR/notebookllm.env"

# Load configuration
if [ -f "$CONFIG_FILE" ]; then
    set +e  # Temporarily disable exit on error for config loading
    set -a
    source "$CONFIG_FILE" 2>&1 | grep -v "command not found" || true
    set +a
    set -e  # Re-enable exit on error
else
    echo -e "${YELLOW}⚠${NC} Config file not found: $CONFIG_FILE"
    echo -e "${YELLOW}   Using defaults. Copy config/notebookllm.env.example to config/notebookllm.env${NC}"
fi

# Set defaults if not in config
API_PORT=${API_PORT:-8000}
FRONTEND_PORT=${FRONTEND_PORT:-3002}
API_URL=${API_URL:-http://localhost:8000}
FRONTEND_URL=${FRONTEND_URL:-http://localhost:3002}
API_BASE_URL=${API_BASE_URL:-http://localhost:8000}
API_STARTUP_TIMEOUT=${API_STARTUP_TIMEOUT:-15}  # Increased for AgentBridge init
FRONTEND_STARTUP_TIMEOUT=${FRONTEND_STARTUP_TIMEOUT:-8}  # Increased for Nuxt compilation
API_LOG=${API_LOG:-/tmp/notebookllm-api.log}
FRONTEND_LOG=${FRONTEND_LOG:-/tmp/notebookllm-frontend.log}

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  NotebookLLM Startup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to cleanup background processes
cleanup() {
    echo -e "\n${YELLOW}Shutting down servers...${NC}"
    kill $API_PID $FRONTEND_PID 2>/dev/null || true
    wait $API_PID $FRONTEND_PID 2>/dev/null || true
    echo -e "${GREEN}Servers stopped.${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Check if API dependencies are installed
echo -e "${BLUE}[1/4] Checking API dependencies...${NC}"
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo -e "${YELLOW}Installing API dependencies...${NC}"
    cd api
    pip install -r requirements.txt --break-system-packages --quiet || {
        echo -e "${YELLOW}Warning: Some dependencies may not be installed${NC}"
    }
    cd ..
fi

# Check if Frontend dependencies are installed
echo -e "${BLUE}[2/4] Checking Frontend dependencies...${NC}"
if [ ! -d "frontend/node_modules" ]; then
    echo -e "${YELLOW}Installing Frontend dependencies...${NC}"
    cd frontend
    npm install
    cd ..
fi

# Simplified function to check if port is used by NotebookLLM
is_notebookllm_process() {
    local pid=$1
    local port=$2
    
    [ -z "$pid" ] && return 1
    kill -0 $pid 2>/dev/null || return 1
    
    local cmdline=$(ps -p $pid -o args= 2>/dev/null || echo "")
    [ -z "$cmdline" ] && return 1
    
    # Check for API (uvicorn with api.main:app)
    if [ $port -eq $API_PORT ]; then
        echo "$cmdline" | grep -q "api.main:app" && return 0
        echo "$cmdline" | grep -q "uvicorn.*$API_PORT" && return 0
    fi
    
    # Check for Frontend (nuxt dev in NotebookLLM/frontend)
    if [ $port -eq $FRONTEND_PORT ]; then
        echo "$cmdline" | grep -q "NotebookLLM/frontend" && return 0
        echo "$cmdline" | grep -q "nuxt.*$FRONTEND_PORT" && return 0
    fi
    
    return 1
}

# Function to check port and show what's using it
check_port() {
    local port=$1
    local service=$2
    local result=0
    
    if lsof -ti:$port > /dev/null 2>&1; then
        local pid=$(lsof -ti:$port | head -1)
        local process=$(ps -p $pid -o comm= 2>/dev/null || echo "unknown")
        
        if is_notebookllm_process $pid $port; then
            echo -e "${GREEN}✓ Port $port ($service) already running (PID: $pid)${NC}"
            result=2  # Already running NotebookLLM
        else
            echo -e "${YELLOW}⚠ Port $port ($service) is in use by: $process (PID: $pid)${NC}"
            result=1  # Conflict with other service
        fi
    else
        result=0  # Port is free
    fi
    
    return $result
}

# Function to kill process on port
kill_port() {
    local port=$1
    local service=$2
    
    if lsof -ti:$port > /dev/null 2>&1; then
        local pids=$(lsof -ti:$port)
        for pid in $pids; do
            if is_notebookllm_process $pid $port; then
                echo -e "${GREEN}✓ Port $port ($service) already running (PID: $pid)${NC}"
                return 2  # Already running NotebookLLM
            else
                local process=$(ps -p $pid -o comm= 2>/dev/null || echo "unknown")
                echo -e "${YELLOW}⚠ Port $port ($service) is in use by: $process (PID: $pid)${NC}"
                echo -e "${BLUE}  → Killing process...${NC}"
                kill -9 $pid 2>/dev/null || true
                sleep 0.2  # Reduced from 0.5s to 0.2s
                # Verify it's killed
                if kill -0 $pid 2>/dev/null; then
                    echo -e "${YELLOW}  ⚠ Failed to kill process $pid, trying force kill...${NC}"
                    kill -9 $pid 2>/dev/null || true
                    sleep 0.2  # Reduced from 0.5s to 0.2s
                fi
                if ! kill -0 $pid 2>/dev/null; then
                    echo -e "${GREEN}  ✓ Process killed successfully${NC}"
                else
                    echo -e "${YELLOW}  ⚠ Process still running, may require manual intervention${NC}"
                fi
            fi
        done
    fi
    return 0  # Port is free or cleared
}

# Check and handle ports
echo -e "${BLUE}Checking ports...${NC}"
API_ALREADY_RUNNING=0
FRONTEND_ALREADY_RUNNING=0

set +e  # Temporarily disable exit on error to capture return codes
kill_port $API_PORT "NotebookLLM API"
API_STATUS=$?
set -e  # Re-enable exit on error
if [ $API_STATUS -eq 2 ]; then
    API_ALREADY_RUNNING=1
fi

set +e  # Temporarily disable exit on error to capture return codes
kill_port $FRONTEND_PORT "NotebookLLM Frontend"
FRONTEND_STATUS=$?
set -e  # Re-enable exit on error
if [ $FRONTEND_STATUS -eq 2 ]; then
    FRONTEND_ALREADY_RUNNING=1
fi

if [ $API_ALREADY_RUNNING -eq 1 ] && [ $FRONTEND_ALREADY_RUNNING -eq 1 ]; then
    echo ""
    echo -e "${GREEN}NotebookLLM is already running!${NC}"
    echo ""
    echo -e "  ${BLUE}Frontend:${NC} $FRONTEND_URL"
    echo -e "  ${BLUE}API:${NC}      $API_URL"
    echo -e "  ${BLUE}API Docs:${NC} $API_URL/docs"
    echo ""
    echo -e "${YELLOW}To restart, stop existing services first:${NC}"
    echo -e "  lsof -ti:$API_PORT | xargs kill"
    echo -e "  lsof -ti:$FRONTEND_PORT | xargs kill"
    exit 0
fi

# Wait a moment for ports to be fully released
if [ $API_ALREADY_RUNNING -eq 0 ] || [ $FRONTEND_ALREADY_RUNNING -eq 0 ]; then
    sleep 0.5  # Reduced from 1s to 0.5s
fi
echo ""

# Reusable function to wait for service
wait_for_service() {
    local service_name=$1
    local check_command=$2
    local timeout=$3
    local sleep_interval=${4:-1}
    
    echo -n "      Waiting for $service_name"
    local ready=false
    local iterations=$((timeout / sleep_interval))
    
    for i in $(seq 1 $iterations); do
        if eval "$check_command" > /dev/null 2>&1; then
            echo ""
            echo -e "${GREEN}✓${NC} $service_name ready"
            ready=true
            break
        fi
        if [ $((i % 2)) -eq 0 ]; then
            echo -n "."
        fi
        sleep $sleep_interval
    done
    
    if [ "$ready" = false ]; then
        echo ""
        echo -e "${YELLOW}⚠${NC} $service_name not ready after ${timeout} seconds, continuing anyway..."
    fi
}

# Start API server (if not already running)
if [ $API_ALREADY_RUNNING -eq 0 ]; then
    echo -e "${BLUE}[3/4] Starting API server on port $API_PORT...${NC}"
    cd "$SCRIPT_DIR"
    export PYTHONPATH="${PYTHONPATH}:${SCRIPT_DIR}"
    export API_PORT API_URL CORS_ORIGINS
    
    # Pre-compile Python bytecode for faster startup
    python3 -m compileall -q api integration 2>/dev/null || true
    
    uvicorn api.main:app --reload --port $API_PORT > "$API_LOG" 2>&1 &
    API_PID=$!

    # Wait for API to start
    wait_for_service "API" "lsof -ti:$API_PORT" $API_STARTUP_TIMEOUT 1
    
    # Check if process died
    if ! kill -0 $API_PID 2>/dev/null; then
        echo -e "${YELLOW}API server process died. Check $API_LOG${NC}"
        tail -20 "$API_LOG"
        exit 1
    fi

    echo -e "${GREEN}✓ API server running (PID: $API_PID)${NC}"
else
    API_PID=$(lsof -ti:$API_PORT | head -1)
    echo -e "${GREEN}✓ API server already running (PID: $API_PID)${NC}"
fi

# Start Frontend server (if not already running)
if [ $FRONTEND_ALREADY_RUNNING -eq 0 ]; then
    echo -e "${BLUE}[4/4] Starting Frontend server on port $FRONTEND_PORT...${NC}"
    cd "$SCRIPT_DIR/frontend"
    export PORT=$FRONTEND_PORT
    export API_BASE_URL
    PORT=$FRONTEND_PORT npm run dev > "$FRONTEND_LOG" 2>&1 &
    FRONTEND_PID=$!

    # Wait for Frontend to start
    wait_for_service "Frontend" "curl -s $FRONTEND_URL" $FRONTEND_STARTUP_TIMEOUT 1
    
    # Check if Frontend started successfully
    if ! kill -0 $FRONTEND_PID 2>/dev/null; then
        echo -e "${YELLOW}Frontend server failed to start. Check $FRONTEND_LOG${NC}"
        tail -30 "$FRONTEND_LOG"
        if [ $API_ALREADY_RUNNING -eq 0 ]; then
            kill $API_PID 2>/dev/null || true
        fi
        exit 1
    fi

    echo -e "${GREEN}✓ Frontend server running (PID: $FRONTEND_PID)${NC}"
else
    FRONTEND_PID=$(lsof -ti:$FRONTEND_PORT | head -1)
    echo -e "${GREEN}✓ Frontend server already running (PID: $FRONTEND_PID)${NC}"
fi
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  NotebookLLM is running!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "  ${BLUE}Frontend:${NC} $FRONTEND_URL"
echo -e "  ${BLUE}API:${NC}      $API_URL"
echo -e "  ${BLUE}API Docs:${NC} $API_URL/docs"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all servers${NC}"
echo ""

# Wait for user interrupt
wait
