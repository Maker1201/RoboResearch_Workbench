import os
import tempfile
from pathlib import Path

os.environ["WORKBENCH_DATABASE_URL"] = f"sqlite:///{tempfile.gettempdir()}/roboresearch_workbench_test.db"

from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app

client = TestClient(app)


def setup_module():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def configure_obsidian(vault: Path):
    response = client.patch("/api/settings", json={
        "integrations": {
            "obsidian": {
                "enabled": True,
                "vault_path": str(vault),
                "knowledge_root": "Knowledge",
                "use_obsidian_uri": True,
            }
        },
        "paths": {"obsidian_vault": str(vault)},
    })
    assert response.status_code == 200


def test_zotero_annotation_sync_inbox_and_reading_note(monkeypatch):
    paper = client.post("/papers", json={
        "title": "Feedback-aware Task Planning",
        "venue": "ICRA",
        "status": "To Read",
        "zotero_item_key": "ITEM123",
    }).json()

    async def fake_annotations(item_key):
        assert item_key == "ITEM123"
        return [{
            "zotero_item_key": item_key,
            "zotero_annotation_key": "ANN1",
            "annotation_type": "highlight",
            "selected_text": "Execution feedback can trigger replanning in assembly tasks.",
            "comment": "#knowledge useful for long-horizon assembly",
            "page_label": "6",
            "page_index": 5,
            "tags": "knowledge",
            "date_modified": None,
        }]

    import app.routers.knowledge_workflow as router

    monkeypatch.setattr(router, "get_item_annotations", fake_annotations)
    first = client.post(f"/api/papers/{paper['id']}/zotero-annotations/sync")
    assert first.status_code == 200
    assert first.json()["synced"] == 1
    assert first.json()["inbox_created"] == 1

    second = client.post(f"/api/papers/{paper['id']}/zotero-annotations/sync").json()
    assert second["inbox_created"] == 0

    inbox = client.get("/api/knowledge/inbox?status=pending").json()
    assert len(inbox) == 1
    assert inbox[0]["zotero_annotation_key"] == "ANN1"

    note = client.post(f"/papers/{paper['id']}/reading-note").json()
    updated = client.post(f"/api/reading-notes/{note['id']}/annotations", json={"zotero_annotation_key": "ANN1"}).json()
    assert "zotero_annotation_key: ANN1" in updated["content_markdown"]
    updated_again = client.post(f"/api/reading-notes/{note['id']}/annotations", json={"zotero_annotation_key": "ANN1"}).json()
    assert updated_again["content_markdown"].count("zotero_annotation_key: ANN1") == 1


