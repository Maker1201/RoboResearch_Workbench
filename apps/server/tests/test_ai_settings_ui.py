import os
import tempfile

os.environ["WORKBENCH_DATABASE_URL"] = f"sqlite:///{tempfile.gettempdir()}/roboresearch_ai_settings_test.db"

from fastapi.testclient import TestClient

from app import bootstrap
from app.database import Base, engine
from app.main import app
from app.paper_integrations.ai_assistant import ai_settings, configure_settings_loader


client = TestClient(app)


def setup_module():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def teardown_module():
    configure_settings_loader(lambda: {})


def test_ai_settings_roundtrip_masks_secret():
    response = client.patch("/api/settings", json={
        "integrations": {
            "ai": {
                "provider": "openai-compatible",
                "api_base": "http://127.0.0.1:9/v1",
                "api_key": "sk-secret-123456789",
                "model": "glm-5",
                "output_language": "zh",
                "research_interests": "VLA, manipulation",
                "max_pdf_chars": 30000,
            },
            "zotero": {"data_dir": "/home/robot/Zotero"},
        }
    })
    assert response.status_code == 200
    payload = response.json()
    ai = payload["integrations"]["ai"]
    assert ai["provider"] == "openai-compatible"
    assert ai["api_base"] == "http://127.0.0.1:9/v1"
    assert ai["api_key"] is None
    assert ai["api_key_masked"]
    assert ai["model"] == "glm-5"
    assert ai["max_pdf_chars"] == 30000
    assert payload["integrations"]["zotero"]["data_dir"] == "/home/robot/Zotero"
    assert "sk-secret" not in str(payload)


def test_stored_settings_flow_into_ai_assistant(monkeypatch):
    monkeypatch.setenv("AI_MODEL", "env-model")
    bootstrap.configure_integrations()
    settings = ai_settings()
    assert settings.provider == "openai-compatible"
    assert settings.model == "glm-5"
    assert settings.api_key == "sk-secret-123456789"
    assert settings.max_pdf_chars == 30000
    assert settings.research_interests == "VLA, manipulation"


def test_empty_stored_values_fall_back_to_env(monkeypatch):
    bootstrap.configure_integrations()
    configure_settings_loader(lambda: {"provider": "", "model": "", "api_key": "", "max_pdf_chars": ""})
    monkeypatch.setenv("AI_PROVIDER", "openai-compatible")
    monkeypatch.setenv("AI_MODEL", "env-model")
    monkeypatch.setenv("AI_API_KEY", "env-key")
    settings = ai_settings()
    assert settings.provider == "openai-compatible"
    assert settings.model == "env-model"
    assert settings.api_key == "env-key"
    assert settings.max_pdf_chars == 60000


def test_ai_connection_test_endpoint_uses_draft(monkeypatch):
    import app.routers.settings as settings_router
    captured = {}

    async def fake_test(provider, api_base, api_key, model):
        captured.update(provider=provider, api_base=api_base, api_key=api_key, model=model)
        return True, f"AI 接口可用（模型：{model}）。"

    monkeypatch.setattr(settings_router, "test_connection", fake_test)
    response = client.post("/api/settings/test/ai", json={
        "integrations": {"ai": {"provider": "openai-compatible", "api_base": "https://draft.example.com/v1", "api_key": "draft-key", "model": "draft-model"}}
    })
    assert response.status_code == 200
    assert response.json() == {"ok": True, "message": "AI 接口可用（模型：draft-model）。"}
    assert captured["api_base"] == "https://draft.example.com/v1"
    assert captured["api_key"] == "draft-key"


def test_ai_connection_test_endpoint_reports_failure():
    # 未 monkeypatch：走真实路径，连接 127.0.0.1:9 立即被拒绝，快速返回失败
    response = client.post("/api/settings/test/ai", json={"integrations": {"ai": {}}})
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert "无法" in body["message"] or "未启用" in body["message"] or "填写" in body["message"]
