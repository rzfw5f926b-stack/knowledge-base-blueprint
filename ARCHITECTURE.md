# Dual Knowledge Base System — Architecture

## System Overview

```
Knowledge Input
       │
       ▼
 Ingest / Classify
       │
  ┌────┴────────────────────────────┐
  │                                 │
  ▼                                 ▼
System A                        System B
Vector DB                     Routing / Index Layer
source of truth               derived, optional synthesis
```

---

## System A: Vector Database

**Location:** `$KB_BASE/{Topic}/records.json`  
**Role:** source of truth / immutable archive  
**Embedding model:** `nomic-embed-text-v2-moe:latest` (768 dimensions)  
**Query method:** semantic similarity / vector search

**Rules:**
- all new knowledge lands here first
- preserve provenance and traceability
- never delete promoted records
- track usage with `metadata.hit_count`

**Record schema:** see `SCHEMA.md` and `system-a-vector-db/schema/record.example.json`

---

## System B: Routing / Index Layer

**Location:** `$KB_BASE/wiki/{Topic}/*.md`  
**Role:** fast routing, summaries, topic maps, and optional distilled synthesis  
**Query method:** direct file read / grep / simple index lookup  
**Maintained by:** AI agent

**Rules:**
- System B is derived from System A
- System B may contain only pointers, summaries, and high-value synthesis
- System B should stay lean and navigable

**File format:** see `SCHEMA.md` and `system-b-wiki/README.md`

---

## Promotion Rule

```
System A record queried
    │
    ├─ hit_count < 3 → keep in A only
    │
    └─ hit_count >= 3 → auto-promote to System B
```

**Promotion behavior:**
- automatic
- preserve System A record
- write/update System B entry
- mark metadata:
  - `promoted_to_wiki = true`
  - `promoted_at = YYYY-MM-DD`

---

## Query Routing

### Step 1 — Classify

| Signal | Route |
|--------|-------|
| Exact name / acronym / title | System B first |
| Exploratory / semantic / comparison | System A first |
| Ambiguous | Both |
| Latest / recent / current event | Web search |
| Personal notes / decisions | System B first |

### Step 2 — Execute

**System B first:**
1. read `_summary.md` / `_tags.md`
2. follow relevant links or pointers
3. if insufficient, fall through to System A

**System A first:**
1. semantic search across the relevant topic
2. take top results above threshold
3. use them as source material for the answer

### Step 3 — After answering

If the answer is stable and reusable:
- keep it in System A
- optionally auto-promote to System B when hit_count threshold is reached

---

## Maintenance

| Frequency | Task |
|-----------|------|
| Every write | Update source metadata / hit counts |
| On promotion | Write System B entry + update `_summary.md` / `_tags.md` |
| Periodic | Lint for stale links, duplicates, orphan pages |

---

## Scaling

| Record Count | Recommendation |
|-------------|---------------|
| < 5,000 | full scan is fine |
| 5,000–50,000 | add index / sqlite-vec |
| > 50,000 | add reranker |
| > 100,000 | move to dedicated vector service |
