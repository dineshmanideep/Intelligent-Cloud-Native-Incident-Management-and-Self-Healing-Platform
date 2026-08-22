import asyncio

from httpx import ASGITransport, AsyncClient, Response

from backend.app.main import app


def request(path: str) -> Response:
    async def make_request() -> Response:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(path)

    return asyncio.run(make_request())


def test_health() -> None:
    response = request("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_hello() -> None:
    response = request("/api/hello")

    assert response.status_code == 200
    assert "Hello" in response.json()["message"]


def test_controlled_error() -> None:
    response = request("/api/error")

    assert response.status_code == 500


def test_metrics() -> None:
    response = request("/metrics")

    assert response.status_code == 200
    assert "http_requests_total" in response.text
