"""Store first signup acquisition on users."""

from alembic import op
import sqlalchemy as sa

revision = "202609240001"
down_revision = "202609200001"
branch_labels = None
depends_on = None


def upgrade():
    for name in ("source", "medium", "campaign", "content"):
        op.add_column("users", sa.Column(f"acquisition_{name}", sa.String(100), nullable=True))


def downgrade():
    for name in ("content", "campaign", "medium", "source"):
        op.drop_column("users", f"acquisition_{name}")
