import os
import uuid
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from fastapi.responses import JSONResponse, Response

from config.user import get_record_signup_consent_service, get_user_service, get_anonymous_session_service
from shared.session_token import decode_session_token
from user.application.ports.inbound.change_role import ChangeRoleCommand
from user.application.ports.inbound.deactivate_user import DeactivateUserCommand
from user.application.ports.inbound.get_user import GetUserQuery
from user.application.ports.inbound.record_signup_consent import RecordSignupConsentCommand
from user.application.ports.inbound.update_email import UpdateEmailCommand
from user.application.services.change_role_service import ChangeRoleService
from user.application.services.deactivate_user_service import DeactivateUserService
from user.application.services.get_user_service import GetUserService
from user.application.services.record_signup_consent_service import RecordSignupConsentService
from user.application.services.update_email_service import UpdateEmailService
from user.domain.aggregates.user import UserRole, UserStatus
from user.domain.value_objects.acquisition import Acquisition
from user.application.ports.inbound.anonymous_session import AnonymousSessionCommand
from user.application.services.create_anonymous_session_service import CreateAnonymousSessionService
from user.adapter.inbound.fastapi.session import BOOTSTRAP_COOKIE, set_user_cookie
from user.adapter.inbound.fastapi.oauth2 import AcquisitionCommand



router = APIRouter(prefix="/users", tags=["users"])

SECRET_KEY = os.getenv("JWT_SECRET_KEY")


class UpdateEmailBody(BaseModel):
    email: str


class ChangeRoleBody(BaseModel):
    new_role: UserRole


class RecordSignupConsentBody(BaseModel):
    terms_version: str
    privacy_version: str
    is_fourteen_or_older: bool


class AnonymousSessionBody(BaseModel):
    acquisition: AcquisitionCommand | None = None


def _get_user_id(request: Request) -> str:
    token = request.cookies.get("user_token")
    if token is None:
        raise HTTPException(401, "유효하지 않은 사용자입니다")
    try:
        payload = decode_session_token(token, SECRET_KEY)
        return payload["user_id"]
    except (jwt.InvalidTokenError, KeyError):
        raise HTTPException(401, "유효하지 않은 사용자입니다")


@router.get("/me")
def get_current_user(
    request: Request,
    response: Response,
    service: GetUserService = Depends(get_user_service),
):
    result = service.execute(GetUserQuery(user_id=_get_user_id(request)))
    payload = decode_session_token(request.cookies["user_token"], SECRET_KEY)
    if result.status != UserStatus.ACTIVE or result.session_version != payload["session_version"]:
        raise HTTPException(401, "유효하지 않은 세션입니다")
    set_user_cookie(response, result.user_id, result.user_kind, result.session_version, "review_login" in payload and payload["review_login"] is True)
    return {"ok": True, "user_id": result.user_id, "email": result.email, "user_kind": result.user_kind, "consent_required": result.consent_required}


