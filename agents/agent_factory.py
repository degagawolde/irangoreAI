"""Unified agent factory for loading agents from YAML configuration."""

from importlib import import_module
import warnings
from typing import Dict, Any, Optional, List, Callable
from pathlib import Path
from uuid import uuid4

import yaml

from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.tools import Tool, StructuredTool

from core.logger import get_logger
from core.exceptions import AgentException
from llms import get_llm

logger = get_logger(__name__)


def _build_react_agent(llm, tools, prompt: PromptTemplate):
    """Create a ReAct agent using the best available backend.

    Prefer `langchain.agents.create_agent` (new API), and fall back to
    `langgraph.prebuilt.create_react_agent` for compatibility.
    """
    try:
        from langchain.agents import create_agent

        return create_agent(model=llm, tools=tools, system_prompt=prompt.template)
    except Exception:
        warnings.filterwarnings(
            "ignore",
            message=r"The default value of `allowed_objects` will change in a future version\..*",
        )
        from langgraph.prebuilt import create_react_agent

        return create_react_agent(llm, tools, prompt=prompt)


class AgentFactory:
    """Factory for creating unified LangGraph agent instances from YAML configuration."""

    _instance = None
    _config: Dict[str, Any] = {}
    _agents_cache: Dict[str, Any] = {}
    _config_path = Path(__file__).parent / "agents.yaml"

    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self) -> None:
        """Load agent configuration from YAML file."""
        try:
            if not self._config_path.exists():
                raise AgentException(
                    f"Agent configuration file not found: {self._config_path}"
                )

            with open(self._config_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f)

            if not isinstance(self._config, dict):
                raise AgentException("Invalid agents.yaml: root must be a mapping")

            logger.info(f"Loaded agent configuration from {self._config_path}")

        except yaml.YAMLError as e:
            raise AgentException(f"Failed to parse agents.yaml: {str(e)}")

        except Exception as e:
            raise AgentException(
                f"Failed to load agent configuration: {str(e)}"
            )

    def get_agent(self, agent_name: str = None) -> Optional[Dict[str, Any]]:
        """Get agent configuration by name."""

        if agent_name is None:
            agent_name = self._config.get("settings", {}).get("default_agent", "chat")

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
        resolved_agent_name = ( 
            agent_name or self._config.get("settings", {}).get("default_agent", "chat")
            )
        agent_config = self.get_agent(resolved_agent_name)

        # Return cached instance
        if resolved_agent_name in self._agents_cache:
            logger.debug(f"Using cached agent: {resolved_agent_name}")
            return self._agents_cache[resolved_agent_name]

        try:
            logger.info(f"Creating agent: {resolved_agent_name}")

            llm = get_llm()

            # Build tools
            tools = self._build_tools(agent_config.get("tools", []))

            settings = self._config.get("settings", {})
            prompt_preamble = settings.get("system_prompt_preamble", "").strip()
            system_prompt = agent_config.get("system_prompt", "You are a helpful AI assistant.").strip()
            full_system_prompt = "\n\n".join(
                part for part in [prompt_preamble, system_prompt] if part
            )

            prompt = PromptTemplate.from_template(full_system_prompt)
            agent = _build_react_agent(llm=llm, tools=tools, prompt=prompt)

            # Cache
            self._agents_cache[resolved_agent_name] = agent

            logger.info(
                f"Agent '{resolved_agent_name}' created successfully"
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
        """Build tools from configuration using StructuredTool for multi-parameter functions."""

        tools = []

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

        tool_functions = self._resolve_tool_functions()
        tool_functions["document_chat"] = create_document_chat

        for tool_config in tool_configs:

            tool_type = tool_config.get("type")

            if tool_type not in tool_functions:
                logger.warning(
                    f"Tool type '{tool_type}' not recognized, skipping"
                )
                continue

            tool_name = tool_config.get("name") or tool_type
            tool_description = tool_config.get("description") or f"{tool_type} tool"
            func = tool_functions[tool_type]
            
            # Use StructuredTool for functions to properly handle multiple parameters
            # This allows LangChain to understand the function signature and call it correctly
            try:
                tool = StructuredTool.from_function(
                    func=func,
                    name=tool_name,
                    description=tool_description,
                )
            except Exception as e:
                logger.warning(
                    f"Failed to create StructuredTool for '{tool_name}': {e}, "
                    f"falling back to Tool.from_function"
                )
                # Fallback to Tool.from_function if StructuredTool creation fails
                tool = Tool.from_function(
                    name=tool_name,
                    description=tool_description,
                    func=func,
                )

            tools.append(tool)

            logger.debug(
                f"Added tool: {tool_config.get('name')}"
            )

        return tools

    def _resolve_tool_functions(self) -> Dict[str, Callable]:
        """Resolve configured tool function targets from agents.yaml."""
        tools_config = self._config.get("tools", {})
        resolved: Dict[str, Callable] = {}

        for tool_type, cfg in tools_config.items():
            module_name = cfg.get("module")
            function_name = cfg.get("function")
            if not module_name or not function_name:
                logger.warning(f"Tool '{tool_type}' missing module/function; skipping")
                continue
            try:
                module = import_module(module_name)
                resolved[tool_type] = getattr(module, function_name)
            except Exception as exc:
                logger.warning(
                    f"Failed to resolve tool '{tool_type}' from {module_name}.{function_name}: {exc}"
                )
        return resolved

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
            messages = response.get("messages", []) if isinstance(response, dict) else []

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
