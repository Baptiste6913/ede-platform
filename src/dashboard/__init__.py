"""Phase 7 — Streamlit dashboard MVP.

Single-file Streamlit at the repo root (`streamlit_app.py`) consumes
this module for everything that is NOT Streamlit-specific (DB queries,
score formatting, Plotly chart builders, mock paper-portfolio data).

Splitting the data layer out keeps it testable without launching
Streamlit and keeps `streamlit_app.py` focused on layout + widgets.
"""

from src.dashboard.charts import (
    build_calibration_plot,
    build_feature_importance_bar,
    build_pipeline_timeline,
    build_score_distribution,
)
from src.dashboard.data import (
    DealsFilters,
    get_all_clusters,
    get_calibration_data,
    get_cluster_detail,
    get_events_for_cluster,
    get_feature_importance,
    get_pipeline_timeline,
    get_score_for_cluster,
)
from src.dashboard.paper_portfolio_mock import (
    build_mock_portfolio,
    build_mock_watchlist,
)
from src.dashboard.scoring_helpers import (
    decision_badge,
    format_stars,
    score_color,
    status_badge,
)

__all__ = [
    "DealsFilters",
    "build_calibration_plot",
    "build_feature_importance_bar",
    "build_mock_portfolio",
    "build_mock_watchlist",
    "build_pipeline_timeline",
    "build_score_distribution",
    "decision_badge",
    "format_stars",
    "get_all_clusters",
    "get_calibration_data",
    "get_cluster_detail",
    "get_events_for_cluster",
    "get_feature_importance",
    "get_pipeline_timeline",
    "get_score_for_cluster",
    "score_color",
    "status_badge",
]
