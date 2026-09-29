from dataclasses import dataclass
from enum import Enum

from shared.exceptions import ValidationException


class IntendedContext(str, Enum):
    DIRECT_CHAT = "direct_chat"
    GROUP_CHAT = "group_chat"
    COMMUNITY_POST = "community_post"
    SNS = "sns"
    PERSONAL_KEEP = "personal_keep"
    CURIOSITY = "curiosity"
    OTHER = "other"


class ActualAction(str, Enum):
    VIEWED_ONLY = "viewed_only"
    SAVED = "saved"
    DIRECT_CHAT = "direct_chat"
    GROUP_CHAT = "group_chat"
    COMMUNITY_POST = "community_post"
    SNS = "sns"
    SHARED_LINK = "shared_link"
    OTHER = "other"


class NonExternalUseReason(str, Enum):
    UNEXPECTED_RESULT = "unexpected_result"
    NO_SITUATION = "no_situation"
    SAVE_SHARE_INCONVENIENT = "save_share_inconvenient"
    SHOWING_BURDEN = "showing_burden"
    RIGHTS_CONCERN = "rights_concern"
    CURIOSITY_ONLY = "curiosity_only"
    PERSONAL_KEEP = "personal_keep"
    PLANNED_NOT_YET = "planned_not_yet"
    OTHER = "other"


EXTERNAL_ACTIONS = frozenset(
    {
        ActualAction.DIRECT_CHAT,
        ActualAction.GROUP_CHAT,
        ActualAction.COMMUNITY_POST,
        ActualAction.SNS,
        ActualAction.SHARED_LINK,
    }
)


@dataclass(frozen=True)
class ExperimentSurveyAnswers:
    intended_context: IntendedContext
    actual_actions: tuple[ActualAction, ...]
    intended_context_other: str | None = None
    actual_action_other: str | None = None
    non_external_use_reason: NonExternalUseReason | None = None
    non_external_use_reason_other: str | None = None
    next_context: str | None = None

    def __post_init__(self):
        actions = set(self.actual_actions)
        if not actions:
            raise ValidationException("실제로 한 행동을 하나 이상 선택해 주세요")
        if len(actions) != len(self.actual_actions):
            raise ValidationException("실제로 한 행동은 중복해서 선택할 수 없습니다")
        if ActualAction.VIEWED_ONLY in actions and len(actions) != 1:
            raise ValidationException("보기만 했음은 다른 행동과 함께 선택할 수 없습니다")

        has_external_action = bool(actions & EXTERNAL_ACTIONS)
        if has_external_action and self.non_external_use_reason is not None:
            raise ValidationException("외부 사용 행동이 있으면 미사용 이유를 제출할 수 없습니다")
        if not has_external_action and self.non_external_use_reason is None:
            raise ValidationException("외부에서 사용하지 않은 이유를 선택해 주세요")

        self._validate_other(
            self.intended_context == IntendedContext.OTHER,
            self.intended_context_other,
            "사용하려던 곳의 기타 내용을 입력해 주세요",
        )
        self._validate_other(
            ActualAction.OTHER in actions,
            self.actual_action_other,
            "실제로 한 행동의 기타 내용을 입력해 주세요",
        )
        self._validate_other(
            self.non_external_use_reason == NonExternalUseReason.OTHER,
            self.non_external_use_reason_other,
            "외부에서 사용하지 않은 이유의 기타 내용을 입력해 주세요",
        )
        if self.next_context is not None:
            if not self.next_context.strip():
                raise ValidationException("다음 사용 상황은 비워둘 수 없습니다")
            if len(self.next_context.strip()) > 500:
                raise ValidationException("다음 사용 상황은 500자 이하여야 합니다")

    @staticmethod
    def _validate_other(selected: bool, value: str | None, message: str) -> None:
        if selected and (value is None or not value.strip()):
            raise ValidationException(message)
        if not selected and value is not None:
            raise ValidationException("선택하지 않은 기타 내용은 제출할 수 없습니다")
        if value is not None and len(value.strip()) > 500:
            raise ValidationException("기타 내용은 500자 이하여야 합니다")

    def to_dict(self) -> dict[str, object]:
        values: dict[str, object] = {
            "intended_context": self.intended_context.value,
            "actual_actions": [action.value for action in self.actual_actions],
        }
        optional_values = {
            "intended_context_other": self.intended_context_other,
            "actual_action_other": self.actual_action_other,
            "non_external_use_reason": (
                self.non_external_use_reason.value
                if self.non_external_use_reason is not None
                else None
            ),
            "non_external_use_reason_other": self.non_external_use_reason_other,
            "next_context": self.next_context,
        }
        values.update(
            {
                key: value.strip() if isinstance(value, str) else value
                for key, value in optional_values.items()
                if value is not None
            }
        )
        return values
