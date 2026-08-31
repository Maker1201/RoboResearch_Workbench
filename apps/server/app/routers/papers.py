from __future__ import annotations

import re
from datetime import datetime

import httpx
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
from ..paper_integrations.ai_assistant import ai_configured, ai_settings, draft_reading_note, triage_papers
from ..paper_integrations.zotero import (
    attach_pdf_to_zotero,
    auto_attach_pdf,
    build_existing_item_index,
    ZoteroItemNotFound,
    get_zotero_item_sync_state,
    import_to_zotero,
    list_zotero_library,
    zotero_status,
)
from ..services.dashboard_service import focus_elapsed_seconds
from ..services.papers_service import (
    apply_pdf_state,
    apply_zotero_import_result_to_paper,
    apply_zotero_import_result_to_payload,
    apply_zotero_sync_state_to_paper,
    db_paper_to_search_model,
    find_existing_paper,
    mark_zotero_item_deleted,
    merge_search_papers,
    normalize_doi,
    normalize_paper_status,
    normalize_reading_mode,
    normalize_venue,
    reading_note_template,
    search_paper_to_db_payload,
    title_year_key,
    upsert_paper,
)
from ..services.settings_service import setting_value
from ..services.zotero_storage import (
    ZoteroStorageError,
    extract_pdf_text,
    paper_pdf_text,
    resolve_pdf_path,
)

router = APIRouter()


@router.post("/papers/search", response_model=SearchResponse)
async def search_papers(request: SearchRequest, db: Session = Depends(get_db)) -> SearchResponse:
    openalex_papers = await search_openalex(request)
    crossref_papers = await search_crossref(request)
    papers_by_key = {}
    for paper in [*crossref_papers, *openalex_papers]:
        key = (paper.doi or paper.id).lower()
        current = papers_by_key.get(key)
        papers_by_key[key] = merge_search_papers(current, paper) if current else paper
    papers = sorted(papers_by_key.values(), key=lambda paper: (paper.relevance, paper.year or 0), reverse=True)
    papers = await translate_papers(papers)
    return SearchResponse(papers=await _align_with_local_state(papers, db))


async def _align_with_local_state(papers: list[SearchPaperModel], db: Session) -> list[SearchPaperModel]:
    """给检索结果打上“已在文献库 / 已在 Zotero”标记，避免重复导入。"""
    db_index: dict[str, models.Paper] = {}
    for paper in db.query(models.Paper).limit(1000).all():
        doi = normalize_doi(paper.doi)
        if doi:
            db_index.setdefault(f"doi:{doi}", paper)
        title_key = title_year_key(paper.title, paper.year)
        if title_key:
            db_index.setdefault(f"ty:{title_key}", paper)
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as zotero_client:
            zotero_index = await build_existing_item_index(zotero_client)
    except (httpx.HTTPError, RuntimeError):
        zotero_index = {}

    for paper in papers:
        doi = normalize_doi(paper.doi)
        db_paper = (db_index.get(f"doi:{doi}") if doi else None) or None
        if db_paper is None:
            title_key = title_year_key(paper.title, paper.year)
            if title_key:
                db_paper = db_index.get(f"ty:{title_key}")
        paper.in_library = db_paper is not None
        paper.library_paper_id = db_paper.id if db_paper else None
        paper.library_status = db_paper.status if db_paper else None
        paper.library_pdf_status = db_paper.pdf_status if db_paper else None

        zotero_key = None
        if doi and f"doi:{doi}" in zotero_index:
            zotero_key = zotero_index[f"doi:{doi}"]
        else:
            normalized_title = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", (paper.title or "").lower())).strip()
            year_text = str(paper.year or "")
            candidate = zotero_index.get(f"title:{normalized_title}|year:{year_text}")
            zotero_key = candidate
        paper.in_zotero = zotero_key is not None
        paper.zotero_item_key = zotero_key
    return papers


