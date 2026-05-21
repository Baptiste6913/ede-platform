"""EDE Platform — Phase 7 Streamlit dashboard MVP.

Launch:

    streamlit run streamlit_app.py

Single-file by design: layout / widgets / callbacks live here, the
data layer + charts / mock paper portfolio live in `src/dashboard/`
(testable without spinning up Streamlit).

See `docs/phase-07/wireframes.md` for the page-by-page layout spec
and `docs/DASHBOARD.md` for operational notes.
"""

from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from src.dashboard import (
    DealsFilters,
    build_calibration_plot,
    build_feature_importance_bar,
    build_pipeline_timeline,
    build_score_distribution,
    decision_badge,
    format_stars,
    get_all_clusters,
    get_calibration_data,
    get_cluster_detail,
    get_events_for_cluster,
    get_feature_importance,
    get_pipeline_timeline,
    score_color,
    status_badge,
)
from src.dashboard.charts import (
    build_class_balance_pie,
    build_jurisdiction_star_heatmap,
)
from src.dashboard.data import (
    get_filter_options,
    get_latest_model_metadata,
    get_live_positions,
    get_rampup_status,
    get_realized_pnl_series,
    get_recent_trades,
    get_trading_kpis,
)

st.set_page_config(
    page_title="EDE Platform Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --------------------------------------------------------------------- caching


@st.cache_data(ttl=300, show_spinner=False)
def _cached_clusters(filters_key: str) -> pd.DataFrame:
    return get_all_clusters(_decode_filters(filters_key))


@st.cache_data(ttl=300, show_spinner=False)
def _cached_detail(cluster_id: int) -> dict[str, Any] | None:
    return get_cluster_detail(cluster_id)


@st.cache_data(ttl=300, show_spinner=False)
def _cached_events(cluster_id: int) -> list[dict[str, Any]]:
    return get_events_for_cluster(cluster_id)


@st.cache_data(ttl=300, show_spinner=False)
def _cached_calibration() -> pd.DataFrame:
    return get_calibration_data()


@st.cache_data(ttl=300, show_spinner=False)
def _cached_pipeline(filters_key: str) -> pd.DataFrame:
    return get_pipeline_timeline(_decode_filters(filters_key))


@st.cache_data(ttl=600, show_spinner=False)
def _cached_feature_importance() -> pd.DataFrame:
    return get_feature_importance()


@st.cache_data(ttl=600, show_spinner=False)
def _cached_filter_options() -> dict[str, Any]:
    return get_filter_options()


@st.cache_data(ttl=600, show_spinner=False)
def _cached_model_metadata() -> dict[str, Any]:
    return get_latest_model_metadata()


@st.cache_data(ttl=60, show_spinner=False)
def _cached_live_positions() -> pd.DataFrame:
    return get_live_positions()


@st.cache_data(ttl=60, show_spinner=False)
def _cached_recent_trades() -> pd.DataFrame:
    return get_recent_trades()


@st.cache_data(ttl=60, show_spinner=False)
def _cached_rampup() -> dict[str, int]:
    return get_rampup_status()


@st.cache_data(ttl=60, show_spinner=False)
def _cached_trading_kpis() -> dict[str, Any]:
    return get_trading_kpis()


@st.cache_data(ttl=60, show_spinner=False)
def _cached_pnl_series() -> pd.DataFrame:
    return get_realized_pnl_series()


# Filter encode/decode is in-process — pickled keys can be unstable
# across reloads so we serialize via JSON.
def _encode_filters(f: DealsFilters) -> str:
    return json.dumps(
        {
            "jurisdictions": list(f.jurisdictions) if f.jurisdictions else None,
            "stars": list(f.stars) if f.stars else None,
            "status": f.status,
            "date_from": f.date_from.isoformat() if f.date_from else None,
            "date_to": f.date_to.isoformat() if f.date_to else None,
            "acquirer_types": list(f.acquirer_types) if f.acquirer_types else None,
            "deal_types": list(f.deal_types) if f.deal_types else None,
        },
        sort_keys=True,
    )


def _decode_filters(key: str) -> DealsFilters:
    payload = json.loads(key)
    return DealsFilters(
        jurisdictions=tuple(payload["jurisdictions"]) if payload["jurisdictions"] else None,
        stars=tuple(payload["stars"]) if payload["stars"] else None,
        status=payload["status"],
        date_from=date.fromisoformat(payload["date_from"]) if payload["date_from"] else None,
        date_to=date.fromisoformat(payload["date_to"]) if payload["date_to"] else None,
        acquirer_types=tuple(payload["acquirer_types"]) if payload["acquirer_types"] else None,
        deal_types=tuple(payload["deal_types"]) if payload["deal_types"] else None,
    )


# --------------------------------------------------------------------- sidebar


def _render_sidebar() -> tuple[str, DealsFilters]:
    st.sidebar.title("EDE Platform")
    st.sidebar.caption("v0.7.0 — Phase 7 MVP")

    page = st.sidebar.radio(
        "Navigation",
        options=[
            "🏠 Overview",
            "📋 Deals List",
            "🔍 Deal Detail",
            "📊 Analytics",
            "💼 Paper Portfolio",
        ],
        key="page",
    )

    st.sidebar.divider()
    st.sidebar.subheader("Global filters")

    opts = _cached_filter_options()
    jurisdictions = st.sidebar.multiselect(
        "Jurisdiction",
        options=opts.get("jurisdictions", []),
        default=opts.get("jurisdictions", []),
    )
    stars = st.sidebar.multiselect(
        "Score ★",
        options=[1, 2, 3, 4, 5],
        default=[3, 4, 5],
        format_func=lambda s: f"{s}★",
    )
    status = st.sidebar.selectbox(
        "Status",
        options=["all", "pending", "closed", "failed"],
        index=0,
    )

    today = date.today()
    date_range = st.sidebar.date_input(
        "Announcement date",
        value=(today - timedelta(days=730), today),
        min_value=date(2010, 1, 1),
        max_value=today,
    )
    if isinstance(date_range, tuple) and len(date_range) == 2:
        date_from, date_to = date_range
    else:
        date_from, date_to = today - timedelta(days=730), today

    acquirer_types = st.sidebar.multiselect(
        "Acquirer type",
        options=opts.get("acquirer_types", []),
        default=opts.get("acquirer_types", []),
    )
    deal_types = st.sidebar.multiselect(
        "Deal type",
        options=opts.get("deal_types", []),
        default=opts.get("deal_types", []),
    )

    st.sidebar.divider()
    md = _cached_model_metadata()
    st.sidebar.caption("**alembic head**: 0010")
    st.sidebar.caption(f"**model**: `{md.get('model_version', '-')}`")
    latest = md.get("latest_run_at")
    if latest:
        latest_str = pd.to_datetime(latest).strftime("%Y-%m-%d %H:%M UTC")
        st.sidebar.caption(f"**latest run**: {latest_str}")

    if st.sidebar.button("↻ Refresh data"):
        st.cache_data.clear()
        st.rerun()

    filters = DealsFilters(
        jurisdictions=tuple(jurisdictions) if jurisdictions else None,
        stars=tuple(stars) if stars else None,
        status=status,
        date_from=date_from,
        date_to=date_to,
        acquirer_types=tuple(acquirer_types) if acquirer_types else None,
        deal_types=tuple(deal_types) if deal_types else None,
    )
    return page, filters


# --------------------------------------------------------------------- pages


def _page_overview(filters: DealsFilters) -> None:
    df_filtered = _cached_clusters(_encode_filters(filters))
    df_all = _cached_clusters(_encode_filters(DealsFilters()))

    st.title("🏠 Overview")
    st.caption(f"Filtered: **{len(df_filtered)}** / Total: **{len(df_all)}** clusters")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total tracked", len(df_all))
    with c2:
        st.metric("Active (filtered)", len(df_filtered))
    with c3:
        avg = float(df_filtered["p_completion"].mean()) if not df_filtered.empty else 0.0
        st.metric("Avg p_completion", f"{avg:.2f}")
    with c4:
        jur_counts = df_filtered["juridiction"].value_counts().to_dict()
        text = " · ".join(f"{k} {v}" for k, v in jur_counts.items()) or "—"
        st.metric("By jurisdiction", text)

    st.divider()
    st.subheader("Heat-map - jurisdiction x score star")
    st.plotly_chart(build_jurisdiction_star_heatmap(df_filtered), use_container_width=True)

    st.divider()
    col_high, col_watch = st.columns(2)
    with col_high:
        st.subheader("🌟 Top 5 high-conviction (p≥0.85, pending)")
        high = df_filtered[
            (df_filtered["p_completion"] >= 0.85) & (df_filtered["completion_label"].isna())
        ].head(5)
        for _, row in high.iterrows():
            _render_quick_row(row)
    with col_watch:
        st.subheader("⚠️ Top 5 watchlist (p≤0.60 or failures pending)")
        watch = df_filtered[df_filtered["p_completion"] <= 0.60].sort_values("p_completion").head(5)
        for _, row in watch.iterrows():
            _render_quick_row(row)

    st.divider()
    st.subheader("📅 Recent activity (last 7 days)")
    cutoff = pd.Timestamp(date.today() - timedelta(days=7))
    recent = df_filtered[pd.to_datetime(df_filtered["announcement_date"]) >= cutoff].head(10)
    if recent.empty:
        st.caption("No deals announced in the last 7 days within current filters.")
    else:
        st.dataframe(
            recent[
                [
                    "announcement_date",
                    "target_name",
                    "juridiction",
                    "deal_type",
                    "score_stars",
                    "p_completion",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )


def _render_quick_row(row: pd.Series) -> None:
    stars = int(row["score_stars"]) if pd.notna(row["score_stars"]) else 0
    color = score_color(stars)
    cluster_id = int(row["cluster_id"])
    label = (
        f"<span style='color:{color}'>{format_stars(stars)}</span> "
        f"**{row['target_name']}** / {row['acquirer_name']}  "
        f"`p={row['p_completion']:.2f}`"
    )
    cols = st.columns([6, 1])
    with cols[0]:
        st.markdown(label, unsafe_allow_html=True)
    with cols[1]:
        if st.button("→", key=f"drill_{cluster_id}_{row['juridiction']}"):
            st.session_state["selected_cluster"] = cluster_id
            st.session_state["_navigate_to"] = "🔍 Deal Detail"
            st.rerun()


def _page_deals_list(filters: DealsFilters) -> None:
    df = _cached_clusters(_encode_filters(filters))
    st.title("📋 Deals List")
    st.caption(f"Showing **{len(df)}** clusters · sort by clicking column headers")

    if df.empty:
        st.warning("No clusters match current filters.")
        return

    # Compact display copy with star unicode + status badge.
    display = df.copy()
    display["★"] = display["score_stars"].apply(format_stars)
    display["status"] = display.apply(
        lambda r: "closed"
        if r["completion_label"] == 1
        else ("failed" if r["completion_label"] == 0 else "pending"),
        axis=1,
    )
    display["spread (Φ)"] = "—"  # Phase 9 placeholder
    display = display[
        [
            "cluster_id",
            "juridiction",
            "target_name",
            "acquirer_name",
            "deal_type",
            "announcement_date",
            "events_count",
            "★",
            "p_completion",
            "status",
            "spread (Φ)",
            "source_url",
        ]
    ]

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "p_completion": st.column_config.NumberColumn("p", format="%.3f"),
            "source_url": st.column_config.LinkColumn("link", display_text="open ↗"),
        },
        height=600,
    )

    csv = display.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇ Export filtered CSV",
        data=csv,
        file_name=f"ede_deals_{date.today().isoformat()}.csv",
        mime="text/csv",
    )

    st.divider()
    st.subheader("Drill-down")
    cluster_options = df["cluster_id"].tolist()
    target_lookup = dict(zip(df["cluster_id"], df["target_name"], strict=True))
    selected = st.selectbox(
        "Select cluster to inspect",
        options=cluster_options,
        format_func=lambda cid: f"{cid} — {target_lookup.get(cid, '?')}",
    )
    if st.button("Open in Deal Detail"):
        st.session_state["selected_cluster"] = int(selected)
        st.session_state["_navigate_to"] = "🔍 Deal Detail"
        st.rerun()


