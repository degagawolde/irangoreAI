# Chatbot Backend - Graph RAG with Agentic AI

A production-ready chatbot backend powered by agentic AI with Graph Retrieval Augmented Generation (RAG) capabilities.

## Overview

This chatbot backend combines:
- **Agentic AI**: ReAct agents for intelligent decision-making and tool usage
- **Graph RAG**: Leverages Neo4j for structured knowledge retrieval
- **Vector Search**: Semantic search capabilities for document retrieval
- **LLM Integration**: Support for Ollama, OpenAI, and other LLM providers
- **Session Management**: Persistent conversation history
- **FastAPI**: Modern, production-ready API

## Architecture

```
chatbot-backend/
├── main.py                 # FastAPI application
├── config.py              # Configuration management
├── schemas.py             # Pydantic models
├── core/                  # Core utilities
│   ├── logger.py         # Logging setup
│   ├── exceptions.py     # Custom exceptions
│   └── __init__.py
├── graph/                 # Graph database management
│   ├── manager.py        # Neo4j connection manager
│   └── __init__.py
├── llms/                  # LLM management
│   ├── manager.py        # LLM initialization
│   └── __init__.py
├── agents/                # Agentic AI
│   ├── react_agent.py    # ReAct agent implementation
│   └── __init__.py
├── tools/                 # Agent tools
│   ├── cypher_tool.py    # Graph query tool
│   ├── vector_tool.py    # Vector search tool
│   └── __init__.py
├── sessions/              # Session management
│   ├── manager.py        # Session lifecycle
│   └── __init__.py
├── requirements.txt       # Python dependencies
├── .env.example          # Environment template
└── README.md             # This file
```

## Installation

### Prerequisites

- Python 3.9+
- Neo4j database (running)
- Ollama or OpenAI API key (for LLM)

### Setup

1. **Clone and navigate to project**
```bash
cd IranGoreBackend
```

2. **Create virtual environment**
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. **Run the application**
```bash
fastapi dev main.py
```

The API will be available at `http://localhost:8000`

## Configuration

### Environment Variables

Key configuration variables in `.env`:

```
# LLM Provider
LLM_PROVIDER=ollama              # ollama, openai, etc.
LLM_MODEL=qwen3:8b             # Model name
LLM_TEMPERATURE=0.7            # Temperature for generation

# Neo4j Database
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password
NEO4J_DATABASE=neo4j

# Ollama (if using local models)
OLLAMA_BASE_URL=http://localhost:11434

# Vector Store
VECTOR_INDEX_NAME=moviePlots
VECTOR_NODE_LABEL=Movie
VECTOR_TEXT_PROPERTY=plot
VECTOR_EMBEDDING_PROPERTY=plotEmbedding

# Session Management
SESSION_TIMEOUT=3600           # 1 hour
MAX_HISTORY_LENGTH=50          # Max messages in history
```

## API Endpoints

### Chat Endpoints

#### Create Chat Session
```
POST /chat
Content-Type: application/json

{
  "message": "What is the capital of France?",
  "session_id": null,  # Optional, creates new session if null
  "include_sources": false
}

Response:
{
  "reply": "Paris is the capital of France.",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "message_count": 2,
  "sources": null,
  "metadata": {"model": "qwen3:8b"}
}
```

#### Get Session Info
```
GET /sessions/{session_id}

Response:
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2024-01-15T10:30:00",
  "last_accessed": "2024-01-15T10:35:00",
  "message_count": 5,
  "metadata": {}
}
```

#### List All Sessions
```
GET /sessions

Response:
{
  "total": 3,
  "sessions": [
    {
      "session_id": "...",
      "created_at": "...",
      "message_count": 5
    }
  ]
}
```

#### Delete Session
```
DELETE /sessions/{session_id}

Response:
{
  "status": "deleted",
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### System Endpoints

#### Health Check
```
GET /health

