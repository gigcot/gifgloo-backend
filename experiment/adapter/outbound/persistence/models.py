from sqlalchemy import Column, DateTime, JSON, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

from config.database import Base


class ExperimentSurveyResponseModel(Base):
    __tablename__ = "experiment_survey_responses"
    __table_args__ = (
        UniqueConstraint(
            "experiment_code",
            "user_id",
            name="uq_experiment_survey_responses_experiment_user",
        ),
    )

    id = Column(String, primary_key=True)
    experiment_code = Column(String(100), nullable=False)
    user_id = Column(String, nullable=False)
    answers = Column(JSON().with_variant(JSONB(), "postgresql"), nullable=False)
    submitted_at = Column(DateTime(timezone=True), nullable=False)
