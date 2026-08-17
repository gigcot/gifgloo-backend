import hmac

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from shared.exceptions import AuthenticationException
from user.application.ports.inbound.review_login import (
    ReviewLoginCommand,
    ReviewLoginPort,
    ReviewLoginResult,
)
from user.application.ports.outbound.domain_bridges.credit_account_init_port import (
    CreditAccountInitPort,
)
from user.application.ports.outbound.user_repository import UserRepositoryPort
from user.domain.aggregates.user import User
from user.domain.value_objects.signup_consent import (
    CURRENT_PRIVACY_VERSION,
    CURRENT_TERMS_VERSION,
)
from user.domain.value_objects.social_account import SocialAccount, SocialProvider


class ReviewLoginService(ReviewLoginPort):
    def __init__(
        self,
        enabled: bool,
        login_id: str,
        password_hash: str,
        user_repo: UserRepositoryPort,
        credit_account_init: CreditAccountInitPort,
    ):
        self._enabled = enabled
        self._login_id = login_id
        self._password_hash = password_hash
        self._user_repo = user_repo
        self._credit_account_init = credit_account_init
        self._password_hasher = PasswordHasher()

    def execute(self, command: ReviewLoginCommand) -> ReviewLoginResult:
        if not self._enabled or not hmac.compare_digest(command.login_id, self._login_id):
            raise AuthenticationException("아이디 또는 비밀번호를 확인해주세요")

        try:
            self._password_hasher.verify(self._password_hash, command.password)
        except VerifyMismatchError as exc:
            raise AuthenticationException("아이디 또는 비밀번호를 확인해주세요") from exc

        review_account = SocialAccount(
            provider=SocialProvider.REVIEW,
            provider_id=self._login_id,
        )
        user = self._user_repo.find_by_social_account(review_account)
        if user is None:
            user = User(social_account=review_account)
            user.record_signup_consent(
                terms_version=CURRENT_TERMS_VERSION,
                privacy_version=CURRENT_PRIVACY_VERSION,
                is_fourteen_or_older=True,
            )
            self._user_repo.save(user)
            self._credit_account_init.init_account(user.id)

        if not user.is_active():
            raise AuthenticationException("아이디 또는 비밀번호를 확인해주세요")

        return ReviewLoginResult(user_id=user.id)
