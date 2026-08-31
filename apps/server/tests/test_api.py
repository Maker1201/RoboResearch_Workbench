import os
import subprocess
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


def test_project_discovery_includes_configured_projects_folder():
    root = tempfile.mkdtemp()
    top_project = os.path.join(root, "TopProject")
    nested_project = os.path.join(root, "Projects", "NestedProject")
    os.makedirs(top_project)
    os.makedirs(nested_project)
    subprocess.run(["git", "init"], cwd=top_project, check=True, capture_output=True)
    subprocess.run(["git", "init"], cwd=nested_project, check=True, capture_output=True)

    client.patch("/api/settings", json={"paths": {
        "projects_root": root,
        "knowledge_root": root,
        "obsidian_vault": root,
        "dataset_root": root,
        "experiment_root": root,
    }})

    directories = client.get("/filesystem/directories").json()
    assert directories["path"] == root

    discovered = client.get("/projects/discover").json()
    discovered_paths = {item["path"] for item in discovered}
    assert os.path.realpath(top_project) in discovered_paths
    assert os.path.realpath(nested_project) in discovered_paths


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
        return {"status": "ok", "message": "PDF 已挂载到 Zotero。", "item_key": payload.item_key, "attachment_key": "ZATT123", "pdf_source": "LOCAL_FILE"}

    monkeypatch.setattr("app.routers.papers.attach_pdf_to_zotero", fake_attach_pdf_to_zotero)

    response = client.post(f"/papers/{paper['id']}/attach-pdf", json={
        "filename": "paper.pdf",
        "content_type": "application/pdf",
        "content_base64": "JVBERi0xLjc=",
    })

    assert response.status_code == 200
    data = response.json()
    assert data["zotero_pdf_attached"] is True
    assert data["zotero_pdf_status"] == "ATTACHED"
    assert data["pdf_status"] == "ATTACHED"
    assert data["pdf_source"] == "LOCAL_FILE"
    assert data["zotero_attachment_key"] == "ZATT123"
    assert data["zotero_synced_at"] is not None


def test_settings_test_endpoint_paths_and_unknown():
    ok = client.post("/api/settings/test/paths", json={"paths": {
        "projects_root": tempfile.gettempdir(),
        "knowledge_root": tempfile.gettempdir(),
        "obsidian_vault": tempfile.gettempdir(),
        "dataset_root": tempfile.gettempdir(),
        "experiment_root": tempfile.gettempdir(),
    }}).json()
    assert ok["ok"] is True

    missing = client.post("/api/settings/test/paths", json={"paths": {
        "projects_root": tempfile.gettempdir(),
        "dataset_root": "/nonexistent/workbench-path-xyz",
    }}).json()
    assert missing["ok"] is False
    assert "dataset_root" in missing["message"]

    assert client.post("/api/settings/test/unknown").status_code == 404


def test_paper_knowledge_link_round_trip():
    paper = client.post("/papers", json={
        "title": "Knowledge Link Paper",
        "authors": "A. Author",
        "year": 2026,
        "venue": "ICRA",
        "status": "To Read",
    }).json()
    knowledge = client.post("/knowledge-links", json={
        "title": "Policy Distillation",
        "area": "Robot Learning",
    }).json()

    linked = client.put(f"/papers/{paper['id']}/knowledge-links/{knowledge['id']}")
    assert linked.status_code == 200
    detail = client.get(f"/papers/{paper['id']}/detail").json()
    assert [item["id"] for item in detail["knowledge_links"]] == [knowledge["id"]]

    unlinked = client.delete(f"/papers/{paper['id']}/knowledge-links/{knowledge['id']}")
    assert unlinked.status_code == 200
    detail_after = client.get(f"/papers/{paper['id']}/detail").json()
    assert detail_after["knowledge_links"] == []


