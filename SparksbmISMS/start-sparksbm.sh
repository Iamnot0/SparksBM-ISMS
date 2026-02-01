#!/bin/bash
#═══════════════════════════════════════════════════════════════════════════════
#  SparksBM ISMS Platform - Full Stack Startup Script
#═══════════════════════════════════════════════════════════════════════════════

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
ORANGE='\033[0;33m'
NC='\033[0m' # No Color

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"

# Use project-local Gradle cache to avoid permission issues
# This works regardless of who runs the script
PROJECT_GRADLE_CACHE="$PROJECT_DIR/.gradle-cache"
export GRADLE_USER_HOME="$PROJECT_GRADLE_CACHE"
mkdir -p "$PROJECT_GRADLE_CACHE" 2>/dev/null || true
# Fix ownership if created as root
if [ -d "$PROJECT_GRADLE_CACHE" ] && [ -O "$PROJECT_GRADLE_CACHE" ]; then
    : # Owned by current user, good
elif [ -d "$PROJECT_GRADLE_CACHE" ]; then
    # Owned by someone else (likely root) - fix it
    chmod -R u+w "$PROJECT_GRADLE_CACHE" 2>/dev/null || true
fi
CONFIG_DIR="$PROJECT_DIR/config"
CONFIG_FILE="$CONFIG_DIR/sparksbm.env"
KEYCLOAK_DIR="$PROJECT_DIR/keycloak"
FRONTEND_DIR="$PROJECT_DIR/verinice-veo-web"
BACKEND_DIR="$PROJECT_DIR/verinice-veo"

# Load configuration
if [ -f "$CONFIG_FILE" ]; then
    set +e  # Temporarily disable exit on error for config loading
    set -a
    source "$CONFIG_FILE" 2>&1 | grep -v "command not found" || true
    set +a
    set -e  # Re-enable exit on error
else
    echo -e "${YELLOW}⚠${NC} Config file not found: $CONFIG_FILE"
    echo -e "${YELLOW}   Using defaults. Copy config/sparksbm.env.example to config/sparksbm.env${NC}"
fi

# Set defaults if not in config
BACKEND_PORT=${BACKEND_PORT:-8070}
FRONTEND_PORT=${FRONTEND_PORT:-3001}
KEYCLOAK_PORT=${KEYCLOAK_PORT:-8080}
POSTGRES_PORT=${POSTGRES_PORT:-5432}
RABBITMQ_MGMT_PORT=${RABBITMQ_MGMT_PORT:-15672}

