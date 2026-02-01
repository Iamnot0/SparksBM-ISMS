# SparksBM System Architecture

Last Updated: 2026-01-30

## System Overview

Intelligent ISMS management system with natural language interface for Information Security Management System operations.

### Architecture Layers

```
Frontend (Vue/Nuxt) → NotebookLLM API (FastAPI) → Agentic Framework (Python) → SparksbmISMS Backend (Java/Kotlin) → PostgreSQL
```

### Deployment Services

- Keycloak (Port 8080) - Authentication
- Verinice Backend (Port 8070) - ISMS API
- PostgreSQL (Port 5432) - Database
- NotebookLLM API (Port 8000) - FastAPI
- Frontend (Port 3000) - Nuxt.js

---

## 1. Frontend Documentation (Vue/Nuxt)

### Overview

A reactive Single Page Application (SPA) serving as the natural language interface for ISMS operations.

### 1.1 Core Architecture

**Framework:** Vue.js 3 with Nuxt.js

**Main Layout:** `notebook.vue` acts as the central hub, managing three synchronized panels

**State Management:** Uses reactive references and localStorage for session persistence

**File:** `NotebookLLM/frontend/layouts/notebook.vue`

#### State Management Details

- **Session ID:** localStorage persistence with automatic restoration
- **Chat History:** localStorage per session (last 20 messages)
- **Sources:** localStorage per session (ISMS object sources)
- **Reasoning Steps:** In-memory only (cleared on page refresh)

#### Reactive References

```javascript
const sessionId = ref(null)
const chatHistory = ref([])
const sources = ref([])
const reasoningSteps = ref([])
```

### 1.2 Key UI Components

#### Chat Panel (Center)

**SSE Consumer:** Listens to `/api/agent/stream/{sessionId}` for real-time events

**Event Types:**
- `thought` - Agent reasoning step
- `tool_start` - Tool execution started
- `tool_complete` - Tool execution finished
- `complete` - Task completed
- `error` - Error occurred

**Thinking UI:** Displays "Thought Bubbles" and incremental tool logs

**Implementation:**
```javascript
// SSE Connection
const eventSource = new EventSource(`/api/agent/stream/${sessionId.value}`)
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data)
  if (data.type === 'thought') {
    reasoningSteps.value.push(data)
  }
}
```

**Status:** ✅ All SSE issues resolved

#### Sources Panel (Left)

**Context Management:** Manages ISMS object sources for context-aware operations

**ISMS Object Sources:**
- Scopes, Assets, Controls, Processes, Persons, Documents, Incidents, Scenarios

**Implementation:**
```javascript
// Sources are ISMS objects, not files
const sources = ref<Array<{
  id: string
  name: string
  type: string
  domainId: string
}>>([])
```

**Status:** ✅ ISMS object context management implemented

#### Studio Panel (Right)

**Agent Processing:** Displays real-time reasoning steps and tool execution

**Components:**
- Reasoning Steps section - Shows agent thought process
- Agent Status - System status indicator

**Status:** ✅ Real-time agent processing display working

### 1.3 API Integration

**Composable:** `composables/useApi.ts`

**Endpoints Integrated:**
1. `POST /api/agent/chat` - Process chat message
2. `POST /api/agent/session` - Create session
3. `GET /api/agent/stream/{sessionId}` - SSE streaming
4. `GET /api/agent/context/{sessionId}` - Get context
5. `POST /api/agent/context` - Add context
6. `DELETE /api/agent/context/{sessionId}/{sourceId}` - Remove context
7. `GET /api/agent/tools` - Get available tools
8. `POST /api/agent/isms` - Direct ISMS operation

**Error Handling:** User feedback via chat messages

**Request/Response Type Safety:** TypeScript interfaces

**Status:** ✅ All critical frontend issues resolved

---

## 2. Backend Documentation (Three-Tier)

### Overview

An intelligent orchestration layer bridging the modern API with the legacy ISMS system.

### 2.1 Layer 1: NotebookLLM API (FastAPI)

**Role:** Gateway and session manager

