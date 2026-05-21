# Phase 7 — Streamlit dashboard wireframes

**Status:** Step 0 deliverable. **Awaiting user validation before coding** (per brief Step 0 mandatory checkpoint).

**Stack:** Streamlit ≥1.31 single-file (`streamlit_app.py`), Plotly ≥5.18, optional `streamlit-aggrid` (only if `st.dataframe` filtering proves insufficient).

**Data source:** Read-only against the live `ede` DB (alembic head = 0010, 329 scored clusters, 222 labelled deals, 7 negatives).

**Navigation:** left sidebar with 5 entries + a global filter panel. Each page is one function in `streamlit_app.py`; data access in `src/dashboard/data.py` (testable, no Streamlit imports there).

---

## Sidebar (global, always visible)

```
┌────────────────────────────┐
│  EDE Platform — Dashboard  │
│  v0.7.0 (Phase 7 MVP)      │
├────────────────────────────┤
│                            │
│  ▣ 🏠 Overview             │
│  ▢ 📋 Deals List           │
│  ▢ 🔍 Deal Detail          │
│  ▢ 📊 Analytics            │
│  ▢ 💼 Paper Portfolio      │
│                            │
├────────────────────────────┤
│  ── Global filters ──      │
│                            │
│  Jurisdiction              │
│  [ All  FR  IT  DE ]       │
│                            │
│  Score ★                   │
│  ☑ 5★  ☑ 4★  ☑ 3★          │
│  ☐ 2★  ☐ 1★                │
│                            │
│  Status                    │
│  [ All ▾ ]                 │
│   • pending                │
│   • closed (label=1)       │
│   • failed  (label=0)      │
│                            │
│  Announcement date         │
│  From: [2024-05-20 📅]      │
│  To  : [2026-05-20 📅]      │
│                            │
│  Acquirer type             │
│  [ All ▾ ]                 │
│   • corporate              │
│   • pe                     │
│   • family                 │
│   • soe                    │
│   • unknown                │
│                            │
│  Deal type (multi)         │
│  [ ✕ opa ] [ ✕ opa_simpl ] │
│  [ + Add deal type ]       │
│                            │
├────────────────────────────┤
│  alembic_version: 0010     │
│  model_version:            │
│   scoring_v1_20260520T...  │
│  Last refresh: 14:42 UTC   │
│  [ ↻ Refresh data ]        │
└────────────────────────────┘
```

**Filter behavior:** filters are persisted in `st.session_state` and apply to **every** page that has rows / charts. The Overview KPIs and the Deals List table both react to the same filter selection.

**Cache contract:** `data.py` functions accept the filter dict as arg, `@st.cache_data(ttl=300)`. Pressing **↻ Refresh data** calls `st.cache_data.clear()`.

---

