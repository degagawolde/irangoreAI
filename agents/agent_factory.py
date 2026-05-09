"""Unified agent factory for loading agents from YAML configuration."""

from typing import Dict, Any, Optional, List
from pathlib import Path
from uuid import uuid4

import yaml

from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.tools import Tool

from core.logger import get_logger
from core.exceptions import AgentException
from llms import get_llm

logger = get_logger(__name__)


class AgentFactory:
    """Factory for creating unified LangGraph agent instances from YAML configuration."""

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
                raise AgentException(
                    f"Agent configuration file not found: {config_path}"
                )

            with open(config_path, "r") as f:
                self._config = yaml.safe_load(f)

            logger.info(f"Loaded agent configuration from {config_path}")

        except yaml.YAMLError as e:
            raise AgentException(f"Failed to parse agents.yaml: {str(e)}")

        except Exception as e:
            raise AgentException(
                f"Failed to load agent configuration: {str(e)}"
            )

    def get_agent(self, agent_name: str = None) -> Optional[Dict[str, Any]]:
        """Get agent configuration by name."""

        if agent_name is None:
            agent_name = (
                self._config
                .get("settings", {})
                .get("default_agent", "chat")
            )

        if agent_name not in self._config.get("agents", {}):
            raise AgentException(
                f"Agent '{agent_name}' not found in configuration"
            )

        agent_config = self._config["agents"][agent_name]

        if not agent_config.get("enabled", False):
            raise AgentException(
                f"Agent '{agent_name}' is disabled"
            )

        return agent_config

    def list_agents(self) -> List[str]:
        """List all available agents."""
        return list(self._config.get("agents", {}).keys())

    def get_enabled_agents(self) -> List[str]:
        """List all enabled agents."""
        return [
            name
            for name, config in self._config.get("agents", {}).items()
            if config.get("enabled", False)
        ]

    def create_agent(self, agent_name: str = None):
        """Create a fully configured LangGraph ReAct agent."""

        agent_config = self.get_agent(agent_name)

        # Return cached instance
        if agent_name in self._agents_cache:
            logger.debug(f"Using cached agent: {agent_name}")
            return self._agents_cache[agent_name]

        try:
            logger.info(f"Creating agent: {agent_name}")

            llm = get_llm()

            # Build tools
            tools = self._build_tools(
                agent_config.get("tools", [])
            )

            # System prompt
            system_prompt = agent_config.get(
                "system_prompt",
                "You are a helpful AI assistant."
            )

            enhanced_system_prompt = f"""
{system_prompt}

===== PLANNING PHASE =====

Before answering:
1. Understand the user's request carefully
2. Decide which tools are relevant
3. Gather evidence before answering

===== VALIDATION PHASE =====

Before finalizing:
1. Ensure the answer is relevant
2. Ensure supporting evidence exists
3. Use tools again if information is incomplete

Always provide accurate and grounded responses.
"""

            # Create LangGraph ReAct agent
            agent = create_react_agent(
                model=llm,
                tools=tools,
                prompt=enhanced_system_prompt,
            )

            # Cache
            self._agents_cache[agent_name] = agent

            logger.info(
                f"Agent '{agent_name}' created successfully"
            )

            return agent

        except Exception as e:
            logger.error(
                f"Failed to create agent '{agent_name}': {str(e)}"
            )

            raise AgentException(
                f"Failed to create agent '{agent_name}': {str(e)}"
            )

    def _build_tools(
        self,
        tool_configs: List[Dict[str, str]]
    ) -> List[Tool]:
        """Build tools from configuration."""

        tools = []

        # Import tool functions
        from tools.vector_tool import semantic_search
        from tools.cypher_tool import graph_qa

        # Simple document chat tool
        def create_document_chat(input_text: str) -> str:
            llm = get_llm()

            chat_prompt = ChatPromptTemplate.from_messages([
                (
                    "system",
                    "You are a helpful assistant providing "
                    "information from documents."
                ),
                ("human", "{input}"),
            ])

            document_chat = (
                chat_prompt
                | llm
                | StrOutputParser()
            )

            return document_chat.invoke(
                {"input": input_text}
            )

        # Tool registry
        tool_functions = {
            "document_chat": create_document_chat,
            "vector_search": semantic_search,
            "cypher_qa": graph_qa,
        }

        for tool_config in tool_configs:

            tool_type = tool_config.get("type")

            if tool_type not in tool_functions:
                logger.warning(
                    f"Tool type '{tool_type}' not recognized, skipping"
                )
                continue

            tool = Tool.from_function(
                name=tool_config.get("name"),
                description=tool_config.get("description"),
                func=tool_functions[tool_type],
            )

            tools.append(tool)

            logger.debug(
                f"Added tool: {tool_config.get('name')}"
            )

        return tools

    def generate_response(
        self,
        user_input: str,
        agent_name: str = None,
        session_id: Optional[str] = None,
    ) -> str:
        """Generate response using LangGraph agent."""

        agent = self.create_agent(agent_name)

        active_session_id = (
            session_id or str(uuid4())
        )

        try:
            logger.info(
                f"Running agent '{agent_name}' "
                f"with session {active_session_id}"
            )

            response = agent.invoke(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": user_input,
                        }
                    ]
                },
                config={
                    "configurable": {
                        "thread_id": active_session_id
                    }
                },
            )

            logger.debug(f"Raw response: {response}")

            # Extract assistant response
            messages = response.get("messages", [])

            if not messages:
                return ""

            last_message = messages[-1]

            # Handle dict-style messages
            if isinstance(last_message, dict):
                return last_message.get("content", "")

            # Handle LangChain message objects
            content = getattr(
                last_message,
                "content",
                ""
            )

            # Some providers return structured content blocks
            if isinstance(content, list):

                text_parts = []

                for block in content:

                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            text_parts.append(
                                block.get("text", "")
                            )

                    elif isinstance(block, str):
                        text_parts.append(block)

                return "\n".join(
                    [p for p in text_parts if p]
                ).strip()

            return content or ""

        except Exception as e:
            logger.error(
                f"Agent execution failed: {str(e)}"
            )

            raise AgentException(
                f"Agent execution failed: {str(e)}"
            )

    def clear_cache(self) -> None:
        """Clear cached agents."""

        self._agents_cache.clear()

        logger.info("Agent cache cleared")


def get_agent_factory() -> AgentFactory:
    """Get singleton agent factory."""
    return AgentFactory()


def create_agent(agent_name: str = None):
    """Create an agent instance."""
    factory = get_agent_factory()
    return factory.create_agent(agent_name)


def generate_response(
    user_input: str,
    agent_name: str = None,
    session_id: Optional[str] = None,
) -> str:
    """Generate response from agent."""

    factory = get_agent_factory()

    return factory.generate_response(
        user_input=user_input,
        agent_name=agent_name,
        session_id=session_id,
    )


def list_agents() -> List[str]:
    """List all configured agents."""

    factory = get_agent_factory()

    return factory.list_agents()


def get_enabled_agents() -> List[str]:
    """List enabled agents."""

    factory = get_agent_factory()

    return factory.get_enabled_agents()