def test_delete_project_removes_registration_and_clears_loose_links():
    project_dir = tempfile.mkdtemp()
    project = client.post("/projects", json={
        "name": "Delete Me Project",
        "path": project_dir,
        "status": "active",
    }).json()
    paper = client.post("/papers", json={
        "title": "Project Linked Paper",
        "authors": "A. Author",
        "year": 2026,
        "venue": "ICRA",
        "status": "To Read",
    }).json()
    client.patch(f"/papers/{paper['id']}", json={"related_project_id": project["id"]})

    deleted = client.delete(f"/projects/{project['id']}")
    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True
    assert client.get(f"/projects/{project['id']}/detail").status_code == 404
    assert os.path.isdir(project_dir)
    assert client.get(f"/papers/{paper['id']}/detail").json()["paper"]["related_project_id"] is None


def test_refresh_projects_git_returns_list():
    project = client.post("/projects", json={
        "name": "Refresh Git Project",
        "path": tempfile.mkdtemp(),
        "status": "active",
    }).json()
    response = client.post("/projects/refresh-git")
    assert response.status_code == 200
    projects = response.json()
    assert any(item["id"] == project["id"] for item in projects)
    assert all("health" in item for item in projects)



def test_check_zotero_deleted_item_clears_local_link(monkeypatch):
    from app.paper_integrations.zotero import ZoteroItemNotFound

    paper = client.post("/papers", json={
        "title": "Deleted Zotero Item Paper",
        "authors": "A. Author",
        "year": 2026,
        "venue": "ICRA",
        "status": "To Read",
        "zotero_item_key": "ZDELETED1",
        "zotero_key": "ZDELETED1",
        "zotero_attachment_key": "ZATTOLD",
        "zotero_pdf_attached": True,
        "zotero_pdf_status": "ATTACHED",
        "pdf_status": "ATTACHED",
        "pdf_source": "ZOTERO",
    }).json()

    async def fake_get_zotero_item_sync_state(item_key):
        raise ZoteroItemNotFound(item_key)

    monkeypatch.setattr("app.routers.papers.get_zotero_item_sync_state", fake_get_zotero_item_sync_state)

    response = client.post(f"/papers/{paper['id']}/zotero/check")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == paper["id"]
    assert data["zotero_item_key"] is None
    assert data["zotero_key"] is None
    assert data["zotero_attachment_key"] is None
    assert data["zotero_pdf_attached"] is False
    assert data["zotero_pdf_status"] == "ZOTERO_ITEM_DELETED"
    assert data["pdf_status"] == "NONE"
    assert data["pdf_error_code"] == "ZOTERO_ITEM_DELETED"


def test_sync_zotero_deleted_item_clears_local_link(monkeypatch):
    from app.paper_integrations.zotero import ZoteroItemNotFound

    paper = client.post("/papers", json={
        "title": "Bulk Deleted Zotero Item Paper",
        "authors": "A. Author",
        "year": 2026,
        "venue": "IROS",
        "status": "To Read",
        "zotero_item_key": "ZDELETED2",
        "zotero_key": "ZDELETED2",
        "zotero_attachment_key": "ZATTOLD2",
        "zotero_pdf_attached": True,
        "zotero_pdf_status": "ATTACHED",
        "pdf_status": "ATTACHED",
        "pdf_source": "ZOTERO",
    }).json()

    async def fake_get_zotero_item_sync_state(item_key):
        if item_key == "ZDELETED2":
            raise ZoteroItemNotFound(item_key)
        return {"item_key": item_key, "pdf_attached": False, "pdf_status": "NONE"}

    monkeypatch.setattr("app.routers.papers.get_zotero_item_sync_state", fake_get_zotero_item_sync_state)

    response = client.post("/zotero/sync")

    assert response.status_code == 200
    sync = response.json()
    assert sync["deleted"] >= 1
    assert not sync["failed"]
    data = client.get(f"/papers/{paper['id']}/detail").json()["paper"]
    assert data["zotero_item_key"] is None
    assert data["zotero_attachment_key"] is None
    assert data["pdf_error_code"] == "ZOTERO_ITEM_DELETED"
