import html
import re
from collections.abc import Iterable

import httpx

from .models import Paper, SearchRequest, SourceConfig

OPENALEX_WORKS_API = "https://api.openalex.org/works"
OPENALEX_SOURCES_API = "https://api.openalex.org/sources"
OPENALEX_MAILTO = "academic-paper-finder@example.local"

DEFAULT_SOURCE_IDS = {
    "ral": ["https://openalex.org/S4210177955"],
}

_SOURCE_CACHE: dict[str, list[str]] = {}


def _abstract_from_inverted_index(index: dict | None) -> str | None:
    if not index:
        return None
    positions: list[tuple[int, str]] = []
    for word, offsets in index.items():
        for offset in offsets:
            positions.append((offset, word))
    positions.sort(key=lambda item: item[0])
    return " ".join(word for _, word in positions)


def _normalize_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    return doi.replace("https://doi.org/", "").strip()


def _title(value: str | None) -> str:
    return html.unescape(value or "Untitled")


def _keyword_matches(text: str, keywords: Iterable[str]) -> list[str]:
    haystack = text.lower()
    matches: list[str] = []
    for keyword in keywords:
        clean = keyword.strip()
        if clean and clean.lower() in haystack:
            matches.append(clean)
    return matches


def _score(title: str, abstract: str | None, matches: list[str]) -> float:
    text = f"{title}\n{abstract or ''}".lower()
    score = 0.15
    score += min(len(matches) * 0.12, 0.6)
    if re.search(r"\b(robot|robotic|embodied|planning|world model|vla|vlm)\b", text):
        score += 0.15
    return min(round(score, 2), 0.98)


def _search_terms(request: SearchRequest) -> str:
    chunks = [request.query.strip(), *[kw.strip() for kw in request.keywords]]
    return " OR ".join(chunk for chunk in chunks if chunk)


async def _resolve_source_ids(client: httpx.AsyncClient, source: SourceConfig) -> list[str]:
    if source.openalex_ids:
        return source.openalex_ids
    if source.id in DEFAULT_SOURCE_IDS:
        return DEFAULT_SOURCE_IDS[source.id]

    cache_key = "|".join([source.label, *source.aliases]).lower()
    if cache_key in _SOURCE_CACHE:
        return _SOURCE_CACHE[cache_key]

    resolved: list[str] = []
    candidates = [*source.aliases, source.label]
    for candidate in candidates:
        try:
            response = await client.get(
                OPENALEX_SOURCES_API,
                params={"search": candidate, "per-page": 5, "mailto": OPENALEX_MAILTO},
            )
            response.raise_for_status()
        except httpx.HTTPStatusError:
            _SOURCE_CACHE[cache_key] = []
            return []
        for item in response.json().get("results", []):
            display_name = (item.get("display_name") or "").lower()
            abbreviated_title = (item.get("abbreviated_title") or "").lower()
            normalized_candidate = candidate.lower()
            if normalized_candidate in display_name or normalized_candidate == abbreviated_title:
                source_id = item.get("id")
                if source_id and source_id not in resolved:
                    resolved.append(source_id)
        if resolved:
            break

    _SOURCE_CACHE[cache_key] = resolved
    return resolved


def _venue_matches_source(venue: str | None, source: SourceConfig) -> bool:
    if not venue:
        return False
    haystack = venue.lower()
    labels = [source.label, *source.aliases]
    return any(label.lower() in haystack for label in labels if label)


async def search_openalex(request: SearchRequest) -> list[Paper]:
    terms = _search_terms(request)
    if not terms:
        return []

    papers_by_key: dict[str, Paper] = {}
    async with httpx.AsyncClient(timeout=25.0) as client:
        for source in request.sources:
            source_ids = await _resolve_source_ids(client, source)
            filters = [
                f"from_publication_date:{request.from_year}-01-01",
                f"to_publication_date:{request.to_year}-12-31",
            ]
            if source_ids:
                filters.append(f"primary_location.source.id:{'|'.join(source_ids)}")

            params = {
                "search": terms,
                "filter": ",".join(filters),
                "per-page": max(1, min(request.per_source_limit, 50)),
                "sort": "relevance_score:desc",
                "mailto": OPENALEX_MAILTO,
            }
            try:
                response = await client.get(OPENALEX_WORKS_API, params=params)
                response.raise_for_status()
            except httpx.HTTPStatusError:
                continue
            for item in response.json().get("results", []):
                paper = _paper_from_openalex(item, source, request.keywords)
                if not source_ids and not _venue_matches_source(paper.venue, source):
                    continue
                key = paper.doi or paper.id
                papers_by_key[key] = paper

    return sorted(
        papers_by_key.values(),
        key=lambda paper: (paper.relevance, paper.year or 0),
        reverse=True,
    )


def _paper_from_openalex(item: dict, source: SourceConfig, keywords: list[str]) -> Paper:
    title = _title(item.get("title"))
    abstract = _abstract_from_inverted_index(item.get("abstract_inverted_index"))
    text = f"{title}\n{abstract or ''}"
    matches = _keyword_matches(text, keywords)
    primary_location = item.get("primary_location") or {}
    source_info = primary_location.get("source") or {}
    best_oa_location = item.get("best_oa_location") or {}
    doi = _normalize_doi(item.get("doi"))
    authorships = item.get("authorships") or []
    authors = [
        author.get("author", {}).get("display_name", "")
        for author in authorships[:8]
        if author.get("author", {}).get("display_name")
    ]
    url = item.get("doi") or primary_location.get("landing_page_url") or item.get("id")

    return Paper(
        id=item.get("id"),
        title=title,
        translated_title=None,
        abstract=abstract,
        translated_abstract=None,
        authors=authors,
        year=item.get("publication_year"),
        venue=source_info.get("display_name") or source.label,
        source_id=source.id,
        source_label=source.label,
        doi=doi,
        url=url,
        pdf_url=best_oa_location.get("pdf_url"),
        is_oa=bool(item.get("open_access", {}).get("is_oa")),
        relevance=_score(title, abstract, matches),
        matched_keywords=matches,
    )
