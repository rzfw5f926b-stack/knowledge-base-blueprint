# SCHEMA.md v0.1 — Knowledge Base Maintenance Protocol

> **Version**: v0.1
> **Last updated**: 2026-05-04
> **Owner**: human only — no agent may modify this file

---

## 0. Meta

This file is the shared protocol for all agents writing to this knowledge base. Every agent that reads or writes to `knowledge_base/` must follow these rules.

**Role of this file**: behavioral contract, not technical documentation. Technical details live in each System README.

**Changelog**:
- v0.1 (2026-05-04): Initial version, integrates Karpathy LLM Wiki pattern with existing dual-system architecture

---

## 1. System Positioning

### Raw Layer vs Wiki Layer

| Layer | Location | Role | Writer |
|-------|----------|------|--------|
| Raw | `<Topic>/records.json` | Ground truth — entry point for all knowledge | ingestion script only |
| Wiki | `concepts/`, `entities/`, `<Topic>/...` | Derived from raw — human-readable crystallization | primary agent, Claude Code |

**Core principle**: Raw is the entry point; Wiki is the derived output. Wiki can be rebuilt from Raw; the reverse is not true.

### Storage Layer vs Retrieval Layer

These are two orthogonal dimensions. Don't conflate them:

| Dimension | Option A | Option B |
|-----------|----------|----------|
| **Storage** (how data is stored) | Raw (`records.json`) | Wiki (`*.md`) |
| **Retrieval** (how queries are answered) | System A (vector similarity) | System B (grep + index) |

System A runs entirely on Raw — it does not depend on the Wiki layer.

---

## 2. Write Permissions

### Agent Roles

| Role | Description |
|------|-------------|
| **Primary agent** | The main AI agent. Responsible for ingestion, crystallization, and wiki maintenance. In a multi-agent setup, this is the orchestrator. |
| **Sub-agent** | Any agent spawned by the primary agent for a specific task. Inherits the primary agent's write permissions within the scope of its task. |
| **Read-only agent** | An agent that queries the KB but must not write to wiki files or modify records. Useful for agents that only need to answer questions. |

### Permission Table

| Resource | Writers | Restriction |
|----------|---------|-------------|
| `records.json` | ingestion script | all agents read-only |
| `wiki/*.md` (incl. `concepts/`, `entities/`) | primary agent, sub-agents, Claude Code | read-only agents cannot write |
| `log.md` | all agents | append only — existing lines must not be modified |
| `SCHEMA.md` | human owner | no agent may modify |
| `_summary.md` | human owner | LLM must not overwrite — human-authored |

---

## 3. Directory Structure

```
knowledge_base/
├── SCHEMA.md               ← this file (owner-only)
├── log.md                  ← append-only operation log
├── concepts/               ← cross-topic abstractions, methods, principles
│   └── RAG.md
├── entities/               ← cross-topic tools, products, companies, people
│   └── Tailscale.md
└── <Topic>/
    ├── records.json        ← raw layer (ingestion script writes here)
    ├── _summary.md         ← owner-authored topic overview (LLM must not overwrite)
    ├── index.md            ← LLM-maintained directory of wiki pages
    ├── sources/            ← source summaries for this topic
    │   └── <source-slug>.md
    └── entities/           ← topic-specific entities
        └── <Entity>.md
```

### `_summary.md` vs `index.md`

| File | Maintained by | Purpose |
|------|---------------|---------|
| `_summary.md` | human owner | Describes topic scope, goals, and boundaries. Agents read it to understand context. Lint does not touch it. |
| `index.md` | primary agent (auto) | Directory listing of all wiki pages in this topic. Updated after every page creation. |

---

## 4. Frontmatter Specification

All wiki pages (`concepts/`, `entities/`, `sources/`) must begin with:

```yaml
---
title: <page name>
type: entity | concept
sources: [<source_slug>, ...]
last_confirmed: YYYY-MM-DD
confidence: low | medium | high
supersedes: []
superseded_by: ""
status: active | stale | redirected
---
```

### Confidence Rules

| Condition | Value |
|-----------|-------|
| 1 source supports this | `low` |
| 2–3 sources support this | `medium` |
| 4+ sources, at least one confirmed within the last 30 days | `high` |

> Confidence is calculated from raw sources only — wiki cross-references do not count (prevents self-reinforcing loops).

### Status: Three Valid Values

| Value | Meaning |
|-------|---------|
| `active` | Normal (default) |
| `stale` | Superseded — information is outdated |
| `redirected` | Stub left behind after promoting to top-level |

**Do not use** deprecated, outdated, archived, or other synonyms.

### `entities/` vs `concepts/`: Decision Rule

- **`entities/`**: specific, nameable things — people, products, companies, tools, places
- **`concepts/`**: abstract methods, principles, patterns

**Test**: "Can this be owned or developed by a specific company or person?"
- Yes → `entities/`
- No → `concepts/`

### Memory Dreaming Integration (optional — OpenClaw users)

