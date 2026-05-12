# Dual Knowledge Base System — Architecture

## Core Concepts

### Storage Layer vs Retrieval Layer

| Dimension | Option A | Option B |
|-----------|----------|----------|
| **Storage** | Raw (`records.json`) | Wiki (`wiki/{Topic}/*.md`) |
| **Retrieval** | System A (vector search) | System B (direct read / grep) |

System A runs entirely on Raw. System B is a derived routing layer — it does not replace System A.

### Data Flow

```
New document
     │
     ▼
records.json            ← immutable, source of truth
     │
     │  every query → hit_count + 1
     │
     └── hit_count >= 3 ──► wiki/{Topic}/<slug>.md
                             (routing index, LLM-synthesized)
```

---

## System A: Vector Database

**Location:** `$KB_BASE/{Topic}/records.json`
**Role:** immutable archive and semantic search layer
**Embedding model:** `nomic-embed-text-v2-moe:latest` (768 dimensions)
**Query method:** cosine similarity

**Rules:**
- All new knowledge enters here first
- Records are never deleted
- `hit_count` is incremented on every query hit
- Provenance is preserved via `id` (UUID) and `content_hash`

**Record schema:** see `SCHEMA.md §4` and `system-a-vector-db/schema/record.example.json`

---

## System B: Routing / Index Layer

**Location:** `$KB_BASE/wiki/{Topic}/*.md`
**Role:** fast routing index for frequently-accessed documents
**Query method:** direct file read / grep — zero embedding cost
**Maintained by:** AI agent (auto-promoted from System A)

**What a routing index page contains:**
- 2–3 sentence description of the document
- Key topics for discoverability
- `system_a_ids` — UUIDs pointing back to the original System A records

**What it does NOT contain:** full document content (always in System A)

```
$KB_BASE/
├── {Topic}/
│   └── records.json
└── wiki/
    └── {Topic}/
        ├── _summary.md     ← human-authored
        ├── _tags.md        ← agent-maintained
        └── <doc-slug>.md   ← routing index (auto-promoted)
```

---

## Promotion Rule

```
System A record queried
    │
    ├── hit_count < 3 → stays in A only
    │
    └── hit_count >= 3 → promotion triggered
            │
            ├── find ALL chunks with same doc_name
            ├── doc_name missing → skip
            ├── feed all chunks to qwen3.5:9b
            ├── synthesize routing index page
            └── write to wiki/{Topic}/<slug>.md
                mark all chunks: promoted_to_wiki = true
```

Promotion overwrites any existing wiki page for the same `doc_name`.

---

## Query Routing

### Step 1 — Classify

| Signal | Route |
|--------|-------|
| Exact name / known term | System B first |
| Semantic / exploratory | System A first |
| Comparison ("X vs Y") | System A |
| "Latest" / "recent" | Web search |
| Personal notes / decisions | System B first |

### Step 2 — Execute

**System B first:**
1. Scan `wiki/{Topic}/` for matching routing pages
2. Found → read `system_a_ids`, fetch those records from System A for full content
3. Not found → fall through to System A

**System A:**
1. Embed query (`nomic-embed-text-v2-moe:latest`)
2. Cosine similarity on `records.json`, threshold > 0.75
3. Return top 3–5 results, increment `hit_count` on each

### Step 3 — No results

```
System B: miss → fall through to System A
System A: miss → widen to all topics
          still miss → "Not found. Search web and add to KB?"
```

---

## Maintenance

| Frequency | Task |
|-----------|------|
| Every ingest | Append to `log.md` |
| Every query | Increment `hit_count` on returned records |
| On promotion | Write wiki page, mark records as promoted |
| Weekly | Lint — orphan wiki pages, dead `system_a_ids`, stale entries |
| Quarterly | Review `_summary.md` topic overviews |

---

## Scaling Path

| Record Count | Recommendation |
|-------------|---------------|
| < 5,000 | NumPy full scan |
| 5,000–50,000 | sqlite-vec with HNSW index |
| > 50,000 | Add cross-encoder reranker (e.g. `ms-marco-MiniLM`): retrieve top-20, rerank to top-5 |
| > 100,000 | Qdrant or similar dedicated vector DB |

> When `hit_count` updates become a concurrency bottleneck (multiple agents writing simultaneously), migrate `records.json` to SQLite with file-level locking.
