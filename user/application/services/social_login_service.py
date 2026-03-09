from user.application.ports.inbound.social_login import (
    SocialLoginCommand,
    SocialLoginPort,
    SocialLoginResult,
)
from user.application.ports.outbound.social_provider_port import SocialProviderPort
from user.application.ports.outbound.user_repository import UserRepositoryPort
from user.domain.aggregates.user import User
from user.domain.value_objects.email import Email
from user.domain.value_objects.social_account import SocialAccount


class SocialLoginService(SocialLoginPort):
    def __init__(
        self,
        social_provider: SocialProviderPort,
        user_repo: UserRepositoryPort,
    ):
        self._social_provider = social_provider
        self._user_repo = user_repo

    def execute(self, command: SocialLoginCommand) -> SocialLoginResult:
        # 1. 소셜 제공자에서 유저 정보 조회 (code → token → user_info 는 어댑터가 처리)
        social_info = self._social_provider.get_user_info(command.code)

        # 2. DB에서 유저 찾기
        social_account = SocialAccount(
            provider=social_info.provider,
            provider_id=social_info.provider_id,
        )
        user = self._user_repo.find_by_social_account(social_account)

        # 3. 없으면 새로 생성
        is_new_user = user is None
        if is_new_user:
            email = Email(social_info.email) if social_info.email else None
            user = User(social_account=social_account, email=email)
            self._user_repo.save(user)

        return SocialLoginResult(user_id=user.id, is_new_user=is_new_user)
