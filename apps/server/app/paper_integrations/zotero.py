from __future__ import annotations

import base64
import hashlib
import re
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any, Callable
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse
import httpx

from .models import Paper, ZoteroAttachPdfRequest, ZoteroImportRequest

ZOTERO_BASE_URL = "http://127.0.0.1:23119/api"
ZOTERO_APP_NAME = "Academic Paper Finder"
MAX_PDF_BYTES = 80 * 1024 * 1024
BIBLIOGRAPHIC_ITEM_TYPES = {
    "journalArticle",
    "conferencePaper",
    "preprint",
    "report",
    "bookSection",
    "thesis",
}

_zotero_key: str | None = None
_zotero_server_id: str | None = None
_key_loader: Callable[[], str | None] | None = None
_key_saver: Callable[[str], None] | None = None


def configure_key_store(loader: Callable[[], str | None], saver: Callable[[str], None]) -> None:
    """让授权 key 可以在进程重启后从本地持久层恢复。"""
    global _key_loader, _key_saver
    _key_loader = loader
    _key_saver = saver


def _current_key() -> str | None:
    global _zotero_key
    if _zotero_key:
        return _zotero_key
    if _key_loader:
        try:
            stored = _key_loader()
        except Exception:
            stored = None
        if stored:
            _zotero_key = stored
    return _zotero_key


def _persist_key(key: str) -> None:
    if _key_saver:
        try:
            _key_saver(key)
        except Exception:
            pass


@dataclass
class ZoteroWriteResult:
    imported: int
    collections: dict[str, str]
    item_keys: list[str]
    attached_pdfs: int
    skipped_pdfs: int
    pending_pdfs: list[dict[str, str | None]]
    reused: int
    created: int
    item_results: list[dict[str, Any]]


@dataclass
class ZoteroPdfAttachment:
    key: str
    source: str


@dataclass
class PdfResolution:
    status: str
    source: str | None = None
    content: bytes | None = None
    content_type: str | None = None
    url: str | None = None
    error_code: str | None = None
    error_message: str | None = None


RESTRICTED_PUBLISHER_HOSTS = (
    "ieeexplore.ieee.org",
    "sciencedirect.com",
    "www.sciencedirect.com",
    "link.springer.com",
    "dl.acm.org",
)
PUBLIC_REPOSITORY_HOST_HINTS = (
    "arxiv.org",
    "openreview.net",
    "proceedings.mlr.press",
    "aclanthology.org",
    "biorxiv.org",
    "medrxiv.org",
    "pmc.ncbi.nlm.nih.gov",
)
HTML_AUTH_HINTS = (
    "sign in",
    "login",
    "institutional login",
    "authentication",
    "access denied",
    "purchase access",
    "subscribe",
    "shibboleth",
    "saml",
    "carsi",
    "captcha",
)


async def zotero_status() -> dict:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{ZOTERO_BASE_URL}/")
            response.raise_for_status()
        return {
            "available": True,
            "version": response.headers.get("X-Zotero-Version"),
            "api_version": response.headers.get("Zotero-API-Version"),
            "server_id": response.headers.get("Zotero-Server-ID"),
            "authorized": bool(_current_key()),
        }
    except httpx.HTTPError as exc:
        return {"available": False, "authorized": False, "error": str(exc)}


async def import_to_zotero(payload: ZoteroImportRequest) -> dict:
    if not payload.papers:
        return {
            "status": "empty",
            "message": "没有选中的论文。",
            "collection_root": payload.collection_root,
            "paper_count": 0,
        }

    unique_papers, duplicate_count = _dedupe_selected_papers(payload.papers)
    unique_payload = payload.model_copy(update={"papers": unique_papers})

    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        server_id = await _get_server_id(client)
        api_key = await _ensure_api_key(client, server_id)
        collections = await _ensure_collection_tree(client, server_id, api_key, unique_payload)
        result = await _create_items(client, server_id, api_key, unique_papers, collections)

    message = f"已加入 Zotero：{result.imported} 篇论文（新建 {result.created}，复用 {result.reused}"
    if duplicate_count:
        message += f"，本次选择跳过重复 {duplicate_count}"
    message += "）"
    if result.attached_pdfs:
        message += f"，并挂载 {result.attached_pdfs} 个 PDF"
    if result.skipped_pdfs:
        message += f"，{result.skipped_pdfs} 个 PDF 未自动挂载，可稍后同步或手动获取"
    message += "。"

    return {
        "status": "ok",
        "message": message,
        "collection_root": payload.collection_root,
        "paper_count": len(payload.papers),
        "unique_paper_count": len(unique_papers),
        "duplicate_selection_count": duplicate_count,
        "imported": result.imported,
        "attached_pdfs": result.attached_pdfs,
        "skipped_pdfs": result.skipped_pdfs,
        "collections": result.collections,
        "item_keys": result.item_keys,
        "pending_pdfs": result.pending_pdfs,
        "reused": result.reused,
        "created": result.created,
        "item_results": result.item_results,
    }