If you use [OpenClaw Dreaming](https://docs.openclaw.ai/concepts/dreaming), which automatically memorizes conversation information and tracks how often each memory is recalled, keep its metrics separate from wiki frontmatter:

| Metric | Where it lives | Why |
|--------|---------------|-----|
| `confidence` | wiki frontmatter | content quality — how many sources support this |
| `recalls` (retrieval frequency) | OpenClaw Dreaming | usage metric — how often this memory was accessed |

These are orthogonal: high confidence + low recalls = solid but rarely needed knowledge (normal). Mixing them in the same metadata makes lint decisions ambiguous.

If you don't use OpenClaw, ignore this section — the wiki frontmatter spec works independently.

---

## 5. Ingest Flow

All new data goes directly into `<Topic>/records.json`. **No routing at ingest time.**

> Ingest what you find. Crystallization into wiki pages happens later (see §6).

### log.md Format

Every ingest operation must append one line:

```
## [YYYY-MM-DD HH:MM] ingest | <source> | <topic> | <N> chunks
```

### Command Modes

```
Default (90% of cases):
  "ingest <URL or file> [into <topic>]"
  → writes records.json + log.md, does not touch wiki

Batch:
  "batch ingest the following list [into <topic>]"
  → processes each item, one log entry per item

Immediate crystallize:
  "ingest <URL>, crystallize immediately"
  → runs partial lint + crystallization for this topic after ingest

Rebuild:
  "rebuild <topic> wiki"
  → does not modify records.json; clears wiki/* and re-crystallizes from raw
```

---

## 6. Wiki Crystallization

**Default**: periodic lint batch (primary) + query-triggered gap-fill (secondary)
**Not done**: synchronous crystallization on ingest (token cost is 5–10× higher)

> Exception: when the user explicitly requests immediate crystallization.

### Pre-Creation Search Order

Before creating any new wiki page, search these three locations in order:

1. Top-level `concepts/`
2. Target topic's `entities/`
3. Legacy files at the topic root (read-only — do not write here)

Only create a new page if all three searches return nothing.

---

## 6.5. Supersession

When new information replaces old:

1. New page frontmatter: add `supersedes: [<old page>]`
2. Old page frontmatter: add `superseded_by: <new page>` + `status: stale`
3. Append to log.md: `## [date] supersede | <new> → <old> | <reason>`
4. **Do not delete the old page** — preserve historical context

---

## 6.6. Cross-Topic Promotion

### Trigger Conditions (any one is sufficient)

a. A second topic needs to reference an existing page in another topic's `entities/`
b. Agent finds the term already exists in another topic while building a new page
c. Lint finds the same page name in multiple topics

### Automatic vs Manual Threshold

- Conditions a, b → agent handles automatically
- Condition c → lint flags for human review
- **Inbound links ≤ 3 → automatic promotion**; > 3 → requires human confirmation

### Steps

1. Create the new page under `concepts/` or top-level `entities/`
2. New page frontmatter: add `redirected_from: [<old path>]`
3. Old location: leave a redirect stub with `redirect_to` + `status: redirected`
4. log.md: `## [date] promote | <old path> → <new path> | reason: ...`

---

## 7. Query Routing

**Query-side routing only** — ingest has no routing.

| Query type | Route | Reason |
|------------|-------|--------|
| Exact name, acronym, title ("what is X") | System B first | named concept → wiki |
| Comparison / relationship ("how does X differ from Y") | System A | semantic |
| Vague / exploratory ("anything about X") | System A | semantic |
| "Latest", "recent", "when did" | web search | KB does not track time-sensitive data |
| Personal notes, past decisions, architecture choices | System B first | structured knowledge → wiki |

### Execution Order

**System B first**:
1. Scan `<topic>/index.md` to check if the topic exists
2. Found → read directly
3. Not found → fall through to System A

**System A**:
1. Embed the query with the same model
2. Run cosine similarity against `<topic>/records.json`
3. Return top results with score > 0.75

---

## 8. Lint

**Frequency**: weekly, or after any large-scale ingest

**Checklist**:
- [ ] Orphan pages (wiki pages not referenced by any other page)
- [ ] Dead links (`[[xxx]]` pointing to non-existent pages)
- [ ] Pending supersessions (new info ingested but old page not marked stale)
- [ ] Uncrystallized raw content (recent ingests without wiki pages)
- [ ] Stale references (source updated but wiki still cites old version)
- [ ] Cross-topic promotion candidates (same page name in multiple topics)

**Seven error mechanisms** (rotate — cover 1–2 per week, full cycle every 3 weeks):

| Mechanism | Prevention |
|-----------|-----------|
| Over-interpretation | Spot-check 3–5 pages against raw |
| Temporal statements frozen in time | Review `last_confirmed`-old pages with `high` confidence |
| Conflict smoothing | Check that `supersede` log entries are justified |
| Context loss from chunking | Verify new crystallized pages cite full context |
| Entity ambiguity | Check near-duplicate page names for incorrectly merged entities |
| Self-referencing loops | Confidence counted from raw sources only, not wiki links |
| Rule drift | Audit frontmatter against this SCHEMA |

---

## 9. Reserved Extension Points (not implemented)

| Extension | Trigger |
|-----------|---------|
| Typed relationships (`derived_from::`, `contradicts::`) | wiki exceeds 50 pages and link types need classification |
| Hybrid search (BM25 + vector + graph) | `records.json` exceeds ~20,000 chunks |
| Auto-crystallize hooks | when periodic lint becomes too slow |
| Chunk-level citations `[[sources/<slug>#chunk-<n>]]` | when paragraph-level traceability is needed |
| `last_verified: YYYY-MM-DD` frontmatter field | for time-sensitive topics (e.g. Finance) |
| Per-topic sub-index (multiple `index.md` files) | wiki exceeds 100 pages |
| Raw layer versioning | when tracking the same source at different points in time |

---

## Log Format Reference

```
## [YYYY-MM-DD HH:MM] ingest | <source> | <topic> | <N> chunks
## [YYYY-MM-DD] crystallize | <topic> | <N> pages written
## [YYYY-MM-DD] supersede | <new page> → <old page> | <reason>
## [YYYY-MM-DD] promote | <old path> → <new path> | reason: ...
## [YYYY-MM-DD] conflict | <page A> vs <page B> | <description>
## [YYYY-MM-DD] lint | <topic> | <N> issues found
```
