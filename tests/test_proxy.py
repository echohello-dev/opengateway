import pytest
from fastapi.testclient import TestClient

from opengateway.config import get_settings
from opengateway.main import app
from opengateway.router import Router

ROOT = {"Authorization": "Bearer sk-root-change-me"}


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestHealth:
    def test_health(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestAuth:
    def test_missing_auth(self, client):
        response = client.post("/v1/chat/completions", json={"model": "gpt-4", "messages": []})
        assert response.status_code == 401

    def test_invalid_key(self, client):
        response = client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4", "messages": []},
            headers={"Authorization": "Bearer invalid-key"},
        )
        assert response.status_code == 401

    def test_root_key(self, client):
        response = client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4", "messages": [{"role": "user", "content": "Hello"}]},
            headers=ROOT,
        )
        # 503: the model routes to the OpenAI adapter, but no API key
        # is configured in tests (issue #46 made this distinguishable
        # from an unknown model).
        assert response.status_code == 503


class TestRoutingErrors:
    def test_unknown_model(self, client):
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "totally-unknown-model",
                "messages": [{"role": "user", "content": "hi"}],
            },
            headers=ROOT,
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "Unknown model: totally-unknown-model"

    def test_missing_api_key_is_not_unknown_model(self, client):
        response = client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
            headers=ROOT,
        )
        assert response.status_code == 503
        detail = response.json()["detail"]
        assert "no API key configured" in detail
        assert "opengateway.providers.openai" in detail


class TestProviderConfigFromSettings:
    def test_api_key_read_from_env_file_not_os_environ(self, tmp_path):
        """Regression test for #46: a ``.env`` file alone must configure
        the provider — the router must read ``Settings``, not
        ``os.environ``."""
        (tmp_path / ".env").write_text(
            "OPENAI_API_KEY=sk-from-env-file\nOPENAI_BASE_URL=http://upstream.test/v1\n"
        )
        get_settings.cache_clear()
        try:
            provider = Router().select_provider("gpt-4o-mini")
            assert provider is not None
            assert provider.api_key == "sk-from-env-file"
            assert provider.base_url == "http://upstream.test/v1"
        finally:
            get_settings.cache_clear()

    def test_env_file_only_keys_serve_requests(self, tmp_path, monkeypatch):
        """End-to-end shape of #46: a request succeeds when the key
        lives only in ``.env`` (upstream provider stubbed)."""
        (tmp_path / ".env").write_text("OPENAI_API_KEY=sk-from-env-file\n")
        get_settings.cache_clear()
        try:
            from opengateway.providers.base import ChatRequest, ChatResponse

            class FakeProvider:
                def __init__(self, api_key: str, base_url: str | None = None) -> None:
                    self.api_key = api_key
                    self.base_url = base_url

                async def chat(self, request: ChatRequest) -> ChatResponse:
                    return ChatResponse(
                        id="chatcmpl-fake",
                        model=request.model,
                        content="hi",
                        usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                        finish_reason="stop",
                    )

            def fake_load(_module: str) -> type:
                return FakeProvider

            monkeypatch.setattr("opengateway.mojo_bridge.chat._load_provider_class", fake_load)
            with TestClient(app) as test_client:
                response = test_client.post(
                    "/v1/chat/completions",
                    json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
                    headers=ROOT,
                )
            assert response.status_code == 200
            assert response.json()["choices"][0]["message"]["content"] == "hi"
        finally:
            get_settings.cache_clear()
