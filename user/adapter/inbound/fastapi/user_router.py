import jwt
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from user.application.ports.inbound.change_role import ChangeRoleCommand
from user.application.ports.inbound.deactivate_user import DeactivateUserCommand
from user.application.ports.inbound.get_user import GetUserQuery
from user.application.ports.inbound.social_login import SocialLoginCommand
from user.application.ports.inbound.update_email import UpdateEmailCommand
from user.application.services.change_role_service import ChangeRoleService
from user.application.services.deactivate_user_service import DeactivateUserService
from user.application.services.get_user_service import GetUserService
from user.application.services.social_login_service import SocialLoginService
from user.application.services.update_email_service import UpdateEmailService
from user.domain.aggregates.user import UserRole
from user.domain.value_objects.social_account import SocialProvider

router = APIRouter(prefix="/users", tags=["user"])

SECRET_KEY = "TODO: config에서 주입"  # TODO: config로 분리


def _issue_jwt(user_id: str) -> str:
    return jwt.encode({"user_id": user_id}, SECRET_KEY, algorithm="HS256")


class SocialLoginBody(BaseModel):
    provider: SocialProvider
    access_token: str


class UpdateEmailBody(BaseModel):
    email: str


class ChangeRoleBody(BaseModel):
    new_role: UserRole


@router.post("/login")
def social_login(
    body: SocialLoginBody,
    service: SocialLoginService = Depends(),
):
    result = service.execute(
        SocialLoginCommand(
            provider=body.provider,
            access_token=body.access_token,
        )
    )
    token = _issue_jwt(result.user_id)
    return {"token": token, "is_new_user": result.is_new_user}


@router.post("/me/deactivate")
def deactivate(
    service: DeactivateUserService = Depends(),
    user_id: str = "",  # TODO: JWT에서 추출
):
    service.execute(DeactivateUserCommand(user_id=user_id))


@router.patch("/me/email")
def update_email(
    body: UpdateEmailBody,
    service: UpdateEmailService = Depends(),
    user_id: str = "",  # TODO: JWT에서 추출
):
    service.execute(UpdateEmailCommand(user_id=user_id, email=body.email))


@router.get("/{user_id}")
def get_user(
    user_id: str,
    service: GetUserService = Depends(),
):
    result = service.execute(GetUserQuery(user_id=user_id))
    return result


@router.patch("/{user_id}/role")
def change_role(
    user_id: str,
    body: ChangeRoleBody,
    service: ChangeRoleService = Depends(),
):
    service.execute(ChangeRoleCommand(target_user_id=user_id, new_role=body.new_role))
