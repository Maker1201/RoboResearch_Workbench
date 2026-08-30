from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..database import get_db
from ..paper_integrations.crossref import search_crossref
from ..paper_integrations.models import (
    Paper as SearchPaperModel,
    SearchRequest,
    SearchResponse,
    ZoteroAttachPdfRequest,
    ZoteroImportRequest,
)
from ..paper_integrations.openalex import search_openalex
from ..paper_integrations.translator import translate_papers
from ..paper_integrations.zotero import (
    attach_pdf_to_zotero,
    get_zotero_item_sync_state,
    import_to_zotero,
    zotero_status,
)
from ..services.dashboard_service import focus_elapsed_seconds
from ..services.papers_service import (
    apply_pdf_state,
    apply_zotero_import_result_to_paper,
    apply_zotero_import_result_to_payload,
    apply_zotero_sync_state_to_paper,
    db_paper_to_search_model,
    merge_search_papers,
    normalize_doi,
    normalize_paper_status,
    normalize_reading_mode,
    normalize_venue,
    search_paper_to_db_payload,
    upsert_paper,
)

router = APIRouter()


@router.post("/papers/search", response_model=SearchResponse)
async def search_papers(request: SearchRequest) -> SearchResponse:
    openalex_papers = await search_openalex(request)
    crossref_papers = await search_crossref(request)
    papers_by_key = {}
    for paper in [*crossref_papers, *openalex_papers]:
        key = (paper.doi or paper.id).lower()
        current = papers_by_key.get(key)
        papers_by_key[key] = merge_search_papers(current, paper) if current else paper
    papers = sorted(papers_by_key.values(), key=lambda paper: (paper.relevance, paper.year or 0), reverse=True)
    return SearchResponse(papers=await translate_papers(papers))


@router.post("/papers/import-zotero")
async def papers_import_zotero(request: ZoteroImportRequest) -> dict:
    try:
        return await import_to_zotero(request)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/papers/attach-pdf")
async def papers_attach_pdf(request: ZoteroAttachPdfRequest) -> dict:
    try:
        return await attach_pdf_to_zotero(request)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/zotero/status")
async def get_zotero_status() -> dict:
    return await zotero_status()


@router.get("/papers", response_model=list[schemas.PaperOut])
def list_papers(venue: str | None = None, status: str | None = None, queue: bool = False, db: Session = Depends(get_db)):
    query = db.query(models.Paper)
    if venue:
        query = query.filter(models.Paper.venue == venue)
    if status:
        query = query.filter(func.lower(models.Paper.status) == normalize_paper_status(status).lower())
    if queue:
        query = query.filter(models.Paper.queued_at.is_not(None))
        query = query.order_by(models.Paper.priority.asc(), models.Paper.queued_at.asc())
    else:
        query = query.order_by(models.Paper.updated_at.desc())
    return query.limit(300).all()


@router.post("/papers", response_model=schemas.PaperOut)
def create_paper(payload: schemas.PaperCreate, db: Session = Depends(get_db)):
    data = payload.model_dump()
    data["status"] = normalize_paper_status(data.get("status"))
    data["reading_mode"] = normalize_reading_mode(data.get("reading_mode"))
    data["doi"] = normalize_doi(data.get("doi"))
    data["venue"] = normalize_venue(data.get("venue"))
    data["source_url"] = data.get("source_url") or data.get("url")
    return upsert_paper(db, data)


@router.post("/papers/candidate", response_model=schemas.PaperOut)
def save_candidate(payload: schemas.PaperLibraryImportRequest, db: Session = Depends(get_db)):
    data = search_paper_to_db_payload(payload.paper, "Candidate")
    data["priority"] = payload.priority
    data["reading_purpose"] = payload.reading_purpose
    data["related_project_id"] = payload.related_project_id
    if payload.related_project_id is not None:
        crud.get_item(db, models.Project, payload.related_project_id)
    return upsert_paper(db, data)


@router.post("/papers/library", response_model=schemas.PaperOut)
async def add_to_library(payload: schemas.PaperLibraryImportRequest, db: Session = Depends(get_db)):
    search_model = SearchPaperModel.model_validate(payload.paper)
    try:
        zotero_result = await import_to_zotero(ZoteroImportRequest(papers=[search_model]))
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    data = search_paper_to_db_payload(search_model, "To Read")
    data["priority"] = payload.priority
    data["reading_purpose"] = payload.reading_purpose
    data["related_project_id"] = payload.related_project_id
    if payload.related_project_id is not None:
        crud.get_item(db, models.Project, payload.related_project_id)
    apply_zotero_import_result_to_payload(db, data, zotero_result, 0)
    return upsert_paper(db, data)