BACKEND_URL=${BACKEND_URL:-http://localhost:8070}
FRONTEND_URL=${FRONTEND_URL:-http://localhost:3001}
KEYCLOAK_URL=${KEYCLOAK_URL:-http://localhost:8080}
RABBITMQ_URL=${RABBITMQ_URL:-http://localhost:15672}

KEYCLOAK_REALM=${KEYCLOAK_REALM:-sparksbm}
KEYCLOAK_CLIENT=${KEYCLOAK_CLIENT:-sparksbm}
POSTGRES_USER=${POSTGRES_USER:-sparksbm}
POSTGRES_DB=${POSTGRES_DB:-sparksbm}

JAVA_HOME=${JAVA_HOME:-/usr/lib/jvm/java-21-openjdk-amd64}
GRADLE_OPTS=${GRADLE_OPTS:-"-Dorg.gradle.daemon=true -Dorg.gradle.parallel=true -Dorg.gradle.caching=true"}

POSTGRES_WAIT_TIMEOUT=${POSTGRES_WAIT_TIMEOUT:-30}
KEYCLOAK_WAIT_TIMEOUT=${KEYCLOAK_WAIT_TIMEOUT:-120}
RABBITMQ_WAIT_TIMEOUT=${RABBITMQ_WAIT_TIMEOUT:-60}
BACKEND_WAIT_TIMEOUT=${BACKEND_WAIT_TIMEOUT:-240}
FRONTEND_WAIT_TIMEOUT=${FRONTEND_WAIT_TIMEOUT:-40}

echo ""
echo -e "${ORANGE}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${ORANGE}║${NC}          	${ORANGE}⚡ SparksBM${NC} ISMS Platform			${ORANGE}║${NC}"
echo -e "${ORANGE}║${NC}                Private Capital × Innovation     		${ORANGE}║${NC}"
echo -e "${ORANGE}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""

#───────────────────────────────────────────────────────────────────────────────
# Check Dependencies
#───────────────────────────────────────────────────────────────────────────────
echo -e "${BLUE}[1/6]${NC} Checking dependencies..."

if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker not found. Please install Docker.${NC}"
    exit 1
fi

if ! command -v node &> /dev/null; then
    echo -e "${RED}✗ Node.js not found. Please install Node.js.${NC}"
    exit 1
fi

if ! command -v java &> /dev/null; then
    echo -e "${RED}✗ Java not found. Please install Java 21 JDK.${NC}"
    exit 1
fi

if ! command -v javac &> /dev/null; then
    echo -e "${RED}✗ Java compiler not found. Please install Java 21 JDK.${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} Dependencies OK"

#───────────────────────────────────────────────────────────────────────────────
# Start Docker Services (PostgreSQL, Keycloak, RabbitMQ)
#───────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}[2/6]${NC} Starting Docker services (PostgreSQL, Keycloak, RabbitMQ)..."

cd "$KEYCLOAK_DIR" || { echo -e "${RED}✗${NC} Cannot access keycloak directory"; exit 1; }

# Export environment variables for Docker Compose
export POSTGRES_USER POSTGRES_PASS POSTGRES_DB POSTGRES_PORT
export KEYCLOAK_PORT KEYCLOAK_REALM KEYCLOAK_CLIENT
export RABBITMQ_MGMT_PORT

# Try docker without sudo first, then with sudo if needed
# This prevents the script from running as root unnecessarily
if docker compose up -d 2>/dev/null || docker-compose up -d 2>/dev/null; then
    : # Docker worked without sudo - good!
elif sudo docker compose up -d 2>/dev/null || sudo docker-compose up -d 2>/dev/null; then
    echo -e "${YELLOW}⚠${NC} Docker required sudo. Gradle will run as user 'clay' to avoid permission issues."
else
    echo -e "${RED}✗${NC} Failed to start Docker services"; exit 1
fi

# Reusable function to wait for service
wait_for_service() {
    local service_name=$1
    local check_command=$2
    local timeout=$3
    local sleep_interval=$4
    
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
        if [ $((i % 5)) -eq 0 ]; then
            echo -n "."
        fi
        sleep $sleep_interval
    done
    
    if [ "$ready" = false ]; then
        echo ""
        echo -e "${YELLOW}⚠${NC} $service_name not ready after ${timeout} seconds, continuing anyway..."
    fi
}

# Wait for PostgreSQL
wait_for_service "PostgreSQL" "docker exec sparksbm-postgres pg_isready -U $POSTGRES_USER" $POSTGRES_WAIT_TIMEOUT 1

# Wait for Keycloak
wait_for_service "Keycloak" "curl -s $KEYCLOAK_URL/health/ready" $KEYCLOAK_WAIT_TIMEOUT 2

# Wait for RabbitMQ
wait_for_service "RabbitMQ" "curl -s $RABBITMQ_URL" $RABBITMQ_WAIT_TIMEOUT 2

#───────────────────────────────────────────────────────────────────────────────
# Create Databases
#───────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}[3/6]${NC} Setting up databases..."

# Create databases
for db in veo forms history accounts; do
    docker exec sparksbm-postgres psql -U $POSTGRES_USER -c "CREATE DATABASE $db;" 2>/dev/null || echo -e "    ${YELLOW}⚠${NC} Database '$db' may already exist"
done

echo -e "${GREEN}✓${NC} Databases ready"

#───────────────────────────────────────────────────────────────────────────────
# Start Backend (VEO REST API)
#───────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}[4/6]${NC} Starting Backend (Spring Boot)..."

cd "$BACKEND_DIR"

# Check if backend is already running
if curl -s $BACKEND_URL/actuator/health > /dev/null 2>&1 || curl -s $BACKEND_URL/swagger-ui.html > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Backend already running on port $BACKEND_PORT"
    BACKEND_PID=$(lsof -ti:$BACKEND_PORT | head -1)
else
    # Kill any existing backend processes
    pkill -f "veo-rest" 2>/dev/null || true
    pkill -f "gradlew.*bootRun" 2>/dev/null || true
    sleep 1

    # Set Java environment
    export JAVA_HOME
    export GRADLE_OPTS
    # GRADLE_USER_HOME already set at top of script to project-local cache
    # Remove any stale lock files
    find "$GRADLE_USER_HOME" -name "*.lck" -type f -delete 2>/dev/null || true
    
    # Simplified: Use Gradle bootRun (Gradle handles compilation caching)
    echo -n "      Starting backend"
    cd "$BACKEND_DIR"
    # CRITICAL: Pass GRADLE_USER_HOME explicitly in the command to ensure it's used
    GRADLE_USER_HOME="$PROJECT_GRADLE_CACHE" ./gradlew veo-rest:bootRun -PspringProfiles=local > /tmp/sparksbm-backend.log 2>&1 &
    BACKEND_PID=$!
    
    # Wait for backend
    wait_for_service "Backend" "curl -s $BACKEND_URL/actuator/health || curl -s $BACKEND_URL/swagger-ui.html" $BACKEND_WAIT_TIMEOUT 2
    
    # Check if process died
    if ! kill -0 $BACKEND_PID 2>/dev/null; then
        echo -e "${RED}✗${NC} Backend process died. Check /tmp/sparksbm-backend.log"
        tail -30 /tmp/sparksbm-backend.log
        exit 1
    fi
fi

#───────────────────────────────────────────────────────────────────────────────
# Start Frontend
#───────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}[5/6]${NC} Starting Frontend..."

cd "$FRONTEND_DIR"

# Kill any existing frontend servers
pkill -f "nuxi dev" 2>/dev/null || true
sleep 1

# Set environment variables for frontend
export VEO_DEFAULT_API_URL=${VEO_DEFAULT_API_URL:-$BACKEND_URL}
export VEO_FORMS_API_URL=${VEO_FORMS_API_URL:-$BACKEND_URL}
export VEO_HISTORY_API_URL=${VEO_HISTORY_API_URL:-$BACKEND_URL}
export VEO_REPORTING_API_URL=${VEO_REPORTING_API_URL:-$BACKEND_URL/api/reporting}
export VEO_ACCOUNTS_API_URL=${VEO_ACCOUNTS_API_URL:-$BACKEND_URL}
export VEO_OIDC_URL=${VEO_OIDC_URL:-$KEYCLOAK_URL}
export VEO_OIDC_REALM=${VEO_OIDC_REALM:-$KEYCLOAK_REALM}
export VEO_OIDC_CLIENT=${VEO_OIDC_CLIENT:-$KEYCLOAK_CLIENT}
export PORT=$FRONTEND_PORT

# Start frontend in background
echo -n "      Starting frontend on port $FRONTEND_PORT"
PORT=$FRONTEND_PORT npm run dev > /tmp/sparksbm-frontend.log 2>&1 &
FRONTEND_PID=$!

# Give frontend a moment to start
sleep 3

# Wait for frontend
wait_for_service "Frontend" "curl -s $FRONTEND_URL" $FRONTEND_WAIT_TIMEOUT 2

# Verify frontend is actually running
if ! kill -0 $FRONTEND_PID 2>/dev/null; then
    echo -e "${RED}✗${NC} Frontend process died. Check /tmp/sparksbm-frontend.log"
    tail -30 /tmp/sparksbm-frontend.log
    echo -e "${YELLOW}   Attempting to start frontend manually...${NC}"
    cd "$FRONTEND_DIR"
    PORT=$FRONTEND_PORT npm run dev > /tmp/sparksbm-frontend.log 2>&1 &
    FRONTEND_PID=$!
    sleep 5
fi

#───────────────────────────────────────────────────────────────────────────────
# Display Status
#───────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}[6/6]${NC} All services started!"
echo ""
echo -e "${ORANGE}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${ORANGE}║${NC}  ${GREEN}SparksBM ISMS is running!${NC}                                    ${ORANGE}║${NC}"
echo -e "${ORANGE}╠═══════════════════════════════════════════════════════════════╣${NC}"
echo -e "${ORANGE}║${NC}                                                               ${ORANGE}║${NC}"
echo -e "${ORANGE}║${NC}  🌐 Frontend:    ${BLUE}$FRONTEND_URL${NC}                       ${ORANGE}║${NC}"
echo -e "${ORANGE}║${NC}  🔧 Backend:     ${BLUE}$BACKEND_URL${NC}                         ${ORANGE}║${NC}"
echo -e "${ORANGE}║${NC}  📚 API Docs:    ${BLUE}$BACKEND_URL/swagger-ui.html${NC}           ${ORANGE}║${NC}"
echo -e "${ORANGE}║${NC}  🔐 Keycloak:    ${BLUE}$KEYCLOAK_URL${NC}                         ${ORANGE}║${NC}"
echo -e "${ORANGE}║${NC}  🐰 RabbitMQ:    ${BLUE}$RABBITMQ_URL${NC}                        ${ORANGE}║${NC}"
echo -e "${ORANGE}║${NC}  🗄️  PostgreSQL:  localhost:$POSTGRES_PORT                              ${ORANGE}║${NC}"
echo -e "${ORANGE}║${NC}                                                               ${ORANGE}║${NC}"
echo -e "${ORANGE}╠═══════════════════════════════════════════════════════════════╣${NC}"
echo -e "${ORANGE}║${NC}  ${YELLOW}Keycloak Admin:${NC}  ${KEYCLOAK_ADMIN_USER:-admin} / ${KEYCLOAK_ADMIN_PASS:-admin123}                            ${ORANGE}║${NC}"
echo -e "${ORANGE}║${NC}  ${YELLOW}RabbitMQ Admin:${NC}   ${RABBITMQ_USER:-guest} / ${RABBITMQ_PASS:-guest}                               ${ORANGE}║${NC}"
echo -e "${ORANGE}║${NC}  ${YELLOW}Test User:${NC}        admin@${KEYCLOAK_REALM:-sparksbm}.com / ${KEYCLOAK_ADMIN_PASS:-admin123}              ${ORANGE}║${NC}"
echo -e "${ORANGE}║${NC}                                                               ${ORANGE}║${NC}"
echo -e "${ORANGE}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "Press ${YELLOW}Ctrl+C${NC} to stop all services"
echo ""

#───────────────────────────────────────────────────────────────────────────────
# Wait and Cleanup
#───────────────────────────────────────────────────────────────────────────────
cleanup() {
    echo ""
    echo -e "${YELLOW}Stopping services...${NC}"
    
    # Stop frontend
    kill $FRONTEND_PID 2>/dev/null || true
    pkill -f "nuxi dev" 2>/dev/null || true
    
    # Stop backend
    kill $BACKEND_PID 2>/dev/null || true
    pkill -f "veo-rest" 2>/dev/null || true
    pkill -f "gradlew.*bootRun" 2>/dev/null || true
    
    # Stop Docker services
    cd "$KEYCLOAK_DIR" && docker compose down 2>/dev/null || docker-compose down 2>/dev/null
    
    echo -e "${GREEN}✓${NC} All services stopped"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Keep script running
wait $FRONTEND_PID
