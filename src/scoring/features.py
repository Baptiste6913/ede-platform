"""Phase 6 V1 feature extraction.

12 features per `(target_name, juridiction)` cluster. Cluster = the
underlying M&A operation; for FR a cluster aggregates the multi-stage
BDIF filings (visa → réouverture → suite → OPR-RO), for IT/DE a
cluster is one Consob/BaFin row.

Missing-value handling:
- Numeric features that we cannot read from the DB (PDF parser didn't
  extract them) are returned as `float('nan')`. The training Pipeline
  uses `IterativeImputer` to fill them.
- Categorical features that cannot be inferred default to the literal
  string `"unknown"`. `OneHotEncoder(handle_unknown='ignore')` keeps
  inference robust to unseen levels.

Outlier capping:
- `bid_premium_pct` is clipped to [-50, 500] per brief.
- `relative_size` is clipped to [0, 10].
- `days_to_expected_close` is clipped to [0, 730].
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Final

from sqlalchemy import select

from src.core.models import Deal

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# Public surface ------------------------------------------------------------

NUMERIC_FEATURES: Final[tuple[str, ...]] = (
    "bid_premium_pct",
    "relative_size",
    "min_acceptance_threshold",
    "days_to_expected_close",
    "events_count",
)
CATEGORICAL_FEATURES: Final[tuple[str, ...]] = (
    "deal_type",
    "payment_type",
    "jurisdiction",
    "target_sector",
    "acquirer_type",
)
BOOLEAN_FEATURES: Final[tuple[str, ...]] = (
    "cross_border",
    "has_irrevocable_undertaking",
    "fdi_risk_flag",
)
FEATURE_NAMES: Final[tuple[str, ...]] = (
    *NUMERIC_FEATURES,
    *CATEGORICAL_FEATURES,
    *BOOLEAN_FEATURES,
)


# Heuristics ----------------------------------------------------------------

_PE_TOKENS = (
    "bidco", "bid co", "holding", "holdings", "capital", "partners",
    "investment", "investments", "sarl", "s.à r.l", "luxembourg",
    "lux", "private equity", "kkr", "cinven", "cvc", "ardian",
    "warburg", "advent", "ep global", "ephios",
)
_SOE_TOKENS = ("adnoc", "edf", "engie", "orano", "areva", "saudi", "qatar")
_CORPORATE_SUFFIXES = (
    " ag", " se", " spa", " s.p.a", " sa", " s.a.", " nv", " n.v",
    " plc", " ltd", " gmbh", " inc",
)
_CROSS_BORDER_TOKENS = (
    "italien", "italy", "italia", "luxembourg", "lux ", "s.à r.l",
    "sarl", "germany", "uk ", "usa", "canada", "japan", "china",
    "saudi", "switzerland", "swiss", "abu dhabi", "qatar", "states",
    "international",
)
_FDI_RISK_TOKENS = (
    "adnoc", "china", "chinese", "jd.com", "jingdong", "saudi",
    "qatar", "abu dhabi", "uae", "uzbek", "huawei", "alibaba",
)


def _classify_acquirer(name: str) -> str:
    lower = name.lower()
    if any(t in lower for t in _SOE_TOKENS):
        return "soe"
    if any(t in lower for t in _PE_TOKENS):
        return "pe"
    if any(lower.endswith(s) or s + " " in lower for s in _CORPORATE_SUFFIXES):
        return "corporate"
    # Surname-only heuristic: short and no corporate suffix → family.
    if 0 < len(name.split()) <= 3 and not any(  # noqa: PLR2004
        kw in lower for kw in ("group", "company", "co.", "corp")
    ):
        return "family"
    return "unknown"


def _is_cross_border(target: str, acquirer: str) -> bool:
    target_lower = target.lower()
    acq_lower = acquirer.lower()
    for token in _CROSS_BORDER_TOKENS:
        if token in acq_lower and token not in target_lower:
            return True
    return False


def _fdi_risk(acquirer: str) -> bool:
    lower = acquirer.lower()
    return any(t in lower for t in _FDI_RISK_TOKENS)


def _classify_payment(deal: Deal) -> str:
    # No explicit payment column. opa* = cash; ope/opas = exchange/mixed.
    if deal.deal_type in {"ope", "opas"}:
        return "stock"
    return "cash"


def _days_to_close(deal: Deal, today: date) -> float:
    if deal.expected_close_date is None:
        return float("nan")
    delta = (deal.expected_close_date - deal.announcement_date).days
    return float(min(max(delta, 0), 730))


# Aggregation ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ClusterFeatures:
    target_name: str
    jurisdiction: str
    representative_deal_id: int
    features: dict[str, Any]
    label: int | None
    earliest_announcement: date


async def extract_cluster_features(
    target_name: str,
    jurisdiction: str,
    session: AsyncSession,
    *,
    today: date | None = None,
) -> ClusterFeatures | None:
    """Aggregate all `deals` rows matching `(target, jurisdiction)` into one
    feature row. Earliest announcement = `announcement_date` proxy."""
    today = today or date.today()
    rows = (
        (
            await session.execute(
                select(Deal)
                .where(Deal.target_name == target_name)
                .where(Deal.juridiction == jurisdiction)
                .order_by(Deal.announcement_date)
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        return None

    first = rows[0]
    # Pick the most informative acquirer label (avoid '[pending parse]').
    acquirer = first.acquirer_name
    for d in rows:
        if d.acquirer_name and d.acquirer_name != "[pending parse]":
            acquirer = d.acquirer_name
            break

    # Numeric: use first non-null across cluster
    def _first_non_null(getter):  # type: ignore[no-untyped-def]
        for d in rows:
            v = getter(d)
            if v is not None:
                return v
        return None

    premium_raw = _first_non_null(lambda d: d.premium_pct)
    bid_premium_pct = float("nan")
    if premium_raw is not None:
        bid_premium_pct = float(premium_raw) * 100.0
        bid_premium_pct = max(min(bid_premium_pct, 500.0), -50.0)

    min_acc_raw = _first_non_null(lambda d: d.min_acceptance_threshold)
    min_acc = float(min_acc_raw) if min_acc_raw is not None else float("nan")

    expected_close = (
        max((d.expected_close_date for d in rows if d.expected_close_date), default=None)
    )
    days_to_close = float("nan")
    if expected_close is not None:
        days_to_close = float(
            min(max((expected_close - first.announcement_date).days, 0), 730)
        )

    # Cluster-level signals
    events_count = float(len(rows))

    # Consolidated label: any labelled deal in the cluster propagates.
    label: int | None = None
    for d in rows:
        if d.completion_label is not None:
            label = int(d.completion_label)
            break

    features: dict[str, Any] = {
        "bid_premium_pct": bid_premium_pct,
        "relative_size": float("nan"),  # phase 8+ feature
        "min_acceptance_threshold": min_acc,
        "days_to_expected_close": days_to_close,
        "events_count": events_count,
        "deal_type": first.deal_type or "unknown",
        "payment_type": _classify_payment(first),
        "jurisdiction": jurisdiction,
        "target_sector": "unknown",  # phase 8+ feature (GICS)
        "acquirer_type": _classify_acquirer(acquirer or "unknown"),
        "cross_border": _is_cross_border(target_name, acquirer or ""),
        "has_irrevocable_undertaking": False,  # phase 7+ feature (PDF text scan)
        "fdi_risk_flag": _fdi_risk(acquirer or ""),
    }

    return ClusterFeatures(
        target_name=target_name,
        jurisdiction=jurisdiction,
        representative_deal_id=first.id,
        features=features,
        label=label,
        earliest_announcement=first.announcement_date,
    )


async def iter_all_clusters(
    session: AsyncSession,
) -> list[ClusterFeatures]:
    """Group every `deals` row by `(target_name, juridiction)`. One
    cluster per group. Excludes targets with `[pending parse]`
    (cannot reliably cluster without a real name)."""
    pairs = (
        await session.execute(
            select(Deal.target_name, Deal.juridiction)
            .where(Deal.target_name != "[pending parse]")
            .distinct()
        )
    ).all()

    clusters: list[ClusterFeatures] = []
    for target, jur in pairs:
        cf = await extract_cluster_features(target, jur, session)
        if cf is not None:
            clusters.append(cf)
    return clusters


def features_to_vector(features: dict[str, Any]) -> dict[str, float | str]:
    """Flatten the dict so it can be fed to pandas / sklearn. Booleans
    become 0.0/1.0; NaN stays NaN; categoricals stay as strings."""
    out: dict[str, float | str] = {}
    for k in NUMERIC_FEATURES:
        v = features.get(k, float("nan"))
        out[k] = float(v) if v is not None and not (isinstance(v, float) and math.isnan(v)) else float("nan")
    for k in CATEGORICAL_FEATURES:
        out[k] = str(features.get(k, "unknown") or "unknown")
    for k in BOOLEAN_FEATURES:
        out[k] = 1.0 if features.get(k) else 0.0
    return out


def utc_now_iso() -> str:
    from datetime import UTC

    return datetime.now(tz=UTC).isoformat()
