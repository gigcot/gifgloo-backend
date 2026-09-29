import importlib
import unittest
from unittest.mock import patch

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect


class ExperimentSurveyMigrationTest(unittest.TestCase):
    def test_creates_portable_response_table_and_can_roll_back(self):
        migration = importlib.import_module(
            "migrations.versions.202609290001_experiment_survey_responses"
        )
        engine = create_engine("sqlite://")
        with engine.begin() as connection:
            operations = Operations(MigrationContext.configure(connection))
            with patch.object(migration, "op", operations):
                migration.upgrade()
                columns = {
                    column["name"]
                    for column in inspect(connection).get_columns(
                        "experiment_survey_responses"
                    )
                }
                self.assertEqual(
                    columns,
                    {
                        "id",
                        "experiment_code",
                        "user_id",
                        "answers",
                        "submitted_at",
                    },
                )
                unique_constraints = inspect(connection).get_unique_constraints(
                    "experiment_survey_responses"
                )
                self.assertEqual(
                    unique_constraints[0]["column_names"],
                    ["experiment_code", "user_id"],
                )
                migration.downgrade()
                self.assertNotIn(
                    "experiment_survey_responses",
                    inspect(connection).get_table_names(),
                )
        engine.dispose()


if __name__ == "__main__":
    unittest.main()
