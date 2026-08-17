import os

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from config.user import get_record_signup_consent_service, get_user_service
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
from user.domain.aggregates.user import UserRole



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
    service: GetUserService = Depends(get_user_service),
):
    result = service.execute(GetUserQuery(user_id=_get_user_id(request)))
    return {"ok": True, "email": result.email}


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
