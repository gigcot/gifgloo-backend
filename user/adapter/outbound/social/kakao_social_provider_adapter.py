import httpx

from user.application.ports.outbound.social_provider_port import SocialProviderPort, SocialUserInfo
from user.domain.value_objects.social_account import SocialProvider
import os
from dotenv import load_dotenv
load_dotenv(".env")

KAKAO_CLIENT_ID = os.getenv("KAKAO_RESTAPI_KEY")
KAKAO_CLIENT_SECRET = "TODO"
KAKAO_REDIRECT_URI = "http://localhost:8000/oauth/kakao/callback"


class KakaoSocialProviderAdapter(SocialProviderPort):
    def get_user_info(self, auth_code: str) -> SocialUserInfo:
        access_token = self._exchange_code_for_token(auth_code)
        return self._fetch_user_info(access_token)

    def _exchange_code_for_token(self, code: str) -> str:
        response = httpx.post(
            "https://kauth.kakao.com/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": KAKAO_CLIENT_ID,
                "client_secret": KAKAO_CLIENT_SECRET,
                "redirect_uri": KAKAO_REDIRECT_URI,
                "code": code,
            },
        )
        response.raise_for_status()
        return response.json()["access_token"]

    def _fetch_user_info(self, access_token: str) -> SocialUserInfo:
        response = httpx.get(
            "https://kapi.kakao.com/v2/user/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        data = response.json()

        email = data.get("kakao_account", {}).get("email")
        return SocialUserInfo(
            provider=SocialProvider.KAKAO,
            provider_id=str(data["id"]),
            email=email,
        )
