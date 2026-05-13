# IranGore AI Backend - Graph RAG + Agentic AI

Production-ready chatbot backend combining Graph Retrieval Augmented Generation (RAG) with LangGraph-powered agentic AI. Features intelligent planning, validation, and retry logic for robust question-answering.

## ✨ Key Features

### 🧠 Intelligent Agent System
- **6 Agent Types**: chat, vector, cypher, full, scoped, deep_search (each with different strengths)
- **Planning Phase**: Agents understand questions and plan tool usage before acting
- **Validation Phase**: Answers verified for relevance and document sourcing
- **Automatic Retry**: Failed validations trigger retries with different strategies
- **LangGraph Powered**: Modern, production-ready framework with built-in persistence

### 📊 Graph RAG Architecture
- Neo4j knowledge graphs for structured document retrieval
- Semantic/vector search for content discovery
- **Smart Document Discovery** - finds relevant documents by name or content
- Cypher queries for relationship analysis
- Multi-layer retrieval combining structured and semantic approaches

### 🚀 API & Session Management
- FastAPI with async support
- Session-based conversation history via Neo4j
- RESTful endpoints for chat, agents, sessions
- Interactive API docs at `/docs`

### ⚙️ Flexible Configuration
- YAML-driven agent configuration (`agents/agents.yaml`)
- Environment-based settings for multi-deployment scenarios
- Support for Ollama (local) and OpenAI LLMs
- Configurable tool chains per agent

---

## 🚀 Quick Start (30 seconds)

### Local Development
```bash
# Setup environment
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your Neo4j, Ollama/OpenAI credentials

# Run
fastapi dev main.py
```

### Docker
```bash
cp .env.example .env
# Edit .env
docker-compose up -d
```

### Verify Installation
```bash
# Check health
curl http://localhost:8000/health

# List agents
curl http://localhost:8000/agents

# Chat with automatic orchestration
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What are the main topics?", "agent_name": "auto"}'
```

---

## 📚 Core Concepts

### The Six Agents

| Agent | Iterations | Best For | Speed |
|-------|-----------|----------|-------|
| **chat** | 12 | Simple Q&A | ⚡ Fast |
| **vector** | 14 | Content search | ⚡⚡ Medium |
| **cypher** | 16 | Complex queries | ⚡⚡ Medium ⭐ |
| **full** | 18 | Maximum analysis | 🔥 Slower |
| **scoped** | 12 | Domain-specific | ⚡ Fast |
| **deep_search** | 18 | Internet + internal document research | 🔥 Slower |

**Default**: `auto` - orchestration routes the query to the best agent.

### Planning → Execute → Validate → Retry

```
User Question
    ↓
[PLANNING] Agent analyzes question and plans tool usage
    ↓
[EXECUTING] Agent uses tools strategically
    ├─ Semantic search (find content)
    ├─ Graph queries (find relationships)
    └─ Document chat (context)
    ↓
[VALIDATING] Agent checks:
    ✓ Is answer relevant to question?
    ✓ Are sources from documents?
    ✓ Is answer complete?
    ↓
    NO → Retry with different tools/strategy
    YES → Final Answer (with sources)
```

### Tool Types

- **semantic_search**: Vector-based content discovery
- **graph_qa**: Cypher queries for relationships
- **document_chat**: LLM-based document interaction
- **list_documents**: List all available documents
- **search_documents_by_name**: Find documents by name/type (e.g., "statement of purpose", "CV")
- **find_relevant_documents**: Find documents relevant to a query using semantic similarity
- **get_chunks_from_query_documents**: Integrated workflow - find relevant docs then retrieve chunks
- **web_search**: Public internet search for broader or recent context

### Smart Document Discovery

The **cypher agent** uses intelligent document discovery:

1. **Extract** document type hints from questions (e.g., "statement of purpose")
2. **Search by name** if explicit document mentions are found
3. **Fall back to semantic search** for general queries
4. **Retrieve chunks** from identified documents
5. **Synthesize answers** with source citations

**Example**:
```
Query: "also look at the statement of purpose documents and identify what he is applying for?"

Agent workflow:
1. Extracts: "statement of purpose"
2. Searches by name → finds matching document
3. Retrieves chunks from that document
4. Answers: "Based on the statement of purpose, they are applying for..."
```

---

## 🏗️ Architecture & File Layout

