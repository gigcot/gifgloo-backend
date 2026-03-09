import os

import jwt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from user.application.ports.inbound.change_role import ChangeRoleCommand
from user.application.ports.inbound.deactivate_user import DeactivateUserCommand
from user.application.ports.inbound.get_user import GetUserQuery
from user.application.ports.inbound.update_email import UpdateEmailCommand
from user.application.services.change_role_service import ChangeRoleService
from user.application.services.deactivate_user_service import DeactivateUserService
from user.application.services.get_user_service import GetUserService
from user.application.services.update_email_service import UpdateEmailService
from user.domain.aggregates.user import UserRole
from fastapi import Request                                                                                                                



router = APIRouter(prefix="/users", tags=["users"])

SECRET_KEY = os.getenv("JWT_SECRET_KEY")


class UpdateEmailBody(BaseModel):
    email: str


class ChangeRoleBody(BaseModel):
    new_role: UserRole

@router.get("/me")
def is_signed_in(request: Request):  
    
    token = request.cookies.get("user_token")
    if token is None:
        raise HTTPException(401, "유효하지않은 사용자입니다")
    try:
        jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return {"ok": True}
    except:
        raise HTTPException(401, "유효하지않은 사용자입니다")


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
