"""Cypher query and graph-based tools."""

from typing import List, Dict, Any
from core.logger import get_logger
from core.exceptions import GraphException
from graph import get_graph
from llms import get_llm

from langchain_neo4j import GraphCypherQAChain
from langchain_core.prompts import PromptTemplate

logger = get_logger(__name__)


# System prompt for Cypher generation
CYPHER_GENERATION_PROMPT = """
You are an expert Neo4j Developer translating user questions into Cypher queries for a document knowledge graph.
The graph contains Document nodes and Chunk nodes with relationships between them.

INSTRUCTIONS:
1. Analyze the question against the schema provided below
2. If the question can be answered using the schema, generate a valid Cypher query
3. If the question CANNOT be answered with the available schema, respond with: "UNABLE_TO_ANSWER: The question cannot be answered with the current document schema"
4. Use ONLY relationship types and properties that exist in the schema
5. Do NOT invent nodes, relationships, or properties that don't exist
6. Do NOT return embedding properties in results
7. Always start your response with either a valid Cypher query starting with MATCH/RETURN, or with "UNABLE_TO_ANSWER:"

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
            answer = result.get("result", "")
            
            # Check if the response indicates the question cannot be answered
            if answer and "UNABLE_TO_ANSWER" in answer:
                logger.info(f"Question cannot be answered with current schema: {question}")
                return answer
            
            return answer

        except Exception as e:
            error_msg = str(e)
            # Check if it's a syntax error from invalid Cypher
            if "SyntaxError" in error_msg or "Invalid input" in error_msg:
                logger.warning(f"Generated invalid Cypher for question: {question}. Error: {error_msg}")
                return f"Unable to generate a valid query for this question. Please rephrase your question to focus on document content."
            
            logger.error(f"Cypher query failed: {error_msg}")
            raise GraphException(f"Cypher query failed: {error_msg}")

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
