from composition.application.ports.outbound.credit_port import CreditPort


class CreditAdapter(CreditPort):
    """
    Credit 도메인의 Application Service를 호출해서 크레딧을 확인/차감한다.
    Credit 도메인이 구현되면 credit_service 를 주입받아 사용한다.
    """

    def __init__(self, credit_service):
        self._credit_service = credit_service

    def has_enough_credit(self, user_id: str) -> bool:
        return self._credit_service.has_enough(user_id)

    def deduct(self, user_id: str) -> None:
        self._credit_service.deduct(user_id)
