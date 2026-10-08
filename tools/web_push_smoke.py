"""Local, opt-in transport test. No .env, database, storage, or AI clients."""

import asyncio
import base64
import secrets
import uuid
from pathlib import Path

import uvicorn
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from composition.adapter.inbound.fastapi.push_subscription import validate_push_subscription
from composition.adapter.outbound.web_push_adapter import WebPushAdapter
from composition.application.ports.outbound.completion_push_port import CompletionPushCommand
from shared.exceptions import ValidationException

ORIGIN = "http://localhost:8766"
FRONTEND = Path(__file__).resolve().parents[2] / "gifgloo-frontend"


class SmokeKeysCommand(BaseModel):
    p256dh: str = Field(min_length=80, max_length=128)
    auth: str = Field(min_length=20, max_length=64)


class SmokeSubscriptionCommand(BaseModel):
    endpoint: str = Field(min_length=10, max_length=4096)
    keys: SmokeKeysCommand


def create_app():
    key = ec.generate_private_key(ec.SECP256R1())
    private_key = base64.urlsafe_b64encode(key.private_numbers().private_value.to_bytes(32, "big")).decode().rstrip("=")
    public_key = base64.urlsafe_b64encode(key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)).decode().rstrip("=")
    push = WebPushAdapter(private_key, "mailto:support@gifgloo.com")
    token, job_id = secrets.token_urlsafe(32), str(uuid.uuid4())
    state = {"status": "idle"}
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost"])

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        if request.headers["host"] != "localhost:8766":
            return JSONResponse({"detail": "Local test origin required"}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    def require_session(request: Request):
        if not secrets.compare_digest(request.cookies.get("push_smoke", ""), token):
            raise HTTPException(401, "테스트 페이지에서 먼저 시작해주세요.")

    @app.get("/", response_class=HTMLResponse)
    def index():
        response = HTMLResponse((Path(__file__).with_name("web_push_smoke.html")).read_text())
        response.set_cookie("push_smoke", token, httponly=True, samesite="strict", max_age=600)
        return response

    @app.get("/config")
    def config(request: Request):
        require_session(request)
        return {"public_key": public_key, "csrf": token}

    @app.get("/completion-notifications-sw.js")
    def worker():
        return FileResponse(FRONTEND / "public/completion-notifications-sw.js", media_type="application/javascript")

    @app.get("/icon.png")
    def icon():
        return FileResponse(FRONTEND / "public/icon.png", media_type="image/png")

    async def send(command):
        await asyncio.sleep(8)
        state["status"] = await push.send(command)
        print(f"Local push test: {state['status']} (service acceptance is not device receipt)", flush=True)

    @app.post("/send", status_code=202)
    def schedule(body: SmokeSubscriptionCommand, request: Request, tasks: BackgroundTasks):
        require_session(request)
        if request.headers.get("origin") != ORIGIN or not secrets.compare_digest(request.headers.get("x-smoke-token", ""), token):
            raise HTTPException(403, "테스트 페이지에서 요청해주세요.")
        if state["status"] != "idle":
            raise HTTPException(409, "한 번만 발송하는 테스트입니다. 재시험은 서버를 재시작해주세요.")
        try:
            validate_push_subscription(body.endpoint, body.keys.p256dh, body.keys.auth)
        except ValidationException:
            raise HTTPException(422, "지원되지 않는 구독 정보입니다.") from None
        state["status"] = "scheduled"
        tasks.add_task(send, CompletionPushCommand(body.endpoint, body.keys.p256dh, body.keys.auth, job_id))
        return {"status": "scheduled"}

    @app.get("/status")
    def status(request: Request):
        require_session(request)
        return state

    @app.get("/my-assets", response_class=HTMLResponse)
    def result(request: Request, job: str):
        require_session(request)
        if job != job_id:
            raise HTTPException(404, "테스트 결과가 없습니다.")
        return "<html lang='ko'><meta charset='utf-8'><title>알림 복귀 확인</title><h1>알림 클릭 복귀 확인</h1><p>실제 합성물이 아닌 테스트입니다. 서버 발송 → 브라우저 알림 → 같은 브라우저 복귀를 확인했어요.</p><p>운영 로그인·결과 소유권이나 모바일 호환성을 대신 검증한 것은 아닙니다.</p><a href='/'>테스트 구독 정리하기</a></html>"

    return app


if __name__ == "__main__":
    print(f"Open {ORIGIN}. Sends ONE real push only after your permission and button click.", flush=True)
    uvicorn.run(create_app(), host="127.0.0.1", port=8766, access_log=False)
