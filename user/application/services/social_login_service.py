from user.application.ports.inbound.social_login import (
    SocialLoginCommand,
    SocialLoginPort,
    SocialLoginResult,
)
from user.application.ports.outbound.domain_bridges.credit_account_init_port import CreditAccountInitPort
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
        credit_account_init: CreditAccountInitPort,
    ):
        self._social_provider = social_provider
        self._user_repo = user_repo
        self._credit_account_init = credit_account_init

    def execute(self, command: SocialLoginCommand) -> SocialLoginResult:
        social_info = self._social_provider.get_user_info(command.code)

        social_account = SocialAccount(
            provider=social_info.provider,
            provider_id=social_info.provider_id,
        )
        user = self._user_repo.find_by_social_account(social_account)

        is_new_user = user is None
        if is_new_user:
            email = Email(social_info.email) if social_info.email else None
            user = User(social_account=social_account, email=email)
            self._user_repo.save(user)
            self._credit_account_init.init_account(user.id)

        return SocialLoginResult(user_id=user.id, is_new_user=is_new_user)
