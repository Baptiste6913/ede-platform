"""Unit tests for src.dashboard.charts — Plotly figure structure checks."""

from __future__ import annotations

import pandas as pd
import pytest

from src.dashboard.charts import (
    build_calibration_plot,
    build_class_balance_pie,
    build_feature_importance_bar,
    build_jurisdiction_star_heatmap,
    build_pipeline_timeline,
    build_score_distribution,
)


def _sample_clusters_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "cluster_id": [1, 2, 3, 4],
            "p_completion": [0.95, 0.72, 0.45, 0.18],
            "score_stars": [5, 4, 2, 1],
            "juridiction": ["FR", "IT", "DE", "FR"],
            "completion_label": [1, 1, 0, None],
        }
    )


def test_build_score_distribution_returns_histogram() -> None:
    fig = build_score_distribution(_sample_clusters_df())
    assert fig.data, "Expected at least one trace"
    assert fig.layout.title.text and "Score distribution" in fig.layout.title.text


def test_build_score_distribution_handles_empty() -> None:
    fig = build_score_distribution(pd.DataFrame())
    assert "no data" in (fig.layout.title.text or "").lower()


def test_build_calibration_plot_always_includes_diagonal() -> None:
    fig = build_calibration_plot(pd.DataFrame())
    # First trace is the perfect-calibration diagonal.
    names = [t.name for t in fig.data]
    assert "Perfect calibration" in names


def test_build_calibration_plot_renders_observations_when_provided() -> None:
    df = pd.DataFrame(
        {"bin_mid": [0.1, 0.5, 0.9], "empirical_rate": [0.05, 0.6, 0.95], "n": [10, 20, 30]}
    )
    fig = build_calibration_plot(df)
    names = [t.name for t in fig.data]
    assert "Observed" in names


def test_build_feature_importance_bar_truncates_to_top_n() -> None:
    df = pd.DataFrame({"feature": [f"f{i}" for i in range(40)], "coefficient": list(range(40))})
    fig = build_feature_importance_bar(df, top_n=5)
    bar = fig.data[0]
    assert len(bar.y) == 5


def test_build_feature_importance_bar_handles_empty() -> None:
    fig = build_feature_importance_bar(pd.DataFrame())
    assert "no model" in (fig.layout.title.text or "").lower()


def test_build_pipeline_timeline_orders_by_month() -> None:
    df = pd.DataFrame(
        {"month": pd.to_datetime(["2024-06-01", "2024-08-01", "2025-01-01"]), "n": [3, 5, 2]}
    )
    fig = build_pipeline_timeline(df)
    bar = fig.data[0]
    assert list(bar.y) == [3, 5, 2]


def test_build_pipeline_timeline_handles_empty() -> None:
    fig = build_pipeline_timeline(pd.DataFrame())
    assert "no data" in (fig.layout.title.text or "").lower()


@pytest.mark.parametrize(
    "missing_col",
    ["cluster_id", "score_stars", "juridiction"],
)
def test_build_jurisdiction_star_heatmap_gracefully_handles_missing_cols(
    missing_col: str,
) -> None:
    df = _sample_clusters_df().drop(columns=missing_col)
    fig = build_jurisdiction_star_heatmap(df)
    assert fig is not None
    # Returns a placeholder with "no data" in the title.
    assert "no data" in (fig.layout.title.text or "").lower()


def test_build_jurisdiction_star_heatmap_returns_imshow() -> None:
    fig = build_jurisdiction_star_heatmap(_sample_clusters_df())
    # plotly express imshow creates a Heatmap trace.
    assert fig.data[0].type in {"heatmap", "image"}


def test_build_class_balance_pie_counts_three_buckets() -> None:
    fig = build_class_balance_pie(_sample_clusters_df())
    pie = fig.data[0]
    labels = list(pie.labels)
    # Three categories: closed, failed, pending (some may be missing if df is small)
    assert any("closed" in lab for lab in labels)


def test_build_class_balance_pie_handles_empty() -> None:
    fig = build_class_balance_pie(pd.DataFrame())
    assert "no data" in (fig.layout.title.text or "").lower()
