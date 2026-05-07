"""Agent framework for agentic AI."""

from typing import Optional, List, Dict, Any, Callable
from core.logger import get_logger
from core.exceptions import AgentException
from llms import get_llm
from tools import get_cypher_tool, get_vector_store

logger = get_logger(__name__)


class AgentToolkit:
    """Toolkit for agent tools."""

    def __init__(self):
        """Initialize toolkit with available tools."""
        self.tools: Dict[str, Any] = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register default tools for agents."""
        try:
            from langchain_core.tools import Tool
            
            # Cypher QA Tool
            cypher_tool = get_cypher_tool()
            self.tools["graph_qa"] = Tool(
                name="Graph Database Query",
                description="Query the knowledge graph using Cypher. Use this for structured data queries.",
                func=cypher_tool.query,
            )

            # Vector Search Tool
            vector_store = get_vector_store()
            self.tools["semantic_search"] = Tool(
                name="Semantic Search",
                description="Search for semantically similar information. Use this for finding related documents.",
                func=lambda query: vector_store.search(query, k=5),
            )

            logger.info(f"Registered {len(self.tools)} default tools")

        except Exception as e:
            logger.error(f"Failed to register default tools: {str(e)}")
            raise AgentException(f"Failed to register default tools: {str(e)}")

    def register_tool(self, name: str, description: str, func: Callable) -> None:
        """Register a custom tool."""
        from langchain_core.tools import Tool
        
        self.tools[name] = Tool(name=name, description=description, func=func)
        logger.info(f"Registered custom tool: {name}")

    def get_tools(self) -> List[Any]:
        """Get all registered tools."""
        return list(self.tools.values())


class ReactAgent:
    """ReAct (Reasoning + Acting) Agent."""

    def __init__(self, name: str = "ChatBot", toolkit: Optional[AgentToolkit] = None):
        """Initialize ReAct agent."""
        self.name = name
        self.toolkit = toolkit or AgentToolkit()
        self.executor: Optional[Any] = None
        self._initialize_agent()

    def _initialize_agent(self) -> None:
        """Initialize the agent."""
        try:
            from langchain.agents import AgentExecutor, create_react_agent
            from langchain import hub
            
            logger.info(f"Initializing ReAct agent: {self.name}")

            llm = get_llm()
            tools = self.toolkit.get_tools()

            # Use the standard ReAct prompt from hub
            prompt = hub.pull("hwchase17/react")

            # Create the agent
            agent = create_react_agent(llm, tools, prompt)

            # Create the executor
            self.executor = AgentExecutor.from_agent_and_tools(
                agent=agent,
                tools=tools,
                verbose=False,
                max_iterations=10,
                early_stopping_method="force",
            )

            logger.info(f"ReAct agent initialized: {self.name}")

        except Exception as e:
            logger.error(f"Failed to initialize agent: {str(e)}")
            raise AgentException(f"Failed to initialize agent: {str(e)}")

    def run(self, query: str) -> str:
        """Run the agent with a query."""
        try:
            logger.info(f"Agent running query: {query}")

            if not self.executor:
                raise AgentException("Agent not initialized")

            result = self.executor.invoke({"input": query})
            output = result.get("output", "")

            logger.debug(f"Agent output: {output}")
            return output

        except Exception as e:
            logger.error(f"Agent execution failed: {str(e)}")
            raise AgentException(f"Agent execution failed: {str(e)}")


def get_react_agent(name: str = "ChatBot") -> ReactAgent:
    """Get or create a ReAct agent."""
    return ReactAgent(name)