@router.post("/papers/import-zotero")
async def papers_import_zotero(request: ZoteroImportRequest) -> dict:
    try:
        return await import_to_zotero(request)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _zotero_data_dir(db: Session) -> str | None:
    return setting_value(db, "integrations.zotero.data_dir")


@router.get("/papers/{paper_id}/pdf-text", response_model=schemas.PdfTextOut)
def get_paper_pdf_text(paper_id: int, db: Session = Depends(get_db)):
    """从 Zotero 本地存储读取该论文 PDF 的文本（截断），供调试与 AI 流程使用。"""
    paper = crud.get_item(db, models.Paper, paper_id)
    limit = ai_settings().max_pdf_chars
    try:
        path = resolve_pdf_path(paper, _zotero_data_dir(db))
        text = extract_pdf_text(path, limit)
    except ZoteroStorageError as exc:
        raise HTTPException(status_code=409, detail=f"{exc.code}: {exc.message}") from exc
    return {
        "paper_id": paper.id,
        "pdf_path": str(path),
        "char_count": len(text),
        "truncated": len(text) >= limit,
        "text": text,
    }


@router.post("/papers/ai/triage", response_model=list[schemas.PaperOut])
async def ai_triage_papers(payload: schemas.AITriageRequest | None = None, db: Session = Depends(get_db)):
    """批量 AI 分诊：给阅读队列中的论文生成一句话总结、相关度与建议阅读方式。"""
    if not ai_configured():
        raise HTTPException(status_code=400, detail="AI 未配置：请在 apps/server/.env 中设置 AI_PROVIDER / AI_API_BASE / AI_API_KEY / AI_MODEL。")
    query = db.query(models.Paper)
    if payload and payload.paper_ids:
        query = query.filter(models.Paper.id.in_(payload.paper_ids))
    else:
        query = query.filter(models.Paper.queued_at.is_not(None))
    papers = query.limit(30).all()
    if not papers:
        return []
    results = await triage_papers(papers)
    if not results:
        raise HTTPException(status_code=502, detail="AI 分诊请求失败：模型无有效返回，请检查 AI_API_BASE / AI_API_KEY / AI_MODEL 配置。")
    by_id = {row["id"]: row for row in results}
    now = datetime.utcnow()
    updated: list[models.Paper] = []
    for paper in papers:
        row = by_id.get(paper.id)
        if not row:
            continue
        paper.ai_summary = row["one_liner"]
        paper.ai_relevance = row["relevance"]
        paper.ai_suggested_mode = row["suggested_mode"]
        paper.ai_triaged_at = now
        updated.append(paper)
    db.commit()
    for paper in updated:
        db.refresh(paper)
    return updated


def _note_section_text(note_markdown: str, heading: str) -> str | None:
    """从模板笔记中取出某个小节的正文（到下一个 ## 标题为止）。"""
    lines = note_markdown.splitlines()
    collecting = False
    buffer: list[str] = []
    for line in lines:
        if line.strip() == heading:
            collecting = True
            continue
        if collecting and line.startswith("## "):
            break
        if collecting:
            buffer.append(line)
    text = "\n".join(buffer).strip()
    return text or None


