import httpx
import pytest

from app.main import app


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.anyio
async def test_health_returns_200(client: httpx.AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_health_body(client: httpx.AsyncClient):
    data = (await client.get("/health")).json()
    assert data == {"status": "ok", "version": "0.1.0", "account_exists": False}
