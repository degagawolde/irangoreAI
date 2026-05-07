
from config import get_settings
from core.logger import get_logger, setup_logging
from tools.document_graph_tool import ingest_documents_to_graph
# Setup logging
setup_logging(log_level="INFO", log_format="standard")
logger = get_logger(__name__)

settings = get_settings()


if __name__ == "__main__":
    result = ingest_documents_to_graph(
        path="./_files",          # folder containing txt/md files
        chunk_size=1000,
        chunk_overlap=150
    )

    print(result)