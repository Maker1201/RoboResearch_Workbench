import asyncio

from app.paper_integrations import zotero


def setup_function():
    zotero.configure_key_store(lambda: None, lambda key: None)
    zotero._zotero_key = None


def test_persist_key_saves_through_hook():
    saved = {}
    zotero.configure_key_store(lambda: None, lambda key: saved.update(key=key))

    zotero._persist_key("ZKEY123")

    assert saved["key"] == "ZKEY123"


def test_current_key_falls_back_to_loader():
    zotero.configure_key_store(lambda: "ZKEY-STORED", lambda key: None)
    zotero._zotero_key = None

    assert zotero._current_key() == "ZKEY-STORED"
    assert zotero._zotero_key == "ZKEY-STORED"


def test_current_key_swallows_loader_errors():
    def broken_loader():
        raise RuntimeError("db missing")

    zotero.configure_key_store(broken_loader, lambda key: None)
    zotero._zotero_key = None

    assert zotero._current_key() is None


def test_ensure_api_key_reuses_persisted_key_without_authorize():
    zotero.configure_key_store(lambda: "ZKEY-STORED", lambda key: None)
    zotero._zotero_key = None

    class FakeClient:
        async def post(self, *args, **kwargs):
            raise AssertionError("authorize should not be called when a stored key exists")

    key = asyncio.run(zotero._ensure_api_key(FakeClient(), "server-1"))
    assert key == "ZKEY-STORED"