@router.post("/anonymous-session")
def prepare_anonymous_session(
    body: AnonymousSessionBody,
    request: Request,
    users: GetUserService = Depends(get_user_service),
    service: CreateAnonymousSessionService = Depends(get_anonymous_session_service),
):
    token = request.cookies.get("user_token")
    if token is not None:
        try:
            payload = decode_session_token(token, SECRET_KEY)
        except jwt.InvalidTokenError:
            response = JSONResponse({"message": "세션이 만료되었습니다. 다시 시도해주세요"}, status_code=401)
            response.delete_cookie("user_token")
            return response
        user = users.execute(GetUserQuery(payload["user_id"]))
        if (
            user.status != UserStatus.ACTIVE or user.session_version != payload["session_version"]
            or ("user_kind" not in payload and user.user_kind != "member")
        ):
            response = JSONResponse({"message": "세션이 변경되었습니다. 다시 시도해주세요"}, status_code=401)
            response.delete_cookie("user_token")
            return response
        response = JSONResponse({"ready": True, "created": False, "user_id": user.user_id, "user_kind": user.user_kind, "email": user.email, "consent_required": user.consent_required})
        set_user_cookie(response, user.user_id, user.user_kind, user.session_version, "review_login" in payload and payload["review_login"] is True)
        response.delete_cookie(BOOTSTRAP_COOKIE)
        return response

    bootstrap = request.cookies.get(BOOTSTRAP_COOKIE)
    if bootstrap is None:
        seed = jwt.encode({
            "user_id": str(uuid.uuid4()), "purpose": "anonymous_bootstrap",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
        }, SECRET_KEY, algorithm="HS256")
        response = JSONResponse({"ready": False}, status_code=202)
        response.set_cookie(BOOTSTRAP_COOKIE, seed, max_age=600, httponly=True, samesite="lax", secure=os.getenv("COOKIE_SECURE", "true").lower() == "true")
        return response
    try:
        seed = jwt.decode(bootstrap, SECRET_KEY, algorithms=["HS256"], options={"require": ["exp", "user_id", "purpose"]})
        if seed["purpose"] != "anonymous_bootstrap":
            raise jwt.InvalidTokenError("준비 토큰이 아닙니다")
        user_id = str(uuid.UUID(seed["user_id"]))
    except (jwt.InvalidTokenError, ValueError, TypeError, AttributeError):
        response = JSONResponse({"message": "세션 준비가 만료되었습니다. 다시 시도해주세요"}, status_code=401)
        response.delete_cookie(BOOTSTRAP_COOKIE)
        return response
    acquisition = Acquisition(**body.acquisition.model_dump()) if body.acquisition else None
    if acquisition is not None and not any(asdict(acquisition).values()):
        acquisition = None
    result = service.execute(AnonymousSessionCommand(user_id, acquisition))
    response = JSONResponse({"ready": True, "created": result.created, "user_id": result.user_id, "user_kind": "anonymous", "email": None, "consent_required": users.execute(GetUserQuery(result.user_id)).consent_required})
    set_user_cookie(response, result.user_id, "anonymous", result.session_version)
    response.delete_cookie(BOOTSTRAP_COOKIE)
    return response


@router.post("/me/consents")
def record_signup_consent(
    body: RecordSignupConsentBody,
    request: Request,
    service: RecordSignupConsentService = Depends(get_record_signup_consent_service),
):
    result = service.execute(
        RecordSignupConsentCommand(
            user_id=_get_user_id(request),
            terms_version=body.terms_version,
            privacy_version=body.privacy_version,
            is_fourteen_or_older=body.is_fourteen_or_older,
        )
    )
    return {
        "terms_version": result.terms_version,
        "privacy_version": result.privacy_version,
        "is_fourteen_or_older": result.is_fourteen_or_older,
        "agreed_at": result.agreed_at,
    }


# @router.post("/me/deactivate")
# def deactivate(
#     service: DeactivateUserService = Depends(),
#     user_id: str = "",  # TODO: JWT에서 추출
# ):
#     service.execute(DeactivateUserCommand(user_id=user_id))


# @router.patch("/me/email")
# def update_email(
#     body: UpdateEmailBody,
#     service: UpdateEmailService = Depends(),
#     user_id: str = "",  # TODO: JWT에서 추출
# ):
#     service.execute(UpdateEmailCommand(user_id=user_id, email=body.email))


# @router.get("/{user_id}")
# def get_user(
#     user_id: str,
#     service: GetUserService = Depends(),
# ):
#     result = service.execute(GetUserQuery(user_id=user_id))
#     return result


# @router.patch("/{user_id}/role")
# def change_role(
#     user_id: str,
#     body: ChangeRoleBody,
#     service: ChangeRoleService = Depends(),
# ):
#     service.execute(ChangeRoleCommand(target_user_id=user_id, new_role=body.new_role))
