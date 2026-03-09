import httpx

from user.application.ports.outbound.social_provider_port import SocialProviderPort, SocialUserInfo
from user.domain.value_objects.social_account import SocialProvider
from dotenv import load_dotenv
import os
load_dotenv(".env")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_RESTAPI_KEY")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = "http://localhost:8000/oauth/google/callback"


class GoogleSocialProviderAdapter(SocialProviderPort):
    def get_user_info(self, auth_code: str) -> SocialUserInfo:
        access_token = self._exchange_code_for_token(auth_code)
        return self._fetch_user_info(access_token)

    def _exchange_code_for_token(self, code: str) -> str:
        response = httpx.post(
            "https://oauth2.googleapis.com/token",
            data={
                "grant_type": "authorization_code",
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "code": code,
            },
        )
        response.raise_for_status()
        return response.json()["access_token"]

    def _fetch_user_info(self, access_token: str) -> SocialUserInfo:
        response = httpx.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        data = response.json()

        return SocialUserInfo(
            provider=SocialProvider.GOOGLE,
            provider_id=str(data["id"]),
            email=data.get("email"),
        )