**Directory:** `NotebookLLM/api/`

#### Endpoints

**Main Entry Point:**
- `POST /api/agent/chat` - Process chat message
  - Validates session
  - Builds context from ISMS object sources
  - Calls AgentBridge.process()
  - Returns formatted response

**Real-Time Streaming:**
- `GET /api/agent/stream/{sessionId}` - Server-Sent Events (SSE) endpoint for real-time feedback
  - Heartbeat interval: 30 seconds
  - Connection keep-alive headers
  - Event types: thought, tool_start, tool_complete, complete, error

**Session Management:**
- `POST /api/agent/session` - Create new session (UUID)
- `GET /api/agent/context/{sessionId}` - Get session context
- `POST /api/agent/context` - Add ISMS object source to context
- `DELETE /api/agent/context/{sessionId}/{sourceId}` - Remove source

**Direct ISMS:**
- `POST /api/agent/isms` - Direct ISMS operation (bypasses pattern matching)

#### Services

**agentService.py** - Agent orchestration and lazy loading

**Key Functions:**
- `chat()` - Process chat message
  - Validates session
  - Builds context from ISMS object sources
  - Calls AgentBridge.process()
  - Updates session with messages
- `createSession()` - Create new session
- `getContext()` - Get session context
- `addContext()` - Add ISMS object source to context
- `removeContext()` - Remove source from context

**Lazy Initialization:**
- AgentBridge initialized on first use (not at startup)
- Prevents startup failures

**eventQueue.py** - Thread-safe queue buffering events for the SSE stream

**Key Functions:**
- `get_queue()` - Get or create event queue for session
- `push_event()` - Push event to session queue (non-blocking)
- `get_event()` - Get next event (async, blocking with timeout)
- `get_history()` - Get event history for session (last 100 events)

**Event Structure:**
```python
{
    'type': 'thought',
    'data': {'content': '...', 'iteration': 1},
    'timestamp': 1234567890.123
}
```

**Thread Safety:** Uses asyncio.Queue per session

**sessionService.py** - Session management

**Storage:** In-memory dictionary (UUID → session data)

**Session Data:**
- sessionId: UUID
- userId: string
- createdAt: timestamp
- conversationHistory: last 20 messages
- activeContext: ISMS object sources
- lastActivity: timestamp

**Known Issues:**
- Issue #3: Sessions not persistent (lost on restart) - LOW PRIORITY

#### Integration Layer

**agentBridge.py** - Bridge between web API and Agentic Framework

**Key Functions:**
- `initialize()` - Initialize MainAgent and register tools
- `process()` - Process message through executor

**Initialization:**
- Creates MainAgent instance
- Registers tools (lazy initialization for VeriniceTool)
- Creates AgentExecutor
- Registers ReasoningEngine (Gemini API)

**Context Injection:**
- Injects session context into agent state
- Preserves reasoning steps

**Status:** ✅ LLM tool registration fixed

### 2.2 Layer 2: Agentic Framework (Python)

**Role:** The "Brain" implementing intelligent ISMS operations

**Directory:** `Agentic Framework/`

#### Orchestration

**chatRouter.py** - Routes intents (ISMS operations) using regex patterns

**Routing Priority:**
1. Follow-ups (subtype selection, report generation)
2. Greetings
3. Create-and-link operations
4. Subtype-filtered list queries
5. Verinice operations (ISMS commands)
6. Fallback knowledge base queries
7. ReasoningEngine (Gemini) for knowledge questions

**Pattern Matching Examples:**
- ISMS: `create scope X`, `list assets`, `link Desktop to SCOPE1`
- Subtype queries: `how many assets in our IT-System assets`
- Create-and-link: `create scope X and link with IT-System assets`

**State Management:**
- Router receives state by REFERENCE (not copy)
- All state mutations preserved
- Prevents context loss bugs

**Status:** ✅ All routing handlers implemented

**mainAgent.py** - Central controller delegating tasks to specialized handlers

