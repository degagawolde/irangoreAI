"""Unified agent factory for loading agents from YAML configuration."""

from typing import Dict, Any, Optional, List
from pathlib import Path
from uuid import uuid4
from langchain.agents import create_react_agent
import yaml

from core.logger import get_logger
from core.exceptions import AgentException
from llms import get_llm

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.tools import Tool

logger = get_logger(__name__)


class AgentFactory:
    """Factory for creating unified agent instances from YAML configuration."""

    _instance = None
    _config: Dict[str, Any] = {}
    _agents_cache: Dict[str, Any] = {}

    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self) -> None:
        """Load agent configuration from YAML file."""
        try:
            config_path = Path(__file__).parent / "agents.yaml"
            
            if not config_path.exists():
                raise AgentException(f"Agent configuration file not found: {config_path}")
            
            with open(config_path, "r") as f:
                self._config = yaml.safe_load(f)
            
            logger.info(f"Loaded agent configuration from {config_path}")
        
        except yaml.YAMLError as e:
            raise AgentException(f"Failed to parse agents.yaml: {str(e)}")
        except Exception as e:
            raise AgentException(f"Failed to load agent configuration: {str(e)}")

    def get_agent(self, agent_name: str = None) -> Optional[Dict[str, Any]]:
        """Get agent configuration by name."""
        if agent_name is None:
            agent_name = self._config.get("settings", {}).get("default_agent", "chat")
        
        if agent_name not in self._config.get("agents", {}):
            raise AgentException(f"Agent '{agent_name}' not found in configuration")
        
        agent_config = self._config["agents"][agent_name]
        
        if not agent_config.get("enabled", False):
            raise AgentException(f"Agent '{agent_name}' is disabled")
        
        return agent_config

    def list_agents(self) -> List[str]:
        """List all available agents."""
        return list(self._config.get("agents", {}).keys())

    def get_enabled_agents(self) -> List[str]:
        """List all enabled agents."""
        return [
            name for name, config in self._config.get("agents", {}).items()
            if config.get("enabled", False)
        ]

    def create_agent(self, agent_name: str = None):
        """Create a fully configured agent instance using LangGraph."""
        agent_config = self.get_agent(agent_name)
        
        # Check cache
        if agent_name in self._agents_cache:
            logger.debug(f"Using cached agent: {agent_name}")
            return self._agents_cache[agent_name]
        
        try:
            logger.info(f"Creating agent: {agent_name}")
            llm = get_llm()
            
            # Build tools
            tools = self._build_tools(agent_config.get("tools", []))
            
            # Build system prompt
            system_prompt = agent_config.get("system_prompt", "You are a helpful assistant.")
            
            # Create system prompt with planning/validation
            full_system_prompt = f"""{system_prompt}

===== PLANNING PHASE =====
Before answering, ALWAYS:
1. Understand the question clearly
2. Plan which tools you will use and why
3. Identify what information you need

===== HOW TO PROCEED =====
Use this exact format:

PLAN:
- What the question is asking for
- Which tools I will use and why
- What information I need to gather

Then proceed to execute:

Thought: [Your thinking about the plan]
Action: [tool to use]
Action Input: [input for the tool]
Observation: [result from tool]

Repeat until you have enough information.

===== VALIDATION PHASE =====
Before giving Final Answer:
1. Verify your answer is relevant to the question
2. Check if sources are from documents
3. If answer is incomplete/not from documents: TRY AGAIN with different tools

===== RESPONSE FORMAT =====
When you're ready with a validated answer:

Thought: Is my answer relevant and from the documents? Yes/No
Final Answer: [Your comprehensive answer with sources]

If No, go back and try different tools!"""
                        
            agent = create_react_agent(
                llm=llm,
                tools=tools,
                prompt=full_system_prompt,
            )
          
            # Cache agent
            self._agents_cache[agent_name] = agent
            
            logger.info(f"Agent '{agent_name}' created successfully")
            return agent
        
        except Exception as e:
            logger.error(f"Failed to create agent '{agent_name}': {str(e)}")
            raise AgentException(f"Failed to create agent '{agent_name}': {str(e)}")

    def _build_tools(self, tool_configs: List[Dict[str, str]]) -> List[Tool]:
        """Build tools from configuration."""
        tools = []
        
        # Import tool functions
        from tools.vector_tool import semantic_search
        from tools.cypher_tool import graph_qa
        
        # Create document chat function
        def create_document_chat(input_text: str) -> str:
            llm = get_llm()
            chat_prompt = ChatPromptTemplate.from_messages([
                ("system", "You are a helpful assistant providing information from documents."),
                ("human", "{input}"),
            ])
            document_chat = chat_prompt | llm | StrOutputParser()
            return document_chat.invoke({"input": input_text})
        
        # Tool type mapping
        tool_functions = {
            "document_chat": create_document_chat,
            "vector_search": semantic_search,
            "cypher_qa": graph_qa,
        }
        
        for tool_config in tool_configs:
            tool_type = tool_config.get("type")
            
            if tool_type not in tool_functions:
                logger.warning(f"Tool type '{tool_type}' not recognized, skipping")
                continue
            
            tool = Tool.from_function(
                name=tool_config.get("name"),
                description=tool_config.get("description"),
                func=tool_functions[tool_type],
            )
            tools.append(tool)
            logger.debug(f"Added tool: {tool_config.get('name')}")
        
        return tools

    def generate_response(
        self, user_input: str, agent_name: str = None, session_id: Optional[str] = None
    ) -> str:
        """Generate response using specified agent with LangGraph persistence."""
        agent = self.create_agent(agent_name)
        active_session_id = session_id or str(uuid4())
        
        try:
            # LangGraph handles memory/persistence via checkpointer configuration
            # No need for manual memory management
            response = agent.invoke(
                {"messages": [{"role": "user", "content": user_input}]},
                {"configurable": {"thread_id": active_session_id}},
            )
            
            # Extract last message content from either dict-style or message-object style payloads.
            messages = response.get("messages") if isinstance(response, dict) else None
            if messages:
                last_message = messages[-1]
                if isinstance(last_message, dict):
                    return last_message.get("content", "")
                content = getattr(last_message, "content", "")
                if isinstance(content, list):
                    # Some providers return content blocks; join text parts.
                    text_parts = []
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                        elif isinstance(block, str):
                            text_parts.append(block)
                    return "\n".join([p for p in text_parts if p]).strip()
                return content or ""
            return ""
        
        except Exception as e:
            logger.error(f"Agent execution failed: {str(e)}")
            raise AgentException(f"Agent execution failed: {str(e)}")

    def clear_cache(self) -> None:
        """Clear agent cache."""
        self._agents_cache.clear()
        logger.info("Agent cache cleared")


def get_agent_factory() -> AgentFactory:
    """Get agent factory singleton."""
    return AgentFactory()


def create_agent(agent_name: str = None):
    """Create a new agent instance using LangGraph."""
    factory = get_agent_factory()
    return factory.create_agent(agent_name)


def generate_response(
    user_input: str, agent_name: str = None, session_id: Optional[str] = None
) -> str:
    """Generate response using an agent."""
    factory = get_agent_factory()
    return factory.generate_response(user_input, agent_name, session_id)


def list_agents() -> List[str]:
    """List all agents."""
    factory = get_agent_factory()
    return factory.list_agents()


def get_enabled_agents() -> List[str]:
    """List enabled agents."""
    factory = get_agent_factory()
    return factory.get_enabled_agents()
