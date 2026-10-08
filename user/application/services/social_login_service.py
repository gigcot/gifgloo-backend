from user.application.ports.inbound.social_login import (
    SocialLoginCommand,
    SocialLoginPort,
    SocialLoginResult,
)
from user.application.ports.outbound.domain_bridges.credit_account_init_port import CreditAccountInitPort
from user.application.ports.outbound.social_provider_port import SocialProviderPort
from user.application.ports.outbound.user_repository import UserRepositoryPort
from user.application.ports.outbound.transaction import UserTransaction
from shared.exceptions import AuthenticationException
from user.domain.aggregates.user import User
from user.domain.value_objects.email import Email
from user.domain.value_objects.social_account import SocialAccount


class SocialLoginService(SocialLoginPort):
    def __init__(
        self,
        social_provider: SocialProviderPort,
        user_repo: UserRepositoryPort,
        credit_account_init: CreditAccountInitPort,
        transaction: UserTransaction,
    ):
        self._social_provider = social_provider
        self._user_repo = user_repo
        self._credit_account_init = credit_account_init
        self._transaction = transaction

    def execute(self, command: SocialLoginCommand) -> SocialLoginResult:
        social_info = self._social_provider.get_user_info(command.code)

        social_account = SocialAccount(
            provider=social_info.provider,
            provider_id=social_info.provider_id,
        )
        try:
            self._transaction.lock(f"social:{social_account.provider.value}:{social_account.provider_id}")
            user = self._user_repo.find_by_social_account(social_account)
            is_new_user = user is None
            if user is None:
                email = Email(social_info.email) if social_info.email else None
                if command.anonymous_user_id is not None:
                    self._transaction.lock(f"user:{command.anonymous_user_id}")
                    user = self._user_repo.find_by_id(command.anonymous_user_id)
                    if (
                        user is None or not user.is_active()
                        or user.user_kind != "anonymous"
                        or user.session_version != command.anonymous_session_version
                    ):
                        raise AuthenticationException("익명 세션이 변경되었습니다. 다시 로그인해주세요")
                    user.connect_social_account(social_account, email)
                else:
                    user = User(social_account=social_account, email=email, acquisition=command.acquisition)
                    self._user_repo.save(user)
                    self._credit_account_init.init_account(user.id)
            if not user.is_active():
                raise AuthenticationException("사용할 수 없는 계정입니다")
            user.signup_consent = command.signup_consent
            self._user_repo.save(user)
            self._transaction.commit()
            return SocialLoginResult(user.id, is_new_user, user.session_version)
        except Exception:
            self._transaction.rollback()
            raise
