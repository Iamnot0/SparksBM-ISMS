# System Architecture Overview

## 🏗️ High-Level Architecture

```
User Message
    ↓
ChatRouter (orchestrator/chatRouter.py)
    ├─→ Pattern Matching (fast, simple operations)
    │   ├─→ List operations ("list assets")
    │   ├─→ Create operations ("create scope X")
    │   └─→ Subtype queries ("show subtypes of assets")
    │
    └─→ Complex Operations → MCP Server
            ↓
        LLM (OpenAI) → Understand Intent
            ↓
        Route to Tool:
            ├─→ link_objects (mcp/tools/linking.py)
            ├─→ unlink_objects
            ├─→ analyze_object (mcp/tools/analyze.py)
            └─→ compare_objects (mcp/tools/compare.py)
                ↓
            VeriniceTool → ISMS Backend (Verinice)
```

## 🤖 Agents

### MainAgent (`agents/mainAgent.py`)
- **Role**: Main entry point, orchestrates everything
- **Does**: Routes messages, manages state, coordinates other components
- **Used for**: All user interactions

### ISMSHandler (`agents/ismsHandler.py`)
- **Role**: Handles ISMS CRUD operations (Create, Read, Update, Delete)
- **Does**: Direct ISMS operations via VeriniceTool
- **Used for**: Simple operations like "create scope X", "list assets"

### ISMSCoordinator (`agents/coordinators/ismsCoordinator.py`)
- **Role**: More complex ISMS coordination (legacy, may not be actively used)
- **Does**: Advanced ISMS workflows

### ISMSAgent (`agents/ismsAgent.py`)
- **Role**: Another ISMS agent (legacy, may not be actively used)

### CodeAgent (`agents/codeAgent.py`)
- **Role**: Code-related operations
- **Does**: Code analysis, generation

## 🔧 MCP (Model Context Protocol)

**Location**: `Agentic Framework/mcp/`

**What it does**:
- Uses **LLM** to understand complex natural language requests
- Handles operations that need reasoning beyond simple pattern matching
- Routes to specialized tools

**Main Operations**:
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

**How it works**:
1. User sends message: "link Desktop to SCOPE1"
2. MCP Server uses LLM to understand intent
3. LLM extracts: `{tool: "link_objects", source_name: "Desktop", target_name: "SCOPE1"}`
4. MCP routes to `link_objects` tool
5. Tool executes via VeriniceTool
6. Returns result

## 🤖 LLM (Large Language Model)

### Currently Using: **OpenAI** (gpt-4o-mini)
- **Location**: `tools/llmTool.py`
- **Provider**: OpenAI only (code forces OpenAI)
- **Model**: `gpt-4o-mini` (default, configurable via `OPENAI_MODEL`)
- **API Key**: `OPENAI_API_KEY` environment variable

### Also Available (but not used): **Gemini**
- **Location**: `orchestrator/reasoningEngine.py`
- **Provider**: Google Gemini
- **Model**: `gemini-2.5-flash` or `gemini-1.5-flash`
- **Status**: Code exists but not actively used (main.py forces OpenAI)

### Where LLM is Used:
1. **MCP Server**: Intent understanding for complex operations
2. **ReasoningEngine**: General reasoning/questions (fallback when MCP doesn't handle it)
3. **IntentClassifier**: Classifying user intents (optional, may use pattern matching instead)

## 🔌 ISMS Backend Connection

### VeriniceTool (`tools/veriniceTool.py`)
- **Role**: Connects to Verinice ISMS backend
- **Does**: All ISMS operations (create, list, update, delete, link, etc.)
- **Backend**: Verinice API (http://localhost:8070)
- **Auth**: Keycloak (http://localhost:8080)
- **Client**: `SparksBMClient` from `SparksbmISMS/scripts/sparksbmMgmt.py`

**This is what "ISMS client not available" means** - VeriniceTool can't connect to the backend.

## 📊 Request Flow

### Simple Operations (Pattern Matching)
```
User: "list assets"
  → ChatRouter detects "list" pattern
  → Routes to ISMSHandler._handleList()
  → VeriniceTool.listObjects()
  → Returns results
```

### Complex Operations (MCP + LLM)
```
User: "link Desktop to SCOPE1"
  → ChatRouter detects it needs MCP
  → MCP Server.execute()
  → LLM (OpenAI) understands intent
  → Extracts: {tool: "link_objects", params: {...}}
  → Routes to mcp/tools/linking.py
  → VeriniceTool links objects
  → Returns results
```

### Create-and-Link Operations
```
User: "create scope AA and link with IT-System asset"
  → ChatRouter detects create-and-link pattern
  → MainAgent._handleCreateAndLink()
  → Step 1: ISMSHandler creates scope
  → Step 2: MCP Server links (with retry for bulk linking)
  → Returns combined result
```

## 🎯 What Uses What

| Component | Uses LLM? | Uses VeriniceTool? | Pattern or LLM? |
|-----------|-----------|-------------------|-----------------|
| ChatRouter | ❌ | ❌ | Pattern matching |
| ISMSHandler | ❌ | ✅ | Pattern matching |
| MCP Server | ✅ (OpenAI) | ✅ | LLM understanding |
| MainAgent | ✅ (optional) | ✅ | Both (routes) |
| ReasoningEngine | ✅ (Gemini/fallback) | ❌ | LLM reasoning |

## 🔑 Key Takeaways

1. **MCP = LLM-powered intent understanding** for complex operations
2. **Currently using OpenAI** (gpt-4o-mini), not Gemini
3. **Simple operations** (list, create) use **pattern matching** (fast, no LLM)
4. **Complex operations** (link, analyze, compare) use **MCP + LLM**
5. **ISMS client** = VeriniceTool connection to Verinice backend
6. **MainAgent** orchestrates everything

## 🚨 Common Confusion

- **"ISMS client not available"** = VeriniceTool can't connect to Verinice backend
- **MCP** = Not a separate service, it's a component that uses LLM for understanding
- **LLM** = Currently OpenAI, not Gemini (even though Gemini code exists)
- **Agents** = Multiple exist, but MainAgent is the main one used
