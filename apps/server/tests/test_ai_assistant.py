import asyncio
from types import SimpleNamespace

from app.paper_integrations import ai_assistant


def _configure_ai(monkeypatch, provider="openai-compatible", model="test-model"):
    monkeypatch.setenv("AI_PROVIDER", provider)
    monkeypatch.setenv("AI_API_BASE", "https://ai.example.com/v1")
    monkeypatch.setenv("AI_API_KEY", "sk-test")
    monkeypatch.setenv("AI_MODEL", model)
    monkeypatch.setenv("AI_OUTPUT_LANGUAGE", "zh")
    monkeypatch.setenv("AI_RESEARCH_INTERESTS", "VLA, manipulation")


def test_ai_status_requires_provider_and_model(monkeypatch):
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.delenv("AI_MODEL", raising=False)
    assert ai_assistant.ai_status()["configured"] is False

    _configure_ai(monkeypatch)
    status = ai_assistant.ai_status()
    assert status["configured"] is True
    assert status["model"] == "test-model"
    assert status["output_language"] == "zh"


def test_draft_reading_note_unconfigured_returns_none(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "none")
    called = {}

    def _fail(*args, **kwargs):
        called["hit"] = True
        return "should not be called"

    monkeypatch.setattr(ai_assistant, "_chat", _fail)
    paper = SimpleNamespace(title="T", authors="A", year=2025, venue="ICRA", abstract="Abs")
    assert asyncio.run(ai_assistant.draft_reading_note(paper, None)) is None
    assert not called


def test_draft_reading_note_returns_cleaned_markdown(monkeypatch):
    _configure_ai(monkeypatch)
    captured = {}

    async def _fake_chat(settings, system, user, temperature, timeout):
        captured["user"] = user
        return "```markdown\n" + "\n\n".join(ai_assistant.NOTE_SECTIONS[:8]) + "\ncontent\n```"

    monkeypatch.setattr(ai_assistant, "_chat", _fake_chat)
    paper = SimpleNamespace(title="Test Paper", authors="A. Robot", year=2025, venue="ICRA", abstract="An abstract")
    note = asyncio.run(ai_assistant.draft_reading_note(paper, "PDF body text"))

    assert note is not None
    assert not note.startswith("```")
    assert ai_assistant.NOTE_SECTIONS[1] in note
    assert "PDF body text" in captured["user"]
    assert "VLA" in captured["user"]


def test_draft_reading_note_rejects_incomplete_output(monkeypatch):
    _configure_ai(monkeypatch)

    async def _fake_chat(settings, system, user, temperature, timeout):
        return "Sorry, I cannot help with that."

    monkeypatch.setattr(ai_assistant, "_chat", _fake_chat)
    paper = SimpleNamespace(title="T", authors=None, year=None, venue=None, abstract=None)
    assert asyncio.run(ai_assistant.draft_reading_note(paper, "text")) is None


def test_triage_papers_parses_and_validates_rows(monkeypatch):
    _configure_ai(monkeypatch)
    payload = [
        {"id": 1, "one_liner": "第一篇论文总结", "relevance": 88.4, "suggested_mode": "read"},
        {"id": "bad", "one_liner": "skip", "relevance": 10, "suggested_mode": "DEEP"},
        {"id": 3, "one_liner": "", "relevance": "140", "suggested_mode": "WARP"},
        "not-a-dict",
    ]

    async def _fake_chat(settings, system, user, temperature, timeout):
        return "```json\n" + __import__("json").dumps(payload) + "\n```"

    monkeypatch.setattr(ai_assistant, "_chat", _fake_chat)
    papers = [
        SimpleNamespace(id=1, title="T1", abstract="A1", venue="ICRA", year=2025),
        SimpleNamespace(id=3, title="T3", abstract="A3", venue="RA-L", year=2024),
    ]
    rows = asyncio.run(ai_assistant.triage_papers(papers))
    assert len(rows) == 2
    assert rows[0] == {"id": 1, "one_liner": "第一篇论文总结", "relevance": 88, "suggested_mode": "READ"}
    assert rows[1]["relevance"] == 100
    assert rows[1]["suggested_mode"] is None
    assert rows[1]["one_liner"] is None


def test_triage_papers_unconfigured_or_failed(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "none")
    papers = [SimpleNamespace(id=1, title="T", abstract="A", venue="V", year=2025)]
    assert asyncio.run(ai_assistant.triage_papers(papers)) == []

    _configure_ai(monkeypatch)

    async def _fail_chat(*args, **kwargs):
        return None

    monkeypatch.setattr(ai_assistant, "_chat", _fail_chat)
    assert asyncio.run(ai_assistant.triage_papers(papers)) == []

    async def _garbage_chat(*args, **kwargs):
        return " totally not json "

    monkeypatch.setattr(ai_assistant, "_chat", _garbage_chat)
    assert asyncio.run(ai_assistant.triage_papers(papers)) == []
