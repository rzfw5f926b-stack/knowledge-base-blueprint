# SCHEMA.md v0.2 — Knowledge Base Maintenance Protocol

> **Version**: v0.2
> **Updated**: 2026-05-12
> **Owner**: human only — no agent may modify this file

---

## 0. Meta

This file is the shared protocol for all agents reading or writing to this knowledge base.

**Role of this file**: behavioral contract, not technical documentation. Technical details live in each System README.

**Changelog**:
- v0.2 (2026-05-12): Add promotion rule, hit_count tracking, LLM synthesis, UUID + content_hash schema
- v0.1 (2026-05-04): Initial version

---

## 1. System Positioning

### Storage Layer vs Retrieval Layer

| Dimension | Option A | Option B |
|-----------|----------|----------|
| **Storage** (how data is stored) | Raw (`records.json`) | Wiki (`wiki/{Topic}/*.md`) |
| **Retrieval** (how queries are answered) | System A (vector similarity) | System B (direct read / grep) |

System A runs entirely on Raw — it does not depend on System B.

### Core Principle

Raw is the entry point; Wiki is the derived output. Wiki can be rebuilt from Raw at any time.

```
All knowledge
     │
     ▼
records.json        ← immutable archive, source of truth
     │
     └── hit_count >= 3 → promote → wiki/{Topic}/<slug>.md
                                     (routing index only)
```

---

## 2. Write Permissions

### Agent Roles

| Role | Description |
|------|-------------|
| **Primary agent** | Main AI agent. Handles ingestion, promotion, and wiki maintenance. Orchestrates sub-agents. |
| **Sub-agent** | Spawned by the primary agent for a specific task. Inherits primary agent write permissions within its task scope. |
| **Read-only agent** | Queries the KB only. Cannot write to wiki files or modify records. |

### Permission Table

| Resource | Writers | Restriction |
|----------|---------|-------------|
| `records.json` | ingestion script | all agents read-only after write |
| `wiki/{Topic}/*.md` | primary agent, sub-agents, Claude Code | read-only agents cannot write |
| `log.md` | all agents | append only — existing lines must not be modified |
| `SCHEMA.md` | human owner | no agent may modify |
| `_summary.md` | human owner | LLM must not overwrite |

---

## 3. Directory Structure

```
$KB_BASE/
├── SCHEMA.md               ← this file (owner-only)
├── log.md                  ← append-only operation log
├── {Topic}/
│   └── records.json        ← raw layer, System A source of truth
└── wiki/
    └── {Topic}/
        ├── _summary.md     ← human-authored topic overview
        ├── _tags.md        ← agent-maintained tag index
        └── <doc-slug>.md   ← routing index pages (auto-promoted)
```

### `_summary.md` vs routing index pages

| File | Maintained by | Purpose |
|------|---------------|---------|
| `_summary.md` | human owner | Topic scope and boundaries. Agents read for context. Lint does not touch it. |
| `<doc-slug>.md` | agent (auto) | Routing index for a promoted document. Points back to System A record IDs. |

---

## 4. Record Schema

