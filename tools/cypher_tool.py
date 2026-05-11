"""Cypher query and graph-based tools with dynamic schema extraction and modern Neo4j driver."""

from typing import List, Dict, Any, Optional, Tuple
from core.logger import get_logger
from core.exceptions import GraphException
from graph import get_graph
from llms import get_llm
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

logger = get_logger(__name__)


# -----------------------------------------------------------------------------
# Prompt Templates
# -----------------------------------------------------------------------------

CYPHER_GENERATION_PROMPT = """
You are an expert Neo4j Developer translating user questions into precise Cypher queries.

**Available Schema (dynamically extracted from the database):**
{schema}

**Instructions:**
1. Generate a valid Cypher query to answer the user's question using ONLY the provided schema.
2. If the question CANNOT be answered with the available schema, respond with exactly:
   `UNABLE_TO_ANSWER: The question cannot be answered with the current document schema`
3. Never invent nodes, relationships, or properties that do not exist in the schema.
4. Never return embedding properties in results (they are large and unnecessary).
5. Use `elementId(node)` instead of the deprecated `id(node)`.
6. For optional properties, use `COALESCE(node.optional_prop, "default")` or access via `properties(node)`.
7. Always return human‑readable properties (e.g., `title`, `text`, `chunk_index`).
8. Prefer parameterized values (e.g., `$search_term`) to avoid Cypher injection.

**Examples:**
- Find chunks from documents containing a title:

MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)
WHERE d.title CONTAINS $search_term
RETURN d.title, c.text, c.chunk_index
ORDER BY c.chunk_index 

- Find next chunks in sequence:
MATCH (c1:Chunk)-[:NEXT_CHUNK]->(c2:Chunk)
WHERE c1.document_id = $doc_id
RETURN c1.text AS previous_text, c2.text AS next_text


**Question:** {question}
**Cypher Query:**
"""

QA_PROMPT = """
You are a helpful assistant. Use the following context from the graph database to answer the user's question.
If the context does not contain enough information, say "I don't know based on the provided data."

Context:
{context}

Question: {question}
Answer:
"""


# -----------------------------------------------------------------------------
# Schema Extractor
# -----------------------------------------------------------------------------

class GraphSchemaExtractor:
  """Dynamically extract schema information from Neo4j database."""

  def __init__(self, graph):
      self.graph = graph

  def extract(self) -> str:
      """Return a formatted string describing node labels, relationship types, and key properties."""
      try:
          # Get all node labels with sample properties (limit to 2 per label)
          labels_query = """
          CALL db.labels() YIELD label
          WITH label
          OPTIONAL MATCH (n)
          WHERE label IN labels(n)
          WITH label, n LIMIT 2
          RETURN label, collect(keys(n)) AS sample_props
          """
          labels_result = self.graph.query(labels_query)
          
          # Get all relationship types
          rels_query = "CALL db.relationshipTypes() YIELD relationshipType RETURN collect(relationshipType) AS types"
          rels_result = self.graph.query(rels_query)
          relationship_types = rels_result[0]["types"] if rels_result else []
          
          # Format schema string
          schema_lines = ["Node Labels and their properties (from sample nodes):"]
          for record in labels_result:
              label = record["label"]
              props = set()
              for props_list in record["sample_props"]:
                  props.update(props_list)
              # Remove embedding properties
              props = [p for p in props if "embedding" not in p.lower()]
              props_str = ", ".join(sorted(props)) if props else "(no properties sampled)"
              schema_lines.append(f"  :{label} {{{props_str}}}")
          
          if relationship_types:
              schema_lines.append("\nRelationship Types:")
              for rel in sorted(relationship_types):
                  schema_lines.append(f"  -[:{rel}]->")
          
          # Add constraints and indexes info
          indexes_query = "SHOW INDEXES YIELD name, type, labelsOrTypes, properties WHERE type = 'VECTOR' OR type = 'RANGE' RETURN name, type, labelsOrTypes, properties"
          indexes = self.graph.query(indexes_query)
          if indexes:
              schema_lines.append("\nExisting Indexes:")
              for idx in indexes:
                  idx_info = f"  {idx['name']}: {idx['type']} ON {idx['labelsOrTypes']}({', '.join(idx['properties'])})"
                  schema_lines.append(idx_info)
          
          return "\n".join(schema_lines)
      except Exception as e:
          logger.warning(f"Could not extract full schema: {e}. Returning minimal schema.")
          return "Node labels: Document, Chunk. Relationships: HAS_CHUNK, NEXT_CHUNK."


# -----------------------------------------------------------------------------
# Cypher Query Tool
# -----------------------------------------------------------------------------