```
IranGoreBackend/
├── main.py                    # FastAPI application
├── config.py                  # Settings management
├── schemas.py                 # Pydantic models
│
├── agents/
│   ├── agents.yaml           # Agent configuration (source of truth)
│   ├── agent_factory.py      # Factory with LangGraph integration
│   └── __init__.py          # Exports
│
├── tools/
│   ├── vector_tool.py           # Semantic vector search
│   ├── cypher_tool.py           # Graph queries
│   ├── document_graph_tool.py   # Document ingestion
│   ├── document_discovery_tool.py # Smart document finding
│   └── __init__.py
│
├── graph/
│   ├── connection.py         # Neo4j connection
│   ├── manager.py           # Graph operations
│   └── __init__.py
│
├── llms/
│   ├── manager.py           # LLM provider initialization
│   ├── ollama.py            # Ollama integration
│   └── __init__.py
│
├── sessions/
│   ├── manager.py           # Session lifecycle
│   └── __init__.py
│
├── core/
│   ├── logger.py            # Logging setup
│   ├── exceptions.py        # Custom exceptions
│   └── __init__.py
│
├── requirements.txt         # Python dependencies
├── .env.example            # Configuration template
├── Dockerfile              # Docker image
├── docker-compose.yml      # Multi-container setup
└── deployment/             # Deployment assets
```

---

## 🔧 Configuration

### Environment Variables (`.env`)

**Neo4j Database**:
```env
NEO4J_URI=neo4j://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
NEO4J_DATABASE=neo4j
```

**LLM Provider** (choose one):
```env
# For Ollama (local)
LLM_PROVIDER=ollama
LLM_MODEL=qwen3:8b
OLLAMA_BASE_URL=http://localhost:11434

# OR for OpenAI
LLM_PROVIDER=openai
LLM_MODEL=gpt-4
OPENAI_API_KEY=sk-xxx
```

**Agent Settings**:
```env
SESSION_TIMEOUT=3600
MAX_HISTORY_LENGTH=50
```

### Agent Configuration (`agents/agents.yaml`)

Customize agents directly in YAML:

```yaml
settings:
  default_agent: "auto"
  max_iterations: 15
  verbose_default: true

agents:
  cypher:
    name: "Cypher Agent"
    max_iterations: 16
    system_prompt: |
      You are an expert research assistant...
    tools:
      - name: "Document Chat"
        type: "document_chat"
      - name: "Vector Search"
        type: "vector_search"
      - name: "Graph Query"
        type: "cypher_qa"
```

---

## 📡 API Endpoints

### Chat & Agents

**POST /chat** - Send message to agent
```json
{
  "message": "Your question",
  "agent_name": "auto",    // optional, defaults to auto (orchestrator routing)
  "session_id": null,      // optional, creates new if null
  "include_sources": true  // optional
}
```

**GET /agents** - List available agents and capabilities

### Session Management

**POST /sessions** - Create new session
**GET /sessions** - List all sessions
**GET /sessions/{session_id}** - Get session info
**DELETE /sessions/{session_id}** - Delete session
**GET /history/{session_id}** - Get chat history

### System

**GET /health** - Health check
**GET /docs** - Interactive API documentation
**GET /redoc** - Alternative API docs

---

## 🛠️ Development & Customization

### Create Custom Agent

Edit `agents/agents.yaml`:

```yaml
agents:
  my_custom_agent:
    name: "My Custom Agent"
    description: "Specialized for my domain"
    type: "react"
    enabled: true
    max_iterations: 16
    system_prompt: |
      You are a specialized agent for...
    tools:
      - name: "Tool 1"
        description: "Does X"
        type: "document_chat"
      - name: "Tool 2"
        description: "Does Y"
        type: "vector_search"
```

### Modify Agent Behavior

Edit system_prompt in `agents/agents.yaml` for each agent to change:
- Reasoning style
- Tool preference
- Response format
- Domain constraints

### Add Custom Tool

In `agents/agent_factory.py`, extend `_build_tools()`:

```python
tool_functions = {
    "document_chat": existing_func,
    "vector_search": existing_func,
    "cypher_qa": existing_func,
    "my_custom_tool": my_custom_function,  # Add here
}
```

---

## 🚨 Troubleshooting

### Neo4j Connection Error
```
Error: Failed to connect to Neo4j
```
**Fix**: 
- Verify Neo4j is running: `docker ps | grep neo4j`
- Check credentials in `.env`
- Verify URI format: `neo4j://hostname:7687`

### LLM Not Responding
```
Error: Ollama is not reachable
```
**Fix**:
- Start Ollama: `ollama serve`
- Verify in `.env`: `OLLAMA_BASE_URL=http://localhost:11434`
- Test: `curl http://localhost:11434/api/tags`

### "Max iterations reached"
**Fix**:
- Question too complex → break into steps
- Use `full` agent (18 iterations vs 16)
- Check if documents contain relevant info