@router.post("/papers/library/batch", response_model=list[schemas.PaperOut])
async def add_to_library_batch(payload: schemas.PaperLibraryBatchImportRequest, db: Session = Depends(get_db)):
    if not payload.papers:
        return []
    if payload.related_project_id is not None:
        crud.get_item(db, models.Project, payload.related_project_id)

    search_models = [SearchPaperModel.model_validate(paper) for paper in payload.papers]
    try:
        zotero_result = await import_to_zotero(ZoteroImportRequest(papers=search_models))
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    saved: list[models.Paper] = []
    for index, search_model in enumerate(search_models):
        data = search_paper_to_db_payload(search_model, "To Read")
        data["priority"] = payload.priority
        data["reading_purpose"] = payload.reading_purpose
        data["related_project_id"] = payload.related_project_id
        apply_zotero_import_result_to_payload(db, data, zotero_result, index)
        saved.append(upsert_paper(db, data))
    return saved


@router.post("/papers/{paper_id}/attach-pdf", response_model=schemas.PaperOut)
async def attach_pdf_to_paper(paper_id: int, payload: schemas.PaperPdfAttachRequest, db: Session = Depends(get_db)):
    paper = crud.get_item(db, models.Paper, paper_id)
    item_key = paper.zotero_item_key or paper.zotero_key
    if not item_key:
        raise HTTPException(status_code=400, detail="该文献尚未关联 Zotero 条目，不能挂载 PDF。")
    try:
        result = await attach_pdf_to_zotero(ZoteroAttachPdfRequest(
            item_key=item_key,
            pdf_url=payload.pdf_url or paper.pdf_url or paper.url,
            filename=payload.filename or f"{paper.title}.pdf",
            content_type=payload.content_type or "application/pdf",
            content_base64=payload.content_base64,
            source="LOCAL_FILE",
        ))
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if result.get("status") in {"ok", "skipped"}:
        apply_pdf_state(
            paper,
            status="ATTACHED",
            source=result.get("pdf_source") or "LOCAL_FILE",
            attachment_key=result.get("attachment_key"),
        )
        db.commit()
        db.refresh(paper)
    return paper


@router.patch("/papers/{paper_id}", response_model=schemas.PaperOut)
def update_paper(paper_id: int, payload: schemas.PaperUpdate, db: Session = Depends(get_db)):
    if payload.status is not None:
        payload.status = normalize_paper_status(payload.status)
    if payload.reading_mode is not None:
        payload.reading_mode = normalize_reading_mode(payload.reading_mode)
    if payload.doi is not None:
        payload.doi = normalize_doi(payload.doi)
    data = payload.model_dump(exclude_unset=True)
    if "url" in data and "source_url" not in data:
        data["source_url"] = data.get("url")
    item = crud.get_item(db, models.Paper, paper_id)
    for key, value in data.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.post("/papers/{paper_id}/zotero", response_model=schemas.PaperOut)
async def add_existing_paper_to_zotero(paper_id: int, db: Session = Depends(get_db)):
    paper = crud.get_item(db, models.Paper, paper_id)
    zotero_result = await import_to_zotero(ZoteroImportRequest(papers=[db_paper_to_search_model(paper)]))
    apply_zotero_import_result_to_paper(db, paper, zotero_result, 0)
    paper.status = "To Read"
    db.commit()
    db.refresh(paper)
    return paper


@router.post("/papers/{paper_id}/zotero/check", response_model=schemas.PaperOut)
async def check_paper_zotero_attachment(paper_id: int, db: Session = Depends(get_db)):
    paper = crud.get_item(db, models.Paper, paper_id)
    item_key = paper.zotero_item_key or paper.zotero_key
    if not item_key:
        apply_pdf_state(
            paper,
            status="NONE",
            error_code="PDF_NOT_FOUND",
            error_message="This paper is not linked to a Zotero item.",
        )
        db.commit()
        db.refresh(paper)
        return paper
    try:
        state = await get_zotero_item_sync_state(item_key)
    except Exception as exc:
        apply_pdf_state(
            paper,
            status="FAILED",
            error_code="ZOTERO_NOT_RUNNING",
            error_message=str(exc),
        )
        db.commit()
        db.refresh(paper)
        return paper
    apply_zotero_sync_state_to_paper(paper, state)
    db.commit()
    db.refresh(paper)
    return paper


@router.put("/papers/{paper_id}/knowledge-links/{knowledge_id}", response_model=schemas.PaperOut)
def link_paper_knowledge(paper_id: int, knowledge_id: int, db: Session = Depends(get_db)):
    paper = crud.get_item(db, models.Paper, paper_id)
    knowledge = crud.get_item(db, models.KnowledgeLink, knowledge_id)
    if knowledge not in paper.knowledge_links:
        paper.knowledge_links.append(knowledge)
        db.commit()
        db.refresh(paper)
    return paper


