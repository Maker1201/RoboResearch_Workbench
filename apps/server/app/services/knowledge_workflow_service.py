from __future__ import annotations

import re
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import models
from .settings_service import setting_value

TAG_TO_INBOX_TYPE = {
    "knowledge": "knowledge",
    "idea": "idea",
    "question": "question",
}
MAX_EXCERPT_CHARS = 800
PREVIEW_CHARS = 320


def parse_annotation_tags(tags: str | None, comment: str | None = None) -> list[str]:
    values: set[str] = set()
    for raw in re.split(r"[,\n]", tags or ""):
        tag = raw.strip().lstrip("#").lower()
        if tag in TAG_TO_INBOX_TYPE:
            values.add(tag)
    for match in re.findall(r"#(knowledge|idea|question)\b", comment or "", flags=re.IGNORECASE):
        values.add(match.lower())
    return sorted(values)


def inbox_type_for_annotation(tags: str | None, comment: str | None = None) -> list[str]:
    return [TAG_TO_INBOX_TYPE[tag] for tag in parse_annotation_tags(tags, comment)]


def truncate_excerpt(text: str | None, limit: int = MAX_EXCERPT_CHARS) -> str | None:
    if not text:
        return text
    clean = re.sub(r"\s+", " ", text).strip()
    if len(clean) <= limit:
        return clean
    return clean[:limit].rstrip() + "..."


def annotation_cache_out(annotation: models.ZoteroAnnotationCache, db: Session | None = None) -> dict[str, Any]:
    inbox_types: list[str] = []
    if db is not None:
        rows = db.query(models.KnowledgeInboxItem).filter(
            models.KnowledgeInboxItem.zotero_annotation_key == annotation.zotero_annotation_key,
            models.KnowledgeInboxItem.status != "ignored",
        ).all()
        inbox_types = sorted({row.inbox_type for row in rows})
    return {
        "id": annotation.id,
        "paper_id": annotation.paper_id,
        "zotero_item_key": annotation.zotero_item_key,
        "zotero_annotation_key": annotation.zotero_annotation_key,
        "annotation_type": annotation.annotation_type,
        "selected_text": annotation.selected_text,
        "comment": annotation.comment,
        "page_label": annotation.page_label,
        "page_index": annotation.page_index,
        "tags": annotation.tags,
        "date_modified": annotation.date_modified,
        "inbox_types": inbox_types,
    }


def upsert_annotation_cache(db: Session, paper: models.Paper, payload: dict[str, Any]) -> models.ZoteroAnnotationCache:
    key = str(payload.get("zotero_annotation_key") or "").strip()
    if not key:
        raise ValueError("zotero_annotation_key is required")
    item = db.query(models.ZoteroAnnotationCache).filter(models.ZoteroAnnotationCache.zotero_annotation_key == key).first()
    if item is None:
        item = models.ZoteroAnnotationCache(
            paper_id=paper.id,
            zotero_item_key=paper.zotero_item_key or paper.zotero_key or "",
            zotero_annotation_key=key,
        )
        db.add(item)
    item.paper_id = paper.id
    item.zotero_item_key = paper.zotero_item_key or paper.zotero_key or item.zotero_item_key
    item.annotation_type = payload.get("annotation_type") or "highlight"
    item.selected_text = truncate_excerpt(payload.get("selected_text"))
    item.comment = payload.get("comment")
    item.page_label = payload.get("page_label")
    item.page_index = payload.get("page_index")
    item.tags = payload.get("tags")
    item.date_modified = payload.get("date_modified")
    return item


