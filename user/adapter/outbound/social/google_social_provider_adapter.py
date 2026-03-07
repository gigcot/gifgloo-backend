from user.application.ports.outbound.social_provider_port import SocialProviderPort, SocialUserInfo
from user.domain.value_objects.social_account import SocialProvider


class GoogleSocialProviderAdapter(SocialProviderPort):
    def get_user_info(self, access_token: str) -> SocialUserInfo:
        # TODO: 구글 API 연동 구현
        # GET https://www.googleapis.com/oauth2/v2/userinfo
        raise NotImplementedError
