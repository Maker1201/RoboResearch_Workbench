from __future__ import annotations

from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..database import get_db
from ..paper_integrations.zotero import ZoteroItemNotFound, get_item_annotations
from ..services.knowledge_workflow_service import (
    annotation_cache_out,
    append_evidence_to_knowledge,
    append_manual_evidence_to_knowledge,
    create_knowledge_from_inbox,
    ensure_inbox_from_annotation,
    inbox_out,
    inbox_type_for_annotation,
    search_knowledge,
    truncate_excerpt,
    upsert_annotation_cache,
)
from ..services.papers_service import reading_note_template

router = APIRouter()


@router.get("/api/papers/{paper_id}/zotero-annotations", response_model=list[schemas.ZoteroAnnotationOut])
def get_cached_paper_annotations(paper_id: int, db: Session = Depends(get_db)):
    crud.get_item(db, models.Paper, paper_id)
    rows = db.query(models.ZoteroAnnotationCache).filter(
        models.ZoteroAnnotationCache.paper_id == paper_id
    ).order_by(models.ZoteroAnnotationCache.date_modified.desc().nullslast(), models.ZoteroAnnotationCache.updated_at.desc()).all()
    return [annotation_cache_out(row, db) for row in rows]


@router.post("/api/papers/{paper_id}/zotero-annotations/sync", response_model=schemas.ZoteroAnnotationSyncOut)
async def sync_paper_annotations(paper_id: int, db: Session = Depends(get_db)):
    paper = crud.get_item(db, models.Paper, paper_id)
    item_key = paper.zotero_item_key or paper.zotero_key
    if not item_key:
        raise HTTPException(status_code=409, detail="该文献尚未绑定 Zotero Item，无法同步批注。")
    try:
        payloads = await get_item_annotations(item_key)
    except ZoteroItemNotFound as exc:
        raise HTTPException(status_code=404, detail="Zotero 中找不到该文献条目，请先重新同步 Zotero。") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"无法连接 Zotero 本地服务，请确认 Zotero 已运行：{exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    inbox_created = 0
    cached: list[models.ZoteroAnnotationCache] = []
    for payload in payloads:
        annotation = upsert_annotation_cache(db, paper, payload)
        cached.append(annotation)
        db.flush()
        for inbox_type in inbox_type_for_annotation(annotation.tags, annotation.comment):
            _, created = ensure_inbox_from_annotation(db, annotation, inbox_type)
            if created:
                inbox_created += 1
    paper.zotero_synced_at = datetime.utcnow()
    db.commit()
    for item in cached:
        db.refresh(item)
    return {
        "paper_id": paper.id,
        "synced": len(cached),
        "inbox_created": inbox_created,
        "annotations": [annotation_cache_out(row, db) for row in cached],
        "message": f"已同步 Zotero 批注 {len(cached)} 条，新增知识待整理 {inbox_created} 条。",
    }


@router.post("/api/knowledge/inbox/from-annotation", response_model=schemas.KnowledgeInboxOut)
def create_inbox_from_annotation(payload: schemas.KnowledgeInboxCreateFromAnnotation, db: Session = Depends(get_db)):
    paper = crud.get_item(db, models.Paper, payload.paper_id)
    annotation = db.query(models.ZoteroAnnotationCache).filter(
        models.ZoteroAnnotationCache.paper_id == paper.id,
        models.ZoteroAnnotationCache.zotero_annotation_key == payload.zotero_annotation_key,
    ).first()
    if annotation is None:
        raise HTTPException(status_code=404, detail="未找到该 Zotero 批注，请先同步批注。")
    item, _ = ensure_inbox_from_annotation(db, annotation, payload.inbox_type)
    db.commit()
    db.refresh(item)
    return inbox_out(item)


@router.get("/api/knowledge/inbox", response_model=list[schemas.KnowledgeInboxOut])
def list_knowledge_inbox(status: str | None = None, inbox_type: str | None = None, db: Session = Depends(get_db)):
    query = db.query(models.KnowledgeInboxItem)
    if status:
        query = query.filter(models.KnowledgeInboxItem.status == status)
    if inbox_type:
        query = query.filter(models.KnowledgeInboxItem.inbox_type == inbox_type)
    rows = query.order_by(models.KnowledgeInboxItem.updated_at.desc()).limit(300).all()
    return [inbox_out(row) for row in rows]


@router.patch("/api/knowledge/inbox/{item_id}", response_model=schemas.KnowledgeInboxOut)
def update_knowledge_inbox_item(item_id: int, payload: schemas.KnowledgeInboxUpdate, db: Session = Depends(get_db)):
    item = crud.get_item(db, models.KnowledgeInboxItem, item_id)
    if payload.status is not None:
        if payload.status not in {"pending", "processed", "ignored"}:
            raise HTTPException(status_code=400, detail="Knowledge Inbox 状态只能是 pending / processed / ignored。")
        item.status = payload.status
        if payload.status in {"processed", "ignored"}:
            item.processed_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    return inbox_out(item)


