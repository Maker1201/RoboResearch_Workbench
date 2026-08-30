from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..paper_integrations.models import Paper as SearchPaperModel
from .settings_service import setting_value


def normalize_paper_status(value: str | None) -> str:
    if not value:
        return "Inbox"
    aliases = {"inbox": "Inbox", "candidate": "Candidate", "to_read": "To Read", "to read": "To Read", "skimming": "Skimming", "reading": "Reading", "deep_reading": "Deep Reading", "deep reading": "Deep Reading", "finished": "Finished", "reference": "Reference", "dropped": "Dropped"}
    return aliases.get(value.strip().lower(), value)


def normalize_reading_mode(value: str | None) -> str | None:
    if not value:
        return None
    upper = value.strip().upper().replace(" ", "_")
    mapping = {"SCANNING": "SCAN", "SKIMMING": "SKIM", "READING": "READ", "DEEP_READING": "DEEP"}
    return mapping.get(upper, upper if upper in schemas.READING_MODES else value)


def reading_note_template(paper: models.Paper | None = None) -> str:
    title = paper.title if paper else "Untitled Paper"
    return f"""# Reading Note: {title}

## 1. Why did I read this?

## 2. One Sentence Summary

## 3. Problem

## 4. Core Idea

## 5. Architecture

## 6. Key Technical Details

## 7. Experiments

## 8. What is actually useful to me?

## 9. Limitations

## 10. Questions

## 11. Ideas

## 12. Knowledge to Extract
"""


def normalize_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    return doi.strip().lower().removeprefix("https://doi.org/").removeprefix("http://doi.org/").removeprefix("doi:").strip() or None


def title_year_key(title: str | None, year: int | None) -> str | None:
    if not title:
        return None
    normalized_title = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", title.lower())).strip()
    return f"{normalized_title}|{year or ''}" if normalized_title else None


def find_existing_paper(db: Session, title: str, year: int | None, doi: str | None) -> models.Paper | None:
    normalized = normalize_doi(doi)
    if normalized:
        existing = db.query(models.Paper).filter(func.lower(models.Paper.doi) == normalized).first()
        if existing:
            return existing
    key = title_year_key(title, year)
    if not key:
        return None
    for paper in db.query(models.Paper).filter(models.Paper.year == year).all():
        if title_year_key(paper.title, paper.year) == key:
            return paper
    return None


def normalize_venue(value: str | None) -> str:
    if not value:
        return "Others"
    lower = value.lower()
    if "icra" in lower:
        return "ICRA"
    if "iros" in lower:
        return "IROS"
    if "robotics and automation letters" in lower or "ra-l" in lower or "ral" == lower.strip():
        return "RA-L"
    if "transactions on robotics" in lower or "t-ro" in lower or "tro" == lower.strip():
        return "T-RO"
    if "science robotics" in lower:
        return "Science Robotics"
    return value if value in {"ICRA", "IROS", "RA-L", "T-RO", "Science Robotics"} else "Others"


def search_paper_to_db_payload(paper: SearchPaperModel | dict[str, Any], status: str = "Candidate") -> dict[str, Any]:
    model = paper if isinstance(paper, SearchPaperModel) else SearchPaperModel.model_validate(paper)
    return {
        "title": model.title,
        "translated_title": model.translated_title,
        "abstract": model.abstract,
        "translated_abstract": model.translated_abstract,
        "authors": ", ".join(model.authors),
        "year": model.year,
        "venue": normalize_venue(model.source_label or model.venue),
        "tags": ", ".join(model.matched_keywords),
        "doi": normalize_doi(model.doi),
        "url": model.url,
        "source_url": model.url,
        "pdf_url": model.pdf_url,
        "status": status,
    }


def merge_search_papers(current: SearchPaperModel, incoming: SearchPaperModel) -> SearchPaperModel:
    winner = incoming if incoming.relevance > current.relevance else current
    other = current if winner is incoming else incoming
    updates: dict[str, Any] = {}
    for field in ("pdf_url", "url", "abstract", "translated_abstract", "translated_title", "doi", "venue", "source_label"):
        if not getattr(winner, field) and getattr(other, field):
            updates[field] = getattr(other, field)
    if not winner.is_oa and other.is_oa:
        updates["is_oa"] = True
    keywords = list(dict.fromkeys([*(winner.matched_keywords or []), *(other.matched_keywords or [])]))
    if keywords != winner.matched_keywords:
        updates["matched_keywords"] = keywords
    return winner.model_copy(update=updates) if updates else winner


