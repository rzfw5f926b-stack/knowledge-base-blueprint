# Dual Knowledge Base System Blueprint

A self-contained blueprint for building an AI-powered dual knowledge base:
- **System A** — Vector DB, source of truth
- **System B** — routing / index layer, derived from A

Any AI agent can read this repo and build the same system from scratch.

---

## Why a Dual System?

| Scenario | Route to |
|----------|----------|
| Bulk document ingestion (entire docs site, PDFs) | System A |
| Semantic similarity search ("find concepts related to X") | System A |
| Precise keyword lookup, named concepts, routing | System B |
| Exploratory / uncertain queries | Both |

**System A** is the canonical archive.  
**System B** helps the agent get back to the right A-records fast.

---

## Architecture

```
New document arrives
        │
        ▼
  Ingest / Classify
        │
        ▼
System A
Vector DB (source of truth)
        │
        └── promotion / synthesis ──► System B
                                      Routing / Index Layer
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full decision tree and query routing strategy.

See [SCHEMA.md](SCHEMA.md) for the authoritative record/file schema and promotion rules.

---

## Prerequisites

```bash
# 1. Ollama (local LLM + embedding runtime)
curl -fsSL https://ollama.com/install.sh | sh
ollama pull nomic-embed-text-v2-moe   # embedding model (768-dim)

# 2. Python 3.10+
pip install ollama   # for embedding generation

# 3. (Optional) Docker — for document parsing
docker run -d --name tika -p 9998:9998 apache/tika:latest-full
```

---

## Quick Setup

### System A — Vector DB

```bash
mkdir -p ~/.knowledge_base/MyTopic
# records.json starts as an empty array: []
echo "[]" > ~/.knowledge_base/MyTopic/records.json
```

See [system-a-vector-db/README.md](system-a-vector-db/README.md) for how to ingest and query documents.

### System B — Markdown Wiki

```bash
mkdir -p ~/.knowledge_base/wiki/MyTopic
touch ~/.knowledge_base/wiki/MyTopic/_summary.md
touch ~/.knowledge_base/wiki/MyTopic/_tags.md
```

See [system-b-wiki/README.md](system-b-wiki/README.md) for file format and naming conventions.

### Promotion (A → B)

```bash
export KB_BASE=~/.knowledge_base
python3 tools/migration_helper.py --status          # view current state
python3 tools/migration_helper.py --topic MyTopic   # migrate a topic to wiki
```

Promotion is automatic in the final design when a record's `hit_count >= 3`.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KB_BASE` | `~/.knowledge_base` | Root directory of the knowledge base |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama API endpoint |
| `EMBED_MODEL` | `nomic-embed-text-v2-moe:latest` | Embedding model name |

---

## Repository Structure

```
knowledge-base-blueprint/
├── README.md                        ← You are here
├── ARCHITECTURE.md                  ← Full system design
├── system-a-vector-db/
│   ├── README.md                    ← Setup, ingestion, query guide
│   └── schema/
│       └── record.example.json      ← Record format reference
├── system-b-wiki/
│   ├── README.md                    ← Wiki format and conventions
│   └── template/
│       ├── article_template.md
│       ├── _summary_template.md
│       └── _tags_template.md
└── tools/
    └── migration_helper.py          ← System A → B migration tool
```

---

## Future Upgrade Path

When System A grows beyond ~5,000 records, linear scan becomes slow. Upgrade to [sqlite-vec](https://github.com/asg017/sqlite-vec):

```bash
pip install sqlite-vec
```

Replace the full-scan loop with:
```sql
SELECT id, vec_distance_cosine(embedding, ?) AS dist
FROM knowledge_vectors ORDER BY dist LIMIT 10
```

No change to the record schema or wiki format required.
