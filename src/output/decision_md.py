"""Actionable decision surface (Phase 13) — one Markdown file per decision.

The trading cycle produces a complete decision (entry / stop / take-profit /
sizing / rationale) for every tradable deal, independent of IBKR execution. This
module renders that decision as a human-readable Markdown file the operator reads
*before* placing the order manually, and maintains a cumulative ``INDEX.md``.

Pure renderers (``render_decision_md`` / ``render_index``) take a
:class:`TradeRequest` (trade params + score) and the ORM ``Deal`` (ISIN, tickers,
premium, source). Every Deal-side field is optional: a DE deal with no premium
renders ``N/A`` rather than crashing. :class:`MarkdownDecisionSink` is the
side-effecting adapter the scheduler calls per decision.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

import structlog

if TYPE_CHECKING:
    from src.trading.decision_engine import TradeRequest


class DecisionSink(Protocol):
    """Consumes a produced decision (write MD, notify, …) per cycle."""

    async def emit(self, req: TradeRequest, deal: Any) -> None: ...


log = structlog.get_logger()

_REPO_ROOT = Path(__file__).resolve().parents[2]
DECISIONS_DIR: Path = _REPO_ROOT / "artifacts" / "decisions"
INDEX_NAME = "INDEX.md"

_INDEX_HEADER = (
    "| Date | Cible | Jur. | Ticker IBKR | Entry € | Stop € | Score | Premium | Fichier |"
)
_INDEX_SEP = "|---|---|---|---|---:|---:|---:|---:|---|"
_INDEX_MIN_CELLS = 9  # Date..Fichier — a valid data row has at least this many


def _slug(name: str, *, maxlen: int = 40) -> str:
    """Filesystem-safe lowercase slug ('Covivio Hotels' → 'covivio-hotels')."""
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s[:maxlen].strip("-") or "deal"


def _g(obj: Any, attr: str) -> Any:
    """Attribute or None (Deal fields are all optional for rendering)."""
    return getattr(obj, attr, None)


def _money(value: Any) -> str:
    return f"{float(value):,.2f}" if value is not None else "N/A"


def _pct_from_fraction(value: Any) -> str:
    return f"{float(value) * 100:.1f}%" if value is not None else "N/A"


def _isin_of(deal: Any) -> str:
    return _g(deal, "ticker_target") or "N/A"


def _strategy_label(deal: Any) -> str:
    deal_type = _g(deal, "deal_type") or "opa"
    cash_share = _g(deal, "payment_cash_share")
    if cash_share is None or float(cash_share) >= 1.0:
        mix = "cash"
    elif float(cash_share) <= 0.0:
        mix = "échange d'actions"
    else:
        mix = "mixte cash/actions"
    return f"Merger arb — offre {mix} ({deal_type}), attente complétion"


def decision_filename(deal: Any, today: date) -> str:
    """``{YYYY-MM-DD}_{ISIN}_{target_slug}.md`` — stable per deal per day."""
    isin = _isin_of(deal).replace("/", "-")
    return f"{today.isoformat()}_{isin}_{_slug(_g(deal, 'target_name') or 'deal')}.md"


def decision_view(req: TradeRequest, deal: Any, *, today: date) -> dict[str, str]:
    """Formatted decision fields — the single source of truth shared by the MD
    renderer and the Discord embed (guarantees identical numbers across both)."""
    ibkr = _g(deal, "ibkr_ticker")
    ibkr_exch = _g(deal, "ibkr_exchange")
    ticker_ibkr = f"{ibkr} @ {ibkr_exch}" if ibkr and ibkr_exch else f"via ISIN {_isin_of(deal)}"
    return {
        "date": today.isoformat(),
        "target": req.deal_target,
        "acquirer": req.deal_acquirer,
        "juridiction": _g(deal, "juridiction") or "N/A",
        "isin": _isin_of(deal),
        "ticker_yf": _g(deal, "trading_ticker_yf") or "N/A",
        "ticker_ibkr": ticker_ibkr,
        "currency": req.currency,
        "entry": _money(req.limit_price),
        "stop": _money(req.stop_loss_price),
        "tp": _money(req.take_profit_price),
        "qty": str(req.quantity),
        "notional": _money(req.quantity * req.limit_price),
        "pct_capital": f"{req.position_pct * 100:.1f}%",
        "strategy": _strategy_label(deal),
        "score": f"{req.score_stars}/5",
        "proba": f"{req.expected_p_completion:.0%}",
        "premium": _pct_from_fraction(_g(deal, "premium_pct")),
        "offer": _money(_g(deal, "offer_price")),
        "reference": _money(_g(deal, "reference_price_at_announcement")),
        "deal_type": _g(deal, "deal_type") or "N/A",
        "spread": _pct_from_fraction(req.expected_return_pct),
        "kelly": f"{req.kelly_fractional_pct * 100:.1f}%",
        "filing": _g(deal, "regulator_ref") or "N/A",
        "link": _g(deal, "source_url") or "N/A",
        "announce": str(_g(deal, "announcement_date") or "N/A"),
        "status": "NOUVELLE DÉCISION"
        + ("  (validation ramp-up requise)" if req.requires_approval else ""),
        "md_name": decision_filename(deal, today),
    }


def render_decision_md(req: TradeRequest, deal: Any, *, today: date) -> str:
    """Render one decision as Markdown. Missing Deal fields render as N/A."""
    v = decision_view(req, deal, today=today)
    cur = v["currency"]
    return "\n".join(
        [
            f"# Décision — {v['target']}",
            "",
            f"**Date** : {v['date']}",
            f"**Juridiction** : {v['juridiction']}",
            f"**Statut** : {v['status']}",
            "",
            "## Titre",
            f"- Cible : {v['target']}",
            f"- Acquéreur : {v['acquirer']}",
            f"- ISIN : {v['isin']}",
            f"- Ticker (yfinance) : {v['ticker_yf']}   ← pour pricing/lookup",
            f"- Ticker (IBKR) : {v['ticker_ibkr']}   ← pour passer l'ordre",
            "",
            "## Ordre",
            "- Action : ACHAT",
            f"- Entry : {v['entry']} {cur} (limite)",
            f"- Stop : {v['stop']} {cur}",
            f"- Take-profit : {v['tp']} {cur} (prix d'offre)",
            f"- Sizing : {v['qty']} actions (~{v['notional']} {cur}, "
            f"{v['pct_capital']} du capital)",
            "",
            "## Stratégie",
            v["strategy"],
            "",
            "## Rationale (pourquoi)",
            f"- Score complétion : {v['score']} étoiles (p = {v['proba']})",
            f"- Premium offre : {v['premium']} (offre {v['offer']} vs réf {v['reference']})",
            f"- Type de deal : {v['deal_type']}",
            f"- Spread actuel : {v['spread']} → upside si complétion",
            f"- Kelly fractionnel : {v['kelly']}",
            "",
            "## Source",
            f"- Filing : {v['filing']}",
            f"- Lien : {v['link']}",
            f"- Annonce : {v['announce']}",
            "",
            "---",
            "*Décision générée automatiquement. Exécution manuelle par l'opérateur.*",
            "",
        ]
    )


def _index_row(req: TradeRequest, deal: Any, md_name: str, today: date) -> str:
    v = decision_view(req, deal, today=today)
    ibkr = _g(deal, "ibkr_ticker") or "—"
    return (
        f"| {v['date']} | {v['target']} | {_g(deal, 'juridiction') or '—'} "
        f"| {ibkr} | {v['entry']} | {v['stop']} "
        f"| {v['score']} | {v['premium']} "
        f"| [{md_name}]({md_name}) |"
    )


def _parse_index_rows(text: str) -> dict[str, str]:
    """Existing data rows keyed by the file column (last cell) — for upsert."""
    rows: dict[str, str] = {}
    for line in text.splitlines():
        if not line.startswith("|") or line in (_INDEX_HEADER, _INDEX_SEP):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= _INDEX_MIN_CELLS and cells[0] != "Date":
            # Key by the file name inside the link cell ('[name](name)') so the
            # key matches md_path.name on upsert (else rows duplicate).
            link = re.search(r"\(([^)]+)\)", cells[-1])
            rows[link.group(1) if link else cells[-1]] = line
    return rows


def _row_date(row: str) -> str:
    return row.strip().strip("|").split("|")[0].strip()


def render_index(rows: dict[str, str]) -> str:
    """Render INDEX.md from upserted rows, newest date first."""
    ordered = sorted(rows.values(), key=_row_date, reverse=True)
    lines = ["# Décisions EDE — index", "", _INDEX_HEADER, _INDEX_SEP, *ordered, ""]
    return "\n".join(lines)


def write_decision_md(
    req: TradeRequest, deal: Any, *, decisions_dir: Path | None = None, today: date | None = None
) -> Path:
    """Write the decision MD file; return its path."""
    day = today or date.today()
    out_dir = decisions_dir or DECISIONS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / decision_filename(deal, day)
    path.write_text(render_decision_md(req, deal, today=day), encoding="utf-8")
    log.info("decision_md_written", path=str(path), deal_id=req.deal_id)
    return path


def update_decision_index(
    req: TradeRequest,
    deal: Any,
    md_path: Path,
    *,
    decisions_dir: Path | None = None,
    today: date | None = None,
) -> Path:
    """Upsert the decision into INDEX.md (keyed by file name), newest first."""
    day = today or date.today()
    out_dir = decisions_dir or DECISIONS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    index_path = out_dir / INDEX_NAME
    existing = index_path.read_text(encoding="utf-8") if index_path.exists() else ""
    rows = _parse_index_rows(existing)
    rows[md_path.name] = _index_row(req, deal, md_path.name, day)
    index_path.write_text(render_index(rows), encoding="utf-8")
    return index_path


class MarkdownDecisionSink:
    """Side-effecting sink: write the MD file + update the index per decision."""

    def __init__(self, decisions_dir: Path | None = None, today: date | None = None) -> None:
        self._dir = decisions_dir
        self._today = today

    async def emit(self, req: TradeRequest, deal: Any) -> None:
        path = write_decision_md(req, deal, decisions_dir=self._dir, today=self._today)
        update_decision_index(req, deal, path, decisions_dir=self._dir, today=self._today)