## Page 1 — 🏠 Overview

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│  🏠 Overview                                                              [filtered: 187/329] │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐    │
│  │ Total tracked    │  │ Active pipeline  │  │ Avg p_completion │  │ Coverage by jur. │    │
│  │                  │  │                  │  │                  │  │                  │    │
│  │     329          │  │     187          │  │     0.84         │  │ FR 72 IT 47 DE 42│    │
│  │   clusters       │  │ filtered now     │  │ over filtered    │  │ +collapsed FR    │    │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  └──────────────────┘    │
│                                                                                              │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                              │
│  Heat-map — jurisdiction × score★ (count of clusters)                                        │
│                                                                                              │
│                ┌──────┬──────┬──────┬──────┬──────┐                                          │
│   FR  (240)    │      │  4   │ 12   │ 41   │ 183  │   (1★)(2★)(3★)(4★)(5★)                  │
│                ├──────┼──────┼──────┼──────┼──────┤                                          │
│   IT  (47)     │      │ 11   │      │ 13   │  23  │                                          │
│                ├──────┼──────┼──────┼──────┼──────┤                                          │
│   DE  (42)     │      │  4   │  2   │ 33   │   3  │                                          │
│                └──────┴──────┴──────┴──────┴──────┘                                          │
│                                                                                              │
│  (Plotly imshow, viridis colorscale, hover = count)                                          │
│                                                                                              │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                              │
│  ┌─ 🌟 Top 5 high-conviction (p≥0.85, status=pending) ─┐                                     │
│  │                                                      │                                     │
│  │  ★★★★★  COMMERZBANK / UniCredit         p=1.00  →   │                                     │
│  │  ★★★★★  Klöckner & Co / Worthington     p=1.00  →   │                                     │
│  │  ★★★★★  Eles Semiconductor / Mare       p=1.00  →   │                                     │
│  │  ★★★★★  Ferretti / Azur                 p=1.00  →   │                                     │
│  │  ★★★★★  Banca Sistema / CF+             p=1.00  →   │                                     │
│  │                                                      │                                     │
│  └──────────────────────────────────────────────────────┘                                     │
│                                                                                              │
│  ┌─ ⚠️ Top 5 watchlist (p≤0.6 or candidate_failure_flag=Y, pending) ──┐                      │
│  │                                                                     │                      │
│  │  ★★★      Banco BPM / [pending parse]       p=0.56  flag:Y     →  │                      │
│  │  ★★       ZODIAC AEROSPACE / ?              p=0.43  flag:Y     →  │                      │
│  │  ★★       BALYO / SoftBank Silver Bands     p=0.43             →  │                      │
│  │  ★★       OVH GROUPE / Klaba                p=0.43             →  │                      │
│  │  ★★       VOYAGEURS DU MONDE / family       p=0.43             →  │                      │
│  │                                                                     │                      │
│  └─────────────────────────────────────────────────────────────────────┘                      │
│                                                                                              │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                              │
│  📅 Recent activity (announcement_date last 7 days)                                          │
│                                                                                              │
│   2026-05-19  POULAILLON (FR opa_simplifiee)     [score pending]                             │
│   2026-05-18  FNAC DARTY (FR opa)                ★★★★★ p=1.00                                │
│   2026-05-12  ...                                                                            │
│                                                                                              │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```

**Implementation notes:**
- `→` is a clickable button (`st.button` keyed by cluster_id) that sets `st.session_state.selected_cluster = cluster_id` and switches the sidebar radio to "🔍 Deal Detail".
- Heat-map cells: empty cell (no data) renders as blank, not 0.
- Top-5 lists honor the sidebar filter (so flipping FR off hides FR rows from the Top 5).

---

## Page 2 — 📋 Deals List

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│  📋 Deals List                                              [filtered: 187/329] [⬇ Export]   │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                              │
│ ┌──────────┬───────┬─────────────────────────┬──────────────────┬───────────┬──────────┬──┐ │
│ │ cluster  │ jur ▾ │ target                ▾ │ acquirer       ▾ │ deal_type │ ann.dt ▾ │..│ │
│ ├──────────┼───────┼─────────────────────────┼──────────────────┼───────────┼──────────┼──┤ │
│ │ 348      │  DE   │ COMMERZBANK AG          │ UniCredit S.p.A  │ uebern.   │ 26-05-05 │..│ │
│ │ 326      │  IT   │ Banca Sistema Spa       │ Banca CF+        │ opas      │ 26-05-11 │..│ │
│ │ 14_4     │  FR   │ FNAC DARTY              │ Kretinsky        │ opa       │ 26-05-12 │..│ │
│ │ 1034     │  IT   │ Banco BPM Spa           │ [pending parse]  │ opas      │ 25-04-28 │..│ │
│ │ ...      │       │                         │                  │           │          │..│ │
│ └──────────┴───────┴─────────────────────────┴──────────────────┴───────────┴──────────┴──┘ │
│   (table continues — Streamlit's native st.dataframe with sortable columns)                  │
│                                                                                              │
│ Extra columns (scroll right):                                                                │
│ │ events │  ★ │ p     │ status   │ label │ acquirer_type │ spread (Φ) │ source_url │ ⚙ │   │
│ │   1    │ 5  │ 1.000 │ pending  │   —   │ corporate     │ —          │ bafin.de…  │ ▶ │   │
│ │   1    │ 5  │ 1.000 │ pending  │   —   │ corporate     │ —          │ consob.it… │ ▶ │   │
│ │   4    │ 5  │ 1.000 │ pending  │   —   │ pe            │ —          │ bdif.amf…  │ ▶ │   │
│ │   1    │ 3  │ 0.558 │ failed   │   0   │ unknown       │ —          │ consob.it… │ ▶ │   │
│                                                                                              │
│  Φ = spread column is a Phase-9 placeholder (live cours data not ingested in V1).            │
│  ▶ = drill-down button → opens 🔍 Deal Detail with this cluster preselected.                 │
│                                                                                              │
│  [ ⬇ Export filtered CSV (187 rows) ]   [ ↻ Refresh data ]                                   │
│                                                                                              │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```

