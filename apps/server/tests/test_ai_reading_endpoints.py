import os
import tempfile

os.environ["WORKBENCH_DATABASE_URL"] = f"sqlite:///{tempfile.gettempdir()}/roboresearch_ai_endpoints_test.db"

import fitz
from fastapi.testclient import TestClient

from app import models
from app.database import Base, SessionLocal, engine
from app.main import app


client = TestClient(app)


def setup_module():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _create_paper(**overrides) -> dict:
    payload = {
        "title": "VLA Manipulation Test Paper",
        "venue": "ICRA",
        "year": 2025,
        "abstract": "We propose a vision-language-action model for manipulation.",
        "status": "To Read",
        "queued_at": "2026-08-30T08:00:00",
    }
    payload.update(overrides)
    response = client.post("/papers", json=payload)
    assert response.status_code == 200
    return response.json()


def _set_data_dir_setting(value: str | None):
    db = SessionLocal()
    try:
        row = db.get(models.SystemSetting, "integrations.zotero.data_dir")
        if value is None:
            if row:
                db.delete(row)
        else:
            if row:
                row.value = value
            else:
                db.add(models.SystemSetting(key="integrations.zotero.data_dir", value=value))
        db.commit()
    finally:
        db.close()


def test_ai_triage_updates_papers(monkeypatch):
    paper = _create_paper()
    import app.routers.papers as papers_router

    async def fake_triage(papers):
        return [{"id": papers[0].id, "one_liner": "提出 VLA 操作模型并拿到 SOTA。", "relevance": 91, "suggested_mode": "READ"}]

    monkeypatch.setattr(papers_router, "ai_configured", lambda: True)
    monkeypatch.setattr(papers_router, "triage_papers", fake_triage)

    response = client.post("/papers/ai/triage", json={"paper_ids": [paper["id"]]})
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["ai_summary"] == "提出 VLA 操作模型并拿到 SOTA。"
    assert rows[0]["ai_relevance"] == 91
    assert rows[0]["ai_suggested_mode"] == "READ"


def test_ai_triage_requires_configuration(monkeypatch):
    import app.routers.papers as papers_router

    monkeypatch.setattr(papers_router, "ai_configured", lambda: False)
    response = client.post("/papers/ai/triage", json={"paper_ids": []})
    assert response.status_code == 400
    assert "AI 未配置" in response.json()["detail"]


def test_ai_draft_note_generates_draft_and_summary(monkeypatch):
    paper = _create_paper()
    import app.routers.papers as papers_router

    draft = "\n\n".join([
        "# Reading Note: VLA Manipulation Test Paper",
        "## 1. Why did I read this?",
        "相关项目背景。",
        "## 2. One Sentence Summary",
        "A VLA policy that lifts manipulation success by 12 points.",
        "## 3. Problem",
        "...",
        "## 4. Core Idea",
        "...",
        "## 5. Architecture",
        "...",
        "## 6. Key Technical Details",
        "...",
        "## 7. Experiments",
        "...",
        "## 8. What is actually useful to me?",
        "...",
        "## 9. Limitations",
        "...",
        "## 10. Questions",
        "",
        "## 11. Ideas",
        "",
        "## 12. Knowledge to Extract",
        "- point",
    ])

    async def fake_draft(paper_obj, pdf_text):
        return draft

    monkeypatch.setattr(papers_router, "ai_configured", lambda: True)
    monkeypatch.setattr(papers_router, "draft_reading_note", fake_draft)

    response = client.post(f"/papers/{paper['id']}/ai/draft-note")
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "ai_draft"
    assert body["note"]["note_source"] == "ai_draft"
    assert body["note"]["one_sentence_summary"] == "A VLA policy that lifts manipulation success by 12 points."
    assert "## 4. Core Idea" in body["note"]["content_markdown"]

    again = client.post(f"/papers/{paper['id']}/ai/draft-note")
    assert again.status_code == 200
    assert again.json()["note"]["id"] == body["note"]["id"]


def test_ai_draft_note_falls_back_to_template(monkeypatch):
    paper = _create_paper(title="Fallback Paper")
    import app.routers.papers as papers_router

    async def fake_draft(paper_obj, pdf_text):
        return None

    monkeypatch.setattr(papers_router, "ai_configured", lambda: True)
    monkeypatch.setattr(papers_router, "draft_reading_note", fake_draft)

    response = client.post(f"/papers/{paper['id']}/ai/draft-note")
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "template"
    assert "## 12. Knowledge to Extract" in body["note"]["content_markdown"]


