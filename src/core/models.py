"""ORM models — SQLAlchemy 2.0 typed Mapped/mapped_column.

All Postgres ENUM types are managed manually in the migration scripts
(`create_type=False` here) so alembic stays the single source of truth for DB
state. JSONB is used for free-form payloads per CLAUDE.md §7 phase 1.

FK on `deal_id` use `ON DELETE CASCADE` everywhere a deal is the parent —
deleting a deal drops its events, scores, analyses, and paper positions.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core import enums
from src.core.db import Base

# ---- Postgres ENUM column types (create_type=False — managed by migrations) ----

JurisdictionEnum = Enum(
    *enums.JURISDICTIONS,
    name="jurisdiction_enum",
    create_type=False,
)
DealTypeEnum = Enum(*enums.DEAL_TYPES, name="deal_type_enum", create_type=False)
DealStatusEnum = Enum(*enums.DEAL_STATUSES, name="deal_status_enum", create_type=False)
EventTypeEnum = Enum(*enums.EVENT_TYPES, name="event_type_enum", create_type=False)
DecisionEnum = Enum(*enums.DECISIONS, name="decision_enum", create_type=False)
AnalystVerdictEnum = Enum(
    *enums.ANALYST_VERDICTS,
    name="analyst_verdict_enum",
    create_type=False,
)
AnalystSourceEnum = Enum(
    *enums.ANALYST_SOURCES,
    name="analyst_source_enum",
    create_type=False,
)
PositionSideEnum = Enum(*enums.POSITION_SIDES, name="position_side_enum", create_type=False)
PositionStatusEnum = Enum(
    *enums.POSITION_STATUSES,
    name="position_status_enum",
    create_type=False,
)
CurrencyEnum = Enum(*enums.CURRENCIES, name="currency_enum", create_type=False)
PriceSourceEnum = Enum(*enums.PRICE_SOURCES, name="price_source_enum", create_type=False)


# =========================================================================
# deals
# =========================================================================


class Deal(Base):
    __tablename__ = "deals"
    __table_args__ = (
        UniqueConstraint(
            "juridiction",
            "regulator_ref",
            name="uq_deals_juridiction_regulator_ref",
        ),
        Index("ix_deals_juridiction_status", "juridiction", "status"),
        Index("ix_deals_ticker_target", "ticker_target"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    juridiction: Mapped[str] = mapped_column(JurisdictionEnum, nullable=False)
    # Cross-border deals: when the primary filing is in one regulator but the
    # target is also listed elsewhere (e.g. DE filing for a FR/DE dual-listed
    # target → juridiction='DE', secondary_jurisdictions=['FR']).
    secondary_jurisdictions: Mapped[list[str] | None] = mapped_column(
        ARRAY(JurisdictionEnum),
        nullable=True,
    )
    regulator_ref: Mapped[str] = mapped_column(String(128), nullable=False)

    ticker_target: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    ticker_acquirer: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Phase 8: broker-qualified IBKR symbol + exchange (resolver cache, migration 0011).
    ibkr_ticker: Mapped[str | None] = mapped_column(Text, nullable=True)
    ibkr_exchange: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_name: Mapped[str] = mapped_column(String(255), nullable=False)
    acquirer_name: Mapped[str] = mapped_column(String(255), nullable=False)

    announcement_date: Mapped[date] = mapped_column(Date, nullable=False)
    deal_type: Mapped[str] = mapped_column(DealTypeEnum, nullable=False)
    status: Mapped[str] = mapped_column(DealStatusEnum, nullable=False)

    offer_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    currency: Mapped[str | None] = mapped_column(CurrencyEnum, nullable=True)
    payment_cash_share: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    premium_pct: Mapped[Decimal | None] = mapped_column(Numeric(7, 4), nullable=True)
    min_acceptance_threshold: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )
    expected_close_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    pdf_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Phase 6 scoring V1 ground-truth label (migration 0009).
    completion_label: Mapped[int | None] = mapped_column(
        Integer,  # SMALLINT in SQL; ORM uses Integer.
        nullable=True,
    )
    completion_label_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    completion_label_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    events: Mapped[list[Event]] = relationship(
        back_populates="deal",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    scores: Mapped[list[Score]] = relationship(
        back_populates="deal",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    analyses: Mapped[list[Analysis]] = relationship(
        back_populates="deal",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    positions: Mapped[list[PaperPosition]] = relationship(
        back_populates="deal",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


# =========================================================================
# prices — TimescaleDB hypertable (created in migration via raw SQL)
# =========================================================================


class Price(Base):
    __tablename__ = "prices"
    __table_args__ = (
        # ts is part of the composite PK because Timescale hypertables require
        # the partitioning column to be part of any unique constraint.
        Index("ix_prices_ticker_ts", "ticker", "ts"),
    )

    ticker: Mapped[str] = mapped_column(String(32), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    open: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source: Mapped[str] = mapped_column(PriceSourceEnum, nullable=False)


# =========================================================================
# events
# =========================================================================


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_deal_id_ts", "deal_id", "ts"),
        Index("ix_events_event_type", "event_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    deal_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("deals.id", ondelete="CASCADE"),
        nullable=False,
    )
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event_type: Mapped[str] = mapped_column(EventTypeEnum, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    deal: Mapped[Deal] = relationship(back_populates="events")


# =========================================================================
# scores
# =========================================================================


class Score(Base):
    __tablename__ = "scores"
    __table_args__ = (
        Index("ix_scores_deal_id_ts", "deal_id", "ts"),
        CheckConstraint("p_completion >= 0 AND p_completion <= 1", name="ck_scores_p_completion"),
        CheckConstraint(
            "p_market_implied IS NULL OR (p_market_implied >= 0 AND p_market_implied <= 1)",
            name="ck_scores_p_market_implied",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    deal_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("deals.id", ondelete="CASCADE"),
        nullable=False,
    )
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    p_completion: Mapped[Decimal] = mapped_column(Numeric(6, 5), nullable=False)
    p_market_implied: Mapped[Decimal | None] = mapped_column(Numeric(6, 5), nullable=True)
    edge: Mapped[Decimal | None] = mapped_column(Numeric(7, 5), nullable=True)
    expected_return_annualized: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 5),
        nullable=True,
    )
    decision: Mapped[str] = mapped_column(DecisionEnum, nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    features: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Phase 6 V1 extensions (migration 0010).
    score_stars: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_factors: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    positive_factors: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    deal: Mapped[Deal] = relationship(back_populates="scores")


# =========================================================================
# analyses (Claude brief outputs)
# =========================================================================


class Analysis(Base):
    __tablename__ = "analyses"
    __table_args__ = (Index("ix_analyses_deal_id_ts", "deal_id", "ts"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    deal_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("deals.id", ondelete="CASCADE"),
        nullable=False,
    )
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    source: Mapped[str] = mapped_column(AnalystSourceEnum, nullable=False)
    brief_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    verdict: Mapped[str] = mapped_column(AnalystVerdictEnum, nullable=False)
    thesis_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    risks: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    catalysts: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)

    deal: Mapped[Deal] = relationship(back_populates="analyses")


# =========================================================================
# paper_positions
# =========================================================================


class PaperPosition(Base):
    __tablename__ = "paper_positions"
    __table_args__ = (
        Index("ix_paper_positions_deal_id", "deal_id"),
        Index("ix_paper_positions_status", "status"),
        CheckConstraint("size_eur > 0", name="ck_paper_positions_size_eur_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    deal_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("deals.id", ondelete="CASCADE"),
        nullable=False,
    )
    open_ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    close_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    exit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    size_eur: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    side: Mapped[str] = mapped_column(PositionSideEnum, nullable=False)
    pnl_eur: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    status: Mapped[str] = mapped_column(PositionStatusEnum, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    deal: Mapped[Deal] = relationship(back_populates="positions")


class Trade(Base):
    """Phase 8 order-execution ledger (status machine + idempotency).

    Distinct from `paper_positions` (current state): one row per submitted
    order. `trade_id` is UNIQUE for idempotent re-submits.
    """

    __tablename__ = "trades"
    __table_args__ = (
        UniqueConstraint("trade_id", name="uq_trades_trade_id"),
        CheckConstraint("quantity > 0", name="ck_trades_quantity_positive"),
        CheckConstraint("side IN ('BUY','SELL')", name="ck_trades_side"),
        CheckConstraint(
            "status IN ('PENDING','SUBMITTED','FILLED','REJECTED','CANCELLED')",
            name="ck_trades_status",
        ),
        Index("ix_trades_status", "status"),
        Index("ix_trades_deal_id", "deal_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trade_id: Mapped[str] = mapped_column(String(36), nullable=False)
    deal_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("deals.id", ondelete="CASCADE"), nullable=False
    )
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    limit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    stop_loss_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    take_profit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    ibkr_order_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ibkr_stop_order_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    filled_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    filled_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    filled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pnl_realized: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    pnl_unrealized: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    requires_approval: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=func.false()
    )
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=func.false())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    deal: Mapped[Deal] = relationship()


class VendorApiUsage(Base):
    """Per-call ledger for paid external APIs (ScrapingBee, GDELT, etc.).

    Used to enforce monthly budgets in `src/ingestion/consob/scrapingbee_client.py`
    and to feed the Discord usage-threshold alerts (phase 11).
    """

    __tablename__ = "vendor_api_usage"
    __table_args__ = (
        Index("ix_vendor_api_usage_vendor_month", "vendor", "year_month"),
        Index("ix_vendor_api_usage_ts", "ts"),
        CheckConstraint("credits_cost >= 0", name="ck_vendor_api_usage_cost_nonneg"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    vendor: Mapped[str] = mapped_column(String(32), nullable=False)
    year_month: Mapped[str] = mapped_column(String(7), nullable=False)  # 'YYYY-MM'
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    request_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    credits_cost: Mapped[int] = mapped_column(Integer, nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extra: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


__all__ = [
    "Analysis",
    "Deal",
    "Event",
    "PaperPosition",
    "Price",
    "Score",
    "VendorApiUsage",
]
