"""Unified agent factory for loading agents from YAML configuration."""

from typing import Dict, Any, Optional, List
from pathlib import Path
from uuid import uuid4
import yaml

from core.logger import get_logger
from core.exceptions import AgentException
from llms import get_llm
from graph import get_graph

from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain.schema import StrOutputParser
from langchain.tools import Tool
from langchain_neo4j import Neo4jChatMessageHistory
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.runnables.history import RunnableWithMessageHistory

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

    def create_agent(self, agent_name: str = None) -> RunnableWithMessageHistory:
        """Create a fully configured agent instance."""
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
            
            # Create agent prompt template
            agent_prompt = PromptTemplate.from_template(f"""
{system_prompt}

TOOLS:
------
You have access to the following tools:

{{tools}}

To use a tool, please use the following format:

```
Thought: Do I need to use a tool? Yes
Action: the action to take, should be one of [{{tool_names}}]
Action Input: the input to the action
Observation: the result of the action
```

When you have a response to say to the Human, or if you do not need to use a tool, you MUST use the format:

```
Thought: Do I need to use a tool? No
Final Answer: [your response here]
```

Previous conversation history:
{{chat_history}}

New input: {{input}}
{{agent_scratchpad}}
""")
            
            # Create React agent
            agent = create_react_agent(llm, tools, agent_prompt)
            
            # Create executor
            agent_executor = AgentExecutor(
                agent=agent,
                tools=tools,
                verbose=agent_config.get("verbose", False),
                max_iterations=self._config.get("settings", {}).get("max_iterations", 10),
                handle_parsing_errors=True
            )
            
            # Add memory
            memory_config = agent_config.get("memory", {})
            if memory_config.get("enabled", True):
                chat_agent = RunnableWithMessageHistory(
                    agent_executor,
                    self._get_memory,
                    input_messages_key="input",
                    history_messages_key="chat_history",
                )
            else:
                chat_agent = agent_executor
            
            # Cache agent
            self._agents_cache[agent_name] = chat_agent
            
            logger.info(f"Agent '{agent_name}' created successfully")
            return chat_agent
        
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

    @staticmethod
    def _get_memory(session_id: str) -> Neo4jChatMessageHistory:
        """Get chat memory for session."""
        graph = get_graph()
        return Neo4jChatMessageHistory(session_id=session_id, graph=graph)

    def generate_response(
        self, user_input: str, agent_name: str = None, session_id: Optional[str] = None
    ) -> str:
        """Generate response using specified agent."""
        agent = self.create_agent(agent_name)
        active_session_id = session_id or str(uuid4())
        
        try:
            response = agent.invoke(
                {"input": user_input},
                {"configurable": {"session_id": active_session_id}},
            )
            return response.get("output", "")
        
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


def create_agent(agent_name: str = None) -> RunnableWithMessageHistory:
    """Create a new agent instance."""
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