**Key Functions:**
- `process()` - Main entry point
- `_processChatMessage()` - Chat message processing
- `_executeRoutingDecision()` - Execute ChatRouter decisions
- `_handleVeriniceOp()` - ISMS operation handler
- `_handleCreateAndLink()` - Create-and-link handler
- `_handleISMSReconciliation()` - ISMS reconciliation handler

**Status:** ✅ All routing handlers implemented

#### Agents (Specialized Workers)

**ISMS Operator** - Uses `ismsController.py` for tiered routing

**Tier Detection:**
- Tier 1 (Fast Path): Simple CRUD → ISMSFastPath → ISMSCoordinator (deterministic, fast, no LLM)
- Tier 2/3 (Agent Path): Complex operations → ISMSAgent → ReAct loop (intelligent, reasoning, uses LLM)

**ISMSAgent ReAct Loop:**
- Max iterations: 10
- Pattern: Thought → Action → Observation → Repeat
- System prompt filtering to prevent exposing internal instructions
- **Few-Shot Prompting:** System prompt includes robust examples for CRUD and Analysis reasoning.

**Status:** ✅ All ISMS operations working

#### Tools

**veriniceTool.py** - Manages Verinice API interaction and auth retries

**Authentication:**
- Keycloak integration (port 8080)
- Token refresh on 401 responses
- Retry mechanism: 3 attempts, 2s delay
- Cold start handling for backend

**Operations:**
- createObject, listObjects, getObject, updateObject, deleteObject
- compareObjects, compareDomains, findDifferences
- linkObjects, unlinkObjects
- listCatalogItems

**Status:** ✅ VERIFIED - All operations working
- ✅ UPDATE operation fixed (required field validation, ETag validation)
- ✅ LINK operation fixed (unit-level scope search)
- ✅ All indexing errors fixed (safe array/list/dict access)

**llmTool.py** - LLM integration using Google Gemini API

**Provider:** Google Gemini (not OpenAI)

**Configuration:**
- Model: `gemini-2.5-flash` (default, configurable via `GEMINI_MODEL`)
- API Key: `GEMINI_API_KEY` environment variable
- Features: Text generation, entity extraction

**Status:** ✅ Gemini API integration complete

**ReasoningEngine** - LLM-based reasoning for knowledge questions

**Location:** `orchestrator/reasoningEngine.py`

**Provider:** Google Gemini

**Purpose:** Handles ISMS knowledge questions (e.g., "What is ISO27001?")

**Features:**
- Concise mode (300 tokens max) - Increased from 80 words for better responses
- Markdown stripping
- Question type detection
- Fallback engine when API unavailable: Provides context-aware suggestions (create/list/etc.) based on query keywords.

**Status:** ✅ ISMS knowledge question handling working and improved

#### MCP (Model Context Protocol)

**Location:** `Agentic Framework/mcp/`

**What it does:**
- Uses **Gemini LLM** to understand complex natural language requests
- Handles operations that need reasoning beyond simple pattern matching
- Routes to specialized tools

**Main Operations:**
1. **Linking** (`mcp/tools/linking.py`)
   - "link Desktop to SCOPE1"
   - "link SCOPE1 with IT-System assets" (bulk linking)
   - Handles bidirectional linking, typos, incomplete sentences

2. **Analysis** (`mcp/tools/analyze.py`)
   - "analyze SCOPE1"
   - "what is linked with SCOPE1"
   - Provides detailed object analysis

3. **Comparison** (`mcp/tools/compare.py`)
   - "compare SCOPE1 and SCOPE2"
   - "show differences between IT-System and DataType assets"

**How it works:**
1. User sends message: "link Desktop to SCOPE1"
2. MCP Server uses Gemini LLM to understand intent
3. LLM extracts: `{tool: "link_objects", source_name: "Desktop", target_name: "SCOPE1"}`
4. MCP routes to `link_objects` tool
5. Tool executes via VeriniceTool
6. Returns result

**Fallback:** Pattern matching when LLM quota exceeded (42+ hardcoded patterns)

**Status:** ✅ MCP fully operational for ISMS operations

