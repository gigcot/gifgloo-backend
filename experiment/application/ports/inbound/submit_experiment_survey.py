from dataclasses import dataclass

from experiment.domain.value_objects.experiment_survey_answers import (
    ActualAction,
    IntendedContext,
    NonExternalUseReason,
)


@dataclass(frozen=True)
class SubmitExperimentSurveyCommand:
    user_id: str
    intended_context: IntendedContext
    actual_actions: tuple[ActualAction, ...]
    intended_context_other: str | None = None
    actual_action_other: str | None = None
    non_external_use_reasons: tuple[NonExternalUseReason, ...] = ()
    non_external_use_reason_other: str | None = None
    next_context: str | None = None


@dataclass(frozen=True)
class SubmitExperimentSurveyResult:
    submitted: bool