### Missing Property Warning
```
property `document_title` does not exist in database
```
**Fix**:
- This is non-critical (graceful degradation)
- Vector search still works, just missing that field
- Update document ingestion if you want that property

### Port Already in Use
```bash
# Use different port
fastapi dev main.py --port 8001
# Or in docker-compose.yml, change ports
```

---

## 🧪 Testing

### Run Agent Tests
```bash
python test_planning_validation.py --all-agents
```

### Test Specific Agent
```bash
python test_planning_validation.py --agent cypher --question "Your test question"
```

### Manual API Test
```bash
# List agents
curl http://localhost:8000/agents | jq

# Test chat
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What documents are available?",
    "agent_name": "vector",
    "include_sources": true
  }' | jq
```

---

## 📊 Performance & Optimization

### Agent Selection by Use Case

```
Simple questions (FAQ)          → chat agent (fastest)
Content discovery              → vector agent  
Complex analysis/relationships → cypher agent (recommended)
Maximum reasoning               → full agent
Domain-specific Q&A            → scoped agent
```

### Performance Tips

1. **Reuse sessions** for related questions (preserves context)
2. **Use cypher agent** for best balance of speed & quality
3. **Monitor iterations** - if hitting max, try simpler question
4. **Cache agents** - factory caches created agents
5. **Batch operations** - process multiple questions per session

---

## 🚀 Deployment

### Docker Compose (Recommended)
```bash
docker-compose up -d
# Includes: Backend, Neo4j, Ollama (optional)
```

### Kubernetes / Cloud
1. Build image: `docker build -t irangore-backend .`
2. Push to registry: `docker push your-registry/irangore-backend`
3. Deploy manifest with Neo4j external DB reference

### Production Checklist
- [ ] Set strong Neo4j password
- [ ] Use external LLM API or dedicated Ollama server
- [ ] Enable HTTPS/TLS for API
- [ ] Configure logging to file/ELK
- [ ] Set resource limits in docker-compose/k8s
- [ ] Monitor Neo4j query performance
- [ ] Regular backups of Neo4j data
- [ ] Rate limiting on API endpoints

---

## 🔬 Technology Stack

- **Framework**: FastAPI (async Python web)
- **Agent Framework**: LangGraph (modern ReAct agents)
- **Graph Database**: Neo4j (knowledge graphs)
- **Vector Store**: Neo4j Vector Index
- **LLMs**: Ollama (local) or OpenAI (cloud)
- **Message Protocol**: LangChain message types
- **Persistence**: Neo4j + file-based sessions
- **Containerization**: Docker + Docker Compose

---

## 📖 Additional Resources

### Key Implementation Files
- `agents/agents.yaml` - Full agent & tool configuration
- `agents/agent_factory.py` - Agent creation & planning logic
- `main.py` - FastAPI endpoints and request handling
- `tools/cypher_tool.py` - Graph query implementation
- `tools/vector_tool.py` - Vector search implementation

### Understanding Planning & Validation
The planning/validation system is implemented in:
1. Agent prompts in `agents/agents.yaml` (system_prompt fields)
2. ReAct loop in LangGraph (automatic planning/thinking)
3. Response validation via agent's Final Answer checks

### Database Schema
Documents stored as nodes with properties:
- `text`: Chunk content
- `document_id`: Document identifier
- `source_path`: File path/URL
- `chunk_index`: Position in document
- `page_number`, `line_number`: Location metadata

Embeddings stored in Neo4j Vector Index for semantic search.

---

## 🆘 Support & Debugging

### Enable Verbose Logging
```python
# In agents/agents.yaml
agents:
  cypher:
    verbose: true  # Shows all planning/validation steps
```

### Check Agent Configuration
```bash
python -c "
from agents import get_agent_factory
factory = get_agent_factory()
for agent in factory.get_enabled_agents():
    config = factory.get_agent(agent)
    print(f'{agent}: {config[\"max_iterations\"]} iterations')
"
```

### View API Documentation
Visit: `http://localhost:8000/docs` (Swagger UI)

---

## 📝 Release Notes

**Latest (LangGraph Migration)**
- ✅ Migrated from deprecated LangChain to LangGraph
- ✅ Built-in persistence (no manual memory management)
- ✅ Improved session/thread handling
- ✅ No deprecation warnings
- ✅ All planning/validation features preserved

**Previous Features**
- ✅ Planning phase implementation
- ✅ Validation phase with automatic retry
- ✅ 5-agent unified architecture
- ✅ YAML-based configuration
- ✅ Multi-tool orchestration

---

## 📄 License

[Specify your license here]

---

**Last Updated**: May 2026  
**Status**: ✅ Production Ready
