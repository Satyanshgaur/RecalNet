# Persistent Graph Memory Framework 


## Core Technology Stack and Why

**LLM Runtime: Ollama**
Not llama.cpp directly. Ollama wraps llama.cpp with a clean REST API, handles model management, and gives you `/api/generate` and `/api/chat` without writing C++ bindings. For a solo developer this saves weeks. You'll run Qwen2.5-7B-Instruct at Q4_K_M quantization. This fits in ~4.4GB VRAM, leaves headroom for KV cache, and Qwen2.5 is genuinely strong at structured extraction tasks which you'll need constantly.

**Graph Database: NetworkX + SQLite persistence**
Not Neo4j. Not ArangoDB. NetworkX is a pure Python in-memory graph library with no server process, no JVM, no TCP overhead. You serialize the graph to SQLite using a simple schema you control. This sounds boring but it is the correct choice for a solo developer on constrained hardware — you spend zero time on database administration and your entire graph fits in memory (a knowledge graph of 100,000 nodes with metadata takes roughly 200–400MB RAM in NetworkX, which is perfectly fine). When you scale later, you migrate the serialization layer without touching the graph logic.

**Vector Store: ChromaDB**
Not FAISS directly, not Qdrant. ChromaDB runs embedded (no separate server), persists to disk automatically, has a clean Python API, and uses SQLite under the hood. FAISS is faster but requires you to manage persistence yourself. Qdrant requires a Docker container. ChromaDB gives you 90% of production-grade retrieval with 10% of the operational overhead. For a solo project this ratio matters enormously.

**Embeddings: sentence-transformers with all-MiniLM-L6-v2**
This model is 90MB, runs efficiently on CPU, produces 384-dimensional embeddings, and has excellent semantic quality for its size. You run it on CPU deliberately, keeping your full VRAM for the LLM. Inference on CPU for a batch of 32 sentences takes about 1–2 seconds on an i5 — completely acceptable for an ingestion pipeline. `nomic-embed-text` via Ollama is an alternative if you want GPU acceleration for embeddings, but it competes with your LLM for VRAM and requires model switching logic.

**Orchestration: Pure Python with asyncio**
No LangChain. No LlamaIndex. This is a deliberate choice. Both frameworks add significant abstraction layers that make debugging painful, hide what's actually happening in your prompts, and change their APIs constantly. For a framework project where you are building the memory architecture itself, you want to understand every layer. You'll write clean Python classes with async methods where IO-bound operations benefit from it (Ollama calls, ChromaDB queries) and synchronous code everywhere else.

**Entity and Relation Extraction: Structured prompting to Ollama**
You prompt your local Qwen model with carefully designed JSON-extraction prompts and parse the output. No spaCy NER, no external NLP pipeline in early stages. Local LLM extraction is slower but handles complex relational text far better than rule-based NER and requires zero additional infrastructure.

**API Layer: FastAPI**
When you expose the agent-oriented querying interface, FastAPI is the obvious choice — async-native, automatic OpenAPI docs, minimal boilerplate, runs with uvicorn.

---

## Project Phases

### Phase 0: Environment and Skeleton (Week 1–2)

Before writing a single line of fraework code, set up your development environment correctly once so you never fight it again.

Install Ollama and pull `qwen2.5:7b-instruct-q4_K_M`. Run `ollama serve` and verify you can call it from Python via `httpx` or `requests`. Test that the model loads fully onto your GPU — run `nvidia-smi` during inference and confirm VRAM utilization. If it spills to CPU, your quantization level is wrong.

Create a Python project with a `pyproject.toml` using uv or pip-tools for dependency pinning. Your directory structure should be: `graphmem/core/`, `graphmem/graph/`, `graphmem/retrieval/`, `graphmem/memory/`, `graphmem/agents/`, `graphmem/api/`, `tests/`, `notebooks/`, `data/`. Create this structure empty with `__init__.py` files. This is your map for the entire project.

