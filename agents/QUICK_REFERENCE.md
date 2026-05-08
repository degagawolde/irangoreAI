# Quick Reference: Unified Agent Structure

## One-Liners

```python
# Create default agent
from agents import create_agent
agent = create_agent()

# Generate response
from agents import generate_response
response = generate_response("Your question here")

# Use specific agent
response = generate_response("Question", agent_name="cypher")

# List agents
from agents import list_agents
print(list_agents())  # ['chat', 'vector', 'cypher', 'full', 'scoped']

# Direct factory access
from agents import get_agent_factory
factory = get_agent_factory()
```

## Configuration File Location

```
/agents/agents.yaml
```

## Agent Selection Guide

```
Simple chat? → use "chat"
Find similar docs? → use "vector"  
Complex queries? → use "cypher" ⭐ (recommended)
Everything? → use "full"
Domain-specific? → use "scoped"
```

## Adding a New Agent

1. Edit `agents/agents.yaml`
2. Add new section under `agents:`
3. Specify name, tools, prompt
4. Set `enabled: true`

Example:
```yaml
agents:
  my_agent:
    name: "My Agent"
    enabled: true
    system_prompt: "Your prompt here"
    tools:
      - name: "Tool Name"
        type: "vector_search"
```

## Adding a New Tool

1. Create tool function
2. Add to `tools:` section in YAML
3. Add mapping in `agent_factory.py` line ~165
4. Reference in agent config

## File Structure

```
agents/
├── agents.yaml              ← Configuration (edit this)
├── agent_factory.py         ← Core logic (don't touch)
├── AGENTS_GUIDE.md         ← Detailed docs
├── UNIFIED_STRUCTURE.md    ← Overview
├── __init__.py             ← Exports
├── [legacy files...]       ← Can keep for backward compatibility
```

## Configuration Schema

```yaml
agents:
  name:
    name: string             # Display name
    type: "react"            # Always "react"
    enabled: boolean
    system_prompt: string
    tools:
      - name: string
        description: string
        type: string
    memory:
      enabled: boolean
      type: string
    verbose: boolean

tools:
  type:
    type: "function"
    module: string
    function: string

settings:
  default_agent: string
  timeout: int
  max_iterations: int
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Agent not found | Check `agents.yaml`, verify `enabled: true` |
| Tool not working | Check tool type in YAML, verify mapping in factory |
| Import error | Ensure yaml package installed |
| YAML error | Check indentation (2 spaces), syntax |
| Config not loading | Verify file location: `agents/agents.yaml` |

## Clear Cache

```python
from agents import get_agent_factory
factory = get_agent_factory()
factory.clear_cache()
```

## Key Classes/Functions

```python
# Main factory
AgentFactory()                      # Singleton

# Functions
create_agent(name)                  # Create agent instance
generate_response(input, agent)     # Get response
list_agents()                       # All agents
get_enabled_agents()               # Enabled only
get_agent_factory()                # Get factory
```

## Integration Example

```python
# In your main.py or API
from agents import generate_response, get_enabled_agents

@app.post("/chat")
async def chat(message: str, agent: str = None):
    response = generate_response(message, agent_name=agent)
    return {"reply": response}

@app.get("/agents")
async def get_agents():
    return {"agents": get_enabled_agents()}
```

## Performance Tips

- Use "chat" for simple queries (fastest)
- Use "cypher" for complex queries
- Use "vector" for semantic search
- Agents are cached after first use
- Memory is session-based (efficient)

## Reading Configuration

```python
factory = get_agent_factory()

# Get agent config
config = factory.get_agent("cypher")
print(config["system_prompt"])
print(config["tools"])

# List all
agents = factory.list_agents()
for agent_name in agents:
    config = factory.get_agent(agent_name)
    if config.get("enabled"):
        print(f"✓ {agent_name}: {config['name']}")
```

## Common Customizations

### Change default agent
```yaml
settings:
  default_agent: "cypher"  # was "chat"
```

### Disable an agent
```yaml
agents:
  full:
    enabled: false
```

### Modify system prompt
```yaml
agents:
  chat:
    system_prompt: "Your custom prompt..."
```

### Add tool to agent
```yaml
agents:
  chat:
    tools:
      - name: "New Tool"
        description: "..."
        type: "tool_type"
```

## Support

- See `AGENTS_GUIDE.md` for detailed documentation
- See `UNIFIED_STRUCTURE.md` for architecture overview
- Check `agents.yaml` for current configuration
