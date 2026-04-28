#!/usr/bin/env python3
"""
Migration Helper — Vector DB (System A) → Markdown Wiki (System B)

用途：將 Vector DB 內任何 Topic 的 records.json 轉換為 Wiki 格式的 .md 檔案，
      未來任何 Topic 想遷移到 System B，執行本腳本即可完成。

用法：
  python3 migration_helper.py --topic Finance              # 遷移單一 Topic
  python3 migration_helper.py --topic Finance --dry-run    # 預覽（不寫入）
  python3 migration_helper.py --list-topics                # 列出所有可用 Topic
  python3 migration_helper.py --status                     # 顯示兩系統狀態

Author: knowledge-base-blueprint

"""

import argparse
import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path

BASE = Path(os.environ.get("KB_BASE", Path.home() / ".knowledge_base"))
WIKI_BASE = BASE / "wiki"


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
    # 保留：中文(CJK Unicode range)、英文大小寫、數字、連字符
    allowed = re.compile(r'[^\u4e00-\u9fffA-Za-z0-9-]')
    text = allowed.sub('-', text)
    # 合併多個連字符為一個
    text = re.sub(r'-+', '-', text)
    result = text.strip('-')[:60]
    return result if result else f"record-{uuid.uuid4().hex[:8]}"


def extract_title(text: str, metadata: dict) -> str:
    """從文字內容或 metadata 猜測標題"""
    # 優先取內容第一行（通常就是標題）
    if text:
        first_line = text.strip().split("\n")[0][:60]
        if len(first_line) >= 10:
            # 清理 markdown 標題符號
            cleaned = first_line.lstrip('#').lstrip('*').strip()
            if cleaned:
                return cleaned
    # 如果內容太短或找不到，取 metadata.source 的檔名部分
    source = metadata.get("source", "")
    if source:
        path_part = source.rstrip("/").split("/")[-1]
        # 移除副檔名和常見前輟
        path_part = re.sub(r'\.(txt|md|html?|pdf|docx)$', '', path_part, flags=re.IGNORECASE)
        path_part = re.sub(r'^[\w]+---', '', path_part)  # 移除常見 UUID 前輟
        if path_part and path_part not in ("", "index"):
            return path_part.replace("-", " ").replace("_", " ").strip()
    # 兜底
    return "Untitled"


def record_to_markdown(record: dict) -> str:
    """將單筆記錄轉換為一個 .md 檔案的內容"""
    # 優先使用 content 欄位（Vector DB 常用名稱）
    text = (record.get("content") or record.get("text") or "").strip()
    metadata = record.get("metadata", {})

    title = extract_title(text, metadata)
    source = metadata.get("source", "Unknown source")
    char_count = metadata.get("char_count", len(text))
    topic = metadata.get("topic", "Unknown")
    created_at = metadata.get("created_at", datetime.now().isoformat())

    # 清理內容：移除多餘空行、清理殘留 HTML
    content = re.sub(r'<[^>]+>', '', text)
    content = re.sub(r'\n{3,}', '\n\n', content).strip()

    return f"""# {title}

**主題：** {topic}  
**來源：** {source}  
**字元數：** {char_count:,}  
**寫入時間：** {created_at[:10]}  

---

{content}
"""


def ensure_wiki_structure(topic: str):
    """確保 Wiki 目錄結構存在"""
    topic_dir = WIKI_BASE / topic
    topic_dir.mkdir(parents=True, exist_ok=True)
    for f in ["_summary.md", "_tags.md"]:
        p = topic_dir / f
        if not p.exists():
            p.write_text(f"# {f.replace('_', '').replace('.md', '').title()}\n\n")
    return topic_dir


def write_wiki_topic(topic: str, records: list[dict], dry_run: bool = False):
    """將一個 Topic 的所有 records 寫入 Wiki 格式"""
    topic_dir = ensure_wiki_structure(topic)
    written = 0
    duplicates = 0

    # 先掃描現有的 .md 檔案（排除特殊檔案）
    existing = set()
    for f in topic_dir.glob("*.md"):
        if not f.name.startswith("_"):
            existing.add(f.stem)

    # 處理每一筆記錄
    for record in records:
        text = (record.get("text") or record.get("content") or "").strip()
        if len(text) < 50:
            continue  # 跳過太短的記錄

        title = extract_title(text, record.get("metadata", {}))
        slug = slugify(title)

        # 避免 slug 衝突
        base_slug = slug
        counter = 1
        while slug in existing:
            slug = f"{base_slug}-{counter}"
            counter += 1
        existing.add(slug)

        md_content = record_to_markdown(record)
        md_path = topic_dir / f"{slug}.md"

        if not dry_run:
            md_path.write_text(md_content)
        written += 1

    # 更新 _summary.md（簡單版本：列表式）
    summary_path = topic_dir / "_summary.md"
    current_summary = summary_path.read_text() if summary_path.exists() else ""

    # 簡單的超連結列表置於頂部
    file_list = []
    for f in sorted(topic_dir.glob("*.md")):
        if f.name.startswith("_"):
            continue
        file_list.append(f"- [{f.stem.replace('-', ' ').title()}]({f.name})")

    new_content = f"""# {topic} — 摘要

**總記錄數：** {written}  
**最後更新：** {datetime.now().strftime('%Y-%m-%d')}  
**說明：** 此目錄由 System A（Vector DB）遷移而來。詳見 `KNOWLEDGE_ARCHITECTURE.md`。

## 檔案列表

{chr(10).join(file_list) if file_list else '（尚無檔案）'}

---
*此檔案由 migration_helper.py 自動更新*
"""

    if not dry_run:
        summary_path.write_text(new_content)

    return written, duplicates