Response:
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2024-01-15T10:30:00",
  "services": {
    "llm": "ok",
    "graph": "ok",
    "session_manager": "ok"
  }
}
```

## Core Components

### 1. Configuration Management (`config.py`)

Centralized configuration using Pydantic Settings:
- Loads from environment variables
- Type-safe configuration
- Support for different LLM providers
- Configurable vector store

### 2. Logging (`core/logger.py`)

Production-grade logging:
- Console and file handlers
- Rotating file handlers
- Separate error logs
- Structured logging format

### 3. Graph Management (`graph/manager.py`)

Neo4j integration:
- Connection pooling
- Query execution with error handling
- Schema inspection
- Singleton pattern for single connection

### 4. LLM Management (`llms/manager.py`)

LLM abstraction layer:
- Support for multiple providers (Ollama, OpenAI, etc.)
- Unified embeddings interface
- Lazy initialization
- Singleton pattern

### 5. Agent Framework (`agents/react_agent.py`)

ReAct agent implementation:
- Tool registration
- Agent execution
- Error handling
- Conversation context

### 6. Tools (`tools/`)

- **Cypher Tool**: Graph database queries
- **Vector Tool**: Semantic search

### 7. Session Management (`sessions/manager.py`)

- Session lifecycle management
- Message history tracking
- Session expiration
- In-memory storage (can extend to Redis/DB)

## Usage Examples

### Python Client Example

```python
import requests

BASE_URL = "http://localhost:8000"

# Create a chat session
response = requests.post(
    f"{BASE_URL}/chat",
    json={
        "message": "Tell me about movies directed by Spielberg",
        "include_sources": True
    }
)

session_id = response.json()["session_id"]
print(response.json()["reply"])

# Continue conversation
response = requests.post(
    f"{BASE_URL}/chat",
    json={
        "message": "What about his most famous films?",
        "session_id": session_id
    }
)

print(response.json()["reply"])

# Get session info
response = requests.get(f"{BASE_URL}/sessions/{session_id}")
print(response.json())
```

### cURL Examples

```bash
# Chat
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello"}'

# Get session info
curl http://localhost:8000/sessions/550e8400-e29b-41d4-a716-446655440000

# Health check
curl http://localhost:8000/health
```

## Error Handling

The API uses standard HTTP status codes:

- **200 OK**: Successful request
- **400 Bad Request**: Invalid session or request format
- **404 Not Found**: Session not found
- **500 Internal Server Error**: Server or service error
- **503 Service Unavailable**: One or more services down

Error responses include:
```json
{
  "error": "Error message",
  "error_code": "ERROR_CODE",
  "timestamp": "2024-01-15T10:30:00",
  "details": {}
}
```

## Extending the System

### Adding Custom Tools

```python
from agents import get_react_agent
from langchain_core.tools import Tool

def custom_function(query: str) -> str:
    # Your implementation
    return "result"

agent = get_react_agent()
agent.toolkit.register_tool(
    name="Custom Tool",
    description="Description of what this tool does",
    func=custom_function
)
```

### Adding New LLM Providers

Extend `LLMManager._initialize_llm()` in `llms/manager.py`:

```python
elif settings.LLM_PROVIDER.lower() == "anthropic":
    self._initialize_anthropic(settings)
```

### Persistent Session Storage

Replace in-memory `SessionManager` with database-backed storage:
- Add SQLAlchemy models
- Implement session persistence
- Add session migration to Redis for high-traffic scenarios

## Deployment

### Using Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

CMD ["fastapi", "dev", "main.py"]
```

### Using Gunicorn

```bash
pip install gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app
```

## Monitoring

The application includes:
- Structured logging to `logs/chatbot.log`
- Error logging to `logs/error.log`
- Health check endpoint
- Session metrics

## Performance Considerations

- **Conversation Context**: Limited to `MAX_HISTORY_LENGTH` messages
- **Session Timeout**: Automatic cleanup of expired sessions
- **Vector Search**: K-nearest neighbors default to 5 results
- **Agent Iterations**: Maximum 10 iterations per query

## Troubleshooting

### Neo4j Connection Failed
- Verify Neo4j is running
- Check connection URI in `.env`
- Verify credentials

### LLM Not Responding
- For Ollama: Check `OLLAMA_BASE_URL` and ensure Ollama is running
- For OpenAI: Verify `OPENAI_API_KEY` is set

### Session Issues
- Sessions expire after `SESSION_TIMEOUT` seconds
- Use `/sessions/{id}` to check session status
- Create new session if expired

## Development

### Running Tests
```bash
pytest tests/
```

### Code Quality
```bash
# Format code
black .

# Lint
pylint *.py

# Type checking
mypy .
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - see LICENSE file for details

## Support

For issues, questions, or suggestions, please open an issue on GitHub.

## Roadmap

- [ ] Redis session storage
- [ ] Database persistence layer
- [ ] Advanced analytics
- [ ] Multi-agent orchestration
- [ ] Function calling support
- [ ] Streaming responses
- [ ] WebSocket support for real-time chat

---

**Version**: 1.0.0  
**Last Updated**: January 2024
