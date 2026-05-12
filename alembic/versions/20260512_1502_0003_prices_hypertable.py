"""create prices table as TimescaleDB hypertable + 1h/1d continuous aggregates

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-12 15:02:00.000000

Notes:
- Uses raw SQL because Alembic does not natively model hypertables or
  continuous aggregates.
- `CREATE EXTENSION timescaledb` must be idempotent — `IF NOT EXISTS`.
- Continuous aggregates require WITH (timescaledb.continuous) and reference
  hypertable directly (no joins) for the aggregate definition.
- Refresh policies are added so the aggregates stay up to date in production.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---- Ensure the TimescaleDB extension is available ----------------
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")

    # ---- Plain prices table (will be promoted to hypertable next) -----
    op.execute(
        """
        CREATE TABLE prices (
            ticker   VARCHAR(32) NOT NULL,
            ts       TIMESTAMPTZ NOT NULL,
            open     NUMERIC(18, 6) NOT NULL,
            high     NUMERIC(18, 6) NOT NULL,
            low      NUMERIC(18, 6) NOT NULL,
            close    NUMERIC(18, 6) NOT NULL,
            volume   BIGINT NULL,
            source   price_source_enum NOT NULL,
            PRIMARY KEY (ticker, ts)
        )
        """
    )
    op.execute("CREATE INDEX ix_prices_ticker_ts ON prices (ticker, ts DESC)")

    # ---- Promote to hypertable, 7-day chunks --------------------------
    op.execute(
        """
        SELECT create_hypertable(
            'prices',
            'ts',
            chunk_time_interval => INTERVAL '7 days',
            if_not_exists => TRUE
        )
        """
    )

    # ---- 1h continuous aggregate -------------------------------------
    op.execute(
        """
        CREATE MATERIALIZED VIEW prices_1h
        WITH (timescaledb.continuous) AS
        SELECT
            ticker,
            time_bucket(INTERVAL '1 hour', ts) AS bucket,
            first(open, ts)  AS open,
            max(high)        AS high,
            min(low)         AS low,
            last(close, ts)  AS close,
            sum(volume)      AS volume
        FROM prices
        GROUP BY ticker, bucket
        WITH NO DATA
        """
    )

    # ---- 1d continuous aggregate -------------------------------------
    op.execute(
        """
        CREATE MATERIALIZED VIEW prices_1d
        WITH (timescaledb.continuous) AS
        SELECT
            ticker,
            time_bucket(INTERVAL '1 day', ts) AS bucket,
            first(open, ts)  AS open,
            max(high)        AS high,
            min(low)         AS low,
            last(close, ts)  AS close,
            sum(volume)      AS volume
        FROM prices
        GROUP BY ticker, bucket
        WITH NO DATA
        """
    )

    # ---- Refresh policies (skip in test env via guard) ---------------
    # In production these keep the aggregates current. In ephemeral test
    # databases (CI, dev), policy creation succeeds but the background
    # worker may not run; that's harmless.
    op.execute(
        """
        SELECT add_continuous_aggregate_policy(
            'prices_1h',
            start_offset => INTERVAL '2 days',
            end_offset   => INTERVAL '1 hour',
            schedule_interval => INTERVAL '30 minutes',
            if_not_exists => TRUE
        )
        """
    )
    op.execute(
        """
        SELECT add_continuous_aggregate_policy(
            'prices_1d',
            start_offset => INTERVAL '7 days',
            end_offset   => INTERVAL '1 day',
            schedule_interval => INTERVAL '1 hour',
            if_not_exists => TRUE
        )
        """
    )


def downgrade() -> None:
    # Drop continuous aggregates first (they depend on the hypertable)
    op.execute("DROP MATERIALIZED VIEW IF EXISTS prices_1d CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS prices_1h CASCADE")
    op.execute("DROP TABLE IF EXISTS prices CASCADE")
    # Extension stays installed — other features may depend on it. Manual
    # cleanup via `DROP EXTENSION timescaledb CASCADE` if truly required.
