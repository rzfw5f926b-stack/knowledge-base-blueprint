# System B: Routing / Index Layer

A flat-file routing index automatically promoted from System A. No database, no manual curation — pages are synthesized by an LLM when a document's `hit_count` reaches the promotion threshold.

**System B does not store full content.** It stores routing index pages that point back to System A record IDs. When an agent needs the full content, it fetches from System A using `system_a_ids`.

---

## Directory Structure

```
$KB_BASE/
└── wiki/
    └── {Topic}/
        ├── _summary.md     ← human-authored topic overview (do not overwrite)
        ├── _tags.md        ← agent-maintained tag index
        └── <doc-slug>.md   ← routing index pages (auto-promoted)
```

---

## File Naming

- Use kebab-case for doc slugs: `vanguard-etf-guide.md`
- Derived from `doc_name` in System A metadata
- Max 60 characters, no spaces

---

## Routing Index Page Format

See [`template/article_template.md`](template/article_template.md).

Every routing index page must follow this format:

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

## Index Files

**`_summary.md`** — written by the **human owner**. Describes topic scope, purpose, and boundaries. Agents read it for context but must not overwrite it.

**`_tags.md`** — maintained by the **agent**. Tag index linking key topics to routing pages. Updated after every promotion.

---

## How Routing Pages Are Created

Routing pages are created automatically by `tools/migration_helper.py --promote`:

1. Scan all topics for records with `hit_count >= 3`
2. Group by `doc_name` — skip records with no `doc_name`
3. Feed ALL chunks from the same `doc_name` to `qwen3.5:9b`
4. LLM outputs: title, 2–3 sentence description, key topics
5. Write routing page with `system_a_ids` pointing to all chunk UUIDs
6. Mark all chunks: `promoted_to_wiki = true`, `promoted_at = today`
7. Overwrite if a page for this `doc_name` already exists

---

## How to Use a Routing Page

When System B returns a match:

```python
import json
from pathlib import Path

wiki_page = Path("~/.knowledge_base/wiki/Finance/vanguard-etf-guide.md").read_text()

# Parse system_a_ids from frontmatter (no external dependencies)
system_a_ids = []
in_frontmatter = False
for line in wiki_page.splitlines():
    if line.strip() == "---":
        in_frontmatter = not in_frontmatter
        continue
    if in_frontmatter and line.strip().startswith("- "):
        system_a_ids.append(line.strip()[2:])

# Fetch full content from System A
records = json.loads(Path("~/.knowledge_base/Finance/records.json").read_text())
full_chunks = [r for r in records if r["id"] in system_a_ids]
```

---

## When System B Helps (and When It Doesn't)

| Use System B when... | Use System A when... |
|---------------------|---------------------|
| Query matches a known document title | Exploratory / fuzzy query |
| You want zero embedding cost | First time querying a topic |
| The document has been accessed 3+ times | Document was just ingested |
