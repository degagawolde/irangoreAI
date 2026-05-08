# Unified Agent Structure

Your agents are now unified under a single YAML configuration system. This provides a centralized way to manage, configure, and create agents.

## Configuration File

**Location:** `agents/agents.yaml`

The YAML file defines:
- **Agents**: Available agent configurations (chat, vector, cypher, full, scoped)
- **Tools**: Tool definitions mapped by type
- **Settings**: Global configuration (default agent, timeouts, etc.)

## Available Agents

### 1. **Chat Agent** (Lightweight)
```yaml
agent_name: "chat"
```
- Minimal tools - just general chat
- Best for: Simple conversational interactions
- Uses: Document chat only

### 2. **Vector Search Agent**
```yaml
agent_name: "vector"
```
- Semantic search over document chunks
- Best for: Finding similar content across documents
- Uses: Chat + Vector Search

### 3. **Cypher Agent** (Recommended)
```yaml
agent_name: "cypher"
```
- Full structured queries + semantic search
- Best for: Comprehensive document querying
- Uses: Chat + Vector Search + Cypher Graph Queries

### 4. **Full-Featured Agent**
```yaml
agent_name: "full"
```
- All available tools including document ingestion
- Best for: Complete document analysis workflows
- Uses: All tools (chat, search, cypher, ingestion)

### 5. **Scoped Agent**
```yaml
agent_name: "scoped"
```
- Domain-specific queries with restricted scope
- Best for: Focused domain analysis
- Uses: Chat only (can be extended per domain)

## Usage

### Basic Usage

```python
from agents import create_agent, generate_response, get_agent_factory

# Create default agent (uses agents.yaml default_agent)
agent = create_agent()

# Generate response
response = generate_response("What documents are available?")
print(response)
```

### Using Specific Agent

```python
# Create specific agent
agent = create_agent(agent_name="cypher")

# Or use wrapper function
response = generate_response(
    "What topics are covered in the documents?",
    agent_name="cypher"
)
```

### List Available Agents

```python
from agents import list_agents, get_enabled_agents

# All agents
all_agents = list_agents()
print(all_agents)  # ['chat', 'vector', 'cypher', 'full', 'scoped']

# Only enabled agents
enabled = get_enabled_agents()
print(enabled)
```

### Access Factory

```python
from agents import get_agent_factory

factory = get_agent_factory()

# Get agent configuration
config = factory.get_agent("cypher")
print(config["system_prompt"])

# Get specific agent
agent = factory.create_agent("cypher")
```

## Customization

### Add New Agent

Edit `agents/agents.yaml`:

```yaml
agents:
  my_agent:
    name: "My Custom Agent"
    description: "Description of what this agent does"
    type: "react"
    enabled: true
    system_prompt: "Your custom system prompt..."
    tools:
      - name: "Tool Name"
        description: "What it does"
        type: "tool_type"  # Must match existing tool type
    memory:
      enabled: true
      type: "neo4j_chat_history"
    verbose: false
```

### Add New Tool

1. Create the tool function in appropriate module
2. Add tool definition to `agents/agents.yaml` under `tools:`
3. Add tool function mapping in `agent_factory.py` `_build_tools()` method

## Integration with Main Application

In your `main.py`:

```python
from agents import generate_response, get_enabled_agents

@app.post("/chat")
async def chat(request: ChatRequest):
    # Use default agent or specify one
    response = generate_response(
        request.message,
        agent_name=request.agent or "cypher"  # Default to cypher
    )
    return {"reply": response, "session_id": session_id}

@app.get("/agents")
async def list_available_agents():
    return {"agents": get_enabled_agents()}
```

## Architecture

```
agents/
├── agents.yaml                 # Configuration (Single Source of Truth)
├── agent_factory.py            # Unified factory & loader
├── __init__.py                 # Exports
├── agent-chat.py               # Legacy (keep for backward compatibility)
├── agent-cypher.py             # Legacy
├── agent-vector.py             # Legacy
├── agent-scoped.py             # Legacy
└── react_agent.py              # Legacy framework
```

## Benefits

1. **Centralized Configuration**: All agents defined in one YAML file
2. **Easy Customization**: Add/modify agents without code changes
3. **Tool Management**: Reusable tool definitions
4. **Caching**: Agent instances are cached for performance
5. **Backward Compatible**: Legacy imports still work
6. **Scalable**: Easy to add new agents and tools
7. **Type-Safe**: Clear configuration structure

## Migration from Legacy Agents

Old way:
```python
from agents.agent_cypher import generate_response
response = generate_response(user_input)
```

New way:
```python
from agents import generate_response
response = generate_response(user_input, agent_name="cypher")
```

Both work! The new system is backward compatible.

## Performance Notes

- Agents are cached after first creation
- Memory is managed per session via Neo4j
- Vector search uses existing embeddings
- Cypher queries are optimized for the schema
- Consider using "chat" agent for simple queries (faster)

## Troubleshooting

**Agent not found**
- Check agent name exists in `agents.yaml`
- Verify agent `enabled: true`

**Tool not working**
- Verify tool type exists in tool mappings
- Check tool module/function is imported

**Configuration errors**
- Validate YAML syntax (spaces, indentation)
- Check all required fields are present

Clear cache if making changes:
```python
factory = get_agent_factory()
factory.clear_cache()
```
