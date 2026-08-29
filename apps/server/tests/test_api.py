import os
import tempfile

os.environ["WORKBENCH_DATABASE_URL"] = f"sqlite:///{tempfile.gettempdir()}/roboresearch_workbench_test.db"

from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app


client = TestClient(app)


def setup_module():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_task_crud_round_trip():
    created = client.post("/tasks", json={"title": "Run baseline experiment", "priority": "high"}).json()
    assert created["title"] == "Run baseline experiment"

    updated = client.patch(f"/tasks/{created['id']}", json={"status": "done"}).json()
    assert updated["status"] == "done"


def test_knowledge_link_crud_round_trip():
    created = client.post("/knowledge-links", json={
        "title": "Action Representation",
        "area": "Embodied AI",
        "obsidian_uri": "obsidian://open?vault=Research&file=EmbodiedAI/VLA/Action",
    }).json()
    assert created["area"] == "Embodied AI"


def test_project_progress_log_round_trip():
    project = client.post("/projects", json={
        "name": "Progress Test Project",
        "path": tempfile.gettempdir(),
        "status": "active",
        "progress": 0,
    }).json()

    created = client.post("/project-progress", json={
        "project_id": project["id"],
        "date": "2026-08-27",
        "stage": "Experiment",
        "completed": "Ran baseline\nSaved metrics",
        "pending": "Analyze failures",
        "progress_note": "Daily overview note",
    })
    assert created.status_code == 200
    item = created.json()
    assert item["stage"] == "Experiment"

    listed = client.get("/project-progress?date=2026-08-27").json()
    assert any(row["id"] == item["id"] for row in listed)

    updated = client.patch(f"/project-progress/{item['id']}", json={"pending": "Write report"}).json()
    assert updated["pending"] == "Write report"

    deleted = client.delete(f"/project-progress/{item['id']}").json()
    assert deleted["ok"] is True