def _page_deal_detail() -> None:
    st.title("🔍 Deal Detail")

    cluster_id = st.session_state.get("selected_cluster")
    if cluster_id is None:
        st.info("No cluster selected. Pick one from the Deals List or Overview.")
        return

    detail = _cached_detail(int(cluster_id))
    if detail is None:
        st.error(f"Cluster {cluster_id} not found.")
        return

    stars = int(detail["score_stars"]) if detail.get("score_stars") is not None else 0
    p = float(detail.get("p_completion") or 0)
    color = score_color(stars)
    target = detail["target_name"]
    acquirer = detail["acquirer_name"]
    st.markdown(
        f"""
        <div style="background:#fafafa;padding:18px;border-radius:8px;border:1px solid #eee;">
          <span style="font-size:2.2em;color:{color};">{format_stars(stars)}</span>
          &nbsp;&nbsp;<b>p_completion = {p:.3f}</b>
          &nbsp;&nbsp;{decision_badge(detail.get("decision"))}
          &nbsp;&nbsp;{status_badge(detail.get("deal_status"), detail.get("completion_label"))}
          <h3 style="margin-top:12px;margin-bottom:4px;">
            {target} &larr; {acquirer}
          </h3>
          <small>
            Jurisdiction <b>{detail['juridiction']}</b>
            · regulator_ref <code>{detail.get('regulator_ref') or '—'}</code>
            · type <code>{detail['deal_type']}</code>
            · announced <b>{detail['announcement_date']}</b>
          </small>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()
    st.subheader("Scoring")
    pos = detail.get("positive_factors") or []
    neg = detail.get("risk_factors") or []
    col_pos, col_neg = st.columns(2)
    with col_pos:
        st.markdown("**✅ Top 3 positive factors**")
        for item in pos[:3]:
            st.markdown(f"- `{item['feature']}` → **+{item['contribution']:.3f}**")
    with col_neg:
        st.markdown("**⚠️ Top 3 risk factors**")
        for item in neg[:3]:
            st.markdown(f"- `{item['feature']}` → **{item['contribution']:.3f}**")

    with st.expander("Features snapshot (raw)"):
        st.json(detail.get("features") or {})

    st.divider()
    st.subheader("Identity")
    id_table = pd.DataFrame(
        [
            ("Target", detail["target_name"]),
            ("Acquirer", detail["acquirer_name"]),
            ("Jurisdiction", detail["juridiction"]),
            ("Deal type", detail["deal_type"]),
            ("Status", detail.get("deal_status")),
            ("Completion label", detail.get("completion_label")),
            ("Announce date", detail["announcement_date"]),
            ("Expected close", detail.get("expected_close_date")),
            ("Model version", detail.get("model_version")),
        ],
        columns=["Field", "Value"],
    )
    st.dataframe(id_table, hide_index=True, use_container_width=True)

    siblings = detail.get("siblings") or []
    if len(siblings) > 1:
        with st.expander(f"Sub-filings in this cluster ({len(siblings)})"):
            st.dataframe(pd.DataFrame(siblings), hide_index=True, use_container_width=True)

    st.divider()
    st.subheader("Events timeline")
    events = _cached_events(int(cluster_id))
    if not events:
        st.caption("No events linked.")
    else:
        for e in events:
            st.markdown(
                f"● **{e['ts']}** — `{e['event_type']}` "
                f"({e.get('deal_type', '?')})  \n"
                f"  {e.get('description') or ''}"
            )

    st.divider()
    st.subheader("Documents")
    docs = [
        (s["regulator_ref"], s.get("source_url"), s.get("pdf_path"))
        for s in siblings
        if s.get("source_url") or s.get("pdf_path")
    ]
    if not docs:
        st.caption("No PDFs linked.")
    for ref, url, path in docs:
        text_parts = [f"📄 `{ref}`"]
        if url:
            text_parts.append(f"[remote]({url})")
        if path:
            text_parts.append(f"local: `{path}`")
        st.markdown(" — ".join(text_parts))

    st.divider()
    st.subheader("Manual notes")
    notes_path = Path("data/notes") / f"{cluster_id}.json"
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    existing = ""
    if notes_path.exists():
        try:
            existing = json.loads(notes_path.read_text(encoding="utf-8")).get("text", "")
        except Exception:
            existing = ""
    new_text = st.text_area(
        "Operator notes (saved locally, not synced to DB)",
        value=existing,
        height=140,
        key=f"notes_{cluster_id}",
    )
    if new_text != existing:
        notes_path.write_text(
            json.dumps({"cluster_id": cluster_id, "text": new_text}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        st.success(f"Saved to `{notes_path}`")


def _page_analytics(filters: DealsFilters) -> None:
    df = _cached_clusters(_encode_filters(filters))
    st.title("📊 Analytics")
    st.caption(f"Filtered: **{len(df)}** clusters")

    st.subheader("Score distribution")
    st.plotly_chart(build_score_distribution(df), use_container_width=True)

    st.subheader("Calibration (in-sample on labelled clusters)")
    cal = _cached_calibration()
    st.plotly_chart(build_calibration_plot(cal), use_container_width=True)
    if cal.empty:
        st.caption("No labelled clusters in current filter scope.")

    st.subheader("Feature importance (full-data refit coefficients)")
    fi = _cached_feature_importance()
    st.plotly_chart(build_feature_importance_bar(fi, top_n=15), use_container_width=True)

    st.subheader("Pipeline timeline")
    pipeline = _cached_pipeline(_encode_filters(filters))
    st.plotly_chart(build_pipeline_timeline(pipeline), use_container_width=True)

    st.subheader("Class balance")
    df_all = _cached_clusters(_encode_filters(DealsFilters()))
    st.plotly_chart(build_class_balance_pie(df_all), use_container_width=True)
    n_pos = int((df_all["completion_label"] == 1).sum())
    n_neg = int((df_all["completion_label"] == 0).sum())
    n_null = int(df_all["completion_label"].isna().sum())
    if n_neg > 0:
        ratio = n_pos / n_neg
        st.caption(
            f"Training labels: **{n_pos} closed / {n_neg} failed / {n_null} pending** "
            f"(imbalance ratio {ratio:.1f}:1)."
        )


def _page_paper_portfolio() -> None:
    st.title("💼 Paper Portfolio")
    st.success(
        "✅ **Phase 8 Live** — positions & trades from the paper trading engine "
        "(IBKR **paper** account, delayed market data). Read-only view of the "
        "`trades` + `paper_positions` tables."
    )

    kpis = _cached_trading_kpis()
    rampup = _cached_rampup()
    positions = _cached_live_positions()
    trades = _cached_recent_trades()
    pnl = _cached_pnl_series()

    validated = int(rampup.get("validated", 0))
    required = int(rampup.get("required", 5))
    if validated < required:
        st.info(
            f"🚦 **Ramp-up active — {validated}/{required} trades validated.** "
            "New trades require manual approval via Discord `approve <trade_id>` "
            "before they are sent to IBKR."
        )
    else:
        st.caption(f"🟢 Ramp-up complete ({validated}/{required}) — auto mode.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Open positions", int(kpis.get("open_positions", 0) or 0))
    c2.metric("Filled trades", int(kpis.get("filled", 0) or 0))
    c3.metric("Submitted (open)", int(kpis.get("submitted", 0) or 0))
    c4.metric("Realised P&L", f"€{float(kpis.get('realized_pnl_eur', 0) or 0):+,.0f}")

    st.divider()
    st.subheader("Open positions")
    if positions.empty:
        st.info("No open positions yet.")
    else:
        st.dataframe(positions, hide_index=True, use_container_width=True)

    st.divider()
    st.subheader("Cumulative realised P&L")
    if pnl.empty:
        st.caption("No closed positions yet.")
    else:
        st.line_chart(pnl.set_index("day")["cumulative"])

    st.divider()
    st.subheader("Recent trades")
    if trades.empty:
        st.info("No trades yet — the daily run (`scripts/run_trading.py`) populates this.")
    else:
        st.dataframe(trades, hide_index=True, use_container_width=True)


# --------------------------------------------------------------------- main


def main() -> None:
    # Cross-page navigation: a button on another page stashes its target in
    # `_navigate_to` and reruns. We apply it here, BEFORE the sidebar radio
    # (key="page") is instantiated — setting a widget's state key after the
    # widget exists raises StreamlitAPIException.
    if "_navigate_to" in st.session_state:
        st.session_state["page"] = st.session_state.pop("_navigate_to")

    page, filters = _render_sidebar()
    if page.startswith("🏠"):
        _page_overview(filters)
    elif page.startswith("📋"):
        _page_deals_list(filters)
    elif page.startswith("🔍"):
        _page_deal_detail()
    elif page.startswith("📊"):
        _page_analytics(filters)
    elif page.startswith("💼"):
        _page_paper_portfolio()
    else:
        st.error(f"Unknown page: {page}")


# Streamlit calls the module top-level on every rerun, so we guard.
if __name__ == "__main__" or os.environ.get("STREAMLIT_RUN") == "1":
    main()
else:
    # When loaded via `streamlit run`, __name__ is not "__main__" but the
    # entry-point is reached top-level. Call main() unconditionally.
    main()