#### Reconciliation & Audit

**reconciliationUtils.py**
- Standardized logic for comparing ISMS objects
- Ignores system metadata (IDs, timestamps) to focus on drift

**asset_drift_audit.py**
- Automated script to compare two domains (e.g., Prod vs Backup)
- Uses agent capabilities to detect and report drift

### 2.3 Layer 3: Legacy ISMS Backend (SparksbmISMS)

**Role:** System of Record for compliance data

**Directory:** `SparksbmISMS/`

#### Components

**Verinice VEO** - Java/OSGi backend (Port 8070)

**Technology Stack:**
- Java/Kotlin
- Gradle build system
- OSGi framework
- REST API

**API Endpoints:**
- `/api/v1/domains/{domainId}/scopes` - Scope operations
- `/api/v1/domains/{domainId}/assets` - Asset operations
- `/api/v1/domains/{domainId}/controls` - Control operations
- And more for all object types...

**Keycloak** - Identity Provider (Port 8080)

**Configuration:**
- Realm: master
- Client: sparksbm-client
- Authentication: OAuth2/OIDC

**PostgreSQL** - Database (Port 5432)

**Schema:**
- Domains, Units, Objects (scopes, assets, controls, etc.)
- Relationships, Compliance data

---

## System Status (2026-01-30)

### ISMS Operations Status
- ✅ **LIST**: Working (100%)
- ✅ **CREATE**: Working (100%)
- ✅ **GET**: Working (100%)
- ✅ **UPDATE**: Working (100%)
- ✅ **DELETE**: Working (100%)
- ✅ **LINK**: Working (100%)
- ✅ **UNLINK**: Working (100%)
- ✅ **ANALYZE**: Working (100%)
- ✅ **COMPARE**: Working (100%)

**Core Operations**: 9/9 (100%)

### LLM Integration Status
- ✅ Gemini API integration complete
- ✅ ReasoningEngine for knowledge questions (Improved truncation handling)
- ✅ MCP Server for complex operations
- ✅ Fallback mechanisms in place (Context-aware suggestions)

### Code Quality Status
- ✅ All indexing errors fixed
- ✅ Safe array/list/dict access throughout
- ✅ Comprehensive error handling
- ✅ Clear validation and error messages
- ✅ Production-ready code
- ✅ Robust prompt templates implemented
- ✅ Subtype change restrictions handled automatically (Delete/Recreate logic)

### Frontend Status
- ✅ All critical bugs resolved
- ✅ SSE reconnection logic fixed
- ✅ Session creation feedback implemented
- ✅ Request timeout handling implemented
- ✅ Memory leak fixes (reasoning steps, localStorage quota)
- ✅ File upload removed (ISMS-only focus)
- ✅ Workspace/repository features removed

### Backend Status
- ✅ All routing handlers implemented
- ✅ ISMS reconciliation working (Standardized logic added)
- ✅ LLM tool registration fixed
- ✅ All ISMS operations functional
- ✅ Code analysis/writing features removed
- ✅ Document processing features removed
- ✅ Automated Drift Audit script available

---

## Architecture Quality Assessment

### Strengths
- Modular design with clear separation of concerns
- Robust error handling with fallbacks
- ReAct loops prevent infinite loops with max iteration caps
- SSE streaming for real-time feedback
- Three-tier architecture with clear boundaries
- All critical bugs resolved
- Production-ready code quality
- ISMS-focused architecture (no unnecessary features)
- **Auditable Quality:** Evaluation metrics persist to JSON

### Known Issues (Non-Critical)
- Session persistence not implemented (in-memory only) - LOW PRIORITY
- Event typing not validated (loose dictionaries) - LOW PRIORITY

### Risk Level
- **Critical bugs**: 0 (all resolved)
- **Optimization issues**: 2 (all non-critical, low priority)
- **Production Status**: ✅ READY

---

## Document Status

Status: CURRENT  
Last Updated: 2026-01-30  
System Version: v2.1 (ISMS-Only Focus, Enhanced Gemini Integration, Quality Metrics)