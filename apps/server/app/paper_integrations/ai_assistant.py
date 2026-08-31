"""AI 阅读助手：逐篇草稿笔记 + 阅读队列批量分诊。

配置独立于翻译功能（TRANSLATION_*），走 AI_* 环境变量的 OpenAI 兼容接口，
请求模式与 translator.py 保持一致。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import httpx
from dotenv import load_dotenv

from .translator import _is_real_value, _parse_json_array, _trim

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

NOTE_SECTIONS = [
    "## 1. Why did I read this?",
    "## 2. One Sentence Summary",
    "## 3. Problem",
    "## 4. Core Idea",
    "## 5. Architecture",
    "## 6. Key Technical Details",
    "## 7. Experiments",
    "## 8. What is actually useful to me?",
    "## 9. Limitations",
    "## 10. Questions",
    "## 11. Ideas",
    "## 12. Knowledge to Extract",
]

READING_MODES = {"SCAN", "SKIM", "READ", "DEEP"}

_settings_loader: Callable[[], dict[str, str]] | None = None


def configure_settings_loader(loader: Callable[[], dict[str, str]]) -> None:
    """注入设置页持久化的 AI 配置读取函数（数据库优先，.env 回退）。"""
    global _settings_loader
    _settings_loader = loader


def _stored_settings() -> dict[str, str]:
    if not _settings_loader:
        return {}
    try:
        return _settings_loader() or {}
    except Exception:
        return {}


def _pick(stored: dict[str, str], key: str, env_key: str) -> str | None:
    value = (stored.get(key) or "").strip()
    if value:
        return value
    env_value = os.getenv(env_key)
    return env_value.strip() if env_value else None


@dataclass(frozen=True)
class AISettings:
    provider: str
    api_base: str | None
    api_key: str | None
    model: str | None
    output_language: str
    research_interests: str
    max_pdf_chars: int


def ai_settings() -> AISettings:
    stored = _stored_settings()
    provider = (_pick(stored, "provider", "AI_PROVIDER") or "none").strip().lower()
    raw_limit = _pick(stored, "max_pdf_chars", "AI_MAX_PDF_CHARS")
    try:
        max_pdf_chars = int(raw_limit) if raw_limit else 0
    except ValueError:
        max_pdf_chars = 0
    return AISettings(
        provider=provider,
        api_base=_pick(stored, "api_base", "AI_API_BASE"),
        api_key=_pick(stored, "api_key", "AI_API_KEY") or os.getenv("OPENAI_API_KEY"),
        model=_pick(stored, "model", "AI_MODEL"),
        output_language=(_pick(stored, "output_language", "AI_OUTPUT_LANGUAGE") or "zh").strip() or "zh",
        research_interests=(_pick(stored, "research_interests", "AI_RESEARCH_INTERESTS") or "").strip(),
        max_pdf_chars=max_pdf_chars if max_pdf_chars > 0 else 60000,
    )


def ai_status() -> dict:
    settings = ai_settings()
    configured = settings.provider in {"openai", "openai-compatible"} and _is_real_value(settings.api_key) and _is_real_value(settings.model)
    return {
        "provider": settings.provider,
        "configured": configured,
        "model": settings.model,
        "output_language": settings.output_language,
    }


def ai_configured() -> bool:
    return ai_status()["configured"]


async def draft_reading_note(paper, pdf_text: str | None) -> str | None:
    """按 12 节模板生成草稿笔记；未配置或调用失败时返回 None（由调用方回退到空模板）。"""
    settings = ai_settings()
    if settings.provider not in {"openai", "openai-compatible"} or not settings.api_key or not settings.model:
        return None

    source = pdf_text or ""
    source_note = "full paper text" if pdf_text else "title, abstract and metadata only (PDF unavailable)"
    interest_line = (
        f"The user's research interests (use them to fill sections 1 and 8 concretely): {settings.research_interests}\n"
        if settings.research_interests
        else ""
    )
    prompt = (
        "You are an academic reading assistant. Draft a reading note for the paper below by filling the "
        "12-section Markdown template. Rules:\n"
        "- Keep every section heading EXACTLY as given (same numbering and text).\n"
        f"- Write the content in {settings.output_language}.\n"
        "- Fill sections 1-9 based on the paper. Be specific and concise (2-6 sentences per section); "
        "cite concrete numbers/benchmarks from Experiments when available.\n"
        "- Section 8 must focus on what is practically useful for the user's own research.\n"
        "- Sections 10 (Questions), 11 (Ideas) stay EMPTY except a short placeholder line asking the reader to think.\n"
        "- Section 12 lists 2-5 reusable knowledge points worth moving into a long-term knowledge base.\n"
        "- Output ONLY the Markdown note, no code fences, no commentary.\n\n"
        f"{interest_line}"
        f"Paper metadata:\nTitle: {paper.title}\n"
        f"Authors: {getattr(paper, 'authors', None) or ''}\n"
        f"Year/Venue: {getattr(paper, 'year', None) or ''} / {getattr(paper, 'venue', None) or ''}\n"
        f"Abstract: {_trim(getattr(paper, 'abstract', None), 3000) or 'N/A'}\n\n"
        f"Source ({source_note}):\n"
    )
    if pdf_text:
        prompt += pdf_text

    content = await _chat(settings, "You are a precise academic reading assistant.", prompt, temperature=0.3, timeout=180.0)
    if not content:
        return None
    note = _clean_markdown(content)
    return note if _has_note_sections(note) else None


async def triage_papers(papers) -> list[dict]:
    """批量分诊：返回 [{"id", "one_liner", "relevance", "suggested_mode"}]，失败返回空列表。"""
    settings = ai_settings()
    if not papers or settings.provider not in {"openai", "openai-compatible"} or not settings.api_key or not settings.model:
        return []

    items = [
        {
            "id": paper.id,
            "title": paper.title,
            "abstract": _trim(getattr(paper, "abstract", None), 1800),
            "venue": getattr(paper, "venue", None),
            "year": getattr(paper, "year", None),
        }
        for paper in papers
    ]
    interest_line = (
        f"The user's research interests (relevance and suggested_mode must be judged against them): {settings.research_interests}\n"
        if settings.research_interests
        else ""
    )
    prompt = (
        "Triage these academic papers for the user's reading queue. For each paper return:\n"
        "- one_liner: one sentence (in "
        f"{settings.output_language}) saying what the paper does and its key result\n"
        "- relevance: 0-100 integer, how relevant to the user's research interests\n"
        "- suggested_mode: one of SCAN, SKIM, READ, DEEP (SCAN=only check figures, SKIM=read intro/conclusion, "
        "READ=read carefully, DEEP=read + reproduce details)\n"
        "Return only valid JSON: [{\"id\": int, \"one_liner\": string, \"relevance\": int, \"suggested_mode\": string}]\n\n"
        f"{interest_line}"
        f"Papers: {json.dumps(items, ensure_ascii=False)}"
    )
    content = await _chat(settings, "You are a precise academic triage engine.", prompt, temperature=0.1, timeout=120.0)
    if not content:
        return []
    try:
        data = _parse_json_array(content)
    except (json.JSONDecodeError, TypeError):
        return []
    results: list[dict] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        paper_id = row.get("id")
        if not isinstance(paper_id, int):
            continue
        mode = str(row.get("suggested_mode") or "").strip().upper()
        results.append({
            "id": paper_id,
            "one_liner": (row.get("one_liner") or "").strip() or None,
            "relevance": _clamp_relevance(row.get("relevance")),
            "suggested_mode": mode if mode in READING_MODES else None,
        })
    return results


async def test_connection(provider: str, api_base: str | None, api_key: str | None, model: str | None) -> tuple[bool, str]:
    """设置页"测试连接"：用最小请求验证 AI 接口可用性。"""
    if provider not in {"openai", "openai-compatible"}:
        return False, "AI 服务未启用：请选择 openai-compatible 作为服务类型。"
    if not api_key or not model or not _is_real_value(api_key):
        return False, "请先填写 API Key 和模型名并保存。"
    settings = AISettings(
        provider=provider,
        api_base=api_base,
        api_key=api_key,
        model=model,
        output_language="zh",
        research_interests="",
        max_pdf_chars=60000,
    )
    content = await _chat(settings, "You are a connection test.", "Reply with exactly: ok", temperature=0.0, timeout=20.0)
    if not content:
        return False, f"无法从 {api_base or 'https://api.openai.com/v1'} 获取响应，请检查 API Base / API Key / 模型名。"
    return True, f"AI 接口可用（模型：{model}）。"


async def _chat(settings: AISettings, system: str, user: str, temperature: float, timeout: float) -> str | None:
    api_base = (settings.api_base or "https://api.openai.com/v1").rstrip("/")
    payload = {
        "model": settings.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
    }
    headers = {
        "Authorization": f"Bearer {settings.api_key}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"{api_base}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError):
        return None


def _clean_markdown(content: str) -> str:
    clean = content.strip()
    if clean.startswith("```"):
        clean = clean.strip("`")
        clean = clean.removeprefix("markdown").strip()
    return clean.strip()


def _has_note_sections(note: str) -> bool:
    matches = sum(1 for heading in NOTE_SECTIONS if heading in note)
    return matches >= 6


def _clamp_relevance(value) -> int | None:
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        return None
    return max(0, min(100, number))
