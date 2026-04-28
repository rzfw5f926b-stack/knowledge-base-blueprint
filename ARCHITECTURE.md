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

## Query Routing: AI Agent Decision Algorithm

When a user asks a question, follow this algorithm to decide where to search:

### Step 1 — Classify the query

| Signal in the question | Route |
|------------------------|-------|
| Exact name, acronym, or title ("what is X", "tell me about Y") | System B first |
| Comparison or relationship ("how does X differ from Y") | System A |
| Vague / exploratory ("something about financial risk") | System A |
| "Latest", "recent", "when did" | Neither — use web search |
| Personal notes, past decisions, architecture choices | System B |

### Step 2 — Execute the search

**If System B first:**
1. Scan `$KB_BASE/wiki/{relevant_topic}/_summary.md` to see if the topic exists
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

If you found the answer via web search (not KB), ask yourself:
- Is this knowledge stable and reusable?
- Would future queries benefit from having this stored?

If yes → ingest into System A (and optionally promote to System B via migration_helper).

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