def ensure_inbox_from_annotation(
    db: Session,
    annotation: models.ZoteroAnnotationCache,
    inbox_type: str,
    status: str = "pending",
) -> tuple[models.KnowledgeInboxItem, bool]:
    normalized = inbox_type if inbox_type in {"knowledge", "idea", "question"} else "knowledge"
    existing = db.query(models.KnowledgeInboxItem).filter(
        models.KnowledgeInboxItem.source_type == "ZOTERO_ANNOTATION",
        models.KnowledgeInboxItem.zotero_annotation_key == annotation.zotero_annotation_key,
        models.KnowledgeInboxItem.inbox_type == normalized,
    ).first()
    if existing:
        return existing, False
    item = models.KnowledgeInboxItem(
        source_type="ZOTERO_ANNOTATION",
        source_paper_id=annotation.paper_id,
        zotero_item_key=annotation.zotero_item_key,
        zotero_annotation_key=annotation.zotero_annotation_key,
        inbox_type=normalized,
        selected_text=annotation.selected_text,
        comment=annotation.comment,
        page_label=annotation.page_label,
        tags=annotation.tags,
        status=status,
    )
    db.add(item)
    return item, True


def inbox_out(item: models.KnowledgeInboxItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "source_type": item.source_type,
        "source_paper_id": item.source_paper_id,
        "zotero_item_key": item.zotero_item_key,
        "zotero_annotation_key": item.zotero_annotation_key,
        "inbox_type": item.inbox_type,
        "selected_text": item.selected_text,
        "comment": item.comment,
        "page_label": item.page_label,
        "tags": item.tags,
        "status": item.status,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "processed_at": item.processed_at,
        "paper_title": item.paper.title if item.paper else None,
    }


def search_knowledge(db: Session, query: str | None, category: str | None = None, tags: str | None = None) -> dict[str, list[models.KnowledgeLink]]:
    q = (query or "").strip().lower()
    base = db.query(models.KnowledgeLink)
    if category:
        base = base.filter(models.KnowledgeLink.area.ilike(f"%{category}%"))
    if tags:
        for tag in [part.strip() for part in re.split(r"[,\s]+", tags) if part.strip()]:
            base = base.filter(models.KnowledgeLink.tags.ilike(f"%{tag}%"))
    rows = base.order_by(models.KnowledgeLink.updated_at.desc()).limit(300).all()
    if not q:
        return {"direct_matches": rows[:20], "related": []}
    direct: list[models.KnowledgeLink] = []
    related: list[models.KnowledgeLink] = []
    tokens = [token for token in re.split(r"\s+", q) if token]
    for item in rows:
        title = (item.title or "").lower()
        haystack = " ".join([item.title or "", item.area or "", item.tags or "", item.notes or "", _read_obsidian_text(db, item)[:4000]]).lower()
        if q in title:
            direct.append(item)
        elif all(token in haystack for token in tokens) or any(token in haystack for token in tokens):
            related.append(item)
    return {"direct_matches": direct[:20], "related": [item for item in related if item not in direct][:20]}


def obsidian_config(db: Session) -> tuple[Path, str, bool]:
    vault = setting_value(db, "integrations.obsidian.vault_path") or setting_value(db, "paths.obsidian_vault")
    root = setting_value(db, "integrations.obsidian.knowledge_root") or "Knowledge"
    use_uri = setting_value(db, "integrations.obsidian.use_obsidian_uri").lower() in {"true", "1", "yes"}
    if not vault:
        raise HTTPException(status_code=409, detail="Obsidian Vault 未配置，请先在设置中配置 Vault 路径。")
    vault_path = Path(vault).expanduser()
    if not vault_path.exists():
        raise HTTPException(status_code=409, detail=f"Obsidian Vault 路径不存在：{vault}")
    if not vault_path.is_dir():
        raise HTTPException(status_code=409, detail=f"Obsidian Vault 不是文件夹：{vault}")
    return vault_path, root.strip("/"), use_uri


