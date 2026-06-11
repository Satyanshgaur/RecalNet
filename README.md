# GraphMem: Structured Knowledge Graph Memory

GraphMem is an autonomous knowledge graph construction and storage system designed to provide LLMs with a persistent, structured, and semantically accurate long-term memory. Unlike standard vector databases, GraphMem extracts entities and directional relationships, allowing for complex reasoning and knowledge traversal.

## 🚀 Objectives
- **Semantic Extraction**: Transform unstructured text into high-fidelity entities and relationships.
- **Entity Resolution**: Automatically merge duplicate or similar entities using fuzzy matching and normalized names.
- **Confidence Accumulation**: Weight knowledge based on corroboration across multiple independent sources.
- **Durable Persistence**: Store and reload the entire knowledge graph from a local SQLite database.
- **LLM Agnostic (Ollama)**: Centralized interface for LLMs, optimized for high-performance local models like Qwen and Llama 3.

## 📂 Project Structure
```text
graphmem/
├── core/                # Core system utilities
│   ├── config.py        # Pydantic Settings (ENV overridable)
│   └── ollama_client.py # Resilient Async LLM Interface
├── graph/               # Graph data layer
│   ├── models.py        # Pydantic Node and Edge models
│   ├── store.py         # NetworkX-based graph operations
│   └── persistence.py   # SQLite storage layer
├── memory/              # High-level memory logic
│   ├── ingester.py      # Recursive chunking & ingestion pipeline
│   └── merger.py        # Fuzzy entity resolution & confidence logic
├── agents/              # Autonomous actors
│   └── extractor.py     # Advanced prompt engineering for KG extraction
├── data/                # Local data storage (SQLite, test files)
├── tests/               # Validation suite
├── notebooks/           # Research and visualization
└── pyproject.toml       # Dependency management via uv
```

## 🛠️ Installation

### 1. Prerequisites
- Python 3.10 or higher
- [uv](https://github.com/astral-sh/uv) (recommended) or `pip`

### 2. Install Python Dependencies
If using `uv`:
```bash
uv sync
```
Otherwise, using `pip`:
```bash
pip install httpx tenacity pydantic-settings networkx rapidfuzz
```

### 3. Install & Setup Ollama
Ollama serves the local LLM used for extraction.

1. **Download Ollama**: Visit [ollama.com](https://ollama.com) and download for your OS.
2. **Start the server**:
   ```bash
   ollama serve
   ```
3. **Pull the required model** (default is Qwen 2.5):
   ```bash
   ollama pull qwen2.5:7b
   ```

## ⚙️ Configuration
You can override any setting using environment variables or a `.env` file:
- `OLLAMA_URL`: Default is `http://localhost:11434`
- `MODEL_NAME`: Default is `qwen2.5:7b`
- `SQLITE_PATH`: Path to the SQLite DB (default: `data/graphmem.db`)
- `RETRIEVAL_CONFIDENCE_THRESHOLD`: Confidence floor for queries.

## 📖 Usage
To ingest a document and build your graph:

```python
import asyncio
from graphmem.graph.store import GraphStore
from graphmem.memory.ingester import DocumentIngester

async def main():
    store = GraphStore()
    ingester = DocumentIngester(store)
    
    # Ingest text
    await ingester.ingest("data/testfile.txt")
    
    print(f"Graph now contains {store.graph.number_of_nodes()} entities.")

if __name__ == "__main__":
    asyncio.run(main())
```

## 🧪 Running Tests
The project includes a comprehensive suite of verification scripts:
```bash
uv run python3 -m tests.test_persistence  # Test SQLite saving/loading
uv run python3 -m tests.test_merger       # Test fuzzy entity deduplication
uv run python3 -m tests.test_extractor    # Test LLM extraction quality
```