**Implementation notes:**
- Built on `st.dataframe` (native sort/filter on the column headers). `streamlit-aggrid` is a fallback only if a feature breaks (e.g., multi-column sort) — not bundled by default to keep deps thin.
- The `cluster` ID column shows the FR-collapsed multi-id string (`13_10_3_2`) when applicable — first ID only as link, full string in tooltip.
- Star column uses a Unicode rendering (★★★★☆) not numeric to keep the table scan-friendly.
- Status badge color: pending = grey, closed (label=1) = green, failed (label=0) = red.
- Export CSV uses `st.download_button` with the **filtered** result set, not the full DB.

---

## Page 3 — 🔍 Deal Detail

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│  🔍 Deal Detail                                                       [← back to Deals List] │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────────────────────┐    │
│  │                                                                                       │   │
│  │    ★★★★★    p_completion = 1.000           decision: enter        status: pending     │   │
│  │                                                                                       │   │
│  │   COMMERZBANK Aktiengesellschaft  ←  UniCredit S.p.A                                  │   │
│  │   ISIN DE000CBK1001 · BAFIN-DE000CBK1001-20260505 · Übernahmeangebot · 2026-05-05     │   │
│  │                                                                                       │   │
│  └──────────────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                              │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                              │
│  ── Scoring (model: scoring_v1_20260520T141111Z) ──                                          │
│                                                                                              │
│   ┌─ ✅ Top 3 positive factors ────────┐   ┌─ ⚠ Top 3 risk factors ────────────┐            │
│   │                                     │   │                                    │            │
│   │  + deal_type=opa             +1.35  │   │  - acquirer_type=family    -1.98   │            │
│   │  + events_count              +1.03  │   │  - deal_type=opra          -1.68   │            │
│   │  + payment_type=cash         +0.93  │   │  - jurisdiction=FR         -1.40   │            │
│   │                                     │   │                                    │            │
│   └─────────────────────────────────────┘   └────────────────────────────────────┘            │
│                                                                                              │
│   ▾ Features snapshot (raw, click to expand)                                                 │
│      { bid_premium_pct: null, events_count: 1, deal_type: 'opa_volontaire_totalitaria', ...} │
│                                                                                              │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                              │
│  ── Identity ──                                                                              │
│                                                                                              │
│   Target           │ COMMERZBANK Aktiengesellschaft                                          │
│   Acquirer (Bieter)│ UniCredit S.p.A                                                         │
│   ISIN             │ DE000CBK1001                                                            │
│   Jurisdiction     │ DE                                                                      │
│   Regulator ref    │ BAFIN-DE000CBK1001-20260505                                             │
│   Deal type        │ opa_volontaire_totalitaria (raw: Übernahmeangebot)                      │
│   Status           │ pending                                                                 │
│   Announce date    │ 2026-05-05                                                              │
│   Expected close   │ —                                                                       │
│   Offer price      │ EUR 1.00 (placeholder — parser non-extracted)                           │
│                                                                                              │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                              │
│  ── Events timeline (1 row) ──                                                               │
│                                                                                              │
│   ●  2026-05-05  filing_bafin   "BaFin Angebotsunterlage — Bieter: UniCredit S.p.A,         │
│                                  Zielgesellschaft: COMMERZBANK AG (ref BAFIN-…)"             │
│                                  source: bafin_angebotsunterlagen   has_document: ✓          │
│                                                                                              │
│   (Plotly timeline; rendered as ordered list for cluster with 1 event)                       │
│                                                                                              │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                              │
│  ── Documents ──                                                                             │
│                                                                                              │
│   📄 Angebotsunterlage PDF                                                                   │
│       https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/commerzbank.pdf?…       │
│       Local: data/pdfs/de/2026/BAFIN-DE000CBK1001-20260505.pdf  (3,255,699 bytes)            │
│                                                                                              │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                              │
│  ── Manual override / notes ──                                                               │
│                                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────────────────┐       │
│   │ [text area: free-form notes for this cluster, saved on every keystroke debounce] │       │
│   │                                                                                  │       │
│   │                                                                                  │       │
│   └──────────────────────────────────────────────────────────────────────────────────┘       │
│                                                                                              │
│   Stored in: data/notes/348.json   (gitignored)   [💾 saved at 14:32 UTC]                   │
│                                                                                              │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```

**Implementation notes:**
- Selected cluster is read from `st.session_state.selected_cluster` (set by Top-5 or Deals List drill-down) or query-param `?cluster_id=X`.
- The "raw features" expander uses `st.json` for syntax highlighting.
- The notes textarea writes to `data/notes/{cluster_id}.json` via `st.text_area(... on_change=...)` with a 1-second debounce timer to avoid IO per keystroke.
- For multi-id clusters (FR), the Identity section adds a "Sub-filings" expander listing all `(deal_id, regulator_ref, deal_type, announcement_date)` rows.

---

## Page 4 — 📊 Analytics

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│  📊 Analytics                                                         [filtered: 187/329]    │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                              │
│  ── Distribution of p_completion (filtered) ──                                               │
│                                                                                              │
│   count                                                                                      │
│    220 ┤                                                                       ██  221       │
│    180 ┤                                                                       ██            │
│    140 ┤                                                                       ██            │
│    100 ┤                                                                       ██            │
│     60 ┤                                                       ██              ██            │
│     20 ┤                              ██  19              ██   ██   87         ██            │
│      0 ┴─────────────────────────────█████─────────█████─█████─█████──█████─────             │
│           [1★ <0.3] [2★ 0.3-0.5] [3★ 0.5-0.7] [4★ 0.7-0.85] [5★ ≥0.85]                       │
│                                                                                              │
│   Color: stacked by jurisdiction (FR=blue, IT=green, DE=orange)                              │
│                                                                                              │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                              │
│  ── Calibration plot (in-sample on full training set) ──                                     │
│                                                                                              │
│   Empirical                                                                                  │
│     rate                                                                                     │
│      1.0 ┤                                                  ● 103                            │
│          │                                              ╱                                    │
│      0.8 ┤                                  ● 18    ╱                                        │
│          │                                       ╱                                           │
│      0.6 ┤                              ╱                                                    │
│          │                          ╱                                                        │
│      0.4 ┤              ● 7    ╱                                                             │
│          │              ╱                                                                    │
│      0.2 ┤          ╱                                                                        │
│          │      ╱                                                                            │
│      0.0 ┴──╱──────────────────────────────────────────────                                  │
│            0    0.2     0.4     0.6     0.8     1.0   Predicted-prob bin (mid)               │
│                                                                                              │
│   Diagonal line = perfect calibration. Dots sized by n in each bin.                          │
│                                                                                              │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                              │
│  ── Feature importance (full-data refit coefficients) ──                                     │
│                                                                                              │
│   acquirer_type=family   ████████████████████████░░░░░░░  -1.98                              │
│   deal_type=opra         ██████████████████████░░░░░░░░░  -1.68                              │
│   jurisdiction=FR        ██████████████████░░░░░░░░░░░░░  -1.40                              │
│   deal_type=opa          ████████████████████░░░░░░░░░░░  +1.35                              │
│   events_count           ██████████████░░░░░░░░░░░░░░░░░  +1.03                              │
│   payment_type=cash      ████████████░░░░░░░░░░░░░░░░░░░  +0.93                              │
│   acquirer_type=corp.    ██████████░░░░░░░░░░░░░░░░░░░░░  +0.77                              │
│   ...                                                                                        │
│                                                                                              │
│   Bar color: green if positive (favors label=1), red if negative.                            │
│                                                                                              │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                              │
│  ── Pipeline timeline (deals announced per month, filtered) ──                               │
│                                                                                              │
│    Scored clusters / month                                                                   │
│      40 ┤                                                              ██     ██             │
│      30 ┤                                                ██            ██  ██ ██             │
│      20 ┤                              ██   ██   ██   ██  ██ ██ ██ ██  ██  ██ ██  ██         │
│      10 ┤  ██  ██  ██  ██  ██  ██   ██ ██   ██   ██   ██  ██ ██ ██ ██  ██  ██ ██  ██         │
│       0 ┴────────────────────────────────────────────────────────────────────────────        │
│           2024-06          2024-12         2025-06         2025-12     2026-05               │
│                                                                                              │
│   Click a bar to filter all other charts on that month.                                      │
│                                                                                              │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                              │
│  ── Class balance (training set) ──                                                          │
│                                                                                              │
│            label=1 (closed)          label=0 (failed)         label=NULL (pending)           │
│            ████████████████████ 121   ███ 7                   █████████████ 201              │
│                                                                                              │
│   pie chart (Plotly), 17:1 imbalance flagged in caption.                                     │
│                                                                                              │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```