def _dedupe_selected_papers(papers: list[Paper]) -> tuple[list[Paper], int]:
    seen: set[str] = set()
    unique: list[Paper] = []
    duplicates = 0
    for paper in papers:
        key = _paper_identity_key(paper)
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        unique.append(paper)
    return unique, duplicates


def _paper_identity_key(paper: Paper) -> str:
    doi = _normalize_doi(paper.doi)
    if doi:
        return f"doi:{doi}"
    title_key = _title_year_key(paper.title, str(paper.year or ""))
    if title_key:
        return title_key
    return f"id:{paper.id}"


async def _get_server_id(client: httpx.AsyncClient) -> str:
    global _zotero_server_id
    response = await client.get(f"{ZOTERO_BASE_URL}/")
    response.raise_for_status()
    server_id = response.headers.get("Zotero-Server-ID")
    if not server_id:
        raise RuntimeError("Zotero 本地 API 没有返回 Zotero-Server-ID。")
    _zotero_server_id = server_id
    return server_id


async def _ensure_api_key(client: httpx.AsyncClient, server_id: str) -> str:
    stored = _current_key()
    if stored:
        return stored

    response = await client.post(
        f"{ZOTERO_BASE_URL}/local/authorize",
        headers={"Zotero-Server-ID": server_id, "Content-Type": "application/json"},
        json={"appName": ZOTERO_APP_NAME},
    )
    if response.status_code == 403:
        raise RuntimeError("Zotero 写入授权被拒绝。")
    if response.status_code == 429:
        raise RuntimeError("Zotero 授权请求太频繁，请稍后再试。")
    response.raise_for_status()
    key = response.json().get("key")
    if not key:
        raise RuntimeError("Zotero 授权成功但没有返回 API Key。")
    global _zotero_key
    _zotero_key = key
    _persist_key(key)
    return key


async def _ensure_collection_tree(
    client: httpx.AsyncClient,
    server_id: str,
    api_key: str,
    payload: ZoteroImportRequest,
) -> dict[str, str]:
    existing = await _get_collections(client)
    root_key = await _ensure_collection(client, server_id, api_key, existing, payload.collection_root, False)

    source_labels = sorted({paper.source_label or paper.venue or "Unclassified" for paper in payload.papers})
    result = {"__root__": root_key}
    for label in source_labels:
        result[label] = await _ensure_collection(client, server_id, api_key, existing, label, root_key)
    return result


async def _get_collections(client: httpx.AsyncClient) -> dict[tuple[str, str | bool], str]:
    response = await client.get(f"{ZOTERO_BASE_URL}/users/0/collections?limit=1000")
    response.raise_for_status()
    collections: dict[tuple[str, str | bool], str] = {}
    for item in response.json():
        data = item.get("data", item)
        name = data.get("name")
        key = data.get("key") or item.get("key")
        parent = data.get("parentCollection", False)
        if name and key:
            collections[(name, parent or False)] = key
    return collections


async def _ensure_collection(
    client: httpx.AsyncClient,
    server_id: str,
    api_key: str,
    existing: dict[tuple[str, str | bool], str],
    name: str,
    parent: str | bool,
) -> str:
    lookup = (name, parent or False)
    if lookup in existing:
        return existing[lookup]

    response = await client.post(
        f"{ZOTERO_BASE_URL}/users/0/collections",
        headers=_json_write_headers(server_id, api_key),
        json=[{"name": name, "parentCollection": parent or False}],
    )
    response.raise_for_status()
    key = _first_successful_key(response.json())
    if not key:
        raise RuntimeError(f"Zotero Collection 创建失败：{name}")
    existing[lookup] = key
    return key


