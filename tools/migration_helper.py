#!/usr/bin/env python3
"""
Migration Helper — Vector DB (System A) → Markdown Wiki (System B)

用途：將 Vector DB 內任何 Topic 的 records.json 轉換為 Wiki 格式的來源頁（sources/），
      並重建該 Topic 的 index.md。

用法：
  python3 migration_helper.py --topic Finance              # 遷移單一 Topic
  python3 migration_helper.py --topic Finance --dry-run    # 預覽（不寫入）
  python3 migration_helper.py --list-topics                # 列出所有可用 Topic
  python3 migration_helper.py --status                     # 顯示系統狀態
  python3 migration_helper.py --rebuild-index              # 重建所有 Topic 的 index.md
"""

import argparse
import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path

BASE = Path(os.environ.get("KB_BASE", Path.home() / ".knowledge_base"))
CONCEPTS_DIR = BASE / "concepts"
ENTITIES_DIR = BASE / "entities"


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


def slugify(text: str) -> str:
    """將標題轉換為 URL-safe 的 slug，保留中文、英文、數字"""
    allowed = re.compile(r'[^一-鿿A-Za-z0-9-]')
    text = allowed.sub('-', text)
    text = re.sub(r'-+', '-', text)
    result = text.strip('-')[:60]
    return result if result else f"source-{uuid.uuid4().hex[:8]}"


def extract_title(text: str, metadata: dict) -> str:
    """從文字內容或 metadata 猜測標題"""
    if text:
        first_line = text.strip().split("\n")[0][:60]
        if len(first_line) >= 10:
            cleaned = first_line.lstrip('#').lstrip('*').strip()
            if cleaned:
                return cleaned
    source = metadata.get("source", "")
    if source:
        path_part = source.rstrip("/").split("/")[-1]
        path_part = re.sub(r'\.(txt|md|html?|pdf|docx)$', '', path_part, flags=re.IGNORECASE)
        path_part = re.sub(r'^[\w]+---', '', path_part)
        if path_part and path_part not in ("", "index"):
            return path_part.replace("-", " ").replace("_", " ").strip()
    return "Untitled"


def extract_source_slug(metadata: dict) -> str:
    """從 metadata 取得或生成 source slug"""
    source = metadata.get("source", "")
    doc_name = metadata.get("doc_name", "")
    base = doc_name or source
    if base:
        slug = base.rstrip("/").split("/")[-1]
        slug = re.sub(r'\.(txt|md|html?|pdf|docx)$', '', slug, flags=re.IGNORECASE)
        slug = re.sub(r'[^\w-]', '-', slug)
        slug = re.sub(r'-+', '-', slug).strip('-')[:60]
        if slug:
            return slug
    return f"source-{uuid.uuid4().hex[:8]}"


def record_to_source_page(record: dict) -> tuple[str, str]:
    """將單筆記錄轉換為 sources/ 格式的頁面，返回 (slug, content)"""
    text = (record.get("content") or record.get("text") or "").strip()
    metadata = record.get("metadata", {})

    title = extract_title(text, metadata)
    slug = slugify(extract_source_slug(metadata))
    source_url = metadata.get("source", "unknown")
    indexed_at = metadata.get("indexed_at", datetime.now().isoformat())[:10]

    content = re.sub(r'<[^>]+>', '', text)
    content = re.sub(r'\n{3,}', '\n\n', content).strip()

    page = f"""---
title: "{title}"
type: concept
sources: ["{slug}"]
last_confirmed: {indexed_at}
confidence: low
supersedes: []
superseded_by: ""
status: active
---

# {title}

**Source:** {source_url}
**Indexed:** {indexed_at}

---

{content}
"""
    return slug, page


def ensure_wiki_structure(topic: str):
    """確保 Topic 目錄結構存在"""
    topic_dir = BASE / topic
    topic_dir.mkdir(parents=True, exist_ok=True)
    (topic_dir / "sources").mkdir(exist_ok=True)
    (topic_dir / "entities").mkdir(exist_ok=True)
    CONCEPTS_DIR.mkdir(parents=True, exist_ok=True)
    ENTITIES_DIR.mkdir(parents=True, exist_ok=True)
    return topic_dir


def write_wiki_topic(topic: str, records: list[dict], dry_run: bool = False) -> int:
    """將一個 Topic 的所有 records 寫入 sources/ 格式"""
    topic_dir = ensure_wiki_structure(topic)
    sources_dir = topic_dir / "sources"
    written = 0

    existing_slugs = set(f.stem for f in sources_dir.glob("*.md"))

    for record in records:
        text = (record.get("text") or record.get("content") or "").strip()
        if len(text) < 50:
            continue

        slug, page_content = record_to_source_page(record)

        base_slug = slug
        counter = 1
        while slug in existing_slugs:
            slug = f"{base_slug}-{counter}"
            counter += 1
        existing_slugs.add(slug)

        if not dry_run:
            (sources_dir / f"{slug}.md").write_text(page_content)
        written += 1

    if not dry_run:
        build_topic_index(topic)

    return written


