from typing import Literal

from pydantic import BaseModel, Field


class SourceConfig(BaseModel):
    id: str
    label: str
    kind: Literal["conference", "journal"]
    aliases: list[str] = Field(default_factory=list)
    openalex_ids: list[str] = Field(default_factory=list)


class SearchRequest(BaseModel):
    query: str
    sources: list[SourceConfig]
    keywords: list[str] = Field(default_factory=list)
    from_year: int = 2020
    to_year: int = 2026
    per_source_limit: int = 25


class Paper(BaseModel):
    id: str
    title: str
    translated_title: str | None = None
    abstract: str | None = None
    translated_abstract: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    source_id: str | None = None
    source_label: str | None = None
    doi: str | None = None
    url: str | None = None
    pdf_url: str | None = None
    is_oa: bool = False
    relevance: float = 0.0
    matched_keywords: list[str] = Field(default_factory=list)


class SearchResponse(BaseModel):
    papers: list[Paper]


class ZoteroImportRequest(BaseModel):
    collection_root: str = "Embodied Intelligence Papers"
    papers: list[Paper]


class ZoteroAttachPdfRequest(BaseModel):
    item_key: str
    pdf_url: str | None = None
    filename: str | None = None
    content_type: str = "application/pdf"
    content_base64: str
