import json
from sqlalchemy.ext.asyncio import AsyncSession
from app.rag.retriever import retrieve_relevant_laws
from app.api.v1.services.llm_service import chat
from app.api.v1.schemas.regulation import RegulationQueryResponse, CitedSource
from app.core.prompts import REGULATION_SYSTEM_PROMPT, JURISDICTION_CONTEXT
from app.models.query_log import QueryLog


async def answer_regulation_query(
    question: str,
    jurisdiction: str = "Ethiopia",
    db: AsyncSession = None
) -> RegulationQueryResponse:

    # 1. Hybrid search — BM25 + semantic
    retrieved_docs = await retrieve_relevant_laws(
        query=question,
        jurisdiction=jurisdiction,
        n_results=5
    )

    # 2. Build context
    if retrieved_docs:
        context_block = "\n\n---\n\n".join([
            f"Source: {doc['source']} | Article: {doc['article']}\n{doc['text']}"
            for doc in retrieved_docs
        ])
        jurisdiction_ctx = JURISDICTION_CONTEXT.format(
            jurisdiction=jurisdiction,
            legal_framework=context_block
        )
    else:
        jurisdiction_ctx = JURISDICTION_CONTEXT.format(
            jurisdiction=jurisdiction,
            legal_framework=(
                "No specific regulation found in database. "
                "Answer based on general knowledge but be explicit about this limitation."
            )
        )

    # 3. Call LLM
    messages = [
        {
            "role": "user",
            "content": f"{jurisdiction_ctx}\n\nUser question: {question}"
        }
    ]

    answer = await chat(
        messages=messages,
        system_prompt=REGULATION_SYSTEM_PROMPT,
        temperature=0.1
    )

    # 4. Build sources
    sources = [
        CitedSource(
            source=doc["source"],
            article=doc["article"],
            jurisdiction=doc["jurisdiction"]
        )
        for doc in retrieved_docs
    ]

    result = RegulationQueryResponse(
        answer=answer,
        sources=sources,
        jurisdiction=jurisdiction
    )

    # 5. Log to Postgres
    if db:
        try:
            log = QueryLog(
                question=question,
                jurisdiction=jurisdiction,
                answer=answer,
                sources=json.dumps([s.model_dump() for s in sources])
            )
            db.add(log)
            await db.commit()
        except Exception as e:
            print(f"[WARN] Failed to log query: {e}")

    return result