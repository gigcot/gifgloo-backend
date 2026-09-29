import os

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from config.experiment import (
    get_experiment_survey_status_service,
    get_submit_experiment_survey_service,
)
from experiment.application.ports.inbound.get_experiment_survey_status import (
    GetExperimentSurveyStatusQuery,
)
from experiment.application.ports.inbound.submit_experiment_survey import (
    SubmitExperimentSurveyCommand,
)
from experiment.application.services.get_experiment_survey_status_service import (
    GetExperimentSurveyStatusService,
)
from experiment.application.services.submit_experiment_survey_service import (
    SubmitExperimentSurveyService,
)
from experiment.domain.value_objects.experiment_survey_answers import (
    ActualAction,
    IntendedContext,
    NonExternalUseReason,
)
from shared.session_token import decode_session_token

router = APIRouter(prefix="/experiments", tags=["experiments"])
SECRET_KEY = os.getenv("JWT_SECRET_KEY")


class SubmitExperimentSurveyBody(BaseModel):
    intended_context: IntendedContext
    actual_actions: list[ActualAction] = Field(min_length=1)
    intended_context_other: str | None = Field(default=None, max_length=500)
    actual_action_other: str | None = Field(default=None, max_length=500)
    non_external_use_reason: NonExternalUseReason | None = None
    non_external_use_reason_other: str | None = Field(default=None, max_length=500)
    next_context: str | None = Field(default=None, max_length=500)


def _get_user_id(request: Request) -> str:
    token = request.cookies.get("user_token")
    if not token:
        raise HTTPException(401, "인증이 필요합니다")
    try:
        payload = decode_session_token(token, SECRET_KEY)
        return payload["user_id"]
    except (jwt.PyJWTError, KeyError):
        raise HTTPException(401, "유효하지 않은 토큰입니다")


@router.get("/exp-001/survey")
async def get_exp_001_survey_status(
    request: Request,
    service: GetExperimentSurveyStatusService = Depends(
        get_experiment_survey_status_service
    ),
):
    result = await service.execute(
        GetExperimentSurveyStatusQuery(user_id=_get_user_id(request))
    )
    return {
        "eligible": result.eligible,
        "submitted": result.submitted,
    }


@router.post("/exp-001/survey")
async def submit_exp_001_survey(
    request: Request,
    body: SubmitExperimentSurveyBody,
    service: SubmitExperimentSurveyService = Depends(
        get_submit_experiment_survey_service
    ),
):
    result = await service.execute(
        SubmitExperimentSurveyCommand(
            user_id=_get_user_id(request),
            intended_context=body.intended_context,
            actual_actions=tuple(body.actual_actions),
            intended_context_other=body.intended_context_other,
            actual_action_other=body.actual_action_other,
            non_external_use_reason=body.non_external_use_reason,
            non_external_use_reason_other=body.non_external_use_reason_other,
            next_context=body.next_context,
        )
    )
    return {"submitted": result.submitted}
