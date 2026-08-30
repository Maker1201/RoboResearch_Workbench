from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..database import get_db
from ..services.papers_service import note_content, reading_note_template, safe_markdown_filename

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