def test_ai_draft_note_never_overwrites_manual_note(monkeypatch):
    paper = _create_paper(title="Manual Note Paper")
    manual = client.post("/reading-notes", json={
        "paper_id": paper["id"],
        "title": "Manual",
        "content_markdown": "# my own manual reading notes\n\nvery important",
    }).json()
    assert manual["note_source"] == "manual"

    import app.routers.papers as papers_router

    async def fake_draft(paper_obj, pdf_text):
        return "# AI draft note\n\n## 1. Why did I read this?\n\nx"

    monkeypatch.setattr(papers_router, "ai_configured", lambda: True)
    monkeypatch.setattr(papers_router, "draft_reading_note", fake_draft)

    response = client.post(f"/papers/{paper['id']}/ai/draft-note")
    assert response.status_code == 200
    body = response.json()
    assert body["note"]["id"] != manual["id"]

    notes = client.get(f"/reading-notes?paper_id={paper['id']}").json()
    assert any(note["id"] == manual["id"] and "very important" in note["content_markdown"] for note in notes)


def test_pdf_text_endpoint_reads_zotero_storage(tmp_path, monkeypatch):
    paper = _create_paper(title="PDF Text Paper", zotero_attachment_key="ATTACH99")
    storage_dir = tmp_path / "storage" / "ATTACH99"
    storage_dir.mkdir(parents=True)
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Robots manipulate objects with learned policies.")
    doc.save(str(storage_dir / "paper.pdf"))
    doc.close()

    _set_data_dir_setting(str(tmp_path))
    response = client.get(f"/papers/{paper['id']}/pdf-text")
    assert response.status_code == 200
    body = response.json()
    assert "Robots manipulate objects" in body["text"]
    assert body["pdf_path"].endswith("paper.pdf")

    _set_data_dir_setting(None)
    monkeypatch.setenv("ZOTERO_DATA_DIR", str(tmp_path / "no-such-zotero"))
    missing = client.get(f"/papers/{paper['id']}/pdf-text")
    assert missing.status_code == 409
    assert "ZOTERO_DATA_DIR_MISSING" in missing.json()["detail"]


def test_push_zotero_create_update_recreate(monkeypatch):
    paper = _create_paper(title="Push Note Paper", zotero_item_key="ITEM7")
    note = client.post("/reading-notes", json={
        "paper_id": paper["id"],
        "title": "Push Note",
        "content_markdown": "# Reading Note\n\n## 1. Why did I read this?\n\nFor the project.",
    }).json()
    assert note["zotero_note_key"] is None

    import app.routers.reading_notes as notes_router

    created = {}

    async def fake_create(parent_item_key, note_html, tags=None):
        created["parent"] = parent_item_key
        created["html"] = note_html
        created["tags"] = tags
        return {"key": "NOTE7", "version": 3}

    monkeypatch.setattr(notes_router, "create_child_note", fake_create)

    first = client.post(f"/reading-notes/{note['id']}/push-zotero")
    assert first.status_code == 200
    assert first.json()["action"] == "created"
    assert created["parent"] == "ITEM7"
    assert "<h1>" in created["html"] and "For the project." in created["html"]
    body = client.get("/reading-notes").json()
    saved = next(row for row in body if row["id"] == note["id"])
    assert saved["zotero_note_key"] == "NOTE7"

    async def fake_children(item_key):
        return [{"key": "NOTE7", "version": 5, "note": "<p>old</p>"}]

    updated = {}

    async def fake_update(note_key, version, note_html, tags=None):
        updated["key"] = note_key
        updated["version"] = version
        return {"key": note_key, "version": version + 1}

    monkeypatch.setattr(notes_router, "get_child_notes", fake_children)
    monkeypatch.setattr(notes_router, "update_child_note", fake_update)

    second = client.post(f"/reading-notes/{note['id']}/push-zotero")
    assert second.status_code == 200
    assert second.json()["action"] == "updated"
    assert updated == {"key": "NOTE7", "version": 5}

    async def fake_children_empty(item_key):
        return []

    monkeypatch.setattr(notes_router, "get_child_notes", fake_children_empty)
    third = client.post(f"/reading-notes/{note['id']}/push-zotero")
    assert third.status_code == 200
    assert third.json()["action"] == "recreated"


def test_push_zotero_requires_zotero_link():
    paper = _create_paper(title="No Zotero Paper")
    note = client.post("/reading-notes", json={
        "paper_id": paper["id"],
        "title": "Lonely Note",
        "content_markdown": "# content",
    }).json()
    response = client.post(f"/reading-notes/{note['id']}/push-zotero")
    assert response.status_code == 400
    assert "Zotero" in response.json()["detail"]
