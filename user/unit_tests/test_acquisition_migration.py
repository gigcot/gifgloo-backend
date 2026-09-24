import importlib
import unittest
from unittest.mock import patch

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


class AcquisitionMigrationTest(unittest.TestCase):
    def test_nullable_columns_preserve_existing_users_and_can_be_rolled_back(self):
        migration = importlib.import_module("migrations.versions.202609240001_user_acquisition")
        engine = create_engine("sqlite://")
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE users (id VARCHAR PRIMARY KEY)"))
            connection.execute(text("INSERT INTO users (id) VALUES ('existing')"))
            operations = Operations(MigrationContext.configure(connection))
            with patch.object(migration, "op", operations):
                migration.upgrade()
                row = connection.execute(text("SELECT acquisition_campaign FROM users WHERE id='existing'")).one()
                self.assertIsNone(row[0])
                self.assertEqual(len(inspect(connection).get_columns("users")), 5)
                migration.downgrade()
                self.assertEqual([column["name"] for column in inspect(connection).get_columns("users")], ["id"])
        engine.dispose()
