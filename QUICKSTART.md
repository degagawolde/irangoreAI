# Quick Start Guide

## Option 1: Local Development (Recommended for Development)

### Prerequisites
- Python 3.9+
- Neo4j running locally or accessible
- Ollama or OpenAI API key

### Steps

1. **Clone the repository**
```bash
cd IranGoreBackend
```

2. **Create virtual environment**
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Setup configuration**
```bash
cp .env.example .env
# Edit .env with your settings
```

5. **Verify setup**
```bash
python setup_guide.py
```

6. **Run the server**
```bash
fastapi dev main.py
```

7. **Test the API**
```bash
# In another terminal
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello"}'
```

---

## Option 2: Docker Compose (Recommended for Production)

### Prerequisites
- Docker
- Docker Compose

### Steps

1. **Navigate to project directory**
```bash
cd IranGoreBackend
```

2. **Create .env file**
```bash
cp .env.example .env
```

3. **Start services**
```bash
docker-compose up -d
```

4. **Check logs**
```bash
docker-compose logs -f chatbot
```

5. **Test the API**
```bash
curl http://localhost:8000/health
```

6. **Access UI**
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Neo4j Browser: http://localhost:7474

---

## Option 3: Manual Docker Build

### Build
```bash
docker build -t chatbot-backend .
```

### Run
```bash
docker run -p 8000:8000 \
  -e NEO4J_URI=bolt://host.docker.internal:7687 \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  chatbot-backend
```

---

## Verification Checklist

- [ ] Python 3.9+ installed
- [ ] Virtual environment created and activated
- [ ] Dependencies installed: `pip list | grep -i langchain`
- [ ] .env file configured
- [ ] Neo4j connection working: Check in logs
- [ ] LLM provider accessible
- [ ] API health check passes: `curl http://localhost:8000/health`

---

## Common Issues

### Neo4j Connection Failed
```
Solution: Verify NEO4J_URI in .env and ensure Neo4j is running
docker exec chatbot-neo4j cypher-shell -u neo4j -p password "RETURN 'test'"
```

### Ollama Not Found
```
Solution: Start Ollama or update OLLAMA_BASE_URL in .env
ollama serve  # In separate terminal
```

### Port Already in Use
```
Solution: Change port in config or stop conflicting service
lsof -i :8000  # Find process using port 8000
```

### ModuleNotFoundError
```
Solution: Activate virtual environment and reinstall dependencies
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Next Steps

1. **Read Full Documentation**: See [README.md](README.md)
2. **Explore API**: Visit http://localhost:8000/docs
3. **Test Endpoints**: Use provided examples in README.md
4. **Extend Agents**: Add custom tools and agents
5. **Deploy**: Use docker-compose.yml for production

---

## Support

For detailed troubleshooting, see the README.md file or check logs in `logs/` directory.