Write a single `config.py` with a Pydantic Settings class. Every tunable value — Ollama URL, model name, ChromaDB path, SQLite path, embedding model name, confidence thresholds — lives here and is overridable via environment variables. You will thank yourself for this in Phase 3.

Write a minimal `OllamaClient` class with `generate()` and `chat()` async methods, basic retry logic with exponential backoff, and a timeout. This is the only interface through which the rest of your code talks to the LLM. Centralizing this lets you swap models or add logging in one place.

**Deliverable at end of Phase 0:** You can send a prompt to Qwen from Python, get a JSON response back, and parse it reliably. That's it.

---

### Phase 1: Graph Core and Persistence (Week 3–5)

This is the foundation everything else stands on. Get it right before moving forward.

Design your graph schema first, in a document, before writing code. A node has: a unique ID (UUID), a label (Person, Organization, Concept, Event, Location, Document), a name, a properties dictionary, a confidence score (float 0–1), a creation timestamp, a last-updated timestamp, and a source list (list of document IDs or chunk IDs it was derived from). An edge has: source node ID, target node ID, a relation type (string), a properties dictionary, a confidence score, a creation timestamp, and optionally start/end timestamps for temporal edges.

Implement a `GraphStore` class backed by NetworkX. It wraps a `nx.MultiDiGraph` (directed, allows multiple edges between same nodes). Write methods: `add_node()`, `add_edge()`, `get_node()`, `get_neighbors()`, `find_nodes_by_label()`, `find_nodes_by_name()`, `get_subgraph()`, `delete_node()`, `update_node_confidence()`. Keep these methods dumb — they do graph operations only, no LLM calls, no embeddings.

Write the SQLite persistence layer separately as a `GraphPersistence` class. It has two methods that matter: `save(graph)` and `load() -> graph`. Your SQLite schema has two tables: `nodes` with columns matching your node schema, and `edges` with columns matching your edge schema. Serialize the properties dictionary as JSON in a TEXT column. On save, you do a full replace (drop and recreate) or upsert. On load, you reconstruct the NetworkX graph. This is not elegant but it is fast to implement and correct. You optimize it later if needed.

Write tests for this. Specifically: create a graph with 10 nodes and 15 edges, save to SQLite, load from a fresh `GraphStore`, assert the structure is identical. This test will save you hours of debugging in later phases.

At this point you have a persistent graph that survives process restarts. This feels simple, but it's the hardest constraint to retrofit later.

**Deliverable at end of Phase 1:** A `GraphStore` that you can add nodes and edges to, save to disk, kill the process, restart, load, and find everything intact.

---

### Phase 2: Extraction Pipeline (Week 6–9)

This is where your LLM starts doing real work.

Write an `Extractor` class. Its job is to take a text chunk and return structured entities and relations. The prompt engineering here is the most important work in the entire project. A well-designed extraction prompt is worth more than any architectural decision.

Your extraction prompt should instruct Qwen to return a JSON object with two keys: `entities` (list of objects with `name`, `label`, `properties`) and `relations` (list of objects with `source`, `target`, `relation`, `properties`). Give it 3–4 few-shot examples in the prompt of the quality and format you want. Specify explicitly what counts as an entity worth extracting versus incidental nouns. Specify that relations should be directional and use consistent verb forms.

The output from the LLM will not always be valid JSON. Write a `parse_extraction_output()` function that tries `json.loads()` first, then falls back to regex extraction of the JSON block from markdown code fences, then logs a warning and returns empty lists if parsing fails completely. Never let a parse failure crash your pipeline.

