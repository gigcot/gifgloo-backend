from shared.exceptions import NotFoundException
from user.application.ports.inbound.record_signup_consent import (
    RecordSignupConsentCommand,
    RecordSignupConsentPort,
    RecordSignupConsentResult,
)
from user.application.ports.outbound.user_repository import UserRepositoryPort


class RecordSignupConsentService(RecordSignupConsentPort):
    def __init__(self, user_repo: UserRepositoryPort):
        self._user_repo = user_repo

    def execute(self, command: RecordSignupConsentCommand) -> RecordSignupConsentResult:
        user = self._user_repo.find_by_id(command.user_id)
        if user is None:
            raise NotFoundException("유저를 찾을 수 없습니다")

        user.record_signup_consent(
            terms_version=command.terms_version,
            privacy_version=command.privacy_version,
            is_fourteen_or_older=command.is_fourteen_or_older,
        )
        self._user_repo.save(user)
        consent = user.signup_consent
        return RecordSignupConsentResult(
            terms_version=consent.terms_version,
            privacy_version=consent.privacy_version,
            is_fourteen_or_older=consent.is_fourteen_or_older,
            agreed_at=consent.agreed_at,
        )
