# Dual Knowledge Base System — Architecture

## Core Concepts

Before reading further, understand these two orthogonal dimensions:

### Storage Layer vs Retrieval Layer

| Dimension | Option A | Option B |
|-----------|----------|----------|
| **Storage** (how data is stored) | Raw (`records.json`) | Wiki (`*.md`) |
| **Retrieval** (how queries are answered) | System A (vector search) | System B (grep + index) |

**System A runs entirely on Raw.** It does not depend on the Wiki layer.

### Raw is the Entry Point — Wiki is the Derived Output

All new knowledge enters through `records.json`. Wiki pages are crystallized from Raw by an LLM agent — they are not a parallel entry point.

```
New document arrives
       │
       ▼
  records.json          ← always, no routing
  (raw layer)
       │
       ▼ (crystallization — periodic or on demand)
   wiki pages
  (derived layer)
```

This means:
- Wiki can always be rebuilt from Raw
- Ingest is fast — no LLM needed at write time
- Raw cannot be contaminated by wiki-side writes

---

## System Overview

```
Knowledge Input
       │
       ▼
 Raw Layer (records.json)
       │
  ┌────┴────────────────────────────┐
  │                                 │
  ▼                                 ▼
System A                        System B
Vector DB                     Markdown Wiki
(semantic search on raw)      (crystallized from raw)
```

---

## System A: Vector Database

**Location:** `$KB_BASE/{Topic}/records.json`
**Embedding model:** `nomic-embed-text-v2-moe:latest` (768 dimensions)
**Query method:** Cosine similarity, full scan (acceptable up to ~5K records)

**Role in this architecture:** The retrieval interface for the raw layer. Handles semantic queries that cannot be answered by exact-match wiki lookup.

**Record schema:** See `system-a-vector-db/schema/record.example.json`

---

## System B: Markdown Wiki

**Location:** `$KB_BASE/<Topic>/` (alongside raw data)
**Query method:** Direct file read / grep — zero embedding cost
**Maintained by:** AI agent (crystallized from raw, updated during lint)

**Directory structure:**

```
$KB_BASE/
├── SCHEMA.md               ← agent behavior protocol
├── log.md                  ← append-only operation log
├── concepts/               ← cross-topic abstractions and principles
├── entities/               ← cross-topic tools, products, companies
└── <Topic>/
    ├── records.json        ← raw layer (System A)
    ├── _summary.md         ← human-authored topic overview
    ├── index.md            ← LLM-maintained page directory
    ├── sources/            ← source summaries
    └── entities/           ← topic-specific entities
```

See `system-b-wiki/README.md` and `SCHEMA.md` for full conventions.

---

## Ingest Flow (no routing)

**All new data goes directly into `records.json`.** There is no classification at ingest time.

```
New document arrives
    │
    └─ records.json (always)
       └─ log.md (append ingest record)
```

Wiki crystallization happens separately — during periodic lint, or on explicit request.

> **Deprecated**: the old decision tree ("new document → choose System A or System B") conflated ingest routing with query routing, which caused the wiki to never grow organically. The correct model: ingest always goes to raw; **query routing** decides which system to search.

---

## Query Routing: Decision Algorithm

When a question arrives, follow this algorithm to decide where to search:

### Step 1 — Classify the query

| Signal in the question | Route |
|------------------------|-------|
| Exact name, acronym, or title ("what is X", "tell me about Y") | System B first |
| Comparison or relationship ("how does X differ from Y") | System A |
| Vague / exploratory ("something about financial risk") | System A |
| "Latest", "recent", "when did" | Neither — use web search |
| Personal notes, past decisions, architecture choices | System B first |

### Step 2 — Execute the search

**If System B first:**
1. Scan `$KB_BASE/<relevant_topic>/index.md` to see if the topic exists
2. If a matching file is listed, read it directly
3. If not found → fall through to System A

**If System A:**
1. Embed the query using the same model (`nomic-embed-text-v2-moe:latest`)
2. Run cosine similarity against the relevant topic's `records.json`
3. Take top 3–5 results above a score threshold (recommend: > 0.75)

**If both:**
1. Run System B lookup first (it's instant)
2. Run System A in parallel or immediately after
3. Merge results — prefer System B for definitions, System A for context

### Step 3 — Handle no results

```
System B: no match found
    └─ Fall through to System A automatically

System A: no results above threshold
    └─ Widen search to all topics (not just the assumed topic)
    └─ If still nothing → tell the user: "Not in the knowledge base.
       Do you want me to search the web and add this to the KB?"
```

### Step 4 — After answering, consider updating the KB

If you found the answer via web search (not KB), ask:
- Is this knowledge stable and reusable?
- Would future queries benefit from having this stored?

If yes → ingest into `records.json` (let lint crystallize it into the wiki later).

---

## Query Routing Examples

| User question | Decision | Reason |
|---------------|----------|--------|
| "What is the RIC rule?" | System B | Named regulation — likely in wiki |
| "How does VT ETF compare to QQQ?" | System A | Comparative, semantic |
| "What did I decide about the DB upgrade?" | System B | Personal decision log |
| "Find anything related to inflation hedging" | System A | Exploratory, semantic |
| "Summarize what we know about Ethereum" | Both | Named topic + may have depth in A |

---

## Maintenance Schedule

| Frequency | Task |
|-----------|------|
| Every ingest | Append to `log.md` |
| Every wiki write | Update `index.md` in the affected topic |
| Weekly | Run lint — check orphans, dead links, uncrystallized raw, stale pages |
| Quarterly | Review `_summary.md` files — update if topic scope has shifted |
| As needed | Cross-topic promotion when a page becomes referenced across topics |

See `SCHEMA.md §8` for the full lint checklist.

---

## Migration: System A → System B

When a topic's knowledge matures and needs human-readable organization:

```bash
python3 tools/migration_helper.py --topic TopicName
```

The tool converts `records.json` entries into source pages under `<Topic>/sources/` and rebuilds the topic `index.md`.

---

## Scaling Path

| Record Count | Recommendation |
|-------------|---------------|
| < 5,000 | NumPy full scan — simple, no dependencies |
| 5,000–50,000 | sqlite-vec with HNSW index |
| > 50,000 | Add cross-encoder reranker (e.g. `ms-marco-MiniLM`) after vector search: retrieve top-20, rerank to top-5 |
| > 100,000 | Qdrant or similar vector DB service |
