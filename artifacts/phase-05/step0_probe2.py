"""Phase-5 Step-0 probe #2 — wrapper → real PDF, pagination, offer types."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

LISTING_URL = (
    "https://www.bafin.de/DE/die-bafin/publikationen-daten/datenbanken-uebersichten/"
    "WPUeG/angebotsunterlagen/angebotsunterlagen_node.html"
)
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.7",
}


def main() -> None:
    out_dir = Path("artifacts/phase-05")
    fix_dir = Path("tests/fixtures/bafin")
    fix_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    with httpx.Client(timeout=30.0, follow_redirects=True, headers=HEADERS) as client:
        listing = client.get(LISTING_URL).text
        soup = BeautifulSoup(listing, "lxml")
        table = soup.find("table", class_="data")
        rows = table.find_all("tr")[1:] if table else []

        # ---------------- Offer-type distribution ----------------
        offer_types: list[str] = []
        wrappers: list[tuple[str, str, str, str]] = []  # (bieter, target, type, wrapper_url)
        for tr in rows:
            tds = tr.find_all("td")
            if len(tds) != 5:
                continue
            bieter = tds[0].get_text(" ", strip=True)
            target = tds[1].get_text(" ", strip=True)
            link = tds[3].find("a")
            if not link:
                continue
            offer_type = link.get_text(" ", strip=True)
            offer_types.append(offer_type)
            wrappers.append((bieter, target, offer_type, link.get("href", "")))

        type_dist = Counter(offer_types)
        date_pattern = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")
        dates = [
            date_pattern.search(tr.find_all("td")[4].get_text())
            for tr in rows
            if len(tr.find_all("td")) == 5
        ]
        dates_parsed = [
            (int(m.group(3)), int(m.group(2)), int(m.group(1)))
            for m in dates
            if m
        ]
        years = Counter(y for y, _, _ in dates_parsed)

        print("=" * 70)
        print("ROW COUNTS BY OFFER TYPE")
        print("=" * 70)
        for k, v in type_dist.most_common():
            print(f"  {k:50s} {v:>4d}")
        print(f"  TOTAL: {sum(type_dist.values())}")

        print("\n" + "=" * 70)
        print("ROW COUNTS BY YEAR")
        print("=" * 70)
        for y, v in sorted(years.items(), reverse=True)[:8]:
            print(f"  {y}: {v}")
        print(f"  EARLIEST: {min(years)}  LATEST: {max(years)}")

        # ---------------- Pagination probe ----------------
        # Look for pagination links anywhere on the page.
        print("\n" + "=" * 70)
        print("PAGINATION PROBE")
        print("=" * 70)
        # BaFin frequently uses ?gtp=...
        page_links = [a for a in soup.find_all("a") if "gtp=" in a.get("href", "")]
        nav = soup.find_all(attrs={"class": re.compile(r"(pagin|nav|seite)", re.I)})
        print(f"  links with 'gtp=' param: {len(page_links)}")
        print(f"  elements with class matching pagin/nav/seite: {len(nav)}")
        for n in nav[:3]:
            print(f"    -> {n.name} class={n.get('class')} text={n.get_text(' ', strip=True)[:120]}")

        # ---------------- Wrapper → PDF probe (3 samples) ----------------
        print("\n" + "=" * 70)
        print("WRAPPER → REAL PDF PROBE (first 3 wrappers)")
        print("=" * 70)
        results: list[dict[str, object]] = []
        for bieter, target, offer_type, wrapper_url in wrappers[:3]:
            if not wrapper_url.startswith("http"):
                wrapper_url = "https://www.bafin.de" + wrapper_url
            print(f"\n  [{offer_type}] {bieter} -> {target}")
            print(f"  wrapper: {wrapper_url}")
            wresp = client.get(wrapper_url)
            print(f"  wrapper status: {wresp.status_code}, bytes: {len(wresp.text)}")
            wsoup = BeautifulSoup(wresp.text, "lxml")
            pdf_links = [
                a.get("href")
                for a in wsoup.find_all("a")
                if a.get("href")
                and (".pdf" in a.get("href", "") or "blob=publicationFile" in a.get("href", ""))
            ]
            print(f"  PDF candidates on wrapper: {len(pdf_links)}")
            for pl in pdf_links[:3]:
                print(f"    -> {pl[:120]}")

            entry: dict[str, object] = {
                "bieter": bieter,
                "target": target,
                "type": offer_type,
                "wrapper_url": wrapper_url,
                "wrapper_status": wresp.status_code,
                "wrapper_html_bytes": len(wresp.text),
                "pdf_candidates": pdf_links[:5],
            }

            # Try downloading the first PDF candidate.
            if pdf_links:
                pdf_url = pdf_links[0]
                if not pdf_url.startswith("http"):
                    pdf_url = "https://www.bafin.de" + pdf_url
                presp = client.get(pdf_url)
                entry.update(
                    {
                        "pdf_url_tested": pdf_url,
                        "pdf_status": presp.status_code,
                        "pdf_bytes": len(presp.content),
                        "pdf_content_type": presp.headers.get("content-type"),
                        "pdf_magic_ok": presp.content[:5] == b"%PDF-",
                    }
                )
                print(
                    f"  PDF download: status={presp.status_code} "
                    f"bytes={len(presp.content)} magic_ok={presp.content[:5] == b'%PDF-'}"
                )
                # Save the first sample for fixture reuse.
                if presp.content[:5] == b"%PDF-":
                    safe_name = re.sub(r"[^a-zA-Z0-9]+", "_", target.lower())[:40]
                    fixture_path = fix_dir / f"sample_{safe_name}.pdf"
                    fixture_path.write_bytes(presp.content)
                    entry["fixture_saved"] = str(fixture_path)
            results.append(entry)

        # ---------------- Wrapper HTML fixture ----------------
        # Save 1 wrapper as a fixture for selector test.
        if results:
            first_wrapper = wrappers[0][3]
            if not first_wrapper.startswith("http"):
                first_wrapper = "https://www.bafin.de" + first_wrapper
            wfix = fix_dir / "wrapper-commerzbank.html"
            wfix.write_text(client.get(first_wrapper).text, encoding="utf-8")
            print(f"\nWrapper fixture saved: {wfix}")

        # Persist all findings
        summary = {
            "rows_total": len(rows),
            "offer_type_distribution": dict(type_dist),
            "year_distribution": dict(years),
            "earliest_date": min(dates_parsed) if dates_parsed else None,
            "latest_date": max(dates_parsed) if dates_parsed else None,
            "wrapper_probes": results,
            "pagination": {
                "gtp_links_found": len(page_links),
                "nav_class_elements": len(nav),
            },
        }
        (out_dir / "step0-probe2.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
