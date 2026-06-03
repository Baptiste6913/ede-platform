"""P14 Step 2 — score the fresh FR+DE pool with the V1 model (no retrain).

Loads the existing V1 model and scores only the fresh live clusters
(announcement_date >= SINCE, completion_label NULL), one score per cluster
(target+jurisdiction). The cluster score (p_completion, stars) is computed by the
cluster-aware ``score_deal``; it is **persisted on the latest fresh home_venue
deal of the cluster** (current offer price) rather than ``score_deal``'s earliest
representative — so the Step-3 decision is built from the freshest, resolved
filing and is visible to ``load_candidates`` (completion_label NULL + score join).

Idempotent: existing scores for the chosen decision deals are deleted first.

Run:
    $env:DATABASE_URL="postgresql+asyncpg://ede:ede@localhost:5432/ede"
    .venv/Scripts/python.exe scripts/p14_score_fresh.py            # DRY-RUN
    .venv/Scripts/python.exe scripts/p14_score_fresh.py --apply

Output: artifacts/phase-14/scoring_audit.md (tracked).
"""

from __future__ import annotations

import argparse
import asyncio
import math
import sys
from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.core.models import Deal, Score
from src.core.settings import get_settings
from src.scoring.features import extract_cluster_features
from src.scoring.inference import score_deal
from src.scoring.model import ScoringModel

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_MD = REPO_ROOT / "artifacts" / "phase-14" / "scoring_audit.md"
MODEL_PATH = REPO_ROOT / "models" / "scoring_v1_20260526_p91c.pkl"
SINCE = date(2025, 12, 3)
TRADABLE_STARS = 3
OPRA = "opra"  # share buyback — outside the merger-arb thesis


def _jsonable(value: Any) -> Any:
    if isinstance(value, float):
        return None if (math.isnan(value) or math.isinf(value)) else value
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value


async def _process(*, dry_run: bool) -> None:
    settings = get_settings()
    model = ScoringModel.load(MODEL_PATH)
    engine = create_async_engine(settings.database_url, future=True)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    rows: list[dict[str, Any]] = []

    async with sm() as session:
        fresh = list(
            (
                await session.scalars(
                    select(Deal)
                    .where(
                        Deal.juridiction.in_(["FR", "DE"]),
                        Deal.announcement_date >= SINCE,
                        Deal.completion_label.is_(None),
                    )
                    .order_by(Deal.announcement_date.desc())
                )
            ).all()
        )

        # One decision deal per (target, jurisdiction) cluster. Prefer the most
        # tradable filing: home_venue + offer_price present, then home_venue,
        # then offer present, finally newest — so Step 3 builds the decision from
        # a resolved filing carrying a current offer.
        def _rank(d: Deal) -> tuple[int, int, date]:
            return (
                int(d.ticker_resolution_flag == "home_venue"),
                int(d.offer_price is not None),
                d.announcement_date,
            )

        clusters: dict[tuple[str, str], Deal] = {}
        for d in fresh:
            key = (d.target_name, d.juridiction)
            chosen = clusters.get(key)
            if chosen is None or _rank(d) > _rank(chosen):
                clusters[key] = d
        print(f"[P14-score] {len(fresh)} fresh deals -> {len(clusters)} clusters")

        for (target, jur), deal in clusters.items():
            cf = await extract_cluster_features(target, jur, session)
            out = await score_deal(deal.id, model, session)
            if out is None or cf is None:
                rows.append({"target": target, "jur": jur, "status": "no_features"})
                continue
            if not dry_run:
                await session.execute(delete(Score).where(Score.deal_id == deal.id))
                session.add(
                    Score(
                        deal_id=deal.id,
                        p_completion=Decimal(str(out.p_completion)),
                        decision=out.decision,
                        model_version=out.model_version,
                        features=_jsonable(cf.features),
                        score_stars=out.score_stars,
                        risk_factors=_jsonable(out.top_3_risk_factors),
                        positive_factors=_jsonable(out.top_3_positive_factors),
                    )
                )
            rows.append(
                {
                    "target": target,
                    "jur": jur,
                    "ref": deal.regulator_ref,
                    "deal_type": deal.deal_type,
                    "p": out.p_completion,
                    "stars": out.score_stars,
                    "premium_real": not math.isnan(float(cf.features["bid_premium_pct"])),
                    "offer": deal.offer_price is not None,
                    "qflag": deal.offer_price_quality_flag,
                    "status": "scored",
                }
            )

        if dry_run:
            await session.rollback()
        else:
            await session.commit()

    await engine.dispose()
    _write_md(rows, dry_run=dry_run)
    scored = [r for r in rows if r["status"] == "scored"]
    dist = Counter(r["stars"] for r in scored)
    tradable = sum(1 for r in scored if r["stars"] >= TRADABLE_STARS)
    print(f"[P14-score] mode={'DRY-RUN' if dry_run else 'APPLY'} scored={len(scored)}")
    print(f"[P14-score] stars={dict(sorted(dist.items()))} | >=3*: {tradable}")
    print(f"[P14-score] audit -> {OUT_MD}")


def _note(r: dict[str, Any]) -> str:
    notes = []
    if r.get("deal_type") == OPRA:
        notes.append("OPRA rachat (hors merger-arb)")
    if r.get("qflag") == "verified_mixed":
        notes.append("offre titres (pas de scalaire)")
    if not r.get("offer"):
        notes.append("pas d'offer_price")
    return "; ".join(notes) or "-"


def _write_md(rows: list[dict[str, Any]], *, dry_run: bool) -> None:
    scored = [r for r in rows if r["status"] == "scored"]
    dist = Counter(r["stars"] for r in scored)
    ge3 = sum(1 for r in scored if r["stars"] >= TRADABLE_STARS)
    ge4 = sum(1 for r in scored if r["stars"] >= 4)  # noqa: PLR2004
    eq5 = sum(1 for r in scored if r["stars"] == 5)  # noqa: PLR2004

    lines = ["# Phase 14 Step 2 — fresh pool scoring (V1, no retrain)", ""]
    if dry_run:
        lines.append("> DRY-RUN (no DB writes).")
        lines.append("")
    lines.append(f"Model : `{MODEL_PATH.name}` · clusters scored : **{len(scored)}**")
    lines.append("")
    lines.append(f"≥3★ (tradable seuil) : **{ge3}** · ≥4★ : {ge4} · 5★ : {eq5}")
    lines.append("")
    lines.append("## Star distribution")
    lines.append("")
    lines.append("| stars | count |")
    lines.append("|---|---:|")
    for s in sorted(dist):
        lines.append(f"| {s}★ | {dist[s]} |")
    lines.append("")
    lines.append("## Per cluster")
    lines.append("")
    lines.append("| jur | target | ref | deal_type | p | ★ | premium | offer | note |")
    lines.append("|---|---|---|---|---:|---:|---|---|---|")
    for r in sorted(scored, key=lambda x: -x["p"]):
        lines.append(
            f"| {r['jur']} | {r['target'][:24]} | {r['ref']} | {r['deal_type']} "
            f"| {r['p']:.3f} | {r['stars']} "
            f"| {'réel' if r['premium_real'] else 'imputé'} "
            f"| {'oui' if r['offer'] else 'NON'} | {_note(r)} |"
        )
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="P14 fresh pool scoring (V1)")
    p.add_argument("--apply", action="store_true", help="commit (default = dry-run)")
    args = p.parse_args()
    asyncio.run(_process(dry_run=not args.apply))