def resolve_knowledge_path(db: Session, knowledge: models.KnowledgeLink) -> Path:
    vault, root, _ = obsidian_config(db)
    rel = (knowledge.vault_path or "").strip()
    if not rel:
        rel = f"{root}/{safe_markdown_filename(knowledge.title)}.md"
    path = Path(rel)
    if path.is_absolute():
        full = path
    else:
        full = vault / path
    try:
        full.resolve().relative_to(vault.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Knowledge 文件路径必须位于 Obsidian Vault 内。") from exc
    return full


def safe_markdown_filename(title: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|#\[\]]+", " ", title).strip()
    cleaned = re.sub(r"\s+", "-", cleaned)
    return cleaned[:120] or "Knowledge"


def make_obsidian_uri(db: Session, rel_path: str) -> str | None:
    vault, _, use_uri = obsidian_config(db)
    if not use_uri:
        return None
    return f"obsidian://open?vault={quote(vault.name)}&file={quote(rel_path)}"


def append_evidence_to_knowledge(db: Session, knowledge: models.KnowledgeLink, inbox_item: models.KnowledgeInboxItem) -> models.KnowledgeLink:
    path = resolve_knowledge_path(db, knowledge)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Knowledge 文件不存在：{knowledge.vault_path or path.name}")
    if not path.is_file():
        raise HTTPException(status_code=409, detail="Knowledge 路径不是 Markdown 文件。")
    text = path.read_text(encoding="utf-8")
    marker = f"zotero_annotation_key: {inbox_item.zotero_annotation_key}"
    if marker not in text:
        block = evidence_block(inbox_item)
        text = append_to_section(text, "## Evidence", block)
        path.write_text(text, encoding="utf-8")
    link_paper_knowledge(db, inbox_item.source_paper_id, knowledge)
    inbox_item.status = "processed"
    inbox_item.processed_at = datetime.utcnow()
    knowledge.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(knowledge)
    return knowledge


def append_manual_evidence_to_knowledge(
    db: Session,
    knowledge: models.KnowledgeLink,
    title: str | None,
    content: str | None,
    comment: str | None = None,
    page_label: str | None = None,
    tags: str | None = None,
) -> models.KnowledgeLink:
    body = (content or "").strip()
    note = (comment or "").strip()
    if not body and not note:
        raise HTTPException(status_code=400, detail="请填写要补充的知识内容或个人理解。")
    path = resolve_knowledge_path(db, knowledge)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Knowledge 文件不存在：{knowledge.vault_path or path.name}")
    if not path.is_file():
        raise HTTPException(status_code=409, detail="Knowledge 路径不是 Markdown 文件。")
    text = path.read_text(encoding="utf-8")
    digest_source = "\n".join([knowledge.title or "", title or "", body, note, page_label or "", tags or ""])
    evidence_key = hashlib.sha1(digest_source.encode("utf-8")).hexdigest()[:16]
    marker = f"manual_evidence_key: {evidence_key}"
    if marker not in text:
        block = manual_evidence_block(evidence_key, title, body, note, page_label, tags)
        text = append_to_section(text, "## Evidence", block)
        path.write_text(text, encoding="utf-8")
    knowledge.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(knowledge)
    return knowledge


def create_knowledge_from_inbox(
    db: Session,
    inbox_item: models.KnowledgeInboxItem,
    title: str,
    category: str,
    tags: str | None,
    knowledge_type: str,
    status: str,
    evidence_level: str,
    obsidian_path: str | None,
    related_knowledge_ids: list[int] | None = None,
) -> models.KnowledgeLink:
    vault, root, _ = obsidian_config(db)
    rel = obsidian_path.strip() if obsidian_path else f"{root}/{category}/{safe_markdown_filename(title)}.md"
    full = (vault / rel) if not Path(rel).is_absolute() else Path(rel)
    try:
        full.resolve().relative_to(vault.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="新知识路径必须位于 Obsidian Vault 内。") from exc
    if full.exists():
        raise HTTPException(status_code=409, detail="已存在同名 Knowledge 文件，请搜索后补充到已有知识，或修改标题/路径。")
    full.parent.mkdir(parents=True, exist_ok=True)
    related_titles = []
    for kid in related_knowledge_ids or []:
        related = db.get(models.KnowledgeLink, kid)
        if related:
            related_titles.append(related.title)
    md = knowledge_template(title, category, tags, knowledge_type, status, evidence_level, inbox_item, related_titles)
    full.write_text(md, encoding="utf-8")
    knowledge = models.KnowledgeLink(
        title=title,
        area=category,
        tags=tags,
        vault_path=str(full.relative_to(vault)),
        obsidian_uri=make_obsidian_uri(db, str(full.relative_to(vault))),
        notes=f"type: {knowledge_type}\nstatus: {status}\nevidence_level: {evidence_level}",
    )
    db.add(knowledge)
    db.flush()
    link_paper_knowledge(db, inbox_item.source_paper_id, knowledge, commit=False)
    inbox_item.status = "processed"
    inbox_item.processed_at = datetime.utcnow()
    db.commit()
    db.refresh(knowledge)
    return knowledge


def evidence_block(item: models.KnowledgeInboxItem) -> str:
    paper_title = item.paper.title if item.paper else "Unknown Paper"
    selected = truncate_excerpt(item.selected_text, MAX_EXCERPT_CHARS) or ""
    comment = (item.comment or "").strip()
    date = datetime.utcnow().strftime("%Y-%m-%d")
    lines = [
        f"- date: {date}",
        f"  paper: {paper_title}",
        f"  zotero_item_key: {item.zotero_item_key or ''}",
        f"  zotero_annotation_key: {item.zotero_annotation_key or ''}",
        f"  page: {item.page_label or ''}",
    ]
    if selected:
        lines.append(f"  excerpt: >\n    {selected}")
    if comment:
        lines.append(f"  my_note: >\n    {comment}")
    return "\n".join(lines) + "\n"


def manual_evidence_block(
    evidence_key: str,
    title: str | None,
    content: str,
    comment: str,
    page_label: str | None = None,
    tags: str | None = None,
) -> str:
    date = datetime.utcnow().strftime("%Y-%m-%d")
    lines = [
        f"- date: {date}",
        "  source: Workbench Manual Supplement",
        f"  manual_evidence_key: {evidence_key}",
    ]
    if title:
        lines.append(f"  title: {title.strip()}")
    if page_label:
        lines.append(f"  page: {page_label.strip()}")
    if tags:
        lines.append(f"  tags: {tags.strip()}")
    if content:
        lines.append(f"  content: >\n    {truncate_excerpt(content)}")
    if comment:
        lines.append(f"  my_note: >\n    {comment}")
    return "\n".join(lines) + "\n"


def append_to_section(text: str, heading: str, block: str) -> str:
    if heading not in text:
        return text.rstrip() + f"\n\n{heading}\n\n{block}"
    index = text.index(heading) + len(heading)
    return text[:index].rstrip() + "\n\n" + block.rstrip() + "\n" + text[index:]


def knowledge_template(
    title: str,
    category: str,
    tags: str | None,
    knowledge_type: str,
    status: str,
    evidence_level: str,
    item: models.KnowledgeInboxItem,
    related_titles: list[str],
) -> str:
    tag_list = [part.strip() for part in re.split(r"[,\n]", tags or "") if part.strip()]
    frontmatter_tags = "[" + ", ".join(tag_list) + "]"
    related = "\n".join(f"- [[{name}]]" for name in related_titles) or ""
    my_note = (item.comment or "").strip()
    return f"""---
title: {title}
category: {category}
type: {knowledge_type}
status: {status}
evidence_level: {evidence_level}
tags: {frontmatter_tags}
created: {datetime.utcnow().strftime('%Y-%m-%d')}
---

# {title}

## Definition


## My Understanding

{my_note}

## Evidence

{evidence_block(item)}
## Related Knowledge

{related}
"""


def link_paper_knowledge(db: Session, paper_id: int | None, knowledge: models.KnowledgeLink, commit: bool = True) -> None:
    if paper_id is None:
        return
    paper = db.get(models.Paper, paper_id)
    if paper and knowledge not in paper.knowledge_links:
        paper.knowledge_links.append(knowledge)
    if commit:
        db.commit()


def _read_obsidian_text(db: Session, knowledge: models.KnowledgeLink) -> str:
    try:
        path = resolve_knowledge_path(db, knowledge)
        if path.exists() and path.is_file() and path.suffix.lower() == ".md":
            return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
    return ""
