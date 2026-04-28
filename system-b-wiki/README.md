# System B: Markdown Wiki

A flat-file wiki maintained directly by an AI agent. No database, no indexing — just markdown files that both humans and LLMs can read.

Inspired by [Andrej Karpathy's LLM Wiki approach](https://www.mindstudio.ai/blog/andrej-karpathy-llm-wiki-knowledge-base-claude-code): optimize for LLM reading, not human browsing.

---

## Directory Structure

```
$KB_BASE/wiki/
├── _index.md                ← global index (AI-maintained)
└── {Topic}/
    ├── _summary.md          ← topic summary + file list (AI-maintained)
    ├── _tags.md             ← tag index (AI-maintained)
    └── article-slug.md      ← one article per concept
```

---

## File Naming

- Use kebab-case: `bitcoin-whitepaper-2008.md`
- Chinese titles are fine: `人工智慧革命.md`
- Max 60 characters
- No spaces — use hyphens

---

## Article Format

See [`template/article_template.md`](template/article_template.md).

Every article starts with a metadata header:

```markdown
# Article Title

**Topic:** TopicName
**Source:** https://example.com or "personal note"
**Created:** YYYY-MM-DD

---

Article content here...
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

1. Write the article content following the template format
2. Choose a descriptive filename (kebab-case, max 60 chars)
3. Save to `$KB_BASE/wiki/{Topic}/{filename}.md`
4. Update `_summary.md`: increment count, add link to new file
5. Update `_tags.md` if the article has relevant tags
6. If this is a new topic, update `_index.md` as well

---

## When to Use System B vs System A

| Use System B when... | Use System A when... |
|---------------------|---------------------|
| The concept has a clear name | You need fuzzy/semantic search |
| Humans also need to read it | It's a bulk document dump |
| It's a personal note or decision | You need cross-document similarity |
| You want instant lookup (no embedding cost) | The content is long-tail / archival |
