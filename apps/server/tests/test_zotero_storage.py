import fitz
from types import SimpleNamespace

from app.services.zotero_storage import (
    DEFAULT_PDF_TEXT_CHARS,
    ZoteroStorageError,
    extract_pdf_text,
    pdf_text_char_limit,
    resolve_pdf_path,
    resolve_zotero_data_dir,
    sanitize_note_html_fragment,
)


def _make_pdf(path, text: str = "Hello world from a test PDF page."):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(str(path))
    doc.close()


def _fake_storage(tmp_path, attachment_key="ATTACH1", filename="paper.pdf"):
    storage_dir = tmp_path / "storage" / attachment_key
    storage_dir.mkdir(parents=True)
    pdf_path = storage_dir / filename
    _make_pdf(pdf_path)
    return pdf_path


def _paper(attachment_key="ATTACH1", item_key=None):
    return SimpleNamespace(zotero_attachment_key=attachment_key, zotero_item_key=item_key, zotero_key=item_key)


def test_resolve_zotero_data_dir_expands_user(monkeypatch):
    monkeypatch.delenv("ZOTERO_DATA_DIR", raising=False)
    assert resolve_zotero_data_dir().name == "Zotero"
    monkeypatch.setenv("ZOTERO_DATA_DIR", "/tmp/custom-zotero")
    assert resolve_zotero_data_dir() == __import__("pathlib").Path("/tmp/custom-zotero")
    assert resolve_zotero_data_dir(override="/override") == __import__("pathlib").Path("/override")


def test_resolve_pdf_path_finds_attachment_pdf(tmp_path):
    pdf_path = _fake_storage(tmp_path)
    assert resolve_pdf_path(_paper(), tmp_path) == pdf_path


def test_resolve_pdf_path_falls_back_to_item_key(tmp_path):
    pdf_path = _fake_storage(tmp_path, attachment_key="ITEMKEY")
    paper = _paper(attachment_key=None, item_key="ITEMKEY")
    assert resolve_pdf_path(paper, tmp_path) == pdf_path


def test_resolve_pdf_path_reports_missing_data_dir(tmp_path):
    try:
        resolve_pdf_path(_paper(), tmp_path / "nonexistent")
    except ZoteroStorageError as exc:
        assert exc.code == "ZOTERO_DATA_DIR_MISSING"
    else:
        raise AssertionError("expected ZoteroStorageError")


def test_resolve_pdf_path_reports_missing_pdf(tmp_path):
    (tmp_path / "storage").mkdir()
    try:
        resolve_pdf_path(_paper(), tmp_path)
    except ZoteroStorageError as exc:
        assert exc.code == "PDF_FILE_NOT_FOUND"
    else:
        raise AssertionError("expected ZoteroStorageError")


def test_extract_pdf_text_reads_generated_pdf(tmp_path):
    pdf_path = tmp_path / "doc.pdf"
    _make_pdf(pdf_path, "Embodied agents learn manipulation policies from demonstrations.")
    text = extract_pdf_text(pdf_path)
    assert "Embodied agents learn manipulation" in text


def test_extract_pdf_text_truncates_to_limit(tmp_path):
    pdf_path = tmp_path / "doc.pdf"
    _make_pdf(pdf_path, "A" * 500)
    text = extract_pdf_text(pdf_path, max_chars=50)
    assert text.startswith("A" * 50)
    assert "截断" in text
    assert len(text) < 100


def test_pdf_text_char_limit_from_env(monkeypatch):
    monkeypatch.delenv("AI_MAX_PDF_CHARS", raising=False)
    assert pdf_text_char_limit() == DEFAULT_PDF_TEXT_CHARS
    monkeypatch.setenv("AI_MAX_PDF_CHARS", "1234")
    assert pdf_text_char_limit() == 1234
    monkeypatch.setenv("AI_MAX_PDF_CHARS", "not-a-number")
    assert pdf_text_char_limit() == DEFAULT_PDF_TEXT_CHARS


def test_sanitize_note_html_fragment_strips_document_tags():
    html = "<!DOCTYPE html><html><head><style>p{}</style></head><body><h1>Title</h1><p>body</p></body></html>"
    cleaned = sanitize_note_html_fragment(html)
    assert "<h1>" in cleaned and "<body" not in cleaned and "<!DOCTYPE" not in cleaned
