"""开放获取 PDF 兜底解析。

付费墙论文的服务器端直接下载经常不可行，但机器人领域的论文大多存在
arXiv 预印本或仓库级开放获取副本。这里按可信度依次查询：

1. arXiv DOI（10.48550/arXiv.xxxx）直接变换出 PDF 链接
2. OpenAlex 按 DOI 查询 best_oa_location / locations 中的 pdf_url
3. Semantic Scholar 按 DOI 查询 openAccessPdf
4. arXiv 标题精确匹配检索（归一化后全等才算命中）

所有查询失败（网络错误、限流、字段缺失）都静默降级，不影响主流程。
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from urllib.parse import quote

import httpx

OPENALEX_API = "https://api.openalex.org/works/https://doi.org/{doi}?select=best_oa_location,locations&mailto=roboresearch-workbench@local"
SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=openAccessPdf"
ARXIV_API = "http://export.arxiv.org/api/query?search_query={query}&max_results=5"
ARXIV_LOOKUP_TIMEOUT = 10.0


@dataclass(frozen=True)
class OpenAccessCandidate:
    url: str
    source: str


def normalize_title(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _arxiv_pdf_url(abs_id: str) -> str:
    return f"https://arxiv.org/pdf/{abs_id}"


def _arxiv_doi_pdf(doi: str | None) -> OpenAccessCandidate | None:
    match = re.match(r"(?i)^10\.48550/arxiv\.(.+)$", (doi or "").strip())
    if not match:
        return None
    return OpenAccessCandidate(url=_arxiv_pdf_url(match.group(1)), source="ARXIV")


async def find_open_access_pdfs(client: httpx.AsyncClient, *, doi: str | None, title: str | None) -> list[OpenAccessCandidate]:
    candidates: list[OpenAccessCandidate] = []
    seen: set[str] = set()

    def add(candidate: OpenAccessCandidate | None) -> None:
        if candidate and candidate.url not in seen and candidate.url.startswith("http"):
            seen.add(candidate.url)
            candidates.append(candidate)

    add(_arxiv_doi_pdf(doi))
    for lookup in (_openalex_candidates, _semantic_scholar_candidate, _arxiv_title_candidates):
        try:
            for candidate in await lookup(client, doi=doi, title=title):
                add(candidate)
        except Exception:
            # 单个来源失败（网络、限流、字段缺失）不阻断整体解析。
            continue
    return candidates


async def _openalex_candidates(client: httpx.AsyncClient, *, doi: str | None, title: str | None) -> list[OpenAccessCandidate]:
    if not doi:
        return []
    response = await client.get(OPENALEX_API.format(doi=quote(doi)), timeout=ARXIV_LOOKUP_TIMEOUT)
    if response.status_code != 200:
        return []
    data = response.json()
    results: list[OpenAccessCandidate] = []
    best = (data.get("best_oa_location") or {}).get("pdf_url")
    if best:
        results.append(OpenAccessCandidate(url=best, source="OPENALEX"))
    for location in data.get("locations") or []:
        pdf_url = location.get("pdf_url")
        if pdf_url:
            results.append(OpenAccessCandidate(url=pdf_url, source="OPENALEX"))
    return results


async def _semantic_scholar_candidate(client: httpx.AsyncClient, *, doi: str | None, title: str | None) -> list[OpenAccessCandidate]:
    if not doi:
        return []
    response = await client.get(SEMANTIC_SCHOLAR_API.format(doi=quote(doi)), timeout=ARXIV_LOOKUP_TIMEOUT)
    if response.status_code != 200:
        return []
    url = ((response.json().get("openAccessPdf") or {}).get("url") or "").strip()
    return [OpenAccessCandidate(url=url, source="SEMANTIC_SCHOLAR")] if url else []


async def _arxiv_title_candidates(client: httpx.AsyncClient, *, doi: str | None, title: str | None) -> list[OpenAccessCandidate]:
    normalized_target = normalize_title(title)
    if len(normalized_target) < 8:
        return []
    query = quote(f'ti:"{title}"')
    response = await client.get(ARXIV_API.format(query=query), timeout=ARXIV_LOOKUP_TIMEOUT)
    if response.status_code != 200:
        return []
    namespace = {"a": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(response.content)
    results: list[OpenAccessCandidate] = []
    for entry in root.findall("a:entry", namespace):
        entry_title = re.sub(r"\s+", " ", entry.findtext("a:title", "", namespace)).strip()
        if normalize_title(entry_title) != normalized_target:
            continue
        entry_id = (entry.findtext("a:id", "", namespace) or "").rstrip("/")
        paper_id = entry_id.rsplit("/abs/", 1)[-1]
        if paper_id:
            results.append(OpenAccessCandidate(url=_arxiv_pdf_url(paper_id), source="ARXIV"))
    return results