def test_settings_round_trip_masks_secrets():
    payload = {
        "general": {"language": "en-US"},
        "paths": {
            "projects_root": tempfile.gettempdir(),
            "knowledge_root": tempfile.gettempdir(),
            "obsidian_vault": tempfile.gettempdir(),
            "dataset_root": tempfile.gettempdir(),
            "experiment_root": tempfile.gettempdir(),
        },
        "integrations": {
            "obsidian": {"enabled": True, "vault_path": tempfile.gettempdir(), "knowledge_root": "Knowledge", "use_obsidian_uri": True},
            "zotero": {"enabled": True, "connection_mode": "web_api", "user_id": "123", "api_key": "zotero-secret-token", "library": "My Library"},
            "github": {"enabled": True, "username": "robot", "personal_access_token": "github-secret-token", "default_owner": "robot", "default_branch": "main"},
        },
    }
    response = client.patch("/api/settings", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["general"]["language"] == "en-US"
    assert data["integrations"]["zotero"]["api_key"] is None
    assert data["integrations"]["zotero"]["api_key_masked"] != "zotero-secret-token"
    assert data["integrations"]["github"]["personal_access_token"] is None
    assert data["integrations"]["github"]["personal_access_token_masked"] != "github-secret-token"


def test_dashboard_summary_shape():
    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    data = response.json()
    assert set(data.keys()) == {"today", "projects", "papers", "experiments", "knowledge", "git", "focus", "attention"}
    assert "tasks" in data["today"]
    assert "counts" in data["projects"]
    assert "venue_counts" in data["papers"]


def test_focus_session_lifecycle():
    task = client.post("/tasks", json={"title": "Focus on OpenVLA", "priority": "high"}).json()
    started = client.post("/api/focus/start", json={"task_id": task["id"], "project_id": None, "note": "read method"})
    assert started.status_code == 200
    session = started.json()
    assert session["status"] == "RUNNING"
    assert session["task_title"] == "Focus on OpenVLA"

    current = client.get("/api/focus/current").json()["current_session"]
    assert current["id"] == session["id"]

    paused = client.post(f"/api/focus/{session['id']}/pause").json()
    assert paused["status"] == "PAUSED"

    resumed = client.post(f"/api/focus/{session['id']}/resume").json()
    assert resumed["status"] == "RUNNING"

    finished = client.post(f"/api/focus/{session['id']}/finish").json()
    assert finished["status"] == "COMPLETED"
    assert finished["ended_at"] is not None

    stats = client.get("/api/focus/stats?range=today").json()
    assert stats["duration_seconds"] >= 0
    assert client.get("/api/focus/current").json()["current_session"] is None


def test_literature_candidate_queue_note_export_and_focus():
    paper_payload = {
        "title": "Workflow Test Paper",
        "authors": "Ada Lovelace, Grace Hopper",
        "year": 2026,
        "venue": "ICRA",
        "abstract": "A paper used to verify the literature workflow.",
        "doi": "10.1234/workflow-test-paper",
        "status": "Candidate",
    }
    created = client.post("/papers", json=paper_payload)
    assert created.status_code == 200
    paper = created.json()
    assert paper["status"] == "Candidate"

    duplicate = client.post("/papers", json={**paper_payload, "title": "Workflow Test Paper", "priority": "high"}).json()
    assert duplicate["id"] == paper["id"]
    assert duplicate["priority"] == "high"

    queued = client.post(f"/papers/{paper['id']}/queue", json={
        "priority": "high",
        "reading_purpose": "Learn Method",
        "related_project_id": None,
        "reading_mode": "SKIM",
    }).json()
    assert queued["status"] == "To Read"
    assert queued["reading_purpose"] == "Learn Method"
    assert queued["reading_mode"] == "SKIM"
    assert queued["queued_at"] is not None

    note = client.post(f"/papers/{paper['id']}/reading-note").json()
    assert note["paper_id"] == paper["id"]
    assert "Why did I read this?" in note["content_markdown"]

    saved = client.patch(f"/reading-notes/{note['id']}", json={
        "one_sentence_summary": "A concise workflow verification note.",
        "relevance_to_me": "Useful for checking persistence.",
        "content_markdown": note["content_markdown"] + "\nExtra observation.",
    }).json()
    assert saved["content"] == saved["content_markdown"]
    assert saved["one_sentence_summary"].startswith("A concise")

    exported = client.get(f"/reading-notes/{note['id']}/export").json()
    assert exported["filename"].endswith(".md")
    assert "zotero_item_key" in exported["content"]
    assert "Extra observation." in exported["content"]

    started = client.post("/api/focus/start", json={
        "paper_id": paper["id"],
        "reading_note_id": note["id"],
        "context_type": "PAPER_READING",
        "focus_type": "PAPER_READING",
    }).json()
    assert started["paper_id"] == paper["id"]
    assert started["reading_note_id"] == note["id"]
    assert started["context_type"] == "PAPER_READING"
    client.post(f"/api/focus/{started['id']}/finish")

def test_attach_pdf_to_paper_updates_local_zotero_status(monkeypatch):
    paper_payload = {
        "title": "Manual PDF Attachment Paper",
        "authors": "Haichao Liu",
        "year": 2025,
        "venue": "IROS",
        "status": "To Read",
        "zotero_item_key": "ZITEM123",
        "zotero_key": "ZITEM123",
    }
    paper = client.post("/papers", json=paper_payload).json()

    async def fake_attach_pdf_to_zotero(payload):
        assert payload.item_key == "ZITEM123"
        assert payload.filename == "paper.pdf"
        assert payload.content_base64 == "JVBERi0xLjc="
        return {"status": "ok", "message": "PDF 已挂载到 Zotero。", "item_key": payload.item_key}

    monkeypatch.setattr("app.main.attach_pdf_to_zotero", fake_attach_pdf_to_zotero)

    response = client.post(f"/papers/{paper['id']}/attach-pdf", json={
        "filename": "paper.pdf",
        "content_type": "application/pdf",
        "content_base64": "JVBERi0xLjc=",
    })

    assert response.status_code == 200
    data = response.json()
    assert data["zotero_pdf_attached"] is True
    assert data["zotero_pdf_status"] == "attached"
    assert data["zotero_synced_at"] is not None

