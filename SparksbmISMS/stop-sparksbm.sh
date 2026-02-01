#!/bin/bash
#═══════════════════════════════════════════════════════════════════════════════
#  SparksBM ISMS Platform - Stop Script
#═══════════════════════════════════════════════════════════════════════════════

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
KEYCLOAK_DIR="$PROJECT_DIR/keycloak"

echo ""
echo -e "${YELLOW}⚡ Stopping SparksBM ISMS...${NC}"
echo ""

# Stop frontend
echo -e "${BLUE}  →${NC} Stopping Frontend..."
pkill -f "nuxi dev" 2>/dev/null && echo -e "    ${GREEN}✓${NC} Frontend stopped" || echo -e "    ${YELLOW}⚠${NC} Frontend not running"

# Stop backend
echo -e "${BLUE}  →${NC} Stopping Backend..."
pkill -f "veo-rest" 2>/dev/null && echo -e "    ${GREEN}✓${NC} Backend stopped" || echo -e "    ${YELLOW}⚠${NC} Backend not running"
pkill -f "gradlew.*bootRun" 2>/dev/null || true

# Stop Docker services (PostgreSQL, Keycloak, RabbitMQ)
echo -e "${BLUE}  →${NC} Stopping Docker services (PostgreSQL, Keycloak, RabbitMQ)..."
cd "$KEYCLOAK_DIR"
docker compose down 2>/dev/null || docker-compose down 2>/dev/null
echo -e "    ${GREEN}✓${NC} Docker services stopped"

echo ""
echo -e "${GREEN}✓${NC} All services stopped"
echo ""
