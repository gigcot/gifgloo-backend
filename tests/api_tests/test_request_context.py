from fastapi import FastAPI
from fastapi.testclient import TestClient

from shared.request_context import RequestContextMiddleware, current_request_id


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/request-id")
    async def request_id():
        return {"request_id": current_request_id.get()}

    return app


def test_preserves_proxied_request_id() -> None:
    with TestClient(_app()) as client:
        response = client.get(
            "/request-id",
            headers={"X-Request-ID": "nginx-request-id"},
        )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "nginx-request-id"
    assert response.json() == {"request_id": "nginx-request-id"}


def test_generates_request_id_without_proxy_header() -> None:
    with TestClient(_app()) as client:
        response = client.get("/request-id")

    request_id = response.headers["X-Request-ID"]
    assert len(request_id) == 32
    assert response.json() == {"request_id": request_id}
