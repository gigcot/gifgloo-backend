from user.application.ports.outbound.social_provider_port import SocialProviderPort, SocialUserInfo
from user.domain.value_objects.social_account import SocialProvider


class KakaoSocialProviderAdapter(SocialProviderPort):
    def get_user_info(self, access_token: str) -> SocialUserInfo:
        # TODO: 카카오 API 연동 구현
        # GET https://kapi.kakao.com/v2/user/me
        raise NotImplementedError