@router.delete("/papers/{paper_id}/knowledge-links/{knowledge_id}", response_model=schemas.PaperOut)
def unlink_paper_knowledge(paper_id: int, knowledge_id: int, db: Session = Depends(get_db)):
    paper = crud.get_item(db, models.Paper, paper_id)
    knowledge = crud.get_item(db, models.KnowledgeLink, knowledge_id)
    if knowledge in paper.knowledge_links:
        paper.knowledge_links.remove(knowledge)
        db.commit()
        db.refresh(paper)
    return paper


@router.get("/papers/{paper_id}/open-links")
def paper_open_links(paper_id: int, db: Session = Depends(get_db)) -> dict:
    paper = crud.get_item(db, models.Paper, paper_id)
    item_key = paper.zotero_item_key or paper.zotero_key
    attachment_key = paper.zotero_attachment_key
    return {
        "article_url": paper.url or paper.source_url or (f"https://doi.org/{paper.doi}" if paper.doi else None),
        "zotero_item_uri": f"zotero://select/library/items/{item_key}" if item_key else None,
        "zotero_attachment_uri": f"zotero://select/library/items/{attachment_key}" if attachment_key else None,
    }


@router.post("/zotero/sync")
async def sync_zotero_papers(db: Session = Depends(get_db)) -> dict:
    papers = db.query(models.Paper).filter(or_(models.Paper.zotero_item_key.is_not(None), models.Paper.zotero_key.is_not(None))).all()
    synced = 0
    failed: list[dict[str, str]] = []
    for paper in papers:
        item_key = paper.zotero_item_key or paper.zotero_key
        if not item_key:
            continue
        try:
            state = await get_zotero_item_sync_state(item_key)
        except Exception as exc:
            failed.append({"item_key": item_key, "title": paper.title, "error": str(exc)})
            continue
        apply_zotero_sync_state_to_paper(paper, state)
        if state.get("title"):
            paper.title = state["title"]
        if state.get("doi"):
            synced_doi = normalize_doi(state["doi"])
            duplicate = db.query(models.Paper).filter(models.Paper.doi == synced_doi, models.Paper.id != paper.id).first() if synced_doi else None
            if synced_doi and duplicate is None:
                paper.doi = synced_doi
        if state.get("url"):
            paper.url = state["url"]
        if state.get("abstract") and not paper.abstract:
            paper.abstract = state["abstract"]
        if state.get("year"):
            paper.year = state["year"]
        if state.get("venue"):
            paper.venue = normalize_venue(state["venue"])
        synced += 1
    db.commit()
    return {"status": "ok", "synced": synced, "failed": failed, "message": f"已同步 Zotero：{synced} 篇文献。"}


@router.post("/papers/{paper_id}/queue", response_model=schemas.PaperOut)
def queue_paper(paper_id: int, payload: schemas.PaperQueueRequest, db: Session = Depends(get_db)):
    paper = crud.get_item(db, models.Paper, paper_id)
    if payload.related_project_id is not None:
        crud.get_item(db, models.Project, payload.related_project_id)
    paper.status = "To Read" if normalize_paper_status(paper.status) in {"Inbox", "Candidate"} else normalize_paper_status(paper.status)
    paper.priority = payload.priority
    paper.reading_purpose = payload.reading_purpose
    paper.related_project_id = payload.related_project_id
    paper.reading_mode = normalize_reading_mode(payload.reading_mode)
    paper.queued_at = paper.queued_at or datetime.utcnow()
    db.commit()
    db.refresh(paper)
    return paper


@router.get("/papers/{paper_id}/detail")
def paper_detail(paper_id: int, db: Session = Depends(get_db)) -> dict:
    paper = crud.get_item(db, models.Paper, paper_id)
    notes = db.query(models.ReadingNote).filter(models.ReadingNote.paper_id == paper_id).order_by(models.ReadingNote.updated_at.desc()).all()
    sessions = db.query(models.FocusSession).filter(models.FocusSession.paper_id == paper_id, models.FocusSession.status != "CANCELLED").all()
    knowledge = [{"id": item.id, "title": item.title, "area": item.area} for item in paper.knowledge_links]
    return {
        "paper": schemas.PaperOut.model_validate(paper).model_dump(mode="json"),
        "reading_notes": [schemas.ReadingNoteOut.model_validate(note).model_dump(mode="json") for note in notes],
        "reading_time_seconds": sum(focus_elapsed_seconds(session) for session in sessions),
        "knowledge_links": knowledge,
    }


@router.delete("/papers/{paper_id}")
def delete_paper(paper_id: int, db: Session = Depends(get_db)):
    return crud.delete_item(db, models.Paper, paper_id)