**Implementation notes:**
- All charts respect the global sidebar filter (so flipping a jurisdiction off restacks the histogram).
- Calibration plot uses the 3 populated deciles from `artifacts/phase-06/validation_report.md` (read at startup, refreshed if `artifacts/phase-06/scoring_run_latest.json` mtime changes).
- Coefficients are read from `models/scoring_v1_*.pkl` via `ScoringModel.load(path).inner_clf.coef_[0]` (no DB hit).

---

## Page 5 — 💼 Paper Portfolio (preview)

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│  💼 Paper Portfolio (preview)                                                                │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                              │
│   ┌────────────────────────────────────────────────────────────────────────────────────┐     │
│   │ 🚧  PREVIEW — Phase 8 IBKR connection not yet wired                                 │     │
│   │     The numbers below are mock data for UX validation only.                         │     │
│   │     Real positions + P&L land in Phase 8 after paper trading engine ships.          │     │
│   └────────────────────────────────────────────────────────────────────────────────────┘     │
│                                                                                              │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                              │
│   ── Mock positions (3 deals @ 5★ from the live scoring) ──                                  │
│                                                                                              │
│   ┌─────────────────┬──────┬────────┬───────────┬────────────┬───────────┬─────────────┐    │
│   │ Target          │ Jur  │ Stars  │ Size €    │ Entry €    │ Now €     │ P&L €  (%)  │    │
│   ├─────────────────┼──────┼────────┼───────────┼────────────┼───────────┼─────────────┤    │
│   │ COMMERZBANK     │ DE   │ ★★★★★ │  10 000   │   12.45    │   12.78   │  +265 (+2.7%)│    │
│   │ MorphoSys (cls.)│ DE   │ ★★★★★ │   8 000   │   65.50    │   68.00   │  +305 (+3.8%)│    │
│   │ Mediobanca      │ IT   │ ★★★★★ │  12 000   │   15.20    │   15.08   │   -94 (-0.8%)│    │
│   └─────────────────┴──────┴────────┴───────────┴────────────┴───────────┴─────────────┘    │
│                                                                                              │
│   Aggregate: total deployed € 30 000 | Open P&L € +476 (+1.6%)                              │
│                                                                                              │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                              │
│   ── Mock risk metrics (placeholders) ──                                                     │
│                                                                                              │
│     Sharpe ratio (mock)   1.42                                                               │
│     Sortino ratio (mock)  1.78                                                               │
│     Max drawdown (mock)  -2.1 %                                                              │
│     Hit rate (mock)       0.67 (4/6 last positions)                                          │
│                                                                                              │
│   All numbers above are simulated; Phase 8 will compute them from real IBKR fills.           │
│                                                                                              │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                              │
│   ── Watchlist (deals not in portfolio but flagged for entry trigger) ──                     │
│                                                                                              │
│     ★★★★★  Klöckner & Co SE      / Worthington Steel       p=1.00  spread=Φ                  │
│     ★★★★★  PSI Software SE       / Zest Bidco              p=1.00  spread=Φ                  │
│     ★★★★★  CECONOMY AG           / JD.com                  p=1.00  spread=Φ                  │
│     ★★★★★  ABOUT YOU Holding     / Zalando                 p=1.00  spread=Φ                  │
│     ★★★★★  ENCAVIS AG (closed)   / KKR Elbe BidCo          p=1.00  spread=Φ                  │
│                                                                                              │
│     Φ = spread placeholder, live cours data lands phase 9                                    │
│                                                                                              │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```

**Implementation notes:**
- Mock positions come from `src/dashboard/paper_portfolio_mock.py`: hardcoded 3 entries pulled from the live `scores` table (`p_completion ≥ 0.95`, decision='enter'), with `entry_price` set to `deals.offer_price * (1 - 0.05)` if available else `100.0`, `now_price` = entry × random(-0.03, +0.04). 100 % deterministic via a fixed seed so the page is stable across reloads.
- Banner uses Streamlit's `st.warning` with the 🚧 emoji.
- All "PREVIEW" / "mock" terms appear at least 4 times on the page so a reviewer cannot mistake them for real positions.

---

## Navigation flow

```
        ┌─────────────┐
        │  🏠 Overview │
        └──┬──────┬───┘
           │      │ Top-5 click
           │      ▼
           │   ┌──────────────────┐
           │   │ 🔍 Deal Detail   │◄──────────┐
           │   └──────────────────┘           │
           │                                  │ row → drill-down
           │                                  │
           ▼                                  │
       ┌────────────┐    filter             ┌─────────────────┐
       │📋 Deals    │◄─────────────────────►│ sidebar filters │
       │   List     │                       │ (global state)  │
       └────────────┘                       └─────────────────┘
           │                                  ▲
           ▼                                  │
       ┌────────────┐                         │
       │📊 Analytics│◄────────────────────────┘
       └────────────┘
           │
           ▼
       ┌──────────────────────────────┐
       │💼 Paper Portfolio (preview)  │
       └──────────────────────────────┘
