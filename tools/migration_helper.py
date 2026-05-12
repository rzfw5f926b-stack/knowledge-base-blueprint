#!/usr/bin/env python3
"""
Migration Helper — System A (Vector DB) → System B (Routing Index)

用途：掃描 System A 中 hit_count >= 3 的文件，呼叫 LLM 合成路由索引頁，
      寫入 System B（wiki/{Topic}/），並將 records 標記為 promoted。

用法：
  python3 migration_helper.py --promote Finance          # 升級單一 Topic
  python3 migration_helper.py --promote-all              # 升級所有 Topic
  python3 migration_helper.py --promote Finance --dry-run  # 預覽
  python3 migration_helper.py --status                   # 顯示系統狀態
  python3 migration_helper.py --list-topics              # 列出可用 Topic
"""

import argparse
import json
import os
import re
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import ollama

BASE = Path(os.environ.get("KB_BASE", Path.home() / ".knowledge_base"))
WIKI_BASE = BASE / "wiki"
SYNTHESIS_MODEL = os.environ.get("SYNTHESIS_MODEL", "qwen3.5:9b")
HIT_THRESHOLD = int(os.environ.get("PROMOTE_THRESHOLD", "3"))


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_records(topic: str) -> list[dict]:
    path = BASE / topic / "records.json"
    if not path.exists():
        raise FileNotFoundError(f"找不到 {path}")
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "records" in data:
        return data["records"]
    raise ValueError(f"records.json 格式不符：{path}")


def save_records(topic: str, records: list[dict]):
    path = BASE / topic / "records.json"
    with open(path, "w") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Grouping
# ---------------------------------------------------------------------------

def group_by_doc_name(records: list[dict]) -> dict[str, list[dict]]:
    """Group records by doc_name. Records without doc_name are skipped."""
    groups = defaultdict(list)
    for r in records:
        doc_name = r.get("metadata", {}).get("doc_name")
        if doc_name:
            groups[doc_name].append(r)
    return dict(groups)


def eligible_groups(groups: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """Return only groups where at least one chunk has hit_count >= threshold."""
    result = {}
    for doc_name, chunks in groups.items():
        max_hits = max(c.get("metadata", {}).get("hit_count", 0) for c in chunks)
        if max_hits >= HIT_THRESHOLD:
            result[doc_name] = chunks
    return result


# ---------------------------------------------------------------------------
# LLM synthesis
# ---------------------------------------------------------------------------

def synthesize(chunks: list[dict], model: str = SYNTHESIS_MODEL) -> dict:
    """Call LLM to produce a routing index entry from all chunks of a document."""
    texts = []
    for i, chunk in enumerate(chunks):
        text = (chunk.get("text") or chunk.get("content") or "").strip()
        if text:
            texts.append(f"[Chunk {i + 1}]\n{text}")

    combined = "\n---\n".join(texts)

    prompt = f"""You are a knowledge base indexer. Given the following document chunks, write a brief routing index entry.

Output exactly this format (no extra text):
Title: <concise document title, 1–5 words>
Description: <2–3 sentences describing what this document covers and why it matters>
Topics: <comma-separated key topics a reader might search for>

Be concise. This is a routing index to help an AI decide whether to retrieve the full document.

Document chunks:
---
{combined}
---

Routing index entry:"""

    response = ollama.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.1},
    )

    raw = response["message"]["content"].strip()
    result = {"title": "", "description": "", "topics": []}

    for line in raw.splitlines():
        if line.startswith("Title:"):
            result["title"] = line[6:].strip()
        elif line.startswith("Description:"):
            result["description"] = line[12:].strip()
        elif line.startswith("Topics:"):
            result["topics"] = [t.strip() for t in line[7:].split(",") if t.strip()]

    return result


# ---------------------------------------------------------------------------
# Wiki page building
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    allowed = re.compile(r"[^一-鿿A-Za-z0-9-]")
    text = allowed.sub("-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")[:60] or f"doc-{uuid.uuid4().hex[:8]}"


def build_wiki_page(doc_name: str, synthesis: dict, chunks: list[dict], topic: str) -> str:
    title = synthesis.get("title") or doc_name.replace("-", " ").title()
    description = synthesis.get("description", "")
    topics = synthesis.get("topics", [])

    ids = [c.get("id", "") for c in chunks if c.get("id")]
    ids_yaml = "\n".join(f"  - {i}" for i in ids)
    topics_str = ", ".join(topics) if topics else "—"
    today = datetime.now().strftime("%Y-%m-%d")

    return f"""---
title: "{title}"
topic: {topic}
system_a_ids:
{ids_yaml}
promoted_at: {today}
status: active
---

# {title}

{description}

**Key topics:** {topics_str}

---
*Routing index — full content available in System A*
"""


# ---------------------------------------------------------------------------
# Promotion
# ---------------------------------------------------------------------------

