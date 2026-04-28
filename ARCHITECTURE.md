# Dual Knowledge Base System — Architecture

## System Overview

```
Knowledge Input
       │
       ▼
 Classification Layer
       │
  ┌────┴────────────────────────────┐
  │                                 │
  ▼                                 ▼
System A                        System B
Vector DB                     Markdown Wiki
records.json                   wiki/*.md
(semantic search)             (direct lookup)
```

---

## System A: Vector Database

**Location:** `$KB_BASE/{Topic}/records.json`  
**Embedding model:** `nomic-embed-text-v2-moe:latest` (768 dimensions)  
**Query method:** Cosine similarity, full scan (acceptable up to ~5K records)

**When to use:**
- Bulk document ingestion (entire documentation sites, books, PDFs)
- Semantic similarity search — finding concepts you can't name exactly
- Cross-domain concept matching

**Record schema:** See `system-a-vector-db/schema/record.example.json`

---

## System B: Markdown Wiki

**Location:** `$KB_BASE/wiki/{Topic}/*.md`  
**Query method:** Direct file read / grep — zero embedding cost  
**Maintained by:** AI agent (LLM writes and updates files directly)

**When to use:**
- Precise named concepts, definitions, personal experience
- System architecture decisions
- Reference material that humans also need to read

**File format:** See `system-b-wiki/README.md`

---

## Classification Decision Tree

```
New document arrives
    │
    ├─ Is this a bulk ingestion? (entire docs site, book, data dump)
    │   └─ YES → System A (chunk + embed)
    │
    ├─ Will it be found via semantic similarity?
    │   └─ YES → System A
    │
    └─ Is it a named concept, definition, or personal note?
        └─ YES → System B (write .md + update _summary.md)
```

---

## Query Routing Strategy

| Query Type | Route | Reason |
|------------|-------|--------|
| Exact keyword, named concept | System B first | Fast, zero cost |
| Complex question, comparison | System A | Embedding match is stronger |
| Exploratory / uncertain | Both | Full coverage |

---

## Maintenance Schedule

| Frequency | Task |
|-----------|------|
| Every write | Update `_summary.md` and `_tags.md` in the affected topic |
| Quarterly | Review `_summary.md` files — condense if too long |
| Annually | Full restructure of all `_summary.md` files |

---

## Migration: System A → System B

When a topic's knowledge matures and needs human-readable organization:

```bash
python3 tools/migration_helper.py --topic TopicName
```

The tool converts `records.json` entries into individual `.md` files and updates the wiki index automatically.

---

## Scaling Path

| Record Count | Recommendation |
|-------------|---------------|
| < 5,000 | NumPy full scan — simple, no dependencies |
| 5,000–50,000 | sqlite-vec with HNSW index |
| > 50,000 | Qdrant or similar vector DB service |
