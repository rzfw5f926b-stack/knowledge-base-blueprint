# System B: Routing / Index Layer

A flat-file layer derived from System A. It keeps short summaries, topic maps, pointers, and optional distilled synthesis so the agent can route back to the right A-records quickly.

Inspired by [Andrej Karpathy's LLM Wiki approach](https://www.mindstudio.ai/blog/andrej-karpathy-llm-wiki-knowledge-base-claude-code), but adapted here as a lightweight routing layer rather than a second source of truth.

---

## Directory Structure

```
$KB_BASE/wiki/
├── _index.md                ← global index (AI-maintained)
└── {Topic}/
    ├── _summary.md          ← topic summary + file list (AI-maintained)
    ├── _tags.md             ← tag index (AI-maintained)
    └── article-slug.md      ← optional distilled page / pointer / synthesis
```

---

## File Naming

- Use kebab-case: `bitcoin-whitepaper-2008.md`
- Chinese titles are fine: `人工智慧革命.md`
- Max 60 characters
- No spaces — use hyphens

---

## File Format

See [`template/article_template.md`](template/article_template.md).

Every file starts with a small metadata header:

```markdown
# Title

**Topic:** TopicName
**Source:** System A record / source note
**Created:** YYYY-MM-DD

---

Content here. Keep it short when the file is serving as an index/pointer; use longer synthesis only when it is genuinely useful.
```

---

## Index Files

**`_summary.md`** — maintained automatically by `migration_helper.py` or by the agent after each write. Contains:
- Record count
- Last updated date
- Linked list of all articles in the topic

**`_tags.md`** — tag index linking tags to articles. Updated by the agent when adding articles.

**`_index.md`** (root level) — global overview of all topics. Rebuilt with:
```bash
python3 tools/migration_helper.py --rebuild-index
```

---

## Agent Instructions: How to Add a New Article

1. Write the file content following the template format
2. Choose a descriptive filename (kebab-case, max 60 chars)
3. Save to `$KB_BASE/wiki/{Topic}/{filename}.md`
4. Update `_summary.md`: increment count, add link to new file
5. Update `_tags.md` if the file has relevant tags
6. If this is a new topic, update `_index.md` as well

---

## When to Use System B vs System A

| Use System B when... | Use System A when... |
|---------------------|---------------------|
| You need routing / topic mapping | You need fuzzy/semantic search |
| You want a distilled pointer or synthesis | It's a bulk document dump |
| You want to navigate back to the source quickly | You need cross-document similarity |
| The item has hit the promotion threshold | The raw source must remain authoritative |