async def _create_items(
    client: httpx.AsyncClient,
    server_id: str,
    api_key: str,
    papers: list[Paper],
    collections: dict[str, str],
) -> ZoteroWriteResult:
    existing = await _build_existing_item_index(client)
    item_keys_by_index: dict[int, str] = {}
    reused_by_index: set[int] = set()
    created_by_index: set[int] = set()
    created = 0
    reused = 0

    for index, paper in enumerate(papers):
        collection_key = collections.get(paper.source_label or paper.venue or "Unclassified", collections["__root__"])
        existing_key = _find_existing_item_key(existing, paper)
        if existing_key:
            reused += 1
            item_keys_by_index[index] = existing_key
            reused_by_index.add(index)
            await _ensure_item_in_collection(client, server_id, api_key, existing_key, collection_key)
            continue

        response = await client.post(
            f"{ZOTERO_BASE_URL}/users/0/items",
            headers=_json_write_headers(server_id, api_key),
            json=[_paper_to_zotero_item(paper, collection_key)],
        )
        if response.status_code == 401:
            global _zotero_key
            _zotero_key = None
            raise RuntimeError("Zotero 授权已失效，请再次点击加入 Zotero 并在弹窗中授权。")
        response.raise_for_status()
        key = _first_successful_key(response.json())
        if key:
            created += 1
            item_keys_by_index[index] = key
            created_by_index.add(index)
            _add_to_existing_index(existing, paper, key)

    attached_by_index: dict[int, bool] = {}
    pdf_status_by_index: dict[int, str] = {}
    attached_pdfs = 0
    skipped_pdfs = 0
    for index, paper in enumerate(papers):
        parent_key = item_keys_by_index.get(index)
        if not parent_key:
            continue
        existing_attachment = await _find_pdf_attachment(client, parent_key)
        if existing_attachment:
            attached_by_index[index] = True
            pdf_status_by_index[index] = "ATTACHED"
            continue
        attach_result = await _attach_pdf_from_url(client, server_id, api_key, parent_key, paper)
        ok = attach_result.get("pdf_status") == "ATTACHED"
        attached_by_index[index] = ok
        pdf_status_by_index[index] = attach_result.get("pdf_status", "FAILED")
        if ok:
            attached_pdfs += 1
        else:
            skipped_pdfs += 1

    keys = [item_keys_by_index[index] for index in sorted(item_keys_by_index)]
    item_results = []
    for index, paper in enumerate(papers):
        item_key = item_keys_by_index.get(index)
        if not item_key:
            item_results.append({"index": index, "title": paper.title, "status": "failed", "item_key": None, "pdf_attached": False, "pdf_status": "FAILED", "pdf_error_code": "ZOTERO_ATTACHMENT_WRITE_FAILED", "reused": False})
            continue
        attachment = await _find_pdf_attachment(client, item_key)
        pdf_status = "ATTACHED" if attachment else pdf_status_by_index.get(index, "NONE")
        item_results.append({
            "index": index,
            "title": paper.title,
            "doi": paper.doi,
            "item_key": item_key,
            "status": "ok",
            "pdf_attached": pdf_status == "ATTACHED",
            "pdf_status": pdf_status,
            "pdf_source": attachment.source if attachment else None,
            "zotero_attachment_key": attachment.key if attachment else None,
            "pdf_error_code": None if attachment else _pdf_error_code_for_status(pdf_status),
            "pdf_error_message": None if attachment else _pdf_message_for_status(pdf_status),
            "reused": index in reused_by_index,
            "created": index in created_by_index,
        })
    pending_pdfs = []
    for index, paper in enumerate(papers):
        parent_key = item_keys_by_index.get(index)
        if not parent_key or attached_by_index.get(index):
            continue
        pending_pdfs.append({
            "item_key": parent_key,
            "title": paper.title,
            "url": paper.url,
            "doi": paper.doi,
            "source_label": paper.source_label,
            "pdf_url": paper.pdf_url,
        })
    return ZoteroWriteResult(
        imported=len(keys),
        collections=collections,
        item_keys=keys,
        attached_pdfs=attached_pdfs,
        skipped_pdfs=skipped_pdfs,
        pending_pdfs=pending_pdfs,
        reused=reused,
        created=created,
        item_results=item_results,
    )


async def _build_existing_item_index(client: httpx.AsyncClient) -> dict[str, str]:
    index: dict[str, str] = {}
    start = 0
    while True:
        response = await client.get(
            f"{ZOTERO_BASE_URL}/users/0/items/top",
            params={"limit": 100, "start": start, "itemType": "-attachment"},
        )
        response.raise_for_status()
        items = response.json()
        if not items:
            break
        for item in items:
            data = item.get("data", item)
            key = data.get("key") or item.get("key")
            if not key or data.get("itemType") not in BIBLIOGRAPHIC_ITEM_TYPES:
                continue
            doi = _normalize_doi(data.get("DOI"))
            if doi:
                index[f"doi:{doi}"] = key
            title_key = _title_year_key(data.get("title"), data.get("date"))
            if title_key:
                index[title_key] = key
        if len(items) < 100:
            break
        start += 100
    return index


def _find_existing_item_key(index: dict[str, str], paper: Paper) -> str | None:
    doi = _normalize_doi(paper.doi)
    if doi and f"doi:{doi}" in index:
        return index[f"doi:{doi}"]
    title_key = _title_year_key(paper.title, str(paper.year or ""))
    if title_key:
        return index.get(title_key)
    return None


def _add_to_existing_index(index: dict[str, str], paper: Paper, key: str) -> None:
    doi = _normalize_doi(paper.doi)
    if doi:
        index[f"doi:{doi}"] = key
    title_key = _title_year_key(paper.title, str(paper.year or ""))
    if title_key:
        index[title_key] = key