class CypherQueryTool:
  """Tool for generating and executing Cypher queries with dynamic schema."""

  _instance = None
  _graph = None
  _llm = None
  _schema_extractor = None

  def __new__(cls):
      if cls._instance is None:
          cls._instance = super().__new__(cls)
      return cls._instance

  def __init__(self):
      if self._graph is None:
          self._initialize()

  def _initialize(self) -> None:
      """Initialize graph, LLM, and schema extractor."""
      try:
          self._graph = get_graph()
          self._llm = get_llm()
          self._schema_extractor = GraphSchemaExtractor(self._graph)
          logger.info("CypherQueryTool initialized with dynamic schema extraction")
      except Exception as e:
          logger.error(f"Failed to initialize CypherQueryTool: {e}")
          raise GraphException(f"Failed to initialize CypherQueryTool: {e}")

  def _get_schema(self) -> str:
      """Get current schema as a formatted string."""
      return self._schema_extractor.extract()

  def _generate_cypher(self, question: str) -> Tuple[Optional[str], Optional[str]]:
      """
      Generate a Cypher query from the user's question.
      Returns (cypher_query, error_message). If successful, error_message is None.
      """
      try:
          schema = self._get_schema()
          prompt = PromptTemplate.from_template(CYPHER_GENERATION_PROMPT)
          chain = prompt | self._llm | StrOutputParser()
          
          response = chain.invoke({"schema": schema, "question": question}).strip()
          
          # Check if the model indicates inability to answer
          if response.startswith("UNABLE_TO_ANSWER"):
              return None, response
          
          # Assume the response is a Cypher query (may contain multiple lines)
          # Remove markdown code fences if present
          if response.startswith("```cypher"):
              response = response.split("```cypher", 1)[1].split("```", 1)[0].strip()
          elif response.startswith("```"):
              response = response.split("```", 2)[1].strip()
          
          # Basic validation: ensure it starts with MATCH, OPTIONAL MATCH, CALL, etc.
          first_word = response.split()[0].upper() if response else ""
          if first_word not in ("MATCH", "OPTIONAL", "CALL", "RETURN", "WITH", "UNWIND"):
              logger.warning(f"Generated query does not look like Cypher: {response[:100]}")
              return None, f"Generated invalid Cypher: {response[:100]}..."
          
          return response, None
          
      except Exception as e:
          logger.error(f"Error generating Cypher: {e}")
          return None, f"Error generating query: {str(e)}"

  def _execute_cypher_safe(self, cypher_query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
      """
      Execute a Cypher query with parameterization and property safety.
      Returns list of records (each as dict).
      """
      try:
          if params is None:
              params = {}
          # Log the query (without parameters for debugging)
          logger.debug(f"Executing Cypher: {cypher_query} | Params: {params}")
          result = self._graph.query(cypher_query, params)
          # Filter out large embedding properties if any accidentally returned
          safe_result = []
          for record in result:
              safe_record = {}
              for k, v in record.items():
                  if isinstance(v, list) and len(v) > 1000 and isinstance(v[0], float):
                      # Likely an embedding vector – skip
                      continue
                  safe_record[k] = v
              safe_result.append(safe_record)
          return safe_result
      except Exception as e:
          error_msg = str(e).lower()
          if "does not exist" in error_msg or "property not found" in error_msg:
              logger.warning(f"Query referenced non-existent property: {error_msg}")
              return []
          raise GraphException(f"Cypher execution failed: {error_msg}")

  def query(self, question: str) -> str:
      """
      Answer a natural language question using the graph.
      Returns a textual answer.
      """
      try:
          # Step 1: Generate Cypher
          cypher, error = self._generate_cypher(question)
          if error:
              if error.startswith("UNABLE_TO_ANSWER"):
                  return error
              return f"Unable to answer: {error}"
          
          # Step 2: Execute Cypher
          results = self._execute_cypher_safe(cypher)
          if not results:
              return "No relevant information found in the knowledge graph."
          
          # Step 3: Format context for QA
          context_str = "\n".join(str(record) for record in results[:10])  # Limit to 10 results
          
          # Step 4: Generate final answer using LLM
          qa_prompt = PromptTemplate.from_template(QA_PROMPT)
          qa_chain = qa_prompt | self._llm | StrOutputParser()
          answer = qa_chain.invoke({"context": context_str, "question": question})
          return answer.strip()
          
      except GraphException as e:
          logger.error(f"Graph query failed: {e}")
          return f"Sorry, an error occurred while querying the database: {str(e)}"
      except Exception as e:
          logger.error(f"Unexpected error in graph_qa: {e}")
          return "An unexpected error occurred. Please try again later."

  def execute_cypher(self, cypher_query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
      """
      Execute a raw Cypher query (for advanced users).
      WARNING: Use with proper parameters to avoid injection.
      """
      return self._execute_cypher_safe(cypher_query, params)

  def validate_cypher(self, cypher_query: str) -> Tuple[bool, Optional[str]]:
      """
      Validate a Cypher query by running it with LIMIT 0 (if possible) or querying a fake node.
      Returns (is_valid, error_message).
      """
      # Try to prepend EXPLAIN to get syntax validation without execution
      explain_query = f"EXPLAIN {cypher_query}"
      try:
          self._graph.query(explain_query)
          return True, None
      except Exception as e:
          error_msg = str(e)
          if "SyntaxError" in error_msg or "Invalid input" in error_msg:
              return False, f"Cypher syntax error: {error_msg}"
          # Some other error (e.g., missing index) – still considered invalid for our use
          return False, error_msg


# -----------------------------------------------------------------------------
# Public Interface
# -----------------------------------------------------------------------------

def get_cypher_tool() -> CypherQueryTool:
  """Get the singleton CypherQueryTool instance."""
  return CypherQueryTool()


def graph_qa(question: str) -> str:
  """Convenience function to ask a question against the graph database."""
  tool = get_cypher_tool()
  return tool.query(question)


def execute_cypher(cypher: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
  """Execute raw Cypher query (for debugging or advanced uses)."""
  tool = get_cypher_tool()
  return tool.execute_cypher(cypher, params)