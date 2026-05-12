# System A: Vector Database

Stores documents as text + 768-dimensional embeddings for semantic search. Every record is immutable after ingestion — hit counts are updated in place, but text and embeddings are never modified.

---

## Directory Structure

```
$KB_BASE/
└── {Topic}/
    └── records.json    ← all records for this topic
```

---

## Ingesting a Document

```python
import json
import uuid
import hashlib
import ollama
import os
from datetime import datetime
from pathlib import Path

KB_BASE = Path(os.environ.get("KB_BASE", Path.home() / ".knowledge_base"))
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text-v2-moe:latest")
EMBED_DIM = 768

def normalize(text: str) -> str:
    return " ".join(text.lower().split())

def ingest(
    topic: str,
    text: str,
    doc_name: str,
    source_locator: str,
    source_type: str = "url",   # "url" | "file" | "note"
    chunk_idx: int = 0,
    total_chunks: int = 1,
):
    content_hash = hashlib.sha256(normalize(text).encode()).hexdigest()

    # Skip duplicate content
    records_path = KB_BASE / topic / "records.json"
    records_path.parent.mkdir(parents=True, exist_ok=True)
    records = json.loads(records_path.read_text()) if records_path.exists() else []

    if any(r.get("content_hash") == content_hash for r in records):
        return None  # duplicate, skip

    resp = ollama.embed(model=EMBED_MODEL, input=text)
    embedding = resp["embeddings"][0]

    record = {
        "id": str(uuid.uuid4()),
        "content_hash": content_hash,
        "text": text,
        "embedding": embedding,
        "metadata": {
            "source_type": source_type,
            "source_locator": source_locator,
            "source_fetched_at": datetime.now().isoformat(),
            "doc_name": doc_name,
            "topic": topic,
            "indexed_at": datetime.now().isoformat(),
            "embedding_model": EMBED_MODEL,
            "embedding_dim": EMBED_DIM,
            "chunk_idx": chunk_idx,
            "total_chunks": total_chunks,
            "hit_count": 0,
            "promoted_to_wiki": False,
            "promoted_at": None,
        }
    }

    records.append(record)
    records_path.write_text(json.dumps(records, ensure_ascii=False, indent=2))
    return record["id"]
```

---

## Querying

### Basic query (semantic search)

```python
import json, os
import ollama
import numpy as np
from pathlib import Path

KB_BASE = Path(os.environ.get("KB_BASE", Path.home() / ".knowledge_base"))
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text-v2-moe:latest")

def search(topic: str, query: str, top_k: int = 5) -> list[dict]:
    records_path = KB_BASE / topic / "records.json"
    records = json.loads(records_path.read_text())

    q_vec = np.array(ollama.embed(model=EMBED_MODEL, input=query)["embeddings"][0])

    results = []
    for r in records:
        vec = np.array(r["embedding"])
        score = float(np.dot(q_vec, vec) / (np.linalg.norm(q_vec) * np.linalg.norm(vec)))
        results.append({"score": score, "text": r["text"], "metadata": r["metadata"], "id": r["id"]})

    results.sort(key=lambda x: x["score"], reverse=True)
    hits = [r for r in results if r["score"] > 0.75][:top_k]

    # Increment hit_count for returned records
    hit_ids = {r["id"] for r in hits}
    for r in records:
        if r["id"] in hit_ids:
            r["metadata"]["hit_count"] = r["metadata"].get("hit_count", 0) + 1
    records_path.write_text(json.dumps(records, ensure_ascii=False, indent=2))

    return hits
```

### Query with metadata filtering

```python
def search_filtered(
    topic: str,
    query: str,
    top_k: int = 5,
    source_type: str = None,    # "url" | "file" | "note"
    doc_name: str = None,
    after_date: str = None,     # "YYYY-MM-DD"
) -> list[dict]:
    records_path = KB_BASE / topic / "records.json"
    records = json.loads(records_path.read_text())

    # Pre-filter by metadata (no embedding needed)
    if source_type:
        records = [r for r in records if r["metadata"].get("source_type") == source_type]
    if doc_name:
        records = [r for r in records if r["metadata"].get("doc_name") == doc_name]
    if after_date:
        records = [r for r in records if r["metadata"].get("indexed_at", "") >= after_date]

    if not records:
        return []

    q_vec = np.array(ollama.embed(model=EMBED_MODEL, input=query)["embeddings"][0])
    results = []
    for r in records:
        vec = np.array(r["embedding"])
        score = float(np.dot(q_vec, vec) / (np.linalg.norm(q_vec) * np.linalg.norm(vec)))
        results.append({"score": score, "text": r["text"], "metadata": r["metadata"], "id": r["id"]})

    results.sort(key=lambda x: x["score"], reverse=True)
    hits = [r for r in results if r["score"] > 0.75][:top_k]

    # Increment hit_count for returned records
    all_records_path = KB_BASE / topic / "records.json"
    all_records = json.loads(all_records_path.read_text())
    hit_ids = {r["id"] for r in hits}
    for r in all_records:
        if r["id"] in hit_ids:
            r["metadata"]["hit_count"] = r["metadata"].get("hit_count", 0) + 1
    all_records_path.write_text(json.dumps(all_records, ensure_ascii=False, indent=2))

    return hits
```

**Example calls:**

```python
# Search by source type
search_filtered("Finance", "passive investing", source_type="url")

# Search within a specific document
search_filtered("Finance", "risk adjusted return", doc_name="vanguard-guide")

# Only recently indexed content
search_filtered("Finance", "ETF comparison", after_date="2026-01-01")
```

---

## Chunking Long Documents

For documents longer than ~500 tokens, split before embedding:

```python
def chunk_text(text: str, chunk_size: int = 400, overlap: int = 50) -> list[str]:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunks.append(" ".join(words[i:i + chunk_size]))
        i += chunk_size - overlap
    return chunks

# Ingest a long document
chunks = chunk_text(long_text)
for i, chunk in enumerate(chunks):
    ingest(
        topic="Finance",
        text=chunk,
        doc_name="vanguard-guide",
        source_locator="https://example.com/vanguard-guide",
        chunk_idx=i,
        total_chunks=len(chunks),
    )
```

---

## Record Schema

See [`schema/record.example.json`](schema/record.example.json) for the full format.

Key fields:

| Field | Purpose |
|-------|---------|
| `id` | UUID — stable unique identifier |
| `content_hash` | sha256 of normalized text — dedup key |
| `text` | Full chunk text |
| `hit_count` | Incremented on every query hit. Triggers wiki promotion at >= 3. |
| `promoted_to_wiki` | True once a routing index page exists in System B |
| `embedding_model` | Track which model generated the embedding |
