"""Add is_discoverable column to users table

Revision ID: 0003
Revises: standalone
Create Date: 2026-04-26

Adds is_discoverable (BOOLEAN, NOT NULL, default TRUE) to the users table.
When FALSE the user is excluded from speaking-partner search results.
Existing rows are backfilled to TRUE so no one loses discoverability.
"""

revision = '0003'
down_revision = None
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column(
        'users',
        sa.Column(
            'is_discoverable',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('TRUE'),
        ),
    )


def downgrade():
    op.drop_column('users', 'is_discoverable')