@router.post("/papers/{paper_id}/ai/draft-note", response_model=schemas.AIDraftNoteResponse)
async def ai_draft_paper_note(paper_id: int, db: Session = Depends(get_db)):
    """AI 解析论文内容，按 12 节模板生成阅读笔记草稿。"""
    if not ai_configured():
        raise HTTPException(status_code=400, detail="AI 未配置：请在 apps/server/.env 中设置 AI_PROVIDER / AI_API_BASE / AI_API_KEY / AI_MODEL。")
    paper = crud.get_item(db, models.Paper, paper_id)

    pdf_text: str | None = None
    try:
        pdf_text = paper_pdf_text(paper, _zotero_data_dir(db), max_chars=ai_settings().max_pdf_chars)
    except ZoteroStorageError:
        pdf_text = None

    draft = await draft_reading_note(paper, pdf_text)
    if draft:
        note_source = "ai_draft"
    else:
        draft = reading_note_template(paper)
        note_source = "template"

    existing = db.query(models.ReadingNote).filter(models.ReadingNote.paper_id == paper_id).order_by(models.ReadingNote.updated_at.desc()).first()
    template = reading_note_template(paper)
    manual_content = (existing.content_markdown or existing.content or "").strip() if existing else ""
    if existing and not (existing.note_source in {"ai_draft", "template"} or manual_content in {"", template}):
        item = models.ReadingNote(
            paper_id=paper.id,
            title=f"Reading Note - {paper.title[:220]}",
            status="draft",
            reading_status_snapshot=paper.status,
            reading_mode=paper.reading_mode,
            related_project_id=paper.related_project_id,
        )
        db.add(item)
    else:
        item = existing or models.ReadingNote(
            paper_id=paper.id,
            title=f"Reading Note - {paper.title[:220]}",
            status="draft",
            reading_status_snapshot=paper.status,
            reading_mode=paper.reading_mode,
            related_project_id=paper.related_project_id,
        )
    item.content_markdown = draft
    item.content = draft
    item.note_source = note_source
    item.one_sentence_summary = _note_section_text(draft, "## 2. One Sentence Summary") or item.one_sentence_summary
    if item.id is None:
        db.add(item)
    db.commit()
    db.refresh(item)
    return {"paper_id": paper.id, "note": item, "source": note_source}


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
    except ZoteroItemNotFound:
        mark_zotero_item_deleted(paper, item_key)
        db.commit()
        db.refresh(paper)
        return paper
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


@router.get("/papers/pending-pdfs")
def pending_pdfs(db: Session = Depends(get_db)) -> dict:
    """给浏览器扩展的 CARSI 抓取队列：已关联 Zotero 但还没有 PDF 附件的文献。"""
    papers = db.query(models.Paper).filter(
        or_(models.Paper.zotero_item_key.is_not(None), models.Paper.zotero_key.is_not(None)),
        models.Paper.zotero_pdf_attached.isnot(True),
    ).order_by(models.Paper.updated_at.desc()).limit(50).all()
    pending = []
    for paper in papers:
        item_key = paper.zotero_item_key or paper.zotero_key
        if not item_key:
            continue
        pending.append({
            "item_key": item_key,
            "title": paper.title,
            "doi": paper.doi,
            "pdf_url": paper.pdf_url,
            "url": paper.url or paper.source_url,
            "venue": paper.venue,
        })
    return {"pending_pdfs": pending, "count": len(pending)}


@router.post("/papers/{paper_id}/resolve-pdf", response_model=schemas.PaperOut)
async def resolve_paper_pdf(paper_id: int, db: Session = Depends(get_db)):
    """重新尝试为已有 Zotero 条目自动解析并挂载 PDF（开放获取兜底 + 机构会话）。"""
    paper = crud.get_item(db, models.Paper, paper_id)
    item_key = paper.zotero_item_key or paper.zotero_key
    if not item_key:
        raise HTTPException(status_code=400, detail="该文献尚未关联 Zotero 条目。")
    result = await auto_attach_pdf(item_key, db_paper_to_search_model(paper))
    if result.get("pdf_status") == "ATTACHED":
        apply_pdf_state(
            paper,
            status="ATTACHED",
            source=result.get("pdf_source"),
            attachment_key=result.get("zotero_attachment_key"),
        )
    elif result.get("pdf_error_code"):
        apply_pdf_state(
            paper,
            status=result.get("pdf_status") or "FAILED",
            source=result.get("pdf_source"),
            error_code=result.get("pdf_error_code"),
            error_message=result.get("pdf_error_message"),
        )
    if result.get("pdf_url"):
        paper.pdf_url = result["pdf_url"]
    paper.zotero_synced_at = datetime.utcnow()
    db.commit()
    db.refresh(paper)
    return paper


@router.get("/papers/session-cookies")
def get_session_cookies() -> dict:
    from ..paper_integrations.zotero import session_cookie_hosts

    hosts = session_cookie_hosts()
    return {"hosts": [{"host": host, "cookie_preview": f"{len(value)} 字符"} for host, value in hosts], "count": len(hosts)}


