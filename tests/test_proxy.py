import pytest
from fastapi.testclient import TestClient

from opengateway.main import app


@pytest.fixture
def client():
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
            headers={"Authorization": "Bearer sk-root-change-me"},
        )
        # 400 because no provider is configured in tests
        assert response.status_code == 400