Write a `DocumentIngester` class. It takes a file path or raw text, chunks it (start with fixed-size 512-token chunks with 64-token overlap using a simple recursive character splitter you write yourself — it's 30 lines of code and you understand exactly what it does), runs extraction on each chunk, and calls `GraphStore` to merge the results.

Merging is the subtle part. When extraction returns an entity named "OpenAI", you need to check if a node named "OpenAI" with label "Organization" already exists before creating a new one. Write a `NodeMerger` class that does fuzzy name matching (start with exact lowercase match, add edit-distance matching in Phase 3). If a match exceeds your similarity threshold, update the existing node rather than creating a duplicate. Log every merge decision — you'll need these logs for debugging.

Assign initial confidence scores. Entities extracted from a single source get confidence 0.6. Each additional independent source that corroborates the entity adds 0.1 (capped at 0.95). This is your confidence accumulation model — simple but correct.

**Deliverable at end of Phase 2:** Feed a 10-page PDF into your system and inspect the resulting graph. Open a Python REPL, load the graph, and traverse it manually. Check that entity deduplication is working. Check that relations make semantic sense. Expect it to be imperfect — fix the extraction prompt, not the architecture.

---

### Phase 3: Hybrid Retrieval (Week 10–13)

Now you build the retrieval layer that makes the graph useful for query answering.

Set up ChromaDB. Create a collection called `chunk_embeddings`. When you ingest a document in Phase 2's pipeline, also embed each text chunk using `sentence-transformers` and store it in ChromaDB with metadata: `chunk_id`, `document_id`, `node_ids` (list of node IDs extracted from this chunk), and the raw text.

Write a `VectorRetriever` class. Given a query string, it embeds the query, calls `ChromaDB.query()` with `n_results=10`, and returns the top chunks with their metadata.

Write a `GraphRetriever` class. Given a query string, it first identifies seed nodes relevant to the query — do this by embedding the query, then finding the top-K nodes by cosine similarity to their name embeddings (store node name embeddings in a separate ChromaDB collection or as a numpy array you maintain in memory). From each seed node, do a breadth-first traversal up to 2 hops, collecting all encountered nodes and edges. Return this subgraph.

Write a `HybridRetriever` class that calls both retrievers, deduplicates results by cross-referencing `node_ids` from vector results with graph retrieval results, and ranks the combined context. Your ranking formula at this stage: `score = 0.6 * vector_similarity + 0.4 * graph_centrality_proxy` where graph centrality proxy is simply the degree of the node normalized to [0,1]. This is not sophisticated but it works and is explainable.

Write a `ContextBuilder` class that takes retrieval results and formats them into a prompt context. This is more important than it sounds. You need to represent graph triples (subject, relation, object) and vector chunk text in a format that Qwen can reason over effectively. Design a compact text format — something like "FACT: [EntityA] --[relation]--> [EntityB] (confidence: 0.85, source: doc_3)" followed by raw text chunks. Keep the total context under 3000 tokens to leave room for the question and answer within Qwen's context window.

Write a `QueryEngine` class that takes a question, calls `HybridRetriever`, calls `ContextBuilder`, formats the final prompt, calls Ollama, and returns the response with a list of source references.

**Deliverable at end of Phase 3:** Ask your system a question about a document you ingested. It should return an answer with citations to specific sources. Run 20 test queries manually and score the relevance. Fix retrieval issues by tuning the hybrid weights and the graph traversal depth.

---

### Phase 4: Temporal and Confidence Systems (Week 14–17)

Only build this after Phase 3 is stable and tested. This is where many projects go wrong — building temporal complexity before basic retrieval works.

For temporal edges, add `valid_from` and `valid_to` datetime fields to your edge schema. These are nullable — most edges are not temporally bounded. When extraction produces a relation with temporal context ("was CEO of X from 2010 to 2015"), your extraction prompt should capture this and your ingester should populate these fields. Add a `get_edges_at_time(timestamp)` method to `GraphStore` that filters edges by temporal validity.

For memory aging, write a scheduled job (use Python's `schedule` library or a simple background thread with `threading.Timer`) that runs once per day. It iterates over all nodes and applies a decay function: `confidence = confidence * decay_factor ^ days_since_last_accessed` where `decay_factor` is 0.99 by default (configurable). Nodes that are accessed via retrieval have their `last_accessed` timestamp updated, which resets their decay clock. Nodes that fall below a `minimum_confidence` threshold of 0.2 get flagged (not deleted — you never auto-delete in v1).

For contradiction detection, write a `ContradictionDetector` class. It looks for pairs of edges with the same source node, the same or semantically similar relation, but conflicting target nodes. Semantic similarity between relation strings is checked via embedding cosine similarity (embed the relation strings using your existing embedding model). When a contradiction is detected, log it with both edge IDs, their confidence scores, and their sources. In v1 you don't auto-resolve contradictions — you surface them. Your query engine checks for relevant contradictions and includes them in the context with a note that the information is contested.

**Deliverable at end of Phase 4:** Ingest two documents that contain contradictory claims about the same entity. Your system should detect and flag the contradiction. Query about that entity and see the contradiction surfaced in the response.

---

### Phase 5: Agent API (Week 18–21)

Build the FastAPI layer that makes the framework usable by external agents.

Your API has five endpoints that cover everything an agent needs. `POST /ingest` accepts a text payload or file upload and runs the full ingestion pipeline, returning a job ID and eventually a summary of extracted entities and relations. `POST /query` accepts a question string and optional filters (time range, minimum confidence, specific entity labels) and returns an answer with sources. `GET /graph/node/{node_id}` returns a node with its immediate neighbors. `POST /graph/update` accepts explicit node/edge updates from an agent (for when the agent wants to directly write to memory rather than going through extraction). `GET /health` returns system status including graph size, ChromaDB size, and Ollama availability.

Add API key authentication as a simple header check — one line of FastAPI middleware. Even for local use, this is good practice and costs nothing.

Write an async task queue using `asyncio.Queue` for ingestion jobs so that POST /ingest returns immediately with a job ID and processes in the background. Poll with `GET /jobs/{job_id}` for status.

Document all endpoints. FastAPI generates OpenAPI docs automatically at `/docs` — test every endpoint via the Swagger UI before calling it from code.

**Deliverable at end of Phase 5:** A running local server you can curl against. An agent (even a simple Python script that loops and calls your API) that ingests documents and answers questions autonomously.

---

### Phase 6: Visualization and Observability (Week 22–24)

Build this last, because you need real data in your graph to know what visualization is actually useful.

Write a simple web interface using vanilla HTML and JavaScript with Cytoscape.js loaded from CDN. Serve it from your FastAPI app as a static file. It calls your API's graph endpoints and renders the graph. Add controls for: filtering by node label, filtering by minimum confidence, showing/hiding temporal edges, highlighting contradiction-flagged edges in red.

Add a retrieval trace to your `QueryEngine` — when answering a query, record which nodes were retrieved, which chunks were retrieved, what the hybrid scores were, and which parts of context influenced the answer. Return this trace in the API response as an optional `debug` field. Display it in your UI as a "reasoning path" panel.

---

## Version Roadmap

**v0.1 (Phases 0–2):** Ingestion, graph construction, persistence. No retrieval yet. Use the Python REPL to query the graph directly.

**v0.2 (Phase 3):** Hybrid retrieval and query answering. This is your first "working" demo.

**v0.3 (Phase 4):** Temporal edges, memory aging, contradiction detection. The graph becomes genuinely intelligent.

**v0.4 (Phase 5):** FastAPI layer. The framework becomes usable by other systems.

**v0.5 (Phase 6):** Visualization. The framework becomes explainable.

**v1.0:** Integration testing across all components, performance profiling, documentation, README with quickstart. Open-source release.

**Post-v1.0 considerations if the project succeeds:** Replace NetworkX+SQLite with a proper embedded graph database (Kuzu is the best option here — it's embedded, fast, and supports Cypher queries without a server process). Add a proper NER preprocessing step with spaCy to improve extraction quality. Explore `nomic-embed-text` for better embeddings if you upgrade hardware. Add multi-document summarization for generating graph-level summaries.

---


