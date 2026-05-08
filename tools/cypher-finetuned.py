from langchain_neo4j import GraphCypherQAChain
# tag::import-prompt-template[]
from langchain.prompts.prompt import PromptTemplate
# end::import-prompt-template[]

from llm import llm
from graph import graph

# tag::prompt[]
CYPHER_GENERATION_TEMPLATE = """
You are an expert Neo4j Developer translating user questions into Cypher to query documents stored as a knowledge graph.
Convert the user's question based on the schema.

Use only the provided relationship types and properties in the schema.
Do not use any other relationship types or properties that are not provided.

Do not return entire nodes or embedding properties.

Example Cypher Statements:

1. To find chunks from specific documents:
```
MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)
WHERE d.title CONTAINS "search term"
RETURN d.title, c.text, c.chunk_index
ORDER BY c.chunk_index
```

2. To find related chunks by sequence:
```
MATCH (c1:Chunk)-[:NEXT_CHUNK]->(c2:Chunk)
WHERE c1.document_id = "doc_id"
RETURN c1.text, c2.text
ORDER BY c1.chunk_index
```


Schema:
{schema}

Question:
{question}

Cypher Query:
"""
# end::prompt[]

# tag::template[]
cypher_prompt = PromptTemplate.from_template(CYPHER_GENERATION_TEMPLATE)
# end::template[]


# tag::cypher-qa[]
cypher_qa = GraphCypherQAChain.from_llm(
    llm,
    graph=graph,
    verbose=True,
    cypher_prompt=cypher_prompt,
    allow_dangerous_requests=True
)
# end::cypher-qa[]
