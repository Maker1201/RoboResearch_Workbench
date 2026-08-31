from __future__ import annotations

from datetime import datetime

import httpx
import markdown as markdown_lib
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..database import get_db
from ..paper_integrations.zotero import create_child_note, get_child_notes, update_child_note
from ..services.papers_service import note_content, reading_note_template, safe_markdown_filename
from ..services.zotero_storage import sanitize_note_html_fragment

router = APIRouter()


@router.get("/reading-notes", response_model=list[schemas.ReadingNoteOut])
def list_reading_notes(paper_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(models.ReadingNote)
    if paper_id is not None:
        query = query.filter(models.ReadingNote.paper_id == paper_id)
    return query.order_by(models.ReadingNote.updated_at.desc()).limit(300).all()


@router.post("/reading-notes", response_model=schemas.ReadingNoteOut)
def create_reading_note(payload: schemas.ReadingNoteCreate, db: Session = Depends(get_db)):
    data = payload.model_dump()
    paper = db.get(models.Paper, data["paper_id"]) if data.get("paper_id") else None
    if data.get("paper_id") and not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    if not data.get("content_markdown") and data.get("content"):
        data["content_markdown"] = data["content"]
    if not data.get("content_markdown"):
        data["content_markdown"] = reading_note_template(paper)
    data["content"] = data.get("content_markdown") or data.get("content") or ""
    if paper:
        data["reading_status_snapshot"] = data.get("reading_status_snapshot") or paper.status
        data["reading_mode"] = data.get("reading_mode") or paper.reading_mode
        data["related_project_id"] = data.get("related_project_id") or paper.related_project_id
    item = models.ReadingNote(**data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/papers/{paper_id}/reading-note", response_model=schemas.ReadingNoteOut)
def create_or_get_paper_note(paper_id: int, db: Session = Depends(get_db)):
    paper = crud.get_item(db, models.Paper, paper_id)
    existing = db.query(models.ReadingNote).filter(models.ReadingNote.paper_id == paper_id).order_by(models.ReadingNote.updated_at.desc()).first()
    if existing:
        return existing
    item = models.ReadingNote(
        paper_id=paper.id,
        title=f"Reading Note - {paper.title[:220]}",
        status="draft",
        content=reading_note_template(paper),
        content_markdown=reading_note_template(paper),
        reading_status_snapshot=paper.status,
        reading_mode=paper.reading_mode,
        related_project_id=paper.related_project_id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/reading-notes/{note_id}", response_model=schemas.ReadingNoteOut)
def update_reading_note(note_id: int, payload: schemas.ReadingNoteUpdate, db: Session = Depends(get_db)):
    item = crud.get_item(db, models.ReadingNote, note_id)
    data = payload.model_dump(exclude_unset=True)
    if "content_markdown" in data and "content" not in data:
        data["content"] = data["content_markdown"]
    if "content" in data and "content_markdown" not in data:
        data["content_markdown"] = data["content"]
    for key, value in data.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.get("/reading-notes/{note_id}/export", response_model=schemas.ReadingNoteExportOut)
def export_reading_note(note_id: int, db: Session = Depends(get_db)):
    note = crud.get_item(db, models.ReadingNote, note_id)
    paper = note.paper
    title = paper.title if paper else note.title
    metadata = [
        "---",
        f"title: {title}",
        f"paper_id: {note.paper_id or ''}",
        f"zotero_item_key: {(paper.zotero_item_key or paper.zotero_key) if paper else ''}",
        f"reading_status: {note.reading_status_snapshot or (paper.status if paper else '')}",
        f"reading_mode: {note.reading_mode or (paper.reading_mode if paper else '') or ''}",
        "---",
        "",
    ]
    return {"filename": safe_markdown_filename(title), "content": "\n".join(metadata) + note_content(note)}


@router.delete("/reading-notes/{note_id}")
def delete_reading_note(note_id: int, db: Session = Depends(get_db)):
    return crud.delete_item(db, models.ReadingNote, note_id)


@router.post("/reading-notes/{note_id}/push-zotero")
async def push_reading_note_to_zotero(note_id: int, db: Session = Depends(get_db)):
    """把阅读笔记作为子笔记同步到 Zotero 条目下（幂等：已同步则更新）。"""
    note = crud.get_item(db, models.ReadingNote, note_id)
    paper = note.paper
    if paper is None:
        raise HTTPException(status_code=400, detail="该笔记未关联文献，无法同步到 Zotero。")
    item_key = paper.zotero_item_key or paper.zotero_key
    if not item_key:
        raise HTTPException(status_code=400, detail="该文献尚未关联 Zotero 条目，请先加入 Zotero。")

    note_markdown = note_content(note)
    if not note_markdown.strip():
        raise HTTPException(status_code=400, detail="笔记内容为空，先写点什么再同步。")
    note_html = sanitize_note_html_fragment(
        markdown_lib.markdown(note_markdown, extensions=["extra", "nl2br", "sane_lists"])
    )
    tags = ["reading-note", f"mode:{(paper.reading_mode or 'NA').lower()}"]

    try:
        if note.zotero_note_key:
            existing_notes = await get_child_notes(item_key)
            current = next((n for n in existing_notes if n["key"] == note.zotero_note_key), None)
            if current is None:
                # Zotero 端已被删除，重新创建
                created = await create_child_note(item_key, note_html, tags)
                note.zotero_note_key = created["key"]
                note.zotero_note_synced_at = datetime.utcnow()
                action = "recreated"
            else:
                await update_child_note(current["key"], current["version"], note_html, tags)
                note.zotero_note_synced_at = datetime.utcnow()
                action = "updated"
        else:
            created = await create_child_note(item_key, note_html, tags)
            note.zotero_note_key = created["key"]
            note.zotero_note_synced_at = datetime.utcnow()
            action = "created"
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"无法连接 Zotero 本地服务：{exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.commit()
    db.refresh(note)
    return {
        "status": "ok",
        "action": action,
        "zotero_note_key": note.zotero_note_key,
        "message": {"created": "已在 Zotero 中创建子笔记。", "updated": "已更新 Zotero 子笔记。", "recreated": "原 Zotero 笔记已不存在，已重新创建。"}[action],
    }
