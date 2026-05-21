"""Phase 8 preview — mock paper portfolio sourced from real 5★ scores.

This is **mock data**. The dashboard's Paper Portfolio page mandates
that no real positions are claimed: the figures below assume an
arbitrary entry size of 10 000 EUR per deal and a deterministic
±3 % "mark-to-market" wiggle. Phase 8 will replace this with the
actual IBKR Paper Trading API ledger.

Deterministic for stable reload: seeds `numpy` with a fixed value
derived from the cluster ID.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from src.dashboard.data import DealsFilters, get_all_clusters

# Constants
_MOCK_POSITION_SIZE_EUR = 10_000.0
_MARK_TO_MARKET_VOL = 0.03
_DEFAULT_ENTRY_PRICE = 25.0
_N_POSITIONS = 3


@dataclass(frozen=True)
class MockPosition:
    cluster_id: int
    target: str
    jurisdiction: str
    stars: int
    size_eur: float
    entry_price: float
    now_price: float
    pnl_eur: float
    pnl_pct: float


@dataclass(frozen=True)
class MockMetrics:
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown_pct: float
    hit_rate: float


@dataclass(frozen=True)
class MockPortfolio:
    positions: list[MockPosition]
    metrics: MockMetrics
    total_deployed_eur: float
    open_pnl_eur: float
    open_pnl_pct: float


def _seeded_rng(cluster_id: int) -> np.random.Generator:
    return np.random.default_rng(seed=int(cluster_id) % 2**32)


def _entry_price_from(offer_price: float | None) -> float:
    """Use offer_price if available, else a sensible default. Always
    discount 5 % to simulate entering at the unaffected price."""
    if offer_price is None or pd.isna(offer_price):
        return _DEFAULT_ENTRY_PRICE
    return float(offer_price) * 0.95


def build_mock_portfolio() -> MockPortfolio:
    """Pull the 3 most recent 5★ scored clusters from the live DB and
    fabricate position rows for them."""
    df = get_all_clusters(DealsFilters(stars=(5,)))
    # Most recent first per data layer ordering; pick top N rows.
    head = df.head(_N_POSITIONS)

    positions: list[MockPosition] = []
    for _, row in head.iterrows():
        cluster_id = int(row["cluster_id"])
        rng = _seeded_rng(cluster_id)
        offer = (
            row.get("features", {}).get("offer_price")
            if isinstance(row.get("features"), dict)
            else None
        )
        if offer is None:
            offer = 25.0  # default
        entry = _entry_price_from(offer)
        wiggle = float(rng.uniform(-_MARK_TO_MARKET_VOL, _MARK_TO_MARKET_VOL + 0.01))
        now = entry * (1 + wiggle)
        qty = _MOCK_POSITION_SIZE_EUR / entry
        pnl_eur = qty * (now - entry)
        pnl_pct = (now - entry) / entry if entry else 0.0
        positions.append(
            MockPosition(
                cluster_id=cluster_id,
                target=str(row["target_name"]),
                jurisdiction=str(row["juridiction"]),
                stars=int(row["score_stars"]),
                size_eur=round(_MOCK_POSITION_SIZE_EUR, 2),
                entry_price=round(entry, 2),
                now_price=round(now, 2),
                pnl_eur=round(pnl_eur, 2),
                pnl_pct=round(pnl_pct * 100.0, 2),
            )
        )

    total = sum(p.size_eur for p in positions)
    pnl = sum(p.pnl_eur for p in positions)
    pnl_pct = (pnl / total * 100.0) if total > 0 else 0.0

    return MockPortfolio(
        positions=positions,
        metrics=MockMetrics(
            sharpe_ratio=1.42,
            sortino_ratio=1.78,
            max_drawdown_pct=-2.1,
            hit_rate=0.67,
        ),
        total_deployed_eur=round(total, 2),
        open_pnl_eur=round(pnl, 2),
        open_pnl_pct=round(pnl_pct, 2),
    )


def build_mock_watchlist(limit: int = 5) -> list[dict[str, Any]]:
    """Top N 5★ clusters NOT in the mock portfolio (the next 5 most
    recent after the first 3 positions)."""
    df = get_all_clusters(DealsFilters(stars=(5,)))
    # Skip the first 3 (those are in the portfolio).
    tail = df.iloc[_N_POSITIONS : _N_POSITIONS + limit]
    return [
        {
            "cluster_id": int(r["cluster_id"]),
            "target": str(r["target_name"]),
            "acquirer": str(r["acquirer_name"]),
            "jurisdiction": str(r["juridiction"]),
            "stars": int(r["score_stars"]),
            "p_completion": round(float(r["p_completion"]), 3),
        }
        for _, r in tail.iterrows()
    ]
