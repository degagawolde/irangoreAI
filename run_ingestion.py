
from tools.document_graph_tool import ingest_documents_to_graph


if __name__ == "__main__":
    result = ingest_documents_to_graph(
        path="./docs",          # folder containing txt/md files
        chunk_size=1000,
        chunk_overlap=150
    )

    print(result)