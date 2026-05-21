"""Phase 7 dashboard — DB-facing data layer.

Pure SQLAlchemy + psycopg synchronous access. No Streamlit imports,
no `st.cache_data` wrappers here (the wrappers live in
`streamlit_app.py`). That keeps every function in this module trivially
testable with a pytest DB fixture.

Connection strategy: read `DATABASE_URL` from `src.core.settings`, build
a synchronous SQLAlchemy engine on first use. The dashboard issues a
handful of queries per page load, so a single engine + autocommit
sessions are sufficient (no connection pooling tuning needed for V1).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import Engine, create_engine, text


@dataclass(frozen=True)
class DealsFilters:
    """Sidebar filter contract. All fields nullable / None = "no filter"."""

    jurisdictions: tuple[str, ...] | None = None  # None = all
    stars: tuple[int, ...] | None = None  # None = all
    status: str = "all"  # all|pending|closed|failed
    date_from: date | None = None
    date_to: date | None = None
    acquirer_types: tuple[str, ...] | None = None  # None = all
    deal_types: tuple[str, ...] | None = None  # None = all

    def with_defaults(self) -> DealsFilters:
        """Apply UI defaults (24-month window, stars 3-5, all jurisdictions)."""
        today = date.today()
        return replace(
            self,
            date_from=self.date_from or (today - timedelta(days=730)),
            date_to=self.date_to or today,
            stars=self.stars or (3, 4, 5),
        )


# --------------------------------------------------------------------- engine


def _sync_url(database_url: str) -> str:
    """Convert async DSN (postgresql+asyncpg://...) to sync psycopg DSN."""
    if "+asyncpg" in database_url:
        return database_url.replace("+asyncpg", "+psycopg")
    return database_url


@lru_cache(maxsize=1)
def _get_engine() -> Engine:
    from src.core.settings import get_settings

    settings = get_settings()
    return create_engine(_sync_url(settings.database_url), future=True)


def reset_engine_cache() -> None:
    """Test hook — drop the cached engine so a fresh settings/DSN takes effect.

    Disposes the existing engine first so any open psycopg connections in
    the pool are closed cleanly (avoids `ResourceWarning` under pytest's
    `filterwarnings = error`).
    """
    import contextlib

    info = _get_engine.cache_info()
    if info.currsize > 0:
        with contextlib.suppress(Exception):
            _get_engine().dispose()
    _get_engine.cache_clear()


# --------------------------------------------------------------------- queries

_BASE_CLUSTERS_SQL = """
SELECT
    s.deal_id              AS cluster_id,
    d.target_name,
    d.acquirer_name,
    d.juridiction,
    d.deal_type,
    d.announcement_date,
    d.expected_close_date,
    d.status               AS deal_status,
    d.completion_label,
    d.source_url,
    s.p_completion,
    s.score_stars,
    s.decision,
    s.model_version,
    s.features,
    s.risk_factors,
    s.positive_factors,
    s.ts                   AS scored_at,
    (
        SELECT COUNT(*) FROM deals d2
        WHERE d2.target_name = d.target_name
          AND d2.juridiction = d.juridiction
    )                      AS events_count
FROM scores s
JOIN deals d ON d.id = s.deal_id
WHERE s.id IN (
    SELECT MAX(id) FROM scores GROUP BY deal_id
)
"""


def _apply_filters(sql: str, filters: DealsFilters) -> tuple[str, dict[str, Any]]:
    """Return (SQL with WHERE clauses, params dict)."""
    clauses: list[str] = []
    params: dict[str, Any] = {}
    if filters.jurisdictions:
        clauses.append("d.juridiction = ANY(:jurs)")
        params["jurs"] = list(filters.jurisdictions)
    if filters.stars:
        clauses.append("s.score_stars = ANY(:stars)")
        params["stars"] = list(filters.stars)
    if filters.status == "pending":
        clauses.append("d.completion_label IS NULL")
    elif filters.status == "closed":
        clauses.append("d.completion_label = 1")
    elif filters.status == "failed":
        clauses.append("d.completion_label = 0")
    if filters.date_from is not None:
        clauses.append("d.announcement_date >= :date_from")
        params["date_from"] = filters.date_from
    if filters.date_to is not None:
        clauses.append("d.announcement_date <= :date_to")
        params["date_to"] = filters.date_to
    if filters.acquirer_types:
        clauses.append("COALESCE(s.features->>'acquirer_type', 'unknown') = ANY(:atypes)")
        params["atypes"] = list(filters.acquirer_types)
    if filters.deal_types:
        clauses.append("d.deal_type = ANY(:dtypes)")
        params["dtypes"] = list(filters.deal_types)
    if clauses:
        sql = sql + " AND " + " AND ".join(clauses)
    return sql, params


def get_all_clusters(filters: DealsFilters | None = None) -> pd.DataFrame:
    """One row per scored cluster, honoring the sidebar filter spec.

    The returned DataFrame has these columns (one per Phase-7 wireframe):
        cluster_id, target_name, acquirer_name, juridiction,
        deal_type, announcement_date, expected_close_date,
        deal_status, completion_label, source_url,
        p_completion, score_stars, decision,
        model_version, features (jsonb dict),
        risk_factors (list), positive_factors (list),
        scored_at, events_count
    """
    f = (filters or DealsFilters()).with_defaults()
    sql, params = _apply_filters(_BASE_CLUSTERS_SQL, f)
    sql = sql + " ORDER BY d.announcement_date DESC, s.deal_id ASC"
    with _get_engine().begin() as conn:
        return pd.read_sql_query(text(sql), conn, params=params)


def get_cluster_detail(cluster_id: int) -> dict[str, Any] | None:
    """Single row from the same scored-cluster view, plus the full list
    of sibling `deals` rows in the cluster (FR multi-stage chains)."""
    head_sql = _BASE_CLUSTERS_SQL + " AND s.deal_id = :cid"
    with _get_engine().begin() as conn:
        head = pd.read_sql_query(text(head_sql), conn, params={"cid": cluster_id})
        if head.empty:
            return None
        row = head.iloc[0].to_dict()
        siblings = pd.read_sql_query(
            text(
                """
                SELECT id AS deal_id, regulator_ref, deal_type,
                       announcement_date, expected_close_date, status,
                       source_url, pdf_path
                FROM deals
                WHERE target_name = :tname AND juridiction = :jur
                ORDER BY announcement_date ASC
                """
            ),
            conn,
            params={"tname": row["target_name"], "jur": row["juridiction"]},
        )
    row["siblings"] = siblings.to_dict(orient="records")
    return row


def get_score_for_cluster(cluster_id: int) -> dict[str, Any] | None:
    """Latest `scores` row for a given representative `deal_id`."""
    with _get_engine().begin() as conn:
        df = pd.read_sql_query(
            text(
                """
                SELECT * FROM scores
                WHERE deal_id = :cid
                ORDER BY ts DESC
                LIMIT 1
                """
            ),
            conn,
            params={"cid": cluster_id},
        )
    if df.empty:
        return None
    return df.iloc[0].to_dict()


def get_events_for_cluster(cluster_id: int) -> list[dict[str, Any]]:
    """Every event for every deal sharing the cluster's (target, jurisdiction).

    Cluster events span the whole multi-stage chain on FR.
    """
    with _get_engine().begin() as conn:
        target = conn.execute(
            text("SELECT target_name, juridiction FROM deals WHERE id = :cid"),
            {"cid": cluster_id},
        ).first()
        if target is None:
            return []
        df = pd.read_sql_query(
            text(
                """
                SELECT e.id, e.deal_id, e.ts, e.event_type, e.description,
                       e.source_url, e.raw_payload, d.announcement_date,
                       d.deal_type, d.regulator_ref
                FROM events e
                JOIN deals d ON d.id = e.deal_id
                WHERE d.target_name = :tname AND d.juridiction = :jur
                ORDER BY e.ts ASC, e.id ASC
                """
            ),
            conn,
            params={"tname": target.target_name, "jur": target.juridiction},
        )
    return df.to_dict(orient="records")


def get_calibration_data() -> pd.DataFrame:
    """Reconstruct the calibration deciles in-memory from the current
    `scores` + `deals.completion_label` join. Mirrors the breakdown
    that Phase-6 `artifacts/phase-06/validation_report.md` printed but
    is recomputed live so the dashboard stays in sync with new scoring
    runs.
    """
    with _get_engine().begin() as conn:
        df = pd.read_sql_query(
            text(
                """
                SELECT s.p_completion::float AS p_completion, d.completion_label
                FROM scores s
                JOIN deals d ON d.id = s.deal_id
                WHERE s.id IN (SELECT MAX(id) FROM scores GROUP BY deal_id)
                  AND d.completion_label IS NOT NULL
                """
            ),
            conn,
        )
    if df.empty:
        return pd.DataFrame(columns=["bin_mid", "empirical_rate", "n"])
    # 5 evenly-spaced bins (per Phase-6 small-N convention).
    from itertools import pairwise

    edges = [0.0, 0.2, 0.4, 0.6, 0.8, 1.01]
    rows: list[dict[str, Any]] = []
    for lo, hi in pairwise(edges):
        mask = (df["p_completion"] >= lo) & (df["p_completion"] < hi)
        n = int(mask.sum())
        if n == 0:
            continue
        rows.append(
            {
                "bin_mid": round((lo + hi) / 2, 2),
                "empirical_rate": float(df.loc[mask, "completion_label"].mean()),
                "n": n,
            }
        )
    return pd.DataFrame(rows)


def get_pipeline_timeline(filters: DealsFilters | None = None) -> pd.DataFrame:
    """Count of scored clusters per month, honoring filters."""
    f = (filters or DealsFilters()).with_defaults()
    sql = _BASE_CLUSTERS_SQL
    sql, params = _apply_filters(sql, f)
    with _get_engine().begin() as conn:
        df = pd.read_sql_query(text(sql), conn, params=params)
    if df.empty:
        return pd.DataFrame(columns=["month", "n"])
    df["month"] = pd.to_datetime(df["announcement_date"]).dt.to_period("M").dt.to_timestamp()
    out = df.groupby("month", as_index=False).size().rename(columns={"size": "n"})
    return out.sort_values("month")


def get_feature_importance(model_path: Path | None = None) -> pd.DataFrame:
    """Read coefficients from the persisted `ScoringModel`. If the path
    is omitted, fall back to the latest `models/scoring_v1_*.pkl`."""
    if model_path is None:
        candidates = sorted(Path("models").glob("scoring_v1_*.pkl"))
        if not candidates:
            return pd.DataFrame(columns=["feature", "coefficient"])
        model_path = candidates[-1]
    if not Path(model_path).exists():
        return pd.DataFrame(columns=["feature", "coefficient"])
    from src.scoring.model import ScoringModel

    model = ScoringModel.load(model_path)
    if model.inner_clf is None:
        return pd.DataFrame(columns=["feature", "coefficient"])
    coefs = model.inner_clf.coef_[0]
    names = model.feature_names_post_transform
    return (
        pd.DataFrame({"feature": names, "coefficient": coefs})
        .assign(abs_coef=lambda d: d["coefficient"].abs())
        .sort_values("abs_coef", ascending=False)
        .drop(columns="abs_coef")
        .reset_index(drop=True)
    )


def get_filter_options() -> dict[str, Any]:
    """Distinct values powering the sidebar dropdowns (jurisdictions,
    deal types, acquirer types)."""
    with _get_engine().begin() as conn:
        df = pd.read_sql_query(
            text(
                """
                SELECT DISTINCT d.juridiction, d.deal_type,
                       COALESCE(s.features->>'acquirer_type', 'unknown') AS acquirer_type
                FROM scores s
                JOIN deals d ON d.id = s.deal_id
                WHERE s.id IN (SELECT MAX(id) FROM scores GROUP BY deal_id)
                """
            ),
            conn,
        )
    return {
        "jurisdictions": sorted(df["juridiction"].dropna().unique().tolist()),
        "deal_types": sorted(df["deal_type"].dropna().unique().tolist()),
        "acquirer_types": sorted(df["acquirer_type"].dropna().unique().tolist()),
    }


def get_latest_model_metadata() -> dict[str, Any]:
    """Single row summary used by the sidebar footer."""
    with _get_engine().begin() as conn:
        df = pd.read_sql_query(
            text(
                """
                SELECT MAX(model_version) AS model_version,
                       COUNT(*) AS n_scored,
                       MAX(ts) AS latest_run_at
                FROM scores
                """
            ),
            conn,
        )
    return df.iloc[0].to_dict() if not df.empty else {}
