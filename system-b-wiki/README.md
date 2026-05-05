# System B: Markdown Wiki

A flat-file wiki maintained by an AI agent. No database, no indexing — just markdown files that both humans and LLMs can read.

Inspired by [Andrej Karpathy's LLM Wiki approach](https://www.mindstudio.ai/blog/andrej-karpathy-llm-wiki-knowledge-base-claude-code): optimize for LLM reading, not human browsing.

**Wiki pages are crystallized from the raw layer (`records.json`), not written directly.** See [SCHEMA.md](../SCHEMA.md) for the full maintenance protocol.

---

## Directory Structure

```
$KB_BASE/
├── SCHEMA.md               ← agent behavior protocol
├── log.md                  ← append-only operation log
├── concepts/               ← cross-topic abstractions and principles
│   └── RAG.md
├── entities/               ← cross-topic tools, products, companies
│   └── Tailscale.md
└── <Topic>/
    ├── records.json        ← raw layer (System A — do not modify)
    ├── _summary.md         ← human-authored topic overview
    ├── index.md            ← LLM-maintained page directory
    ├── sources/            ← one page per ingested source
    │   └── <source-slug>.md
    └── entities/           ← topic-specific entities
        └── <Entity>.md
```

---

## File Naming

- Use PascalCase for entities and concepts: `VectorEmbedding.md`, `Tailscale.md`
- Use kebab-case for source slugs: `openai-gpt4-technical-report.md`
- Chinese titles are fine: `人工智慧革命.md`
- Max 60 characters, no spaces

---

## Article Format

See [`template/article_template.md`](template/article_template.md).

Every wiki page starts with YAML frontmatter:

```yaml
---
title: "Page Title"
type: entity | concept
sources: [source-slug-1, source-slug-2]
last_confirmed: YYYY-MM-DD
confidence: low | medium | high
supersedes: []
superseded_by: ""
status: active
---
```

**`confidence` rules:**
- `low` — 1 source supports this
- `medium` — 2–3 sources support this
- `high` — 4+ sources, at least one confirmed within the last 30 days

**`status` values:** `active` / `stale` / `redirected` — no other values allowed

---

## Index Files

**`_summary.md`** — written by the **human owner**. Describes the topic's scope, purpose, and boundaries. Agents read it for context but must not overwrite it.

**`index.md`** — maintained by the **agent** after each wiki write. Contains a linked list of all pages in the topic with one-line descriptions.

---

## Agent Instructions: How to Add a New Page

1. **Search first** — before creating, grep these three locations in order:
   - Top-level `concepts/`
   - Target topic's `entities/`
   - Legacy files at the topic root (read-only — do not write here)

   Only create if nothing is found in all three.

2. Determine `type`: entity or concept?
   - **entity** — specific, nameable thing (person, product, company, tool, place)
   - **concept** — abstract method, principle, or pattern
   - Test: "Can this be owned or developed by a specific company?" Yes → entity; No → concept

3. Write the page with correct frontmatter, save to the appropriate directory

4. Update `index.md` — add a link and one-line description

5. Append to `log.md`:
   ```
   ## [YYYY-MM-DD] crystallize | <topic> | 1 page written
   ```

6. If this page supersedes an older one, follow SCHEMA.md §6.5

---

## When to Use System B vs System A

| Use System B when... | Use System A when... |
|---------------------|---------------------|
| The concept has a clear name | You need fuzzy/semantic search |
| It's a mature, verified piece of knowledge | It's raw or recently ingested |
| Humans also need to read it | It's a bulk document dump |
| You want instant lookup (no embedding cost) | You need cross-document similarity |