def promote_topic(topic: str, dry_run: bool = False, model: str = SYNTHESIS_MODEL) -> int:
    """Promote eligible documents in a topic to System B routing index pages."""
    records = load_records(topic)
    groups = group_by_doc_name(records)
    candidates = eligible_groups(groups)

    if not candidates:
        print(f"  {topic}: 無符合條件的文件（hit_count < {HIT_THRESHOLD}）")
        return 0

    wiki_topic_dir = WIKI_BASE / topic
    if not dry_run:
        wiki_topic_dir.mkdir(parents=True, exist_ok=True)

    promoted = 0
    for doc_name, chunks in candidates.items():
        max_hits = max(c.get("metadata", {}).get("hit_count", 0) for c in chunks)
        print(f"  {'[預覽] ' if dry_run else ''}升級：{doc_name} "
              f"({len(chunks)} chunks, max hit_count={max_hits})")

        if dry_run:
            promoted += 1
            continue

        # Synthesize routing index
        synthesis = synthesize(chunks, model=model)
        wiki_content = build_wiki_page(doc_name, synthesis, chunks, topic)

        # Write wiki page (overwrite if exists)
        slug = slugify(doc_name)
        wiki_path = wiki_topic_dir / f"{slug}.md"
        wiki_path.write_text(wiki_content)

        # Mark records as promoted
        today = datetime.now().strftime("%Y-%m-%d")
        promoted_ids = {c.get("id") for c in chunks}
        for r in records:
            if r.get("id") in promoted_ids:
                r["metadata"]["promoted_to_wiki"] = True
                r["metadata"]["promoted_at"] = today

        promoted += 1

    if not dry_run and promoted > 0:
        save_records(topic, records)
        rebuild_tags(topic)

    return promoted


# ---------------------------------------------------------------------------
# Tag index
# ---------------------------------------------------------------------------

def rebuild_tags(topic: str):
    """Rebuild _tags.md for a topic from all routing index pages."""
    wiki_dir = WIKI_BASE / topic
    if not wiki_dir.exists():
        return

    tag_map = defaultdict(list)
    for f in sorted(wiki_dir.glob("*.md")):
        if f.name.startswith("_"):
            continue
        content = f.read_text()
        for line in content.splitlines():
            if line.startswith("**Key topics:**"):
                topics_str = line.replace("**Key topics:**", "").strip()
                for t in topics_str.split(","):
                    t = t.strip()
                    if t and t != "—":
                        tag_map[t].append(f.name)

    lines = [f"# {topic} — Tag Index", "", f"**Updated:** {datetime.now().strftime('%Y-%m-%d')}", "", "---", ""]
    for tag in sorted(tag_map):
        lines.append(f"### #{tag}")
        for fname in tag_map[tag]:
            lines.append(f"- [{fname.replace('.md', '')}]({fname})")
        lines.append("")

    (wiki_dir / "_tags.md").write_text("\n".join(lines))


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

def show_status():
    print("=== 知識庫系統狀態 ===\n")

    print("System A（records.json）：")
    for d in sorted(BASE.iterdir()):
        if not d.is_dir() or d.name.startswith(".") or d.name == "wiki":
            continue
        rec_path = d / "records.json"
        if not rec_path.exists():
            continue
        records = json.loads(rec_path.read_text())
        total = len(records)
        promoted = sum(1 for r in records if r.get("metadata", {}).get("promoted_to_wiki"))
        eligible = len(eligible_groups(group_by_doc_name(records)))
        print(f"  {d.name}: {total:,} records | {promoted} promoted | {eligible} eligible")

    print(f"\nSystem B（wiki/）：")
    if not WIKI_BASE.exists():
        print("  （尚未建立）")
    else:
        for d in sorted(WIKI_BASE.iterdir()):
            if not d.is_dir() or d.name.startswith("."):
                continue
            pages = len([f for f in d.glob("*.md") if not f.name.startswith("_")])
            print(f"  {d.name}: {pages} routing pages")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Migration Helper: System A → System B routing index")
    parser.add_argument("--promote", metavar="TOPIC", help="升級指定 Topic")
    parser.add_argument("--promote-all", action="store_true", help="升級所有 Topic")
    parser.add_argument("--dry-run", action="store_true", help="預覽模式，不寫入")
    parser.add_argument("--status", action="store_true", help="顯示系統狀態")
    parser.add_argument("--list-topics", action="store_true", help="列出可用 Topic")
    parser.add_argument("--model", default=SYNTHESIS_MODEL, help=f"合成模型（預設 {SYNTHESIS_MODEL}）")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    if args.list_topics:
        print("可用 Topic：")
        for d in sorted(BASE.iterdir()):
            if d.is_dir() and not d.name.startswith(".") and d.name != "wiki" and (d / "records.json").exists():
                print(f"  - {d.name}")
        return

    if args.promote_all:
        topics = [d.name for d in sorted(BASE.iterdir())
                  if d.is_dir() and not d.name.startswith(".") and d.name != "wiki"
                  and (d / "records.json").exists()]
        total = 0
        for topic in topics:
            print(f"\n[{topic}]")
            n = promote_topic(topic, dry_run=args.dry_run, model=args.model)
            total += n
        print(f"\n完成：共升級 {total} 份文件")
        return

    if args.promote:
        topic = args.promote
        print(f"{'[預覽] ' if args.dry_run else ''}升級 Topic：{topic}")
        n = promote_topic(topic, dry_run=args.dry_run, model=args.model)
        print(f"完成：{'預覽' if args.dry_run else '升級'} {n} 份文件")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
