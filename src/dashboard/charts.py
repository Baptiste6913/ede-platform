"""Plotly figure builders used by the dashboard pages.

No Streamlit imports here — figures are pure `plotly.graph_objects`
returned to the caller, which decides how to render them
(`st.plotly_chart` in the dashboard, `fig.show()` in a notebook).
"""

from __future__ import annotations

from typing import Final

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

_JURISDICTION_COLORS: Final[dict[str, str]] = {
    "FR": "#1f77b4",
    "IT": "#2ca02c",
    "DE": "#ff7f0e",
}


def build_score_distribution(df: pd.DataFrame) -> go.Figure:
    """Histogram of `p_completion`, stacked by jurisdiction.

    Empty `df` returns an empty figure so the caller can render a
    placeholder.
    """
    if df.empty:
        fig = go.Figure()
        fig.update_layout(
            title="Score distribution (no data)",
            xaxis_title="p_completion",
            yaxis_title="count",
        )
        return fig
    fig = px.histogram(
        df,
        x="p_completion",
        color="juridiction",
        nbins=20,
        color_discrete_map=_JURISDICTION_COLORS,
        title="Score distribution — stacked by jurisdiction",
    )
    fig.update_layout(
        barmode="stack",
        xaxis_title="p_completion",
        yaxis_title="count",
        legend_title_text="Jurisdiction",
    )
    return fig


def build_calibration_plot(df: pd.DataFrame) -> go.Figure:
    """Predicted-vs-empirical scatter with diagonal reference."""
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=[0, 1],
            y=[0, 1],
            mode="lines",
            line={"dash": "dash", "color": "#888"},
            name="Perfect calibration",
            hoverinfo="skip",
        )
    )
    if df.empty:
        fig.update_layout(
            title="Calibration plot (no labelled data)",
            xaxis_title="Predicted probability (bin mid)",
            yaxis_title="Empirical rate",
        )
        return fig
    fig.add_trace(
        go.Scatter(
            x=df["bin_mid"],
            y=df["empirical_rate"],
            mode="markers+lines",
            marker={
                "size": df["n"] * 1.5 + 8,
                "color": "#1f77b4",
                "line": {"color": "white", "width": 1},
            },
            text=df["n"].apply(lambda n: f"n={n}"),
            name="Observed",
        )
    )
    fig.update_layout(
        title="Calibration (in-sample on labelled clusters)",
        xaxis_title="Predicted probability (bin mid)",
        yaxis_title="Empirical rate",
        xaxis={"range": [0, 1]},
        yaxis={"range": [0, 1]},
    )
    return fig


def build_feature_importance_bar(df: pd.DataFrame, top_n: int = 15) -> go.Figure:
    """Horizontal bar chart of |coefficient| top_n; green=+, red=-."""
    if df.empty:
        fig = go.Figure()
        fig.update_layout(
            title="Feature importance (no model loaded)",
            xaxis_title="coefficient",
            yaxis_title="feature",
        )
        return fig
    head = df.head(top_n).iloc[::-1]  # reverse so largest is at top
    colors = ["#2ca02c" if c >= 0 else "#d62728" for c in head["coefficient"]]
    fig = go.Figure(
        go.Bar(
            x=head["coefficient"],
            y=head["feature"],
            orientation="h",
            marker={"color": colors},
            text=[f"{c:+.2f}" for c in head["coefficient"]],
            textposition="outside",
        )
    )
    fig.update_layout(
        title=f"Feature importance (top {top_n} by |coefficient|)",
        xaxis_title="coefficient (signed)",
        yaxis_title="feature",
        margin={"l": 200},
    )
    return fig


def build_pipeline_timeline(df: pd.DataFrame) -> go.Figure:
    """Bar chart of cluster count per month."""
    if df.empty:
        fig = go.Figure()
        fig.update_layout(
            title="Pipeline (no data)",
            xaxis_title="month",
            yaxis_title="scored clusters",
        )
        return fig
    fig = go.Figure(
        go.Bar(
            x=df["month"],
            y=df["n"],
            marker={"color": "#1f77b4"},
            text=df["n"],
            textposition="outside",
        )
    )
    fig.update_layout(
        title="Pipeline — scored clusters announced per month",
        xaxis_title="month",
        yaxis_title="scored clusters",
        bargap=0.15,
    )
    return fig


def build_jurisdiction_star_heatmap(df: pd.DataFrame) -> go.Figure:
    """Heat-map: jurisdiction (rows) x stars (cols) cell = count."""
    required = {"cluster_id", "score_stars", "juridiction"}
    if df.empty or not required.issubset(df.columns):
        fig = go.Figure()
        fig.update_layout(title="Jurisdiction x stars heat-map (no data)")
        return fig
    pivot = (
        df.assign(score_stars=df["score_stars"].fillna(0).astype(int))
        .pivot_table(
            index="juridiction",
            columns="score_stars",
            values="cluster_id",
            aggfunc="count",
            fill_value=0,
        )
        .reindex(columns=[1, 2, 3, 4, 5], fill_value=0)
    )
    fig = px.imshow(
        pivot.values,
        labels={"x": "Stars", "y": "Jurisdiction", "color": "Clusters"},
        x=[f"{c}★" for c in pivot.columns],
        y=pivot.index.tolist(),
        text_auto=True,
        color_continuous_scale="viridis",
        aspect="auto",
    )
    fig.update_layout(title="Heat-map — jurisdiction x score★")
    return fig


def build_class_balance_pie(df: pd.DataFrame) -> go.Figure:
    """Pie chart over labelled / unlabelled clusters."""
    if df.empty:
        fig = go.Figure()
        fig.update_layout(title="Class balance (no data)")
        return fig
    counts = (
        df["completion_label"]
        .apply(
            lambda v: (
                "label=1 (closed)"
                if v == 1
                else ("label=0 (failed)" if v == 0 else "label=NULL (pending)")
            )
        )
        .value_counts()
    )
    fig = go.Figure(
        go.Pie(
            labels=counts.index.tolist(),
            values=counts.values.tolist(),
            hole=0.3,
            marker={"colors": ["#2ca02c", "#d62728", "#9e9e9e"]},
        )
    )
    fig.update_layout(title="Class balance — labelled vs pending")
    return fig