@router.get("/api/knowledge/search", response_model=schemas.KnowledgeSearchOut)
def api_search_knowledge(q: str = "", category: str | None = None, tags: str | None = None, db: Session = Depends(get_db)):
    return search_knowledge(db, q, category, tags)


@router.post("/api/knowledge/{knowledge_id}/append-evidence", response_model=schemas.KnowledgeLinkOut)
def api_append_evidence(knowledge_id: int, payload: schemas.KnowledgeAppendEvidenceRequest, db: Session = Depends(get_db)):
    knowledge = crud.get_item(db, models.KnowledgeLink, knowledge_id)
    if payload.manual_content is not None or payload.manual_comment is not None:
        return append_manual_evidence_to_knowledge(
            db=db,
            knowledge=knowledge,
            title=payload.manual_title,
            content=payload.manual_content,
            comment=payload.manual_comment,
            page_label=payload.page_label,
            tags=payload.tags,
        )
    inbox_item = _resolve_inbox_item(db, payload)
    return append_evidence_to_knowledge(db, knowledge, inbox_item)


@router.post("/api/knowledge/create-from-inbox", response_model=schemas.KnowledgeLinkOut)
def api_create_knowledge_from_inbox(payload: schemas.KnowledgeCreateFromInboxRequest, db: Session = Depends(get_db)):
    item = crud.get_item(db, models.KnowledgeInboxItem, payload.inbox_item_id)
    if item.status == "ignored":
        raise HTTPException(status_code=409, detail="该 Inbox Item 已忽略，不能创建知识。")
    return create_knowledge_from_inbox(
        db=db,
        inbox_item=item,
        title=payload.title,
        category=payload.category,
        tags=payload.tags,
        knowledge_type=payload.type,
        status=payload.status,
        evidence_level=payload.evidence_level,
        obsidian_path=payload.obsidian_path,
        related_knowledge_ids=payload.related_knowledge_ids,
    )


@router.post("/api/reading-notes/{note_id}/annotations", response_model=schemas.ReadingNoteOut)
def add_annotation_to_reading_note(note_id: int, payload: schemas.ReadingNoteAnnotationRequest, db: Session = Depends(get_db)):
    note = crud.get_item(db, models.ReadingNote, note_id)
    annotation = db.query(models.ZoteroAnnotationCache).filter(
        models.ZoteroAnnotationCache.zotero_annotation_key == payload.zotero_annotation_key
    ).first()
    if annotation is None:
        raise HTTPException(status_code=404, detail="未找到该 Zotero 批注，请先同步批注。")
    if note.paper_id and annotation.paper_id != note.paper_id:
        raise HTTPException(status_code=400, detail="该批注不属于当前阅读笔记关联的论文。")
    content = note.content_markdown or note.content or reading_note_template(note.paper)
    marker = f"zotero_annotation_key: {annotation.zotero_annotation_key}"
    if marker not in content:
        block = _reading_note_annotation_block(annotation)
        content = content.rstrip() + "\n\n## Zotero Annotation Evidence\n\n" + block
        note.content_markdown = content
        note.content = content
        note.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(note)
    return note


def _resolve_inbox_item(db: Session, payload: schemas.KnowledgeAppendEvidenceRequest) -> models.KnowledgeInboxItem:
    if payload.inbox_item_id is not None:
        return crud.get_item(db, models.KnowledgeInboxItem, payload.inbox_item_id)
    if not payload.zotero_annotation_key:
        raise HTTPException(status_code=400, detail="需要 inbox_item_id 或 zotero_annotation_key。")
    query = db.query(models.KnowledgeInboxItem).filter(
        models.KnowledgeInboxItem.zotero_annotation_key == payload.zotero_annotation_key,
        models.KnowledgeInboxItem.inbox_type == "knowledge",
    )
    if payload.paper_id is not None:
        query = query.filter(models.KnowledgeInboxItem.source_paper_id == payload.paper_id)
    item = query.first()
    if item is None:
        raise HTTPException(status_code=404, detail="未找到对应 Knowledge Inbox Item。")
    return item


def _reading_note_annotation_block(annotation: models.ZoteroAnnotationCache) -> str:
    lines = [
        f"- zotero_annotation_key: {annotation.zotero_annotation_key}",
        f"  page: {annotation.page_label or ''}",
    ]
    selected = truncate_excerpt(annotation.selected_text)
    if selected:
        lines.append(f"  highlight: >\n    {selected}")
    if annotation.comment:
        lines.append(f"  my_note: >\n    {annotation.comment.strip()}")
    return "\n".join(lines) + "\n"