```

- Filter state lives in `st.session_state.filters` (a single dict). Each page reads and writes the same dict.
- `selected_cluster` is a separate `st.session_state` key. Setting it + flipping the sidebar radio to "🔍 Deal Detail" is the universal drill-down pattern.
- "← back to Deals List" on Deal Detail is a button that flips the sidebar radio back, preserves filters, scrolls to last position.

---

## Filter spec (what each page consumes)

| Filter | Type | Default | Used by |
|---|---|---|---|
| Jurisdiction | `Literal["all", "FR", "IT", "DE"]` | `all` | All 5 pages |
| Score ★ | `set[int]` 1..5 | `{3, 4, 5}` | Overview / Deals List / Analytics |
| Status | `Literal["all", "pending", "closed", "failed"]` | `all` | Overview / Deals List / Paper Portfolio (watchlist) |
| Announcement date range | `tuple[date, date]` | `(today−730d, today)` | Overview / Deals List / Analytics |
| Acquirer type | `set[str]` (5 values + `all`) | `all` | Deals List / Analytics |
| Deal type | `set[str]` (18 values) | `all` | Deals List / Analytics |

The Overview KPI cards always show the **filtered count / total** so the user knows what's hidden.

---

## Data-layer surface (testable, no Streamlit imports)

```python
# src/dashboard/data.py

