"""Pure-function formatters for score badges, colors, status labels.

No Streamlit imports here — keeps the helpers trivially unit-testable.
The dashboard renders the returned strings/colors via `st.markdown`,
`st.metric`, etc.
"""

from __future__ import annotations

from typing import Final

_STAR_FILLED: Final[str] = "★"  # ★
_STAR_EMPTY: Final[str] = "☆"  # ☆

# Mapping star count → CSS-friendly hex color.
_STAR_COLOR: Final[dict[int, str]] = {
    1: "#d62728",  # red
    2: "#ff7f0e",  # orange
    3: "#bcbd22",  # olive
    4: "#2ca02c",  # green
    5: "#1f77b4",  # blue (high conviction)
}

_STATUS_COLOR: Final[dict[str, str]] = {
    "pending": "#9e9e9e",
    "closed": "#2ca02c",
    "failed": "#d62728",
    "announced": "#9e9e9e",
    "open": "#9e9e9e",
    "lapsed": "#d62728",
    "withdrawn": "#d62728",
    "cleared": "#1f77b4",
}

_DECISION_COLOR: Final[dict[str, str]] = {
    "enter": "#2ca02c",
    "wait": "#ff7f0e",
    "skip": "#d62728",
}


def format_stars(stars: int | None) -> str:
    """Return a 5-char visual badge like ★★★★☆. None → ☆☆☆☆☆."""
    if stars is None or stars < 0:
        return _STAR_EMPTY * 5
    s = max(0, min(int(stars), 5))
    return _STAR_FILLED * s + _STAR_EMPTY * (5 - s)


def score_color(stars: int | None) -> str:
    """CSS hex color for the star tier; neutral grey when unknown."""
    if stars is None:
        return "#9e9e9e"
    return _STAR_COLOR.get(int(stars), "#9e9e9e")


def status_badge(status: str | None, completion_label: int | None = None) -> str:
    """Return an HTML span for the cluster status.

    Prefers the resolved `completion_label` (closed/failed) over the
    raw `deals.status` value when the operator has labelled it.
    """
    if completion_label is not None:
        label_text = "closed" if completion_label == 1 else "failed"
        color = _STATUS_COLOR[label_text]
        return _span(label_text, color)
    text = (status or "pending").lower()
    color = _STATUS_COLOR.get(text, "#9e9e9e")
    return _span(text, color)


def decision_badge(decision: str | None) -> str:
    text = (decision or "skip").lower()
    color = _DECISION_COLOR.get(text, "#9e9e9e")
    return _span(text, color)


def _span(text: str, color: str) -> str:
    return (
        f'<span style="background:{color};color:white;padding:2px 8px;'
        f'border-radius:8px;font-size:0.85em;font-weight:600;">{text}</span>'
    )
