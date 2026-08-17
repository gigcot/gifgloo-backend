import os
import jwt
from dotenv import load_dotenv
from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel

from config.user import (
    get_google_social_login_service,
    get_kakao_social_login_service,
    get_review_login_service,
)
from user.application.ports.inbound.review_login import ReviewLoginCommand
from user.application.ports.inbound.social_login import SocialLoginCommand
from user.application.services.review_login_service import ReviewLoginService
from user.application.services.social_login_service import SocialLoginService
from user.domain.value_objects.social_account import SocialProvider

load_dotenv(".env")

router = APIRouter(prefix="/oauth", tags=["oauth"])

KAKAO_CLIENT_ID = os.getenv("KAKAO_RESTAPI_KEY")
KAKAO_REDIRECT_URI = os.getenv("KAKAO_REDIRECT_URI")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_RESTAPI_KEY")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

FRONTEND_CALLBACK_URL = os.getenv("FRONTEND_CALLBACK_URL")
SECRET_KEY = os.getenv("JWT_SECRET_KEY")


def _issue_jwt(user_id: str, review_login: bool = False) -> str:
    payload: dict[str, str | bool] = {"user_id": user_id}
    if review_login:
        payload["review_login"] = True
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def _set_user_cookie(
    response: Response,
    user_id: str,
    review_login: bool = False,
) -> None:
    response.set_cookie(
        key="user_token",
        value=_issue_jwt(user_id, review_login),
        httponly=True,
        samesite="lax",
        secure=os.getenv("COOKIE_SECURE").lower() == "true",
    )


def _redirect_with_cookie(user_id: str, is_new_user: bool = False) -> RedirectResponse:
    url = f"{FRONTEND_CALLBACK_URL}?is_new_user=true" if is_new_user else FRONTEND_CALLBACK_URL
    response = RedirectResponse(url=url)
    _set_user_cookie(response, user_id)
    return response


class ReviewLoginBody(BaseModel):
    login_id: str
    password: str


@router.post("/review-login", status_code=204)
def review_login(
    body: ReviewLoginBody,
    service: ReviewLoginService = Depends(get_review_login_service),
) -> Response:
    result = service.execute(
        ReviewLoginCommand(login_id=body.login_id, password=body.password)
    )
    response = Response(status_code=204)
    _set_user_cookie(response, result.user_id, review_login=True)
    return response


@router.post("/logout", status_code=204)
def logout() -> Response:
    response = Response(status_code=204)
    response.delete_cookie(
        key="user_token",
        httponly=True,
        samesite="lax",
        secure=os.getenv("COOKIE_SECURE").lower() == "true",
    )
    return response


# --- Kakao ---

@router.get("/kakao")
def kakao_login():
    url = (
        f"https://kauth.kakao.com/oauth/authorize"
        f"?client_id={KAKAO_CLIENT_ID}"
        f"&redirect_uri={KAKAO_REDIRECT_URI}"
        f"&response_type=code"
    )
    return RedirectResponse(url=url)


@router.get("/kakao/callback")
def kakao_callback(
    code: str,
    service: SocialLoginService = Depends(get_kakao_social_login_service),
):
    result = service.execute(SocialLoginCommand(provider=SocialProvider.KAKAO, code=code))
    return _redirect_with_cookie(result.user_id, result.is_new_user)


# --- Google ---

@router.get("/google")
def google_login():
    url = (
        f"https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={GOOGLE_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=openid email profile"
    )
    return RedirectResponse(url=url)


@router.get("/google/callback")
def google_callback(
    code: str,
    service: SocialLoginService = Depends(get_google_social_login_service),
):
    result = service.execute(SocialLoginCommand(provider=SocialProvider.GOOGLE, code=code))
    return _redirect_with_cookie(result.user_id, result.is_new_user)
