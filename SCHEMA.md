# Knowledge Base Schema

This document is the authoritative schema for the dual knowledge base system.

## 1. System A — Vector DB (Source of Truth)

- Purpose: store all raw knowledge first.
- Storage: `$KB_BASE/{Topic}/records.json`
- Behavior:
  - append-only
  - never delete promoted records
  - preserve provenance and traceability
  - track query usage via `metadata.hit_count`

### Record shape

```json
{
  "id": "uuid",
  "text": "original or chunk text",
  "metadata": {
    "topic": "Finance",
    "source": "wiki/Finance/example.md",
    "title": "Example title",
    "char_count": 1234,
    "created_at": "2026-05-12T12:00:00",
    "hit_count": 0,
    "promoted_to_wiki": false
  }
}
```

## 2. System B — Wiki / Routing Layer

- Purpose: fast routing, distilled notes, and high-value synthesis.
- Storage: `$KB_BASE/wiki/{Topic}/*.md`
- Behavior:
  - human/LLM readable
  - may contain summaries, topic maps, pointers, and distilled conclusions
  - should not replace System A as source of truth

### File conventions

- Use kebab-case filenames
- Keep `_summary.md` and `_tags.md` in each topic directory
- Add one article per concept when promotion is justified

## 3. Promotion Rule

- Default trigger: `metadata.hit_count >= 3`
- Promotion is automatic
- System A record is preserved
- System B receives a distilled wiki entry or routing page
- After promotion, set:
  - `metadata.promoted_to_wiki = true`
  - `metadata.promoted_at = YYYY-MM-DD`

## 4. Query Routing

1. Exact names / known terms → System B first
2. Semantic / exploratory questions → System A first
3. Ambiguous questions → search both

## 5. Ingestion Rule

- All new knowledge enters System A first.
- System B is secondary and derived.
- Raw sources are immutable once ingested.

## 6. Maintenance Rule

- System A: preserve all records.
- System B: keep concise and navigable.
- Update summaries and tags whenever System B changes.

