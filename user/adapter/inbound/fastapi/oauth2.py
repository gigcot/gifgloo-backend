import os
import jwt
from dotenv import load_dotenv
from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from config.database import get_db
from user.adapter.outbound.social.kakao_social_provider_adapter import KakaoSocialProviderAdapter
from user.adapter.outbound.social.google_social_provider_adapter import GoogleSocialProviderAdapter
from user.adapter.outbound.persistence.sqlalchemy_user_repository import SqlAlchemyUserRepository
from user.application.ports.inbound.social_login import SocialLoginCommand
from user.application.services.social_login_service import SocialLoginService
from user.domain.value_objects.social_account import SocialProvider

load_dotenv(".env")

router = APIRouter(prefix="/oauth", tags=["oauth"])

KAKAO_CLIENT_ID = os.getenv("KAKAO_RESTAPI_KEY")
KAKAO_REDIRECT_URI = "http://localhost:8000/oauth/kakao/callback"

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_RESTAPI_KEY")
GOOGLE_REDIRECT_URI = "http://localhost:8000/oauth/google/callback"

FRONTEND_CALLBACK_URL = "http://localhost:3000/callback"
SECRET_KEY = os.getenv("JWT_SECRET_KEY")


def _make_service(adapter, db: Session):
    return SocialLoginService(
        social_provider=adapter,
        user_repo=SqlAlchemyUserRepository(db),
    )


def _issue_jwt(user_id: str) -> str:
    return jwt.encode({"user_id": user_id}, SECRET_KEY, algorithm="HS256")


def _redirect_with_cookie(user_id: str) -> RedirectResponse:
    token = _issue_jwt(user_id)
    response = RedirectResponse(url=FRONTEND_CALLBACK_URL)
    response.set_cookie(
        key="user_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,  # 로컬: False, 프로덕션: True (HTTPS)
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
def kakao_callback(code: str, db: Session = Depends(get_db)):
    result = _make_service(KakaoSocialProviderAdapter(), db).execute(
        SocialLoginCommand(provider=SocialProvider.KAKAO, code=code)
    )
    return _redirect_with_cookie(result.user_id)


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
def google_callback(code: str, db: Session = Depends(get_db)):
    result = _make_service(GoogleSocialProviderAdapter(), db).execute(
        SocialLoginCommand(provider=SocialProvider.GOOGLE, code=code)
    )
    return _redirect_with_cookie(result.user_id)
