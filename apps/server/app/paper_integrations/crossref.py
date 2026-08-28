import html
import re
from collections.abc import Iterable

import httpx

from .models import Paper, SearchRequest, SourceConfig

CROSSREF_WORKS_API = "https://api.crossref.org/works"
CROSSREF_MAILTO = "academic-paper-finder@example.local"


def _clean_text(value: str | None) -> str | None:
    if not value:
        return None
    without_tags = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(without_tags)).strip()


def _first(value: list | None) -> str | None:
    if not value:
        return None
    return _clean_text(str(value[0]))


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
    score = 0.12
    score += min(len(matches) * 0.12, 0.58)
    if re.search(r"\b(robot|robotic|embodied|planning|world model|vla|vlm)\b", text):
        score += 0.15
    return min(round(score, 2), 0.95)


def _year(item: dict) -> int | None:
    date_parts = (
        item.get("published-print", {})
        .get("date-parts")
        or item.get("published-online", {}).get("date-parts")
        or item.get("created", {}).get("date-parts")
    )
    if date_parts and date_parts[0]:
        return date_parts[0][0]
    return None


def _authors(item: dict) -> list[str]:
    names: list[str] = []
    for author in item.get("author", [])[:8]:
        given = author.get("given", "")
        family = author.get("family", "")
        name = " ".join(part for part in [given, family] if part).strip()
        if name:
            names.append(name)
    return names


def _venue(item: dict) -> str | None:
    return _first(item.get("container-title")) or _first(item.get("event", {}).get("name"))


def _venue_matches_source(venue: str | None, source: SourceConfig) -> bool:
    if not venue:
        return False
    haystack = venue.lower()
    labels = [source.label, *source.aliases]
    return any(label.lower() in haystack for label in labels if label)


def _query_terms(request: SearchRequest, source: SourceConfig) -> str:
    source_terms = " ".join([source.label, *source.aliases])
    keyword_terms = " ".join(request.keywords)
    return " ".join(part for part in [request.query, keyword_terms, source_terms] if part).strip()


async def search_crossref(request: SearchRequest) -> list[Paper]:
    papers_by_key: dict[str, Paper] = {}
    async with httpx.AsyncClient(timeout=25.0) as client:
        for source in request.sources:
            params = {
                "query.bibliographic": _query_terms(request, source),
                "filter": f"from-pub-date:{request.from_year}-01-01,until-pub-date:{request.to_year}-12-31",
                "rows": max(1, min(request.per_source_limit * 2, 50)),
                "mailto": CROSSREF_MAILTO,
            }
            try:
                response = await client.get(CROSSREF_WORKS_API, params=params)
                response.raise_for_status()
            except httpx.HTTPError:
                continue

            for item in response.json().get("message", {}).get("items", []):
                paper = _paper_from_crossref(item, source, request.keywords)
                if not _venue_matches_source(paper.venue, source):
                    continue
                key = paper.doi or paper.id
                papers_by_key[key] = paper

    return sorted(
        papers_by_key.values(),
        key=lambda paper: (paper.relevance, paper.year or 0),
        reverse=True,
    )


def _paper_from_crossref(item: dict, source: SourceConfig, keywords: list[str]) -> Paper:
    title = _first(item.get("title")) or "Untitled"
    abstract = _clean_text(item.get("abstract"))
    venue = _venue(item) or source.label
    doi = item.get("DOI")
    url = item.get("URL") or (f"https://doi.org/{doi}" if doi else None)
    matches = _keyword_matches(f"{title}\n{abstract or ''}", keywords)

    return Paper(
        id=doi or item.get("URL") or title,
        title=title,
        translated_title=None,
        abstract=abstract,
        translated_abstract=None,
        authors=_authors(item),
        year=_year(item),
        venue=venue,
        source_id=source.id,
        source_label=source.label,
        doi=doi,
        url=url,
        pdf_url=None,
        is_oa=False,
        relevance=_score(title, abstract, matches),
        matched_keywords=matches,
    )
