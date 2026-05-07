"""Dependency verification script."""

import sys
from pathlib import Path

def check_imports():
    """Check if all required packages are installed."""
    required_packages = {
        "fastapi": "FastAPI",
        "pydantic": "Pydantic",
        "pydantic_settings": "Pydantic Settings",
        "langchain": "LangChain",
        "langchain_core": "LangChain Core",
        "langchain_neo4j": "LangChain Neo4j",
        "langchain_ollama": "LangChain Ollama",
        "neo4j": "Neo4j",
        "dotenv": "Python Dotenv",
    }

    missing = []
    installed = []

    for module, display_name in required_packages.items():
        try:
            __import__(module)
            installed.append(display_name)
            print(f"✓ {display_name}")
        except ImportError:
            missing.append(display_name)
            print(f"✗ {display_name}")

    print(f"\n{'='*50}")
    print(f"Installed: {len(installed)}/{len(required_packages)}")
    if missing:
        print(f"\nMissing packages:")
        for pkg in missing:
            print(f"  - {pkg}")
        return False
    return True

if __name__ == "__main__":
    print("Checking dependencies...\n")
    if check_imports():
        print("\n✓ All dependencies satisfied!")
        sys.exit(0)
    else:
        print("\n✗ Some dependencies are missing.")
        print("\nRun: pip install -r requirements.txt")
        sys.exit(1)
