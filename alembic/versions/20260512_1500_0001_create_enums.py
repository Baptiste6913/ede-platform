"""create postgres enum types

Revision ID: 0001
Revises:
Create Date: 2026-05-12 15:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from src.core import enums

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _values_sql(values: tuple[str, ...]) -> str:
    """Render tuple as Postgres ENUM value list."""
    escaped = ", ".join(f"'{v}'" for v in values)
    return escaped


_ENUMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("jurisdiction_enum", enums.JURISDICTIONS),
    ("deal_type_enum", enums.DEAL_TYPES),
    ("deal_status_enum", enums.DEAL_STATUSES),
    ("event_type_enum", enums.EVENT_TYPES),
    ("decision_enum", enums.DECISIONS),
    ("analyst_verdict_enum", enums.ANALYST_VERDICTS),
    ("analyst_source_enum", enums.ANALYST_SOURCES),
    ("position_side_enum", enums.POSITION_SIDES),
    ("position_status_enum", enums.POSITION_STATUSES),
    ("currency_enum", enums.CURRENCIES),
    ("price_source_enum", enums.PRICE_SOURCES),
)


def upgrade() -> None:
    for name, values in _ENUMS:
        op.execute(f"CREATE TYPE {name} AS ENUM ({_values_sql(values)})")


def downgrade() -> None:
    for name, _ in reversed(_ENUMS):
        op.execute(f"DROP TYPE IF EXISTS {name}")
