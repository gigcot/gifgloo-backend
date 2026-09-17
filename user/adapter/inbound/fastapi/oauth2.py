import os
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
import jwt
from dotenv import load_dotenv
from fastapi import APIRouter, Depends
from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
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
from user.domain.value_objects.signup_consent import SignupConsent
from shared.exceptions import AuthenticationException, BusinessRuleException

load_dotenv(".env")

router = APIRouter(prefix="/oauth", tags=["oauth"])

KAKAO_CLIENT_ID = os.getenv("KAKAO_RESTAPI_KEY")
KAKAO_REDIRECT_URI = os.getenv("KAKAO_REDIRECT_URI")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_RESTAPI_KEY")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

FRONTEND_CALLBACK_URL = os.getenv("FRONTEND_CALLBACK_URL")
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
OAUTH_STATE_COOKIE = "oauth_signup_state"


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
    response.delete_cookie(OAUTH_STATE_COOKIE)
    return response


class ReviewLoginBody(BaseModel):
    login_id: str
    password: str


class OAuthConsentBody(BaseModel):
    terms_version: str
    privacy_version: str
    is_fourteen_or_older: bool
    agreed_to_terms: bool
    agreed_to_privacy: bool


def _start_social_login(provider: SocialProvider, body: OAuthConsentBody) -> JSONResponse:
    if not body.agreed_to_terms or not body.agreed_to_privacy:
        raise BusinessRuleException("필수 약관에 동의해야 합니다")
    SignupConsent.record(
        terms_version=body.terms_version,
        privacy_version=body.privacy_version,
        is_fourteen_or_older=body.is_fourteen_or_older,
    )
    state = jwt.encode(
        {
            "provider": provider.value,
            "terms_version": body.terms_version,
            "privacy_version": body.privacy_version,
            "is_fourteen_or_older": body.is_fourteen_or_older,
            "nonce": secrets.token_urlsafe(16),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
        },
        SECRET_KEY,
        algorithm="HS256",
    )
    if provider == SocialProvider.KAKAO:
        url = "https://kauth.kakao.com/oauth/authorize?" + urlencode({
            "client_id": KAKAO_CLIENT_ID,
            "redirect_uri": KAKAO_REDIRECT_URI,
            "response_type": "code",
            "state": state,
        })
    else:
        url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
            "client_id": GOOGLE_CLIENT_ID,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
        })
    response = JSONResponse({"authorization_url": url})
    response.set_cookie(
        OAUTH_STATE_COOKIE,
        state,
        httponly=True,
        samesite="lax",
        secure=os.getenv("COOKIE_SECURE").lower() == "true",
        max_age=600,
    )
    return response


def _get_signup_consent(request: Request, state: str, provider: SocialProvider) -> SignupConsent:
    saved_state = request.cookies.get(OAUTH_STATE_COOKIE)
    if saved_state is None or not hmac.compare_digest(saved_state, state):
        raise AuthenticationException("가입 동의를 확인할 수 없습니다")
    try:
        payload = jwt.decode(state, SECRET_KEY, algorithms=["HS256"])
    except jwt.InvalidTokenError as exc:
        raise AuthenticationException("가입 동의가 만료되었습니다") from exc
    if payload["provider"] != provider.value:
        raise AuthenticationException("로그인 요청이 일치하지 않습니다")
    return SignupConsent.record(
        terms_version=payload["terms_version"],
        privacy_version=payload["privacy_version"],
        is_fourteen_or_older=payload["is_fourteen_or_older"],
    )


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

@router.post("/kakao/start")
def kakao_login(body: OAuthConsentBody) -> JSONResponse:
    return _start_social_login(SocialProvider.KAKAO, body)


@router.get("/kakao/callback")
def kakao_callback(
    code: str,
    state: str,
    request: Request,
    service: SocialLoginService = Depends(get_kakao_social_login_service),
):
    consent = _get_signup_consent(request, state, SocialProvider.KAKAO)
    result = service.execute(SocialLoginCommand(provider=SocialProvider.KAKAO, code=code, signup_consent=consent))
    return _redirect_with_cookie(result.user_id, result.is_new_user)


# --- Google ---

@router.post("/google/start")
def google_login(body: OAuthConsentBody) -> JSONResponse:
    return _start_social_login(SocialProvider.GOOGLE, body)


@router.get("/google/callback")
def google_callback(
    code: str,
    state: str,
    request: Request,
    service: SocialLoginService = Depends(get_google_social_login_service),
):
    consent = _get_signup_consent(request, state, SocialProvider.GOOGLE)
    result = service.execute(SocialLoginCommand(provider=SocialProvider.GOOGLE, code=code, signup_consent=consent))
    return _redirect_with_cookie(result.user_id, result.is_new_user)
