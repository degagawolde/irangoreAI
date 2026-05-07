#!/usr/bin/env python
"""
Startup guide and configuration checker for the chatbot backend.
Run: python setup_guide.py
"""

import os
import sys
from pathlib import Path


def check_python_version():
    """Check Python version."""
    print("✓ Checking Python version...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 9:
        print(f"  Python {version.major}.{version.minor}.{version.micro} ✓")
        return True
    else:
        print(f"  ✗ Python 3.9+ required, found {version.major}.{version.minor}")
        return False


def check_env_file():
    """Check if .env file exists."""
    print("\n✓ Checking environment file...")
    env_file = Path(".env")
    if env_file.exists():
        print("  .env file exists ✓")
        return True
    else:
        print("  ✗ .env file not found")
        print("  Creating .env from .env.example...")
        if Path(".env.example").exists():
            with open(".env.example", "r") as f:
                content = f.read()
            with open(".env", "w") as f:
                f.write(content)
            print("  .env created from template ✓")
            print("  Please edit .env with your configuration")
            return False
        else:
            print("  ✗ .env.example not found")
            return False


def check_dependencies():
    """Check if required packages are installed."""
    print("\n✓ Checking dependencies...")
    required_packages = {
        "fastapi": "FastAPI",
        "pydantic": "Pydantic",
        "langchain": "LangChain",
        "neo4j": "Neo4j Driver",
    }

    missing = []
    for package, name in required_packages.items():
        try:
            __import__(package)
            print(f"  {name} ✓")
        except ImportError:
            print(f"  {name} ✗ (missing)")
            missing.append(package)

    return len(missing) == 0


def check_services():
    """Check if external services are available."""
    print("\n✓ Checking services...")

    # Check Neo4j
    try:
        from neo4j import GraphDatabase
        neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        print(f"  Neo4j URI: {neo4j_uri}")
        print("  ⚠ Run connectivity test after startup")
    except Exception as e:
        print(f"  ✗ Neo4j: {str(e)}")

    # Check LLM Provider
    llm_provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    if llm_provider == "ollama":
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        print(f"  Ollama URL: {ollama_url}")
    elif llm_provider == "openai":
        has_key = bool(os.getenv("OPENAI_API_KEY"))
        print(f"  OpenAI API Key: {'✓' if has_key else '✗ (missing)'}")


def print_next_steps():
    """Print next steps for user."""
    print("\n" + "="*60)
    print("NEXT STEPS")
    print("="*60)
    print("\n1. Edit .env file with your configuration:")
    print("   - NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD")
    print("   - LLM_PROVIDER and related settings")
    print("   - OLLAMA_BASE_URL (if using Ollama)")
    print("\n2. Start the application:")
    print("   fastapi dev main.py")
    print("\n3. Access the API:")
    print("   http://localhost:8000")
    print("\n4. View API documentation:")
    print("   http://localhost:8000/docs (Swagger UI)")
    print("   http://localhost:8000/redoc (ReDoc)")
    print("\n5. Test health endpoint:")
    print("   curl http://localhost:8000/health")
    print("\n" + "="*60)


def main():
    """Run all checks."""
    print("\n" + "="*60)
    print("CHATBOT BACKEND - SETUP GUIDE")
    print("="*60)

    checks = [
        ("Python Version", check_python_version),
        ("Environment Configuration", check_env_file),
        ("Dependencies", check_dependencies),
        ("External Services", check_services),
    ]

    all_passed = True
    for name, check_func in checks:
        try:
            result = check_func()
            if not result:
                all_passed = False
        except Exception as e:
            print(f"  ✗ Error checking {name}: {str(e)}")
            all_passed = False

    print_next_steps()

    if not all_passed:
        print("\n⚠ Some checks did not pass. Please review the output above.")
        print("\nYou can still start the application, but some features may not work.")
    else:
        print("\n✓ All checks passed! Ready to start the application.")


if __name__ == "__main__":
    main()