async def _ensure_item_in_collection(
    client: httpx.AsyncClient,
    server_id: str,
    api_key: str,
    item_key: str,
    collection_key: str,
) -> None:
    response = await client.get(f"{ZOTERO_BASE_URL}/users/0/items/{item_key}")
    response.raise_for_status()
    item = response.json().get("data", response.json())
    collections = item.get("collections", [])
    if collection_key in collections:
        return
    item["collections"] = [*collections, collection_key]
    version = str(item.get("version", response.headers.get("Last-Modified-Version", "0")))
    put_response = await client.put(
        f"{ZOTERO_BASE_URL}/users/0/items/{item_key}",
        headers={**_json_write_headers(server_id, api_key), "If-Unmodified-Since-Version": version},
        json=item,
    )
    put_response.raise_for_status()


async def _item_has_pdf_attachment(client: httpx.AsyncClient, item_key: str) -> bool:
    return bool(await _find_pdf_attachment(client, item_key))


async def _find_pdf_attachment(client: httpx.AsyncClient, item_key: str) -> ZoteroPdfAttachment | None:
    response = await client.get(f"{ZOTERO_BASE_URL}/users/0/items/{item_key}/children")
    response.raise_for_status()
    for child in response.json():
        data = child.get("data", child)
        if data.get("itemType") != "attachment":
            continue
        if not _is_pdf_attachment(child):
            continue
        key = data.get("key") or child.get("key")
        if key:
            return ZoteroPdfAttachment(key=key, source=_attachment_source(data))
    return None


def _is_pdf_attachment(child: dict[str, Any]) -> bool:
    data = child.get("data", child)
    content_type = (data.get("contentType") or "").split(";", 1)[0].strip().lower()
    filename = (data.get("filename") or data.get("title") or data.get("path") or "").lower()
    if content_type != "application/pdf" and not filename.endswith(".pdf"):
        return False
    link_mode = data.get("linkMode")
    has_linked_path = link_mode == "linked_file" and bool(data.get("path"))
    has_imported_file = link_mode in {"imported_file", "imported_url"} and (
        bool(data.get("md5")) or bool(child.get("links", {}).get("enclosure", {}).get("href")) or bool(data.get("filename"))
    )
    return has_linked_path or has_imported_file


def _attachment_source(data: dict[str, Any]) -> str:
    tags = {str(tag.get("tag", "")).upper() for tag in data.get("tags", []) if isinstance(tag, dict)}
    if "LOCAL_FILE" in tags or "MANUAL" in tags:
        return "LOCAL_FILE"
    if data.get("url"):
        return "ZOTERO_CONNECTOR"
    return "ZOTERO"


