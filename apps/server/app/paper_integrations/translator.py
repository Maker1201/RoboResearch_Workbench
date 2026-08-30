import json
import os
from dataclasses import dataclass
from pathlib import Path

import httpx
from dotenv import load_dotenv

from .models import Paper

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


@dataclass(frozen=True)
class TranslationSettings:
    provider: str
    target_language: str
    api_base: str | None
    api_key: str | None
    model: str | None


def translation_settings() -> TranslationSettings:
    provider = os.getenv("TRANSLATION_PROVIDER", "none").strip().lower()
    return TranslationSettings(
        provider=provider,
        target_language=os.getenv("TRANSLATION_TARGET", "zh-CN").strip() or "zh-CN",
        api_base=os.getenv("TRANSLATION_API_BASE"),
        api_key=os.getenv("TRANSLATION_API_KEY") or os.getenv("OPENAI_API_KEY"),
        model=os.getenv("TRANSLATION_MODEL"),
    )


def translation_status() -> dict:
    settings = translation_settings()
    configured = False
    if settings.provider in {"openai", "openai-compatible"}:
        configured = _is_real_value(settings.api_key) and _is_real_value(settings.model)
    elif settings.provider == "libretranslate":
        configured = _is_real_value(settings.api_base)
    elif settings.provider in {"immersivel", "immersive", "immersive-translate"}:
        configured = _is_real_value(settings.api_base)
    return {
        "provider": settings.provider,
        "configured": configured,
        "target_language": settings.target_language,
    }


async def translate_papers(papers: list[Paper]) -> list[Paper]:
    settings = translation_settings()
    if not papers or settings.provider == "none":
        return papers
    if settings.provider in {"openai", "openai-compatible"}:
        return await _translate_with_openai_compatible(papers, settings)
    if settings.provider == "libretranslate":
        return await _translate_with_libretranslate(papers, settings)
    if settings.provider in {"immersivel", "immersive", "immersive-translate"}:
        return await _translate_with_immersivel(papers, settings)
    return papers


async def _translate_with_openai_compatible(papers: list[Paper], settings: TranslationSettings) -> list[Paper]:
    if not settings.api_key or not settings.model:
        return papers

    api_base = (settings.api_base or "https://api.openai.com/v1").rstrip("/")
    items = [
        {
            "id": paper.id,
            "title": paper.title,
            "abstract": _trim(paper.abstract, 1800),
        }
        for paper in papers
    ]
    prompt = (
        "Translate academic paper titles and abstracts into Simplified Chinese. "
        "Keep technical terms such as VLM, VLA, WAM, task planning, world model, CARSI, DOI, and robot names accurate. "
        "Return only valid JSON with this shape: "
        "[{\"id\": string, \"translated_title\": string, \"translated_abstract\": string|null}].\n\n"
        f"Target language: {settings.target_language}\n"
        f"Papers: {json.dumps(items, ensure_ascii=False)}"
    )

    payload = {
        "model": settings.model,
        "messages": [
            {"role": "system", "content": "You are a precise academic translation engine."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
    }
    headers = {
        "Authorization": f"Bearer {settings.api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(f"{api_base}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        translations = _parse_json_array(content)
    except (httpx.HTTPError, KeyError, IndexError, json.JSONDecodeError):
        return papers

    by_id = {item.get("id"): item for item in translations if isinstance(item, dict)}
    for paper in papers:
        translated = by_id.get(paper.id)
        if translated:
            paper.translated_title = translated.get("translated_title") or paper.translated_title
            paper.translated_abstract = translated.get("translated_abstract") or paper.translated_abstract
    return papers


async def _translate_with_immersivel(papers: list[Paper], settings: TranslationSettings) -> list[Paper]:
    if not settings.api_base:
        return papers

    texts: list[str] = []
    refs: list[tuple[Paper, str]] = []
    for paper in papers:
        if paper.title:
            texts.append(paper.title)
            refs.append((paper, "title"))
        if paper.abstract:
            texts.append(_trim(paper.abstract, 1800) or "")
            refs.append((paper, "abstract"))

    if not texts:
        return papers

    endpoint = settings.api_base.rstrip("/") + "/v1/immersive_translate"
    payload = {
        "source_lang": "en",
        "target_lang": settings.target_language,
        "text_list": texts,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(endpoint, json=payload)
            response.raise_for_status()
        translations = response.json().get("translations", [])
    except httpx.HTTPError:
        return papers

    for ref, translated in zip(refs, translations, strict=False):
        paper, field = ref
        text = translated.get("text") if isinstance(translated, dict) else None
        if not text:
            continue
        if field == "title":
            paper.translated_title = text
        else:
            paper.translated_abstract = text
    return papers


async def _translate_with_libretranslate(papers: list[Paper], settings: TranslationSettings) -> list[Paper]:
    if not settings.api_base:
        return papers

    endpoint = settings.api_base.rstrip("/") + "/translate"
    api_key = settings.api_key
    async with httpx.AsyncClient(timeout=30.0) as client:
        for paper in papers:
            paper.translated_title = await _libretranslate_text(client, endpoint, paper.title, settings.target_language, api_key)
            if paper.abstract:
                paper.translated_abstract = await _libretranslate_text(
                    client,
                    endpoint,
                    _trim(paper.abstract, 1800),
                    settings.target_language,
                    api_key,
                )
    return papers


async def _libretranslate_text(
    client: httpx.AsyncClient,
    endpoint: str,
    text: str | None,
    target_language: str,
    api_key: str | None,
) -> str | None:
    if not text:
        return None
    payload = {
        "q": text,
        "source": "auto",
        "target": _libretranslate_target(target_language),
        "format": "text",
    }
    if api_key:
        payload["api_key"] = api_key
    try:
        response = await client.post(endpoint, json=payload)
        response.raise_for_status()
        return response.json().get("translatedText")
    except httpx.HTTPError:
        return None


def _libretranslate_target(target_language: str) -> str:
    return target_language.split("-")[0].lower()


def _is_real_value(value: str | None) -> bool:
    if not value:
        return False
    clean = value.strip().lower()
    placeholders = {
        "your_api_key_here",
        "your_translation_model_here",
        "你的 api key",
        "你的翻译模型",
        "",
    }
    return clean not in placeholders


def _trim(value: str | None, limit: int) -> str | None:
    if not value:
        return None
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + "..."


def _parse_json_array(content: str) -> list[dict]:
    clean = content.strip()
    if clean.startswith("```"):
        clean = clean.strip("`")
        clean = clean.removeprefix("json").strip()
    start = clean.find("[")
    end = clean.rfind("]")
    if start >= 0 and end >= start:
        clean = clean[start : end + 1]
    data = json.loads(clean)
    return data if isinstance(data, list) else []