def build_topic_index(topic: str):
    """重建 Topic 的 index.md"""
    topic_dir = BASE / topic
    if not topic_dir.exists():
        return

    lines = [
        f"# {topic} — Index",
        "",
        f"**Last updated:** {datetime.now().strftime('%Y-%m-%d')}",
        "",
        "---",
        "",
    ]

    sources_dir = topic_dir / "sources"
    if sources_dir.exists():
        source_files = sorted(sources_dir.glob("*.md"))
        if source_files:
            lines.append("## Sources")
            lines.append("")
            for f in source_files:
                lines.append(f"- [{f.stem.replace('-', ' ').title()}](sources/{f.name})")
            lines.append("")

    entities_dir = topic_dir / "entities"
    if entities_dir.exists():
        entity_files = sorted(entities_dir.glob("*.md"))
        if entity_files:
            lines.append("## Entities")
            lines.append("")
            for f in entity_files:
                lines.append(f"- [{f.stem}](entities/{f.name})")
            lines.append("")

    lines.append("---")
    lines.append("*This file is maintained automatically. Do not edit manually.*")

    (topic_dir / "index.md").write_text("\n".join(lines))


def build_global_index() -> list[str]:
    """重建所有 Topic 的 index.md"""
    topics = []
    for d in sorted(BASE.iterdir()):
        if not d.is_dir() or d.name.startswith(".") or d.name in ("concepts", "entities"):
            continue
        if not (d / "records.json").exists():
            continue
        build_topic_index(d.name)
        topics.append(d.name)
    return topics


def show_status():
    """顯示系統現有狀態"""
    print("=== 知識庫系統狀態 ===\n")

    print("Raw 層（records.json）：")
    for d in sorted(BASE.iterdir()):
        if not d.is_dir() or d.name.startswith(".") or d.name in ("concepts", "entities"):
            continue
        rec_path = d / "records.json"
        if rec_path.exists():
            with open(rec_path) as f:
                records = json.load(f)
                count = len(records) if isinstance(records, list) else 0
            print(f"  {d.name}: {count:,} 筆記錄")

    print("\nWiki 層（*.md）：")
    for d in sorted(BASE.iterdir()):
        if not d.is_dir() or d.name.startswith(".") or d.name in ("concepts", "entities"):
            continue
        if not (d / "records.json").exists():
            continue
        sources_count = len(list((d / "sources").glob("*.md"))) if (d / "sources").exists() else 0
        entities_count = len(list((d / "entities").glob("*.md"))) if (d / "entities").exists() else 0
        has_index = (d / "index.md").exists()
        has_summary = (d / "_summary.md").exists()
        print(f"  {d.name}: {sources_count} sources, {entities_count} entities"
              f"{' [index ✓]' if has_index else ''}{' [summary ✓]' if has_summary else ''}")

    print("\n頂層 Wiki（跨 Topic）：")
    concepts_count = len(list(CONCEPTS_DIR.glob("*.md"))) if CONCEPTS_DIR.exists() else 0
    entities_count = len(list(ENTITIES_DIR.glob("*.md"))) if ENTITIES_DIR.exists() else 0
    print(f"  concepts/: {concepts_count} 頁")
    print(f"  entities/: {entities_count} 頁")


def main():
    parser = argparse.ArgumentParser(description="Migration Helper: Vector DB → Markdown Wiki")
    parser.add_argument("--topic", type=str, help="要遷移的 Topic 名稱")
    parser.add_argument("--dry-run", action="store_true", help="預覽模式，不寫入檔案")
    parser.add_argument("--list-topics", action="store_true", help="列出所有可用 Topic")
    parser.add_argument("--status", action="store_true", help="顯示系統狀態")
    parser.add_argument("--rebuild-index", action="store_true", help="重建所有 Topic 的 index.md")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    if args.list_topics:
        print("可用 Topic（有 records.json 的目錄）：")
        for d in sorted(BASE.iterdir()):
            if d.is_dir() and not d.name.startswith(".") and (d / "records.json").exists():
                print(f"  - {d.name}")
        return

    if args.rebuild_index:
        topics = build_global_index()
        print(f"✅ 已重建 {len(topics)} 個 Topic 的 index.md")
        return

    if args.topic:
        topic = args.topic
        print(f"{'[預覽] ' if args.dry_run else ''}正在遷移 Topic：{topic}")
        records = load_records(topic)
        print(f"  載入 {len(records)} 筆記錄")
        written = write_wiki_topic(topic, records, dry_run=args.dry_run)
        print(f"  {'預覽' if args.dry_run else '寫入'}完成：{written} 個來源頁")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