def db_paper_to_search_model(paper: models.Paper) -> SearchPaperModel:
    tags = [tag.strip() for tag in (paper.tags or "").split(",") if tag.strip()]
    authors = [author.strip() for author in (paper.authors or "").split(",") if author.strip()]
    return SearchPaperModel(
        id=paper.doi or paper.url or f"workbench:{paper.id}",
        title=paper.title,
        translated_title=paper.translated_title,
        abstract=paper.abstract,
        translated_abstract=paper.translated_abstract,
        authors=authors,
        year=paper.year,
        venue=paper.venue,
        source_id=paper.venue,
        source_label=paper.venue,
        doi=paper.doi,
        url=paper.url,
        pdf_url=paper.pdf_url,
        is_oa=bool(paper.pdf_url),
        matched_keywords=tags,
    )


def apply_pdf_state(
    paper: models.Paper,
    *,
    status: str,
    source: str | None = None,
    attachment_key: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    paper.pdf_status = status
    paper.zotero_pdf_status = status
    paper.zotero_pdf_attached = status == "ATTACHED"
    if source is not None:
        paper.pdf_source = source
    if attachment_key:
        paper.zotero_attachment_key = attachment_key
    paper.pdf_error_code = error_code
    paper.pdf_error_message = (error_message or "")[:500] or None
    paper.pdf_last_checked_at = datetime.utcnow()
    paper.zotero_synced_at = datetime.utcnow()


def apply_zotero_sync_state_to_paper(paper: models.Paper, state: dict[str, Any]) -> None:
    attachment_key = state.get("zotero_attachment_key")
    if state.get("pdf_status") == "ATTACHED" or attachment_key:
        apply_pdf_state(
            paper,
            status="ATTACHED",
            source=state.get("pdf_source") or "ZOTERO",
            attachment_key=attachment_key,
        )
    else:
        apply_pdf_state(
            paper,
            status="NONE",
            source=state.get("pdf_source"),
            error_code="PDF_NOT_FOUND",
            error_message="No PDF child attachment was found in Zotero.",
        )


def upsert_paper(db: Session, data: dict[str, Any]) -> models.Paper:
    existing = find_existing_paper(db, data["title"], data.get("year"), data.get("doi"))
    if existing:
        for key, value in data.items():
            if value is not None and (key != "status" or existing.status in {"inbox", "Inbox", "Candidate"}):
                setattr(existing, key, value)
        db.commit()
        db.refresh(existing)
        return existing
    item = models.Paper(**data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def zotero_item_result(zotero_result: dict, index: int = 0) -> dict[str, Any]:
    for item in zotero_result.get("item_results") or []:
        if item.get("index") == index:
            return item
    item_keys = zotero_result.get("item_keys") or []
    item_key = item_keys[index] if len(item_keys) > index else None
    return {"item_key": item_key, "pdf_attached": False, "pdf_status": "unknown"}


def apply_zotero_import_result_to_payload(db: Session, data: dict[str, Any], zotero_result: dict, index: int = 0) -> None:
    item = zotero_item_result(zotero_result, index)
    item_key = item.get("item_key")
    if item_key:
        data["zotero_item_key"] = item_key
        data["zotero_key"] = item_key
    data["zotero_library"] = setting_value(db, "integrations.zotero.library") or "My Library"
    pdf_status = item.get("pdf_status") or ("ATTACHED" if item.get("pdf_attached") else "NONE")
    data["zotero_attachment_key"] = item.get("zotero_attachment_key")
    data["zotero_pdf_attached"] = pdf_status == "ATTACHED"
    data["zotero_pdf_status"] = pdf_status
    data["pdf_status"] = pdf_status
    data["pdf_source"] = item.get("pdf_source")
    data["pdf_last_checked_at"] = datetime.utcnow()
    data["pdf_error_code"] = item.get("pdf_error_code")
    data["pdf_error_message"] = item.get("pdf_error_message")
    data["zotero_synced_at"] = datetime.utcnow()
    if item.get("pdf_url"):
        data["pdf_url"] = item["pdf_url"]


def apply_zotero_import_result_to_paper(db: Session, paper: models.Paper, zotero_result: dict, index: int = 0) -> None:
    data: dict[str, Any] = {}
    apply_zotero_import_result_to_payload(db, data, zotero_result, index)
    for key, value in data.items():
        setattr(paper, key, value)


def safe_markdown_filename(title: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", title).strip("-._").lower()[:100]
    return f"{slug or 'reading-note'}.md"


def note_content(note: models.ReadingNote) -> str:
    return note.content_markdown or note.content or ""
