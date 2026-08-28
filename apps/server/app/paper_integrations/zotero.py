from __future__ import annotations

import base64
import hashlib
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import httpx

from .models import Paper, ZoteroAttachPdfRequest, ZoteroImportRequest

ZOTERO_BASE_URL = "http://127.0.0.1:23119/api"
ZOTERO_APP_NAME = "Academic Paper Finder"
MAX_PDF_BYTES = 80 * 1024 * 1024
PDF_LIBRARY_DIR = Path(__file__).resolve().parents[4] / "data" / "papers"
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
            "authorized": bool(_zotero_key),
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
        message += f"，{result.skipped_pdfs} 个 PDF 已进入 CARSI 获取队列"
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
    global _zotero_key
    if _zotero_key:
        return _zotero_key

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
    _zotero_key = key
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
    created = 0
    reused = 0

    for index, paper in enumerate(papers):
        collection_key = collections.get(paper.source_label or paper.venue or "Unclassified", collections["__root__"])
        existing_key = _find_existing_item_key(existing, paper)
        if existing_key:
            reused += 1
            item_keys_by_index[index] = existing_key
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
            _add_to_existing_index(existing, paper, key)

    attached_by_index: dict[int, bool] = {}
    attached_pdfs = 0
    skipped_pdfs = 0
    for index, paper in enumerate(papers):
        parent_key = item_keys_by_index.get(index)
        if not parent_key:
            continue
        if await _item_has_pdf_attachment(client, parent_key):
            attached_by_index[index] = True
            continue
        if not paper.pdf_url:
            attached_by_index[index] = False
            skipped_pdfs += 1
            continue
        ok = await _attach_pdf_from_url(client, server_id, api_key, parent_key, paper)
        attached_by_index[index] = ok
        if ok:
            attached_pdfs += 1
        else:
            skipped_pdfs += 1

    keys = [item_keys_by_index[index] for index in sorted(item_keys_by_index)]
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
    response = await client.get(f"{ZOTERO_BASE_URL}/users/0/items/{item_key}/children")
    response.raise_for_status()
    for child in response.json():
        data = child.get("data", child)
        if data.get("itemType") != "attachment":
            continue
        if data.get("contentType") != "application/pdf":
            filename = (data.get("filename") or data.get("title") or "").lower()
            if not filename.endswith(".pdf"):
                continue

        link_mode = data.get("linkMode")
        has_linked_path = link_mode == "linked_file" and bool(data.get("path"))
        has_imported_file = link_mode in {"imported_file", "imported_url"} and (
            bool(data.get("md5")) or bool(child.get("links", {}).get("enclosure", {}).get("href"))
        )
        if has_linked_path or has_imported_file:
            return True
    return False


async def _attach_pdf_from_url(
    client: httpx.AsyncClient,
    server_id: str,
    api_key: str,
    parent_key: str,
    paper: Paper,
) -> bool:
    try:
        pdf = await _download_pdf(client, paper.pdf_url)
        if not pdf:
            return False

        content, content_type = pdf
        filename = _pdf_filename(paper)
        return await _attach_linked_pdf_bytes(
            client=client,
            server_id=server_id,
            api_key=api_key,
            parent_key=parent_key,
            content=content,
            content_type=content_type or "application/pdf",
            filename=filename,
            source_url=paper.pdf_url,
            source_label=paper.source_label or paper.venue,
            tags=["PDF", "OpenAccess"] if paper.is_oa else ["PDF"],
        )
    except (KeyError, httpx.HTTPError):
        return False


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
        if await _item_has_pdf_attachment(client, payload.item_key):
            return {"status": "skipped", "message": "该条目已有 PDF 附件，已跳过重复挂载。", "item_key": payload.item_key}
        filename = payload.filename or "paper.pdf"
        ok = await _attach_linked_pdf_bytes(
            client=client,
            server_id=server_id,
            api_key=api_key,
            parent_key=payload.item_key,
            content=content,
            content_type=payload.content_type or "application/pdf",
            filename=filename,
            source_url=payload.pdf_url,
            source_label="CARSI",
            tags=["PDF", "CARSI"],
        )
    if not ok:
        raise RuntimeError("PDF 已捕获，但写入 Zotero 附件失败。")
    return {"status": "ok", "message": "PDF 已挂载到 Zotero。", "item_key": payload.item_key}


async def _attach_linked_pdf_bytes(
    client: httpx.AsyncClient,
    server_id: str,
    api_key: str,
    parent_key: str,
    content: bytes,
    content_type: str,
    filename: str,
    source_url: str | None,
    source_label: str | None,
    tags: list[str],
) -> bool:
    try:
        if await _item_has_pdf_attachment(client, parent_key):
            return True
        file_path = _save_pdf_file(content, source_label, filename)
        if await _item_has_pdf_attachment(client, parent_key):
            return True
        attachment = {
            "itemType": "attachment",
            "parentItem": parent_key,
            "linkMode": "linked_file",
            "title": "Full Text PDF",
            "contentType": content_type or "application/pdf",
            "path": str(file_path),
            "tags": [{"tag": tag} for tag in tags],
            "relations": {},
        }
        response = await client.post(
            f"{ZOTERO_BASE_URL}/users/0/items",
            headers=_json_write_headers(server_id, api_key),
            json=[attachment],
        )
        response.raise_for_status()
        return bool(_first_successful_key(response.json()))
    except (OSError, KeyError, httpx.HTTPError):
        return False


def _save_pdf_file(content: bytes, source_label: str | None, filename: str) -> Path:
    source_dir = PDF_LIBRARY_DIR / _safe_path_part(source_label or "Unclassified")
    source_dir.mkdir(parents=True, exist_ok=True)
    clean_name = _safe_filename(filename)
    file_path = source_dir / clean_name
    if file_path.exists() and file_path.read_bytes() != content:
        stem = file_path.stem
        suffix = file_path.suffix or ".pdf"
        digest = hashlib.sha1(content).hexdigest()[:8]
        file_path = source_dir / f"{stem}_{digest}{suffix}"
    file_path.write_bytes(content)
    return file_path


def _safe_path_part(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._ -]+", "_", value).strip(" ._")
    return clean or "Unclassified"


def _safe_filename(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._ -]+", "_", value).strip(" ._")
    if not clean:
        clean = "paper"
    if clean.lower().endswith(".pdf"):
        clean = clean[:-4]
    clean = clean[:150].strip(" ._") or "paper"
    return f"{clean}.pdf"


async def _attach_pdf_bytes(
    client: httpx.AsyncClient,
    server_id: str,
    api_key: str,
    parent_key: str,
    content: bytes,
    content_type: str,
    filename: str,
    source_url: str | None,
) -> bool:
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
            "tags": [{"tag": "PDF"}, {"tag": "CARSI"}],
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
            return False
        return await _upload_file_to_attachment(
            client, server_id, api_key, attachment_key, content, content_type, filename, md5, mtime
        )
    except (KeyError, httpx.HTTPError):
        return False


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


async def _download_pdf(client: httpx.AsyncClient, url: str | None) -> tuple[bytes, str] | None:
    if not url:
        return None
    try:
        response = await client.get(url, headers={"Accept": "application/pdf,*/*"})
        response.raise_for_status()
    except httpx.HTTPError:
        return None

    content = response.content
    if not content or len(content) > MAX_PDF_BYTES:
        return None
    content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
    looks_like_pdf = content.startswith(b"%PDF") or content_type == "application/pdf" or url.lower().endswith(".pdf")
    if not looks_like_pdf:
        return None
    return content, content_type or "application/pdf"


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
