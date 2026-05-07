"""Agent framework for agentic AI."""

from typing import Optional, List, Dict, Any, Callable
from core.logger import get_logger
from core.exceptions import AgentException
from llms import get_llm
from tools import get_cypher_tool, get_vector_store, ingest_documents_tool

from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.tools import Tool
from langchain_core.prompts import PromptTemplate
            
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
            # Cypher QA Tool
            cypher_tool = get_cypher_tool()
            self.tools["graph_qa"] = Tool(
                name="Graph Database Query",
                description="Query the document knowledge graph using Cypher for structured relationship questions.",
                func=cypher_tool.query,
            )

            # Vector Search Tool
            vector_store = get_vector_store()
            self.tools["semantic_search"] = Tool(
                name="Semantic Search",
                description="Search semantically similar chunks from ingested documents.",
                func=lambda query: vector_store.search(query, k=5),
            )

            # Document Ingestion Tool
            self.tools["document_ingestion"] = Tool(
                name="Document Graph Ingestion",
                description=(
                    "Load documents from disk, chunk them, embed chunks, and ingest into the graph. "
                    "Input must be JSON string, e.g. "
                    '{"path":"./docs","chunk_size":1000,"chunk_overlap":150}'
                ),
                func=ingest_documents_tool,
            )

            logger.info(f"Registered {len(self.tools)} default tools")

        except Exception as e:
            logger.error(f"Failed to register default tools: {str(e)}")
            raise AgentException(f"Failed to register default tools: {str(e)}")

    def register_tool(self, name: str, description: str, func: Callable) -> None:
        """Register a custom tool."""
        
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

            logger.info(f"Initializing ReAct agent: {self.name}")

            llm = get_llm()
            tools = self.toolkit.get_tools()

            prompt = PromptTemplate.from_template(
                """You are a helpful assistant that can use tools when needed.

You have access to the following tools:
{tools}

Use this format:
Question: the input question you must answer
Thought: think about what to do next
Action: the action to take, must be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat)
Thought: I now know the final answer
Final Answer: the final answer to the original question

Rules:
- Use tools for graph lookups, semantic search, and document ingestion as needed.
- If you do not need a tool, answer directly.
- Keep answers factual and concise.

Question: {input}
Thought:{agent_scratchpad}"""
            )

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