async def get_zotero_item_sync_state(item_key: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        server_id = await _get_server_id(client)
        api_key = await _ensure_api_key(client, server_id)
        response = await client.get(f"{ZOTERO_BASE_URL}/users/0/items/{item_key}", headers=_auth_headers(server_id, api_key))
        response.raise_for_status()
        item_payload = response.json()
        data = item_payload.get("data", item_payload)
        attachment = await _find_pdf_attachment(client, item_key)
        return {
            "item_key": item_key,
            "title": data.get("title"),
            "doi": _normalize_doi(data.get("DOI")),
            "url": data.get("url"),
            "abstract": data.get("abstractNote"),
            "year": _year_from_date(data.get("date")),
            "venue": data.get("publicationTitle") or data.get("conferenceName") or data.get("proceedingsTitle"),
            "pdf_attached": bool(attachment),
            **_pdf_attachment_state(attachment),
        }


async def _attach_pdf_from_url(
    client: httpx.AsyncClient,
    server_id: str,
    api_key: str,
    parent_key: str,
    paper: Paper,
) -> dict[str, str | None]:
    try:
        resolved = await _resolve_pdf_for_paper(client, paper)
        if resolved.content:
            filename = _pdf_filename(paper)
            attachment_key = await _attach_pdf_bytes(
                client=client,
                server_id=server_id,
                api_key=api_key,
                parent_key=parent_key,
                content=resolved.content,
                content_type=resolved.content_type or "application/pdf",
                filename=filename,
                source_url=resolved.url,
                tags=["PDF", resolved.source or "DIRECT_DOWNLOAD"],
            )
            if attachment_key:
                return {"pdf_status": "ATTACHED", "pdf_source": resolved.source, "zotero_attachment_key": attachment_key}
            return {"pdf_status": "FAILED", "pdf_error_code": "ZOTERO_ATTACHMENT_WRITE_FAILED", "pdf_error_message": "PDF downloaded but Zotero attachment write failed."}
        return {"pdf_status": resolved.status, "pdf_source": resolved.source, "pdf_error_code": resolved.error_code, "pdf_error_message": resolved.error_message}
    except (KeyError, httpx.HTTPError):
        return {"pdf_status": "FAILED", "pdf_error_code": "NETWORK_ERROR", "pdf_error_message": "Network error while resolving PDF."}


async def _resolve_pdf_for_paper(client: httpx.AsyncClient, paper: Paper) -> PdfResolution:
    candidates = _seed_pdf_candidates(paper)
    if not candidates:
        article_url = paper.url or _doi_url(paper.doi)
        if article_url and _is_restricted_publisher_url(article_url):
            return PdfResolution(status="BROWSER_REQUIRED", error_code="BROWSER_REQUIRED", error_message="Publisher page likely needs browser login, institutional access, or JavaScript.")
        return PdfResolution(status="NONE", error_code="PDF_NOT_FOUND", error_message="No direct or open-access PDF URL is available.")

    last_status = PdfResolution(status="FAILED", error_code="PDF_NOT_FOUND", error_message="No valid PDF response found.")
    discovered_pages: set[str] = set()
    for candidate in list(candidates):
        pdf = await _download_pdf(client, candidate)
        if pdf.content:
            return pdf
        last_status = _prefer_actionable_resolution(last_status, pdf)

        if candidate in discovered_pages or not _may_discover_pdf_links(candidate, paper):
            continue
        discovered_pages.add(candidate)
        for discovered in await _discover_pdf_urls_from_page(client, candidate):
            if discovered not in candidates:
                candidates.append(discovered)

    for candidate in candidates:
        pdf = await _download_pdf(client, candidate)
        if pdf.content:
            return pdf
        last_status = _prefer_actionable_resolution(last_status, pdf)
    return last_status


def _seed_pdf_candidates(paper: Paper) -> list[str]:
    candidates: list[str] = []
    for url in (paper.pdf_url, *_known_pdf_url_variants(paper.url), *_known_pdf_url_variants(_doi_url(paper.doi))):
        if url and url not in candidates:
            candidates.append(url)
    return candidates


def _doi_url(doi: str | None) -> str | None:
    normalized = _normalize_doi(doi)
    return f"https://doi.org/{normalized}" if normalized else None


def _known_pdf_url_variants(url: str | None) -> list[str]:
    if not url:
        return []
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path
    result = [url]

    if "arxiv.org" in host and "/abs/" in path:
        paper_id = path.split("/abs/", 1)[1].strip("/")
        result.append(urlunparse((parsed.scheme, parsed.netloc, f"/pdf/{paper_id}.pdf", "", "", "")))
    if "openreview.net" in host:
        query = parse_qs(parsed.query)
        paper_id = (query.get("id") or [None])[0]
        if paper_id:
            result.append(urlunparse((parsed.scheme, parsed.netloc, "/pdf", "", urlencode({"id": paper_id}), "")))
    if "ieeexplore.ieee.org" in host:
        match = re.search(r"/document/(\d+)", path)
        if match:
            article_number = match.group(1)
            result.append(f"https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber={article_number}")
            result.append(f"https://ieeexplore.ieee.org/stampPDF/getPDF.jsp?tp=&arnumber={article_number}")
            result.append(f"https://ieeexplore.ieee.org/stampPDF/getPDF.jsp?tp=&arnumber={article_number}&ref=")
    if "proceedings.mlr.press" in host and path.endswith(".html"):
        result.append(urlunparse((parsed.scheme, parsed.netloc, path[:-5] + ".pdf", "", "", "")))
    if "aclanthology.org" in host and not path.lower().endswith(".pdf"):
        result.append(url.rstrip("/") + ".pdf")

    return list(dict.fromkeys(result))


async def _discover_pdf_urls_from_page(client: httpx.AsyncClient, url: str) -> list[str]:
    html = await _download_html(client, url)
    if not html:
        return []
    parser = PdfLinkParser(url)
    parser.feed(html)
    return parser.urls


async def _download_html(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        response = await client.get(url, headers={"Accept": "text/html,application/xhtml+xml,*/*"})
        response.raise_for_status()
    except httpx.HTTPError:
        return None
    content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
    if content_type and "html" not in content_type and content_type != "text/plain":
        return None
    text = response.text
    return text[:2_000_000]


PDF_LINK_HINTS = ("pdf", "full text", "fulltext", "download")


class PdfLinkParser(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url
        self.urls: list[str] = []
        self._pending_href: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key.lower(): value or "" for key, value in attrs}
        if tag == "meta":
            name = (attr.get("name") or attr.get("property") or "").lower()
            if name in {"citation_pdf_url", "bepress_citation_pdf_url", "eprints.document_url"}:
                self._add(attr.get("content"))
        if tag == "link":
            descriptor = " ".join([attr.get("rel", ""), attr.get("type", ""), attr.get("title", "")]).lower()
            if _has_pdf_link_hint(descriptor):
                self._add(attr.get("href"))
        if tag in {"iframe", "embed", "object"}:
            href = attr.get("src") or attr.get("data")
            descriptor = " ".join([href or "", attr.get("type", ""), attr.get("title", ""), attr.get("aria-label", ""), attr.get("class", "")]).lower()
            if _has_pdf_link_hint(descriptor):
                self._add(href)
        if tag == "a":
            href = attr.get("href")
            descriptor = " ".join([href or "", attr.get("type", ""), attr.get("title", ""), attr.get("aria-label", ""), attr.get("class", "")]).lower()
            if _has_pdf_link_hint(descriptor) or (href and href.lower().endswith(".pdf")):
                self._add(href)
            self._pending_href = href

    def handle_data(self, data: str) -> None:
        if self._pending_href and _has_pdf_link_hint(data.lower()):
            self._add(self._pending_href)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self._pending_href = None

    def _add(self, url: str | None) -> None:
        if not url or url.startswith(("mailto:", "javascript:")):
            return
        absolute = urljoin(self.base_url, url)
        if absolute not in self.urls:
            self.urls.append(absolute)


def _has_pdf_link_hint(value: str) -> bool:
    return any(hint in value for hint in PDF_LINK_HINTS)


async def attach_pdf_to_zotero(payload: ZoteroAttachPdfRequest) -> dict:
    try:
        content = base64.b64decode(payload.content_base64)
    except ValueError as exc:
        raise RuntimeError("PDF 内容不是有效的 base64。") from exc
    if not content.startswith(b"%PDF"):
        raise RuntimeError("捕获到的内容不是 PDF 文件。")
    if len(content) > MAX_PDF_BYTES:
        raise RuntimeError("PDF 文件过大，暂不自动挂载。")

    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        server_id = await _get_server_id(client)
        api_key = await _ensure_api_key(client, server_id)
        existing = await _find_pdf_attachment(client, payload.item_key)
        if existing:
            return {"status": "skipped", "message": "该条目已有 PDF 附件，已跳过重复挂载。", "item_key": payload.item_key, "attachment_key": existing.key, "pdf_source": existing.source}
        filename = payload.filename or "paper.pdf"
        attachment_key = await _attach_pdf_bytes(
            client=client,
            server_id=server_id,
            api_key=api_key,
            parent_key=payload.item_key,
            content=content,
            content_type=payload.content_type or "application/pdf",
            filename=filename,
            source_url=payload.pdf_url,
            tags=["PDF", payload.source or "MANUAL"],
        )
    if not attachment_key:
        raise RuntimeError("PDF 已捕获，但写入 Zotero 附件失败。")
    return {"status": "ok", "message": "PDF 已挂载到 Zotero。", "item_key": payload.item_key, "attachment_key": attachment_key, "pdf_source": payload.source or "MANUAL"}



async def _attach_pdf_bytes(
    client: httpx.AsyncClient,
    server_id: str,
    api_key: str,
    parent_key: str,
    content: bytes,
    content_type: str,
    filename: str,
    source_url: str | None,
    tags: list[str] | None = None,
) -> str | None:
    try:
        md5 = hashlib.md5(content).hexdigest()
        mtime = int(time.time() * 1000)
        attachment = {
            "itemType": "attachment",
            "parentItem": parent_key,
            "linkMode": "imported_url" if source_url else "imported_file",
            "title": filename,
            "accessDate": _zotero_timestamp(),
            "url": source_url or "",
            "note": "",
            "tags": [{"tag": tag} for tag in (tags or ["PDF"])],
            "relations": {},
            "contentType": content_type or "application/pdf",
            "charset": "",
            "filename": filename,
            "md5": None,
            "mtime": None,
        }
        response = await client.post(
            f"{ZOTERO_BASE_URL}/users/0/items",
            headers=_json_write_headers(server_id, api_key),
            json=[attachment],
        )
        response.raise_for_status()
        attachment_key = _first_successful_key(response.json())
        if not attachment_key:
            return None
        ok = await _upload_file_to_attachment(
            client, server_id, api_key, attachment_key, content, content_type, filename, md5, mtime
        )
        return attachment_key if ok else None
    except (KeyError, httpx.HTTPError):
        return None


async def _upload_file_to_attachment(
    client: httpx.AsyncClient,
    server_id: str,
    api_key: str,
    attachment_key: str,
    content: bytes,
    content_type: str,
    filename: str,
    md5: str,
    mtime: int,
) -> bool:
    auth_response = await client.post(
        f"{ZOTERO_BASE_URL}/users/0/items/{attachment_key}/file",
        headers={**_auth_headers(server_id, api_key), "If-None-Match": "*"},
        data={
            "md5": md5,
            "filename": filename,
            "filesize": str(len(content)),
            "mtime": str(mtime),
            "contentType": content_type or "application/pdf",
        },
    )
    auth_response.raise_for_status()
    upload_auth = auth_response.json()
    if upload_auth.get("exists"):
        return True

    upload_url = _absolute_zotero_url(upload_auth["url"])
    upload_body = upload_auth.get("prefix", "").encode() + content + upload_auth.get("suffix", "").encode()
    upload_response = await client.post(
        upload_url,
        headers={"Content-Type": upload_auth.get("contentType", "application/octet-stream")},
        content=upload_body,
    )
    upload_response.raise_for_status()

    register_response = await client.post(
        f"{ZOTERO_BASE_URL}/users/0/items/{attachment_key}/file",
        headers={**_auth_headers(server_id, api_key), "If-None-Match": "*"},
        data={"upload": upload_auth["uploadKey"]},
    )
    register_response.raise_for_status()
    return True


def _pdf_request_headers(url: str) -> dict[str, str]:
    headers = {
        "Accept": "application/pdf,text/html;q=0.9,*/*;q=0.8",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    }
    parsed = urlparse(url)
    if "ieeexplore.ieee.org" in parsed.netloc.lower():
        article_number = (parse_qs(parsed.query).get("arnumber") or [None])[0]
        if not article_number:
            match = re.search(r"/document/(\d+)", parsed.path)
            article_number = match.group(1) if match else None
        if article_number:
            headers["Referer"] = f"https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber={article_number}"
    return headers


async def _download_pdf(client: httpx.AsyncClient, url: str | None) -> PdfResolution:
    if not url:
        return PdfResolution(status="NONE", error_code="PDF_NOT_FOUND", error_message="No PDF URL was provided.")
    try:
        response = await client.get(url, headers=_pdf_request_headers(url))
        response.raise_for_status()
    except httpx.HTTPError:
        code = "AUTH_REQUIRED" if _is_restricted_publisher_url(url) else "NETWORK_ERROR"
        return PdfResolution(status=code, error_code=code, error_message="Could not fetch PDF URL automatically.")

    content = response.content
    content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
    if not content:
        return PdfResolution(status="FAILED", error_code="INVALID_PDF_RESPONSE", error_message="Empty PDF response.")
    if len(content) > MAX_PDF_BYTES:
        return PdfResolution(status="FAILED", error_code="INVALID_PDF_RESPONSE", error_message="PDF response is larger than the supported limit.")
    if content.startswith(b"%PDF-"):
        source = "OPEN_ACCESS" if _is_public_repository_url(url) else "DIRECT_DOWNLOAD"
        return PdfResolution(status="AVAILABLE", source=source, content=content, content_type="application/pdf", url=url)
    if content_type == "application/pdf":
        return PdfResolution(status="FAILED", error_code="INVALID_PDF_RESPONSE", error_message="Response claimed to be a PDF but did not contain a PDF header.")
    text = content[:8000].decode("utf-8", errors="ignore").lower()
    if content_type in {"text/html", "application/xhtml+xml"} or "<html" in text:
        if _is_restricted_publisher_url(url) or any(hint in text for hint in HTML_AUTH_HINTS):
            return PdfResolution(status="AUTH_REQUIRED", error_code="AUTH_REQUIRED", error_message="PDF requires browser login or institutional access.")
        return PdfResolution(status="BROWSER_REQUIRED", error_code="BROWSER_REQUIRED", error_message="PDF URL returned an HTML page; use browser/Zotero Connector.")
    return PdfResolution(status="FAILED", error_code="INVALID_PDF_RESPONSE", error_message="Response is not a valid PDF.")


def _pdf_attachment_state(attachment: ZoteroPdfAttachment | None) -> dict[str, str | bool | None]:
    if not attachment:
        return {"pdf_status": "NONE", "pdf_source": None, "zotero_attachment_key": None}
    return {"pdf_status": "ATTACHED", "pdf_source": attachment.source, "zotero_attachment_key": attachment.key}


def _pdf_error_code_for_status(status: str | None) -> str | None:
    mapping = {
        "NONE": "PDF_NOT_FOUND",
        "BROWSER_REQUIRED": "BROWSER_REQUIRED",
        "AUTH_REQUIRED": "AUTH_REQUIRED",
        "FAILED": "INVALID_PDF_RESPONSE",
    }
    return mapping.get(status or "")


def _pdf_message_for_status(status: str | None) -> str | None:
    if status in {"BROWSER_REQUIRED", "AUTH_REQUIRED"}:
        return "PDF cannot be fetched automatically. Open the article in a browser and use Zotero Connector or attach a local PDF."
    if status == "NONE":
        return "No direct or open-access PDF was found."
    if status == "FAILED":
        return "Automatic PDF retrieval failed."
    return None


def _prefer_actionable_resolution(current: PdfResolution, incoming: PdfResolution) -> PdfResolution:
    rank = {"AUTH_REQUIRED": 4, "BROWSER_REQUIRED": 3, "FAILED": 2, "NONE": 1}
    return incoming if rank.get(incoming.status, 0) >= rank.get(current.status, 0) else current


def _is_restricted_publisher_url(url: str | None) -> bool:
    if not url:
        return False
    host = urlparse(url).netloc.lower()
    return any(host == item or host.endswith(f".{item}") for item in RESTRICTED_PUBLISHER_HOSTS)


def _is_public_repository_url(url: str | None) -> bool:
    if not url:
        return False
    host = urlparse(url).netloc.lower()
    return any(hint in host for hint in PUBLIC_REPOSITORY_HOST_HINTS)


def _may_discover_pdf_links(url: str, paper: Paper) -> bool:
    return not _is_restricted_publisher_url(url)

def _paper_to_zotero_item(paper: Paper, collection_key: str) -> dict[str, Any]:
    item_type = "conferencePaper" if _looks_like_conference(paper.source_label, paper.venue) else "journalArticle"
    item: dict[str, Any] = {
        "itemType": item_type,
        "title": paper.title,
        "creators": [_author_to_creator(author) for author in paper.authors],
        "abstractNote": paper.abstract or "",
        "date": str(paper.year or ""),
        "DOI": paper.doi or "",
        "url": paper.url or "",
        "collections": [collection_key],
        "tags": _tags_for_paper(paper),
        "extra": _extra_for_paper(paper),
    }
    if item_type == "conferencePaper":
        item["conferenceName"] = paper.venue or paper.source_label or ""
        item["proceedingsTitle"] = paper.source_label or paper.venue or ""
    else:
        item["publicationTitle"] = paper.venue or paper.source_label or ""
        item["journalAbbreviation"] = paper.source_label or ""
    return item


def _author_to_creator(author: str) -> dict[str, str]:
    clean = " ".join(author.split())
    if not clean:
        return {"creatorType": "author", "name": "Unknown"}
    parts = clean.split()
    if len(parts) == 1:
        return {"creatorType": "author", "name": clean}
    return {"creatorType": "author", "firstName": " ".join(parts[:-1]), "lastName": parts[-1]}


def _tags_for_paper(paper: Paper) -> list[dict[str, str]]:
    tags = [paper.source_label or paper.venue or "Unclassified"]
    tags.extend(paper.matched_keywords or [])
    if paper.is_oa:
        tags.append("OpenAccess")
    seen: set[str] = set()
    result = []
    for tag in tags:
        clean = tag.strip()
        if clean and clean.lower() not in seen:
            seen.add(clean.lower())
            result.append({"tag": clean})
    return result


def _extra_for_paper(paper: Paper) -> str:
    lines = ["Imported by Academic Paper Finder"]
    if paper.translated_title:
        lines.append(f"Chinese title: {paper.translated_title}")
    if paper.translated_abstract:
        lines.append(f"Chinese abstract: {paper.translated_abstract}")
    if paper.pdf_url:
        lines.append(f"OA PDF: {paper.pdf_url}")
    if paper.relevance:
        lines.append(f"Relevance: {round(paper.relevance * 100)}%")
    return "\n".join(lines)


def _looks_like_conference(source_label: str | None, venue: str | None) -> bool:
    text = f"{source_label or ''} {venue or ''}".lower()
    return bool(re.search(r"\b(icra|iros|conference|proceedings)\b", text))


def _json_write_headers(server_id: str, api_key: str) -> dict[str, str]:
    return {**_auth_headers(server_id, api_key), "Content-Type": "application/json"}


def _auth_headers(server_id: str, api_key: str) -> dict[str, str]:
    return {
        "Zotero-API-Version": "3",
        "Zotero-Server-ID": server_id,
        "Zotero-API-Key": api_key,
    }


def _first_successful_key(data: dict) -> str | None:
    successful = data.get("successful", {})
    if not successful:
        return None
    first = next(iter(successful.values()))
    return first.get("key") or first.get("data", {}).get("key")


def _successful_keys_by_index(data: dict) -> dict[int, str]:
    result: dict[int, str] = {}
    for index, value in data.get("successful", {}).items():
        key = value.get("key") or value.get("data", {}).get("key")
        if key:
            result[int(index)] = key
    return result


def _normalize_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    clean = doi.strip().lower()
    clean = clean.removeprefix("https://doi.org/").removeprefix("http://doi.org/").removeprefix("doi:")
    return clean.strip()


def _year_from_date(date: str | None) -> int | None:
    match = re.search(r"(19|20)\d{2}", date or "")
    return int(match.group(0)) if match else None


def _title_year_key(title: str | None, date: str | None) -> str | None:
    if not title:
        return None
    normalized_title = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", title.lower())).strip()
    year_match = re.search(r"(19|20)\d{2}", date or "")
    year = year_match.group(0) if year_match else ""
    return f"title:{normalized_title}|year:{year}"


def _pdf_filename(paper: Paper) -> str:
    year = str(paper.year or "")
    title = re.sub(r"[^A-Za-z0-9._ -]+", "", paper.title).strip()
    title = re.sub(r"\s+", "_", title)[:90] or "paper"
    name = f"{year}_{title}" if year else title
    return name if name.lower().endswith(".pdf") else f"{name}.pdf"


def _absolute_zotero_url(url: str) -> str:
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return "http://127.0.0.1:23119" + url


def _zotero_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
