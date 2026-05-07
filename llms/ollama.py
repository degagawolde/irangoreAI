from langchain_ollama import ChatOllama, OllamaEmbeddings

# LLM
llm = ChatOllama(model="qwen3:8b",temperature=0.7)

# Embeddings
embeddings = OllamaEmbeddings(model="qwen3-embedding") ## or use qwen3-embedding or use text-embedding-3-large or mxbai-embed-large