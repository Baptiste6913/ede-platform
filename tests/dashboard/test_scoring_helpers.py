"""Unit tests for src.dashboard.scoring_helpers — pure formatting helpers."""

from __future__ import annotations

import pytest

from src.dashboard.scoring_helpers import (
    decision_badge,
    format_stars,
    score_color,
    status_badge,
)


@pytest.mark.parametrize(
    ("stars", "expected"),
    [
        (0, "☆☆☆☆☆"),
        (1, "★☆☆☆☆"),
        (3, "★★★☆☆"),
        (5, "★★★★★"),
        (None, "☆☆☆☆☆"),
        (-2, "☆☆☆☆☆"),
        (99, "★★★★★"),
    ],
)
def test_format_stars(stars: int | None, expected: str) -> None:
    assert format_stars(stars) == expected


def test_score_color_returns_hex_per_tier() -> None:
    for s in [1, 2, 3, 4, 5]:
        out = score_color(s)
        assert out.startswith("#")
        assert len(out) == 7


def test_score_color_neutral_grey_for_none() -> None:
    assert score_color(None) == "#9e9e9e"


def test_status_badge_label_overrides_raw_status() -> None:
    html_closed = status_badge("announced", completion_label=1)
    assert ">closed<" in html_closed
    html_failed = status_badge("announced", completion_label=0)
    assert ">failed<" in html_failed
    html_pending = status_badge("announced", completion_label=None)
    assert ">announced<" in html_pending


def test_status_badge_handles_unknown_raw_status() -> None:
    html = status_badge("brand_new_status", completion_label=None)
    assert "brand_new_status" in html
    # Falls back to neutral grey
    assert "#9e9e9e" in html


@pytest.mark.parametrize(
    ("decision", "expected_color_token"),
    [("enter", "#2ca02c"), ("wait", "#ff7f0e"), ("skip", "#d62728")],
)
def test_decision_badge(decision: str, expected_color_token: str) -> None:
    html = decision_badge(decision)
    assert f">{decision}<" in html
    assert expected_color_token in html


def test_decision_badge_unknown_defaults_to_skip() -> None:
    html = decision_badge(None)
    assert ">skip<" in html
