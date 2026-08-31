"""从 Zotero 本地数据目录读取 PDF 附件并抽取文本。

Zotero 把 imported_file 附件存在 `{数据目录}/storage/{附件条目key}/xxx.pdf`，
工作台数据库已记录 zotero_attachment_key，因此无需通过任何 API 即可拿到文件。
"""

from __future__ import annotations

import os
import re
from pathlib import Path

DEFAULT_PDF_TEXT_CHARS = 60000


class ZoteroStorageError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def resolve_zotero_data_dir(override: str | Path | None = None) -> Path:
    raw = str(override or os.getenv("ZOTERO_DATA_DIR") or "~/Zotero").strip()
    return Path(os.path.expanduser(raw))


def resolve_pdf_path(paper, data_dir: str | Path | None = None) -> Path:
    """按附件 key 定位本地 PDF；找不到时抛出带错误码的 ZoteroStorageError。"""
    base = resolve_zotero_data_dir(data_dir)
    if not base.exists():
        raise ZoteroStorageError(
            "ZOTERO_DATA_DIR_MISSING",
            f"未找到 Zotero 数据目录：{base}。请在 .env 中设置 ZOTERO_DATA_DIR 指向你的 Zotero 数据文件夹。",
        )
    keys = [paper.zotero_attachment_key, paper.zotero_item_key or paper.zotero_key]
    for key in [k for k in keys if k]:
        storage_dir = base / "storage" / key
        if not storage_dir.is_dir():
            continue
        pdfs = sorted(storage_dir.glob("*.pdf"))
        if pdfs:
            return pdfs[0]
    raise ZoteroStorageError(
        "PDF_FILE_NOT_FOUND",
        "Zotero 本地存储中找不到该条目的 PDF 文件（可能尚未同步下载附件，或未挂载 PDF）。",
    )


def pdf_text_char_limit() -> int:
    raw = os.getenv("AI_MAX_PDF_CHARS", "").strip()
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_PDF_TEXT_CHARS
    return value if value > 0 else DEFAULT_PDF_TEXT_CHARS


def extract_pdf_text(path: str | Path, max_chars: int | None = None) -> str:
    """逐页抽取 PDF 文本，超长时按页边界截断。"""
    import fitz

    limit = max_chars if max_chars and max_chars > 0 else pdf_text_char_limit()
    chunks: list[str] = []
    total = 0
    with fitz.open(str(path)) as doc:
        for page in doc:
            text = page.get_text("text").strip()
            if not text:
                continue
            chunks.append(text)
            total += len(text) + 2
            if total >= limit:
                break
    merged = "\n\n".join(chunks)
    if len(merged) > limit:
        merged = merged[:limit].rstrip() + "\n\n[... PDF 文本过长，已截断 ...]"
    return merged


def paper_pdf_text(paper, data_dir: str | Path | None = None, max_chars: int | None = None) -> str:
    """定位并抽取论文 PDF 文本；任何失败都以 ZoteroStorageError 报告。"""
    path = resolve_pdf_path(paper, data_dir)
    return extract_pdf_text(path, max_chars)


def sanitize_note_html_fragment(html: str) -> str:
    """Zotero 子笔记只接受一个 HTML 片段，去掉会破坏结构的外层文档标签。"""
    text = html.strip()
    text = re.sub(r"<!DOCTYPE[^>]*>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"</?(html|head|body)[^>]*>", "", text, flags=re.IGNORECASE)
    return text.strip()
