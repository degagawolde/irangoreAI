# Unified Agent Structure Implementation

## Overview

Your agents module has been refactored into a unified, YAML-driven structure that provides centralized management and configuration of all agents.

## Files Created/Modified

### New Files

1. **`agents/agents.yaml`** ⭐ Configuration Hub
   - Defines all 5 agents (chat, vector, cypher, full, scoped)
   - Configures 4 tool types (document_chat, vector_search, cypher_qa, document_ingestion)
   - Sets global settings (default agent, timeouts, etc.)

2. **`agents/agent_factory.py`** ⭐ Main Implementation
   - `AgentFactory` - Singleton class managing agent lifecycle
   - Loads configuration from YAML
   - Creates agent instances with caching
   - Tool building and registration
   - Memory management per session

3. **`agents/AGENTS_GUIDE.md`** - Documentation
   - Usage examples
   - Agent descriptions
   - Customization guide
   - Troubleshooting

### Modified Files

- **`agents/__init__.py`** - Updated exports to include new factory functions

## Architecture

```
Configuration Layer (YAML)
         ↓
    AgentFactory (Singleton)
         ↓
    create_agent(name) → Fully configured agent
         ↓
    Agent Instance (with tools, memory, prompt)
         ↓
    LangChain ReactAgent + RunnableWithMessageHistory
```

## Key Features

✅ **Centralized Configuration**
- All agents defined in one YAML file
- No code duplication across agent files

✅ **Easy to Extend**
- Add new agents by editing YAML
- Add tools by defining in YAML + updating tool mappings

✅ **Intelligent Caching**
- Agent instances cached after first creation
- Session-based memory via Neo4j

✅ **Type System**
- Clear tool type mapping
- Consistent configuration structure

✅ **Backward Compatible**
- Legacy agent imports still work
- Gradual migration path

## Usage Examples

### Simple Usage
```python
from agents import generate_response

response = generate_response("What's in the documents?")
```

### Specify Agent
```python
from agents import generate_response

response = generate_response(
    "Query the documents",
    agent_name="cypher"  # or "chat", "vector", "full", "scoped"
)
```

### Advanced Usage
```python
from agents import get_agent_factory

factory = get_agent_factory()

# List agents
agents = factory.list_agents()  # ['chat', 'vector', 'cypher', 'full', 'scoped']

# Create specific agent
agent = factory.create_agent("cypher")

# Get configuration
config = factory.get_agent("cypher")
print(config["system_prompt"])
```

## Agent Profiles

| Agent | Tools | Best For | Verbosity |
|-------|-------|----------|-----------|
| **chat** | Chat only | Simple questions | Low |
| **vector** | Chat + Vector Search | Finding similar content | Low |
| **cypher** | Chat + Vector + Cypher | Comprehensive queries | Low |
| **full** | All tools | Complete workflows | High |
| **scoped** | Chat only | Domain-specific | Low |

## Configuration Structure

```yaml
agents:
  agent_name:
    name: Display name
    description: What it does
    type: "react"
    enabled: true/false
    system_prompt: Custom prompt
    tools: [list of tools]
    memory: Configuration
    verbose: true/false

tools:
  tool_type:
    type: "function"
    module: "where.it.is"
    function: "function_name"
    
settings:
  default_agent: Which agent to use if not specified
  timeout: Max execution time
  max_iterations: Max agent loops
```

## Integration Points

### In main.py
```python
from agents import generate_response, get_enabled_agents

@app.post("/chat")
async def chat(request: ChatRequest):
    response = generate_response(
        request.message,
        agent_name=request.agent or "cypher"
    )
    return {"reply": response}

@app.get("/agents")
async def list_agents():
    return {"agents": get_enabled_agents()}
```

### In config
```python
from agents import get_agent_factory

factory = get_agent_factory()
# Access configuration programmatically
```

## Customization Examples

### Add Custom System Prompt
Edit `agents.yaml`:
```yaml
agents:
  research:
    system_prompt: "You are a research assistant specializing in..."
```

### Enable/Disable Agents
```yaml
agents:
  full:
    enabled: false  # Disable full agent
```

### Adjust Tool Timeout
```yaml
settings:
  timeout: 600  # Increase to 10 minutes
```

## Benefits Over Legacy Structure

| Aspect | Legacy | Unified |
|--------|--------|---------|
| Configuration | Code | YAML |
| Duplication | High | None |
| Customization | Code change | YAML edit |
| Tool mapping | Hardcoded | Registry |
| Discovery | Manual | Automatic |
| Caching | Per-file | Centralized |
| Documentation | Multiple | Single source |

## Migration Path

Legacy code continues to work:
```python
# Old way - still works
from agents.agent_cypher import generate_response

# New way - recommended
from agents import generate_response, create_agent
```

No breaking changes - you can migrate gradually.

## Next Steps

1. ✅ Test the unified agent structure
2. ✅ Update main.py to use new factory
3. ✅ Define any custom agents in agents.yaml
4. ✅ Verify all tools work correctly
5. Optional: Archive/remove legacy agent files once fully migrated

## Files Summary

- **agents.yaml** (new) - 120 lines - Configuration
- **agent_factory.py** (new) - 280 lines - Implementation  
- **AGENTS_GUIDE.md** (new) - Usage & reference
- **__init__.py** (updated) - Added new exports
