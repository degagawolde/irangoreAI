# IranGoreBackend

Unified chatbot backend using Graph RAG + Agentic AI, with a YAML-driven multi-agent system, planning/validation workflow, and Docker-ready deployment.

## At a Glance

- FastAPI backend for chat + session APIs
- Graph RAG with Neo4j + semantic/vector search
- Multi-agent architecture (`chat`, `vector`, `cypher`, `full`, `scoped`)
- Centralized agent/tool config in `agents/agents.yaml`
- Planning → Execute → Validate → Retry response flow
- Local + Docker deployment paths

## Core Features

- Agentic AI via ReAct-style tool orchestration
- Graph + vector retrieval for grounded responses
- Structured configuration with environment-driven settings
- Session-aware conversations and memory handling
- Production-oriented logging, health checks, and error handling

## Project Structure

- `main.py`: FastAPI app and endpoints
- `config.py`: settings management
- `schemas.py`: request/response models
- `core/`: logging and exceptions
- `agents/`: agent factory, YAML config, agent docs
- `tools/`: document/vector/cypher/ingestion tools
- `graph/`: Neo4j integration
- `llms/`: LLM provider integration
- `sessions/`: session lifecycle and history
- `deployment/`, `Dockerfile`, `docker-compose.yml`: deployment assets

## Agent System Summary

The unified agent system is built around:

- `agents/agents.yaml`: source of truth for agents, tools, settings
- `agents/agent_factory.py`: loads config, builds/caches agents, binds tools

### Available Agents

- `chat`: lightweight chat/doc interaction
- `vector`: semantic search focused
- `cypher`: graph + vector + chat (recommended default)
- `full`: all tools enabled for complex workflows
- `scoped`: domain-specific constrained behavior

### Planning and Validation Flow

Each response follows:

1. Plan what the question needs and which tools to use
2. Execute tool calls strategically
3. Validate relevance, grounding, and completeness
4. Retry with alternate strategy if validation fails

This is documented across the planning docs and reflected in the agent prompts/config.

## Quick Start

### Option 1: Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python setup_guide.py
fastapi dev main.py
```

### Option 2: Docker Compose

```bash
cp .env.example .env
docker-compose up -d
```

## Basic Verification

```bash
curl http://localhost:8000/health
curl http://localhost:8000/agents
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello","agent_name":"cypher"}'
```

## API Endpoints (Main)

- `POST /chat`
- `POST /sessions`
- `GET /sessions`
- `GET /sessions/{id}`
- `DELETE /sessions/{id}`
- `GET /agents`
- `GET /health`
- `GET /docs` and `GET /redoc`

## Configuration Essentials

Set these in `.env`:

- `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`
- `LLM_PROVIDER` (e.g., `ollama` or `openai`)
- `LLM_MODEL`, `LLM_TEMPERATURE`
- `OLLAMA_BASE_URL` (if using Ollama)
- `OPENAI_API_KEY` (if using OpenAI)
- `SESSION_TIMEOUT`, `MAX_HISTORY_LENGTH`

## Consolidated Documentation Map

This README summarizes the following docs and text guides:

### General backend/refactor docs

- `START_HERE.txt`: onboarding and run flow
- `COMPLETION_REPORT.md`: high-level completion summary
- `REFACTORING_SUMMARY.md`: architecture/code changes
- `QUICKSTART.md`: setup/deployment options

### Unified agent architecture docs

- `UNIFIED_STRUCTURE.md`: architecture overview
- `IMPLEMENTATION_SUMMARY.md`: implementation recap
- `AGENTS_GUIDE.md`: usage/customization guide
- `QUICK_REFERENCE.md`: fast commands and patterns
- `STRUCTURE_DIAGRAM.txt`: visual architecture
- `FILES_MANIFEST.txt`: file inventory

### Planning/validation and migration docs

- `PLANNING_AND_VALIDATION.md`: planning/validation model
- `AGENT_QUICKSTART.md`: quick practical usage
- `COMPLETE_AGENT_GUIDE.md`: full functional guide
- `AGENT_PLANNING_IMPLEMENTATION.md`: implementation details
- `AGENT_IMPLEMENTATION_CHECKLIST.md`: verification checklist
- `AGENT_PLANNING_COMPLETE.md`: completion summary
- `AGENT_FILES_MANIFEST.md`: planning-related file manifest
- `AGENT_DOCUMENTATION_INDEX.md`: documentation index
- `LANGGRAPH_MIGRATION.md`: LangChain → LangGraph migration notes

## Troubleshooting (Common)

- Neo4j failures: verify URI/credentials and that Neo4j is running
- LLM failures: verify provider config, key, or Ollama server
- Port conflicts: run on another port (e.g., `--port 8001`)
- Import/module issues: ensure `.venv` is active and deps are installed

## Notes

- This repository contains extensive historical and implementation docs.
- This `README.md` is intended as the single entry point summarizing all `.md` and `.txt` guides currently in the project.