@dataclass(frozen=True)
class DealsFilters:
    jurisdictions: tuple[str, ...] | None = None       # None = all
    stars: tuple[int, ...] | None = None
    status: str = "all"                                  # all|pending|closed|failed
    date_from: date | None = None
    date_to: date | None = None
    acquirer_types: tuple[str, ...] | None = None
    deal_types: tuple[str, ...] | None = None

async def get_all_clusters(filters: DealsFilters) -> pd.DataFrame: ...
async def get_cluster_detail(cluster_id: str) -> dict[str, Any]: ...
async def get_score_for_cluster(cluster_id: str) -> dict[str, Any]: ...
async def get_events_for_cluster(cluster_id: str) -> list[dict[str, Any]]: ...
async def get_calibration_data() -> pd.DataFrame: ...
async def get_pipeline_timeline(filters: DealsFilters) -> pd.DataFrame: ...
async def get_feature_importance(model_path: Path) -> pd.DataFrame: ...
```

Streamlit caches wrap these in `streamlit_app.py`:

```python
@st.cache_data(ttl=300)
def _cached_get_all_clusters(filters_key: str) -> pd.DataFrame:
    return asyncio.run(data.get_all_clusters(_decode_filters(filters_key)))
```

Filter encoding via a stable JSON string so `st.cache_data` keying is reliable.

---

## What's deliberately out of scope (Phase 8+)

- **No live IBKR connection.** Paper Portfolio is mock — banner makes this loud.
- **No live cours / spread / premium.** `spread` column on Deals List shows `Φ` placeholder; Phase 9 will fill via Stooq/IBKR.
- **No re-training of the scoring model.** Reads `models/scoring_v1_*.pkl` only.
- **No PDF text NLP.** PDF link shown, content not parsed beyond what Phase 6 stored.
- **No write-back to `deals.completion_label`** from the dashboard. Operator labelling stays a CSV → import pipeline (Phase 6 tooling).
- **No multi-user, no auth.** Streamlit single-user local-only for V1.

---

## STOP — awaiting validation before coding Steps 1-10

Per brief: *"Stop après Step 0 wireframes. Wait for user validation avant coder."*

Three things would change the implementation cost meaningfully if you flip them:

1. **`streamlit-aggrid` yes/no?** Brief says optional. Default = no (st.dataframe is enough). If you want column-wise filter chips on the Deals List header, AgGrid is +1 dependency + ~30 min.
2. **Notes persistence path** — currently `data/notes/{cluster_id}.json` (gitignored). Alternative: new table `cluster_notes` (migration 0011) so notes survive a fresh checkout. Recommended for V2; V1 stays local files.
3. **Paper Portfolio mock realism** — currently 3 hardcoded entries based on top-5★ deals. Want anything richer (CSV import, fake transactions log) ?

Reply **VALIDATE Step 0** and I enchaîne Steps 1-10.
