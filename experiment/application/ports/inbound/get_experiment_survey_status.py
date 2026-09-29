from dataclasses import dataclass


@dataclass(frozen=True)
class GetExperimentSurveyStatusQuery:
    user_id: str


@dataclass(frozen=True)
class GetExperimentSurveyStatusResult:
    eligible: bool
    submitted: bool