Every record in `records.json` must follow this shape:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "content_hash": "sha256(normalized_text)",
  "text": "full text of this chunk",
  "embedding": [0.383, -0.129, "... 768 floats"],
  "metadata": {
    "source_type": "url | file | note",
    "source_locator": "https://example.com/article",
    "source_fetched_at": "2026-05-12T12:00:00",
    "doc_name": "article-slug",
    "topic": "Finance",
    "indexed_at": "2026-05-12T12:00:00",
    "embedding_model": "nomic-embed-text-v2-moe:latest",
    "embedding_dim": 768,
    "chunk_idx": 0,
    "total_chunks": 3,
    "hit_count": 0,
    "promoted_to_wiki": false,
    "promoted_at": null
  }
}
```

### Field Definitions

| Field | Type | Purpose |
|-------|------|---------|
| `id` | UUID v4 | Stable unique identifier. Never changes even if content is updated. |
| `content_hash` | sha256 | Hash of normalized text. Used for deduplication and change detection. |
| `text` | string | Full chunk text. No truncation. |
| `embedding` | float[] | 768-dim vector. Tied to `embedding_model`. |
| `source_type` | enum | Origin of the content: `url`, `file`, `note` |
| `source_locator` | string | Re-fetchable location (URL or absolute file path) |
| `source_fetched_at` | ISO 8601 | When the source was retrieved |
| `doc_name` | string | Groups chunks from the same document. Used for promotion grouping. |
| `hit_count` | int | Number of times this record was returned in a query. Incremented by search functions. |
| `promoted_to_wiki` | bool | Whether this record's doc has a wiki routing page. |
| `promoted_at` | date or null | Date of wiki promotion. |
| `embedding_model` | string | Model used to generate the embedding. |
| `embedding_dim` | int | Embedding dimensions. Required for version compatibility checks. |

---

## 5. Promotion Rule

### Trigger

Any chunk whose `hit_count >= 3` triggers promotion for its entire `doc_name` group.

### Scope

ALL chunks sharing the same `doc_name` are included in the synthesis — not just the triggered chunk.

### Behavior

| Condition | Action |
|-----------|--------|
| `doc_name` is missing | Skip — do not promote |
| No existing wiki page | Create new routing index page |
| Wiki page already exists | Overwrite with fresh synthesis |
| Promotion complete | Set `promoted_to_wiki = true` and `promoted_at` on ALL chunks in the group |

### Synthesis Model

Default: `qwen3.5:9b` (local)

---

## 6. Wiki Routing Index Format

Every promoted wiki page must follow this format:

```yaml
---
title: "Document Title"
topic: TopicName
system_a_ids:
  - 550e8400-e29b-41d4-a716-446655440000
  - 7c9e6679-7425-40de-944b-e07fc1f90ae7
promoted_at: YYYY-MM-DD
status: active
---

# Document Title

2–3 sentence description of what this document covers and why it matters.

**Key topics:** topic1, topic2, topic3

---
*Routing index — full content available in System A*
```

---

## 7. Query Routing

**Ingest has no routing** — all data goes to `records.json`.
**Query routing only applies when answering questions.**

| Query type | Route | Fallback |
|------------|-------|---------|
| Exact name / known term ("what is X") | System B first | System A |
| Semantic / exploratory ("anything about X") | System A | widen to all topics |
| Comparison ("X vs Y") | System A | — |
| "Latest" / "recent" | web search | ingest result |
| Personal notes / past decisions | System B first | System A |

### Execution

**System B first:**
1. Check `wiki/{Topic}/_summary.md` and routing index pages
2. Found → read `system_a_ids`, fetch those records from System A for full content
3. Not found → fall through to System A vector search

**System A:**
1. Embed query with same model
2. Cosine similarity against `records.json`, threshold > 0.75
3. Increment `hit_count` on returned records

---

## 8. Maintenance

| Frequency | Task |
|-----------|------|
| Every ingest | Append to `log.md` |
| Every query | Increment `hit_count` on returned records |
| On promotion trigger | Run synthesis, write wiki page, update records |
| Weekly | Lint — check orphan pages, stale routing entries, dead system_a_ids |
| Quarterly | Review `_summary.md` files |

### log.md Format

```
## [YYYY-MM-DD HH:MM] ingest | <source> | <topic> | <N> chunks
## [YYYY-MM-DD] promote | <doc_name> | <topic> | <N> chunks → wiki
## [YYYY-MM-DD] lint | <topic> | <N> issues found
```

### Memory Dreaming Integration (optional — OpenClaw users)

If you use [OpenClaw Dreaming](https://docs.openclaw.ai/concepts/dreaming), keep its metrics separate:

| Metric | Where | Meaning |
|--------|-------|---------|
| `confidence` | wiki frontmatter | content quality |
| `hit_count` | records.json | query frequency (System A layer) |
| `recalls` | OpenClaw Dreaming | conversation memory frequency |

---

## 9. Reserved Extension Points (not implemented)

| Extension | Trigger |
|-----------|---------|
| SQLite + file lock | concurrent agents writing `hit_count` causes corruption |
| Embedding re-index | changing `embedding_model` — must re-embed all records |
| Semantic dedup on ingest | `content_hash` match → merge hit_count, skip re-embed |
| Typed relationships in wiki | wiki exceeds 50 pages |
| Hybrid search (BM25 + vector) | records exceed ~20,000 chunks |