def test_append_evidence_and_create_knowledge_are_idempotent(tmp_path):
    configure_obsidian(tmp_path)
    paper = client.post("/papers", json={
        "title": "Assembly Planner Paper",
        "venue": "IROS",
        "status": "Reading",
        "zotero_item_key": "ITEM999",
    }).json()
    annotation = client.post("/api/knowledge/inbox/from-annotation", json={
        "paper_id": paper["id"],
        "zotero_annotation_key": "MISSING",
        "inbox_type": "knowledge",
    })
    assert annotation.status_code == 404

    # Seed annotation cache through sync endpoint behavior by monkeypatching Zotero.
    async def fake_annotations(_):
        return [{
            "zotero_item_key": "ITEM999",
            "zotero_annotation_key": "ANN2",
            "annotation_type": "highlight",
            "selected_text": "Behavior tree validation reduces invalid planner actions.",
            "comment": "#knowledge BT validation",
            "page_label": "4",
            "page_index": 3,
            "tags": "knowledge",
            "date_modified": None,
        }]

    import app.routers.knowledge_workflow as router

    router.get_item_annotations = fake_annotations
    client.post(f"/api/papers/{paper['id']}/zotero-annotations/sync")
    inbox = client.get("/api/knowledge/inbox?status=pending").json()[0]

    knowledge_file = tmp_path / "Knowledge" / "Robot Task Planning" / "BT-Validation.md"
    knowledge_file.parent.mkdir(parents=True)
    knowledge_file.write_text("# BT Validation\n\n## Evidence\n\n", encoding="utf-8")
    knowledge = client.post("/knowledge-links", json={
        "title": "BT Validation",
        "area": "Robot Task Planning",
        "vault_path": "Knowledge/Robot Task Planning/BT-Validation.md",
        "tags": "Behavior Tree,Validation",
    }).json()

    first = client.post(f"/api/knowledge/{knowledge['id']}/append-evidence", json={"inbox_item_id": inbox["id"]})
    assert first.status_code == 200
    second = client.post(f"/api/knowledge/{knowledge['id']}/append-evidence", json={"inbox_item_id": inbox["id"]})
    assert second.status_code == 200
    text = knowledge_file.read_text(encoding="utf-8")
    assert text.count("zotero_annotation_key: ANN2") == 1

    # Create a second inbox item and turn it into a new Obsidian-backed knowledge node.
    client.post(f"/api/papers/{paper['id']}/zotero-annotations/sync")
    created_inbox = client.post("/api/knowledge/inbox/from-annotation", json={
        "paper_id": paper["id"],
        "zotero_annotation_key": "ANN2",
        "inbox_type": "question",
    }).json()
    created = client.post("/api/knowledge/create-from-inbox", json={
        "inbox_item_id": created_inbox["id"],
        "title": "Planner Invalid Action Question",
        "category": "Robot Task Planning",
        "tags": "planning,question",
        "type": "Insight",
    })
    assert created.status_code == 200
    new_path = tmp_path / created.json()["vault_path"]
    assert new_path.exists()
    assert "zotero_annotation_key: ANN2" in new_path.read_text(encoding="utf-8")


def test_knowledge_search_matches_title_and_obsidian_text(tmp_path):
    configure_obsidian(tmp_path)
    path = tmp_path / "Knowledge" / "Task" / "Execution-Monitoring.md"
    path.parent.mkdir(parents=True)
    path.write_text("# Execution Monitoring\n\nIK failure and replanning trigger.", encoding="utf-8")
    client.post("/knowledge-links", json={
        "title": "Execution Monitoring",
        "area": "Robot Task Planning",
        "vault_path": "Knowledge/Task/Execution-Monitoring.md",
        "tags": "execution,replanning",
    })
    direct = client.get("/api/knowledge/search?q=Execution").json()
    assert direct["direct_matches"]
    related = client.get("/api/knowledge/search?q=IK failure").json()
    assert related["direct_matches"] or related["related"]


def test_manual_knowledge_supplement_is_idempotent(tmp_path):
    configure_obsidian(tmp_path)
    knowledge_file = tmp_path / "Knowledge" / "Robot Task Planning" / "Execution-Feedback.md"
    knowledge_file.parent.mkdir(parents=True)
    knowledge_file.write_text("# Execution Feedback\n\n## Evidence\n\n", encoding="utf-8")
    knowledge = client.post("/knowledge-links", json={
        "title": "Execution Feedback",
        "area": "Robot Task Planning",
        "vault_path": "Knowledge/Robot Task Planning/Execution-Feedback.md",
        "tags": "feedback,replanning",
    }).json()

    payload = {
        "manual_title": "Assembly recovery observation",
        "manual_content": "Insertion pose error can trigger a local replanning step.",
        "manual_comment": "This is useful for long-horizon assembly tasks.",
        "tags": "assembly,replanning",
    }
    first = client.post(f"/api/knowledge/{knowledge['id']}/append-evidence", json=payload)
    assert first.status_code == 200
    second = client.post(f"/api/knowledge/{knowledge['id']}/append-evidence", json=payload)
    assert second.status_code == 200
    text = knowledge_file.read_text(encoding="utf-8")
    assert text.count("manual_evidence_key:") == 1
    assert "Insertion pose error" in text
