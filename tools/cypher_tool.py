"""Cypher query and graph-based tools."""

from typing import List, Dict, Any
from core.logger import get_logger
from core.exceptions import GraphException
from graph import get_graph
from llms import get_llm

logger = get_logger(__name__)


# System prompt for Cypher generation
CYPHER_GENERATION_PROMPT = """
You are an expert Neo4j Developer translating user questions into Cypher to answer questions about the domain.
Convert the user's question based on the schema.

Use only the provided relationship types and properties in the schema.
Do not use any other relationship types or properties that are not provided.

Do not return entire nodes or embedding properties.
Do not include embeddings in the response.

Schema Information:
{schema}

Question: {question}
Cypher Query:
"""

QA_PROMPT = """
Based on the context provided from the graph database, answer the user's question.
If you don't know the answer, say you don't know.

Context:
{context}

Question: {question}
Answer:
"""


class CypherQueryTool:
    """Tool for generating and executing Cypher queries."""

    _instance = None
    _qa_chain = None

    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize Cypher query tool."""
        if self._qa_chain is None:
            self._initialize_qa_chain()

    def _initialize_qa_chain(self) -> None:
        """Initialize the Cypher QA chain."""
        try:
            from langchain_neo4j import GraphCypherQAChain
            from langchain_core.prompts import PromptTemplate
            
            graph = get_graph()
            llm = get_llm()

            logger.info("Initializing Cypher QA chain")

            # Create prompt template for Cypher generation
            cypher_prompt = PromptTemplate.from_template(CYPHER_GENERATION_PROMPT)

            # Create prompt template for QA
            qa_prompt = PromptTemplate.from_template(QA_PROMPT)

            # Initialize the chain
            self._qa_chain = GraphCypherQAChain.from_llm(
                llm,
                graph=graph,
                cypher_prompt=cypher_prompt,
                qa_prompt=qa_prompt,
                validate_cypher=True,
                verbose=False,
                allow_dangerous_requests=True
            )

            logger.info("Cypher QA chain initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Cypher QA chain: {str(e)}")
            raise GraphException(f"Failed to initialize Cypher QA chain: {str(e)}")

    def query(self, question: str) -> str:
        """Execute a question using Cypher QA chain."""
        try:
            logger.debug(f"Cypher query: {question}")
            result = self._qa_chain.invoke({"query": question})
            return result.get("result", "")

        except Exception as e:
            logger.error(f"Cypher query failed: {str(e)}")
            raise GraphException(f"Cypher query failed: {str(e)}")

    def execute_cypher(self, cypher_query: str) -> List[Dict[str, Any]]:
        """Execute raw Cypher query."""
        try:
            graph = get_graph()
            logger.debug(f"Executing Cypher: {cypher_query}")
            result = graph.query(cypher_query)
            return result

        except Exception as e:
            logger.error(f"Cypher execution failed: {str(e)}")
            raise GraphException(f"Cypher execution failed: {str(e)}")


def get_cypher_tool() -> CypherQueryTool:
    """Get Cypher query tool instance."""
    return CypherQueryTool()


def graph_qa(question: str) -> str:
    """Perform a question-answering query on the graph."""
    tool = get_cypher_tool()
    return tool.query(question)