def build_wiki_index():
    """更新 wiki/_index.md 全域總索引"""
    WIKI_BASE.mkdir(parents=True, exist_ok=True)

    topics = []
    for d in sorted(WIKI_BASE.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        summary = d / "_summary.md"
        tags = d / "_tags.md"
        md_count = len(list(d.glob("*.md"))) - (1 if (d / "_summary.md").exists() else 0) - (1 if (d / "_tags.md").exists() else 0)
        topics.append((d.name, md_count, summary.exists(), tags.exists()))

    lines = [
        "# Wiki 全域索引",
        "",
        f"**更新時間：** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**主題數：** {len(topics)}",
        "",
        "---",
        "",
    ]
    for name, count, has_summary, has_tags in topics:
        lines.append(f"## {name}")
        lines.append(f"- 檔案數量：{count}")
        lines.append(f"- 摘要檔：{'✅' if has_summary else '❌'}")
        lines.append(f"- 標籤檔：{'✅' if has_tags else '❌'}")
        lines.append(f"- [→ 進入目錄]({name}/_summary.md)")
        lines.append("")

    index_content = "\n".join(lines)
    index_path = WIKI_BASE / "_index.md"
    index_path.write_text(index_content)

    return topics


def show_status():
    """顯示兩系統的現有狀態"""
    print("=== 雙知識庫系統狀態 ===\n")
    print("System A（Vector DB）：")
    for d in sorted((BASE).iterdir()):
        if not d.is_dir() or d.name == "wiki" or d.name.startswith("."):
            continue
        rec_path = d / "records.json"
        if rec_path.exists():
            with open(rec_path) as f:
                records = json.load(f)
                count = len(records) if isinstance(records, list) else 0
            print(f"  {d.name}: {count:,} 筆記錄")

    print(f"\nSystem B（Wiki）：")
    if not WIKI_BASE.exists():
        print("  （尚未建立）")
    else:
        topics = []
        for d in sorted(WIKI_BASE.iterdir()):
            if not d.is_dir() or d.name.startswith("."):
                continue
            md_count = len(list(d.glob("*.md")))
            topics.append(f"  {d.name}: {md_count} 個 .md 檔案")
        if topics:
            print("\n".join(topics))
        else:
            print("  （目錄為空）")


def main():
    parser = argparse.ArgumentParser(description="Migration Helper: Vector DB → Markdown Wiki")
    parser.add_argument("--topic", type=str, help="要遷移的 Topic 名稱")
    parser.add_argument("--dry-run", action="store_true", help="預覽模式，不寫入檔案")
    parser.add_argument("--list-topics", action="store_true", help="列出所有可用 Topic")
    parser.add_argument("--status", action="store_true", help="顯示兩系統狀態")
    parser.add_argument("--rebuild-index", action="store_true", help="重建全域 _index.md")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    if args.list_topics:
        print("System A（Vector DB）可用 Topic：")
        for d in sorted(BASE.iterdir()):
            if d.is_dir() and d.name not in ("wiki",) and not d.name.startswith("."):
                print(f"  - {d.name}")
        return

    if args.rebuild_index:
        topics = build_wiki_index()
        print(f"✅ 全域索引已重建，共 {len(topics)} 個主題")
        return

    if args.topic:
        topic = args.topic
        print(f"{'[預覽] ' if args.dry_run else ''}正在遷移 Topic：{topic}")
        records = load_records(topic)
        print(f"  載入 {len(records)} 筆記錄")
        written, dup = write_wiki_topic(topic, records, dry_run=args.dry_run)
        print(f"  {'預覽' if args.dry_run else '寫入'}完成：{written} 個檔案（{dup} 個跳過）")
        if not args.dry_run:
            build_wiki_index()
        return

    parser.print_help()


if __name__ == "__main__":
    main()