@router.put("/papers/session-cookies")
def put_session_cookies(payload: dict) -> dict:
    """浏览器扩展把出版商站点的机构会话 Cookie 转交给工作台，供服务器端下载使用。"""
    from ..paper_integrations.zotero import save_session_cookie

    host = str(payload.get("host") or "").strip().lower()
    cookie = str(payload.get("cookie") or "").strip()
    if not host or not cookie:
        raise HTTPException(status_code=400, detail="host 和 cookie 不能为空。")
    save_session_cookie(host, cookie)
    return {"ok": True, "host": host}


@router.delete("/papers/session-cookies/{host}")
def delete_session_cookie(host: str) -> dict:
    from ..paper_integrations.zotero import clear_session_cookie

    clear_session_cookie(host.lower())
    return {"ok": True}


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
    deleted = 0
    failed: list[dict[str, str]] = []
    for paper in papers:
        item_key = paper.zotero_item_key or paper.zotero_key
        if not item_key:
            continue
        try:
            state = await get_zotero_item_sync_state(item_key)
        except ZoteroItemNotFound:
            mark_zotero_item_deleted(paper, item_key)
            synced += 1
            deleted += 1
            continue
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
    message = f"已同步 Zotero：{synced} 篇文献。"
    if deleted:
        message += f" 其中 {deleted} 篇已解除不存在的 Zotero 条目关联。"
    return {"status": "ok", "synced": synced, "deleted": deleted, "failed": failed, "message": message}


@router.post("/zotero/pull")
async def pull_from_zotero(db: Session = Depends(get_db)) -> dict:
    """把 Zotero 本地库中的文献（含以前手动添加的）导入/对齐到工作台文献库。"""
    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            items = await list_zotero_library(client)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=400, detail=f"无法连接 Zotero 本地服务：{exc}") from exc

    library_name = setting_value(db, "integrations.zotero.library") or "My Library"
    now = datetime.utcnow()
    imported = 0
    updated = 0
    skipped = 0
    for item in items:
        title = (item.get("title") or "").strip()
        if not title:
            skipped += 1
            continue
        item_key = item["item_key"]
        doi = normalize_doi(item.get("doi"))
        year = item.get("year")
        venue = normalize_venue(item.get("venue")) if item.get("venue") else None
        existing = find_existing_paper(db, title, year, doi)
        if existing is None:
            paper = models.Paper(
                title=title,
                doi=doi,
                year=year,
                venue=venue or "Others",
                abstract=item.get("abstract"),
                url=item.get("url"),
                source_url=item.get("url"),
                status="Inbox",
            )
            db.add(paper)
            db.flush()
            imported += 1
        else:
            paper = existing
            # 只补空字段，不覆盖已有整理结果
            if not paper.doi and doi:
                paper.doi = doi
            if not paper.year and year:
                paper.year = year
            if not paper.abstract and item.get("abstract"):
                paper.abstract = item["abstract"]
            if not paper.url and item.get("url"):
                paper.url = item["url"]
                paper.source_url = item["url"]
            if (not paper.venue or paper.venue == "Others") and venue:
                paper.venue = venue
            updated += 1

        if not paper.zotero_item_key and not paper.zotero_key:
            paper.zotero_item_key = item_key
            paper.zotero_key = item_key
        paper.zotero_library = paper.zotero_library or library_name
        if item.get("pdf_attached") and paper.pdf_status != "ATTACHED":
            apply_pdf_state(paper, status="ATTACHED", source=item.get("pdf_source") or "ZOTERO", attachment_key=item.get("attachment_key"))
        paper.zotero_synced_at = now
    db.commit()
    message = f"已从 Zotero 导入 {imported} 篇新文献，对齐 {updated} 篇已有文献。" + ("有条目缺少标题被跳过。" if skipped else "")
    return {"status": "ok", "imported": imported, "updated": updated, "skipped": skipped, "total": len(items), "message": message}


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
