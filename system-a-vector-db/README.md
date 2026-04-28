# System A: Vector Database

Stores documents as text + 768-dimensional embeddings for semantic search.

---

## Directory Structure

```
$KB_BASE/
└── {Topic}/
    ├── records.json    ← all records for this topic
    └── manifest.json   ← topic metadata (optional)
```

---

## Ingesting a Document

```python
import json
import ollama
import hashlib
from pathlib import Path
from datetime import datetime

KB_BASE = Path.home() / ".knowledge_base"
EMBED_MODEL = "nomic-embed-text-v2-moe:latest"

def ingest(topic: str, text: str, source: str, doc_name: str):
    # Generate embedding
    resp = ollama.embed(model=EMBED_MODEL, input=text)
    embedding = resp["embeddings"][0]

    record = {
        "doc_id": hashlib.md5(text.encode()).hexdigest(),
        "content": text,
        "embedding": embedding,
        "metadata": {
            "source": source,
            "doc_name": doc_name,
            "topic": topic,
            "indexed_at": datetime.now().isoformat(),
            "model": EMBED_MODEL,
            "chunk_idx": 0,
            "total_chunks": 1,
        }
    }

    records_path = KB_BASE / topic / "records.json"
    records_path.parent.mkdir(parents=True, exist_ok=True)
    records = json.loads(records_path.read_text()) if records_path.exists() else []
    records.append(record)
    records_path.write_text(json.dumps(records, ensure_ascii=False, indent=2))
```

---

## Querying

```python
import json
import ollama
import numpy as np
from pathlib import Path

KB_BASE = Path.home() / ".knowledge_base"
EMBED_MODEL = "nomic-embed-text-v2-moe:latest"

def search(topic: str, query: str, top_k: int = 5) -> list[dict]:
    records_path = KB_BASE / topic / "records.json"
    records = json.loads(records_path.read_text())

    # Embed the query
    q_vec = np.array(ollama.embed(model=EMBED_MODEL, input=query)["embeddings"][0])

    # Cosine similarity (full scan)
    results = []
    for r in records:
        vec = np.array(r["embedding"])
        score = float(np.dot(q_vec, vec) / (np.linalg.norm(q_vec) * np.linalg.norm(vec)))
        results.append({"score": score, "content": r["content"], "metadata": r["metadata"]})

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]
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
        chunks.append(" ".join(words[i:i+chunk_size]))
        i += chunk_size - overlap
    return chunks
```

Ingest each chunk as a separate record with `chunk_idx` and `total_chunks` in metadata.

---

## Record Schema

See [`schema/record.example.json`](schema/record.example.json) for the full format.
