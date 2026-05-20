"""Phase-5 Step-0 probe: test BaFin Angebotsunterlagen listing accessibility.

Run inside Docker container:
    docker run --rm -v $repo:/repo -w /repo python:3.12-slim-bookworm bash -c \
      "pip install --quiet httpx beautifulsoup4 lxml && python artifacts/phase-05/step0_probe.py"
"""

from __future__ import annotations

import json
import sys
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


def probe_listing() -> dict[str, object]:
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        resp = client.get(LISTING_URL, headers=HEADERS)
    body = resp.text
    soup = BeautifulSoup(body, "lxml")

    out: dict[str, object] = {
        "status": resp.status_code,
        "final_url": str(resp.url),
        "content_type": resp.headers.get("content-type"),
        "html_bytes": len(body),
        "anti_bot_indicators": {
            "akamai": "akamai" in body.lower() or "ak_bmsc" in body.lower(),
            "cloudflare": "cloudflare" in body.lower() or "cf-ray" in resp.headers,
            "validate_perfdrive": "validate.perfdrive.com" in body.lower(),
            "captcha_in_title": "captcha" in (soup.title.text.lower() if soup.title else ""),
        },
        "german_markers_count": {
            "Angebotsunterlage": body.count("Angebotsunterlage"),
            "Bieter": body.count("Bieter"),
            "Zielgesellschaft": body.count("Zielgesellschaft"),
            "Veröffentlich": body.count("Veröffentlich"),
            "WpÜG": body.count("WpÜG"),
        },
        "title_tag": soup.title.string.strip() if soup.title and soup.title.string else None,
    }

    # Look for the actual data table — BaFin uses a <table> for the listing.
    tables = soup.find_all("table")
    out["tables_count"] = len(tables)
    if tables:
        first = tables[0]
        rows = first.find_all("tr")
        out["first_table_rows"] = len(rows)
        if rows:
            out["first_table_first_row_html_preview"] = str(rows[0])[:500]
            if len(rows) > 1:
                out["first_table_second_row_html_preview"] = str(rows[1])[:500]
        out["first_table_classes"] = first.get("class", [])

    # Pagination probe — does the page reference numbered pages?
    out["pagination_hints"] = {
        "?docId": body.count("?docId="),
        "gtp": body.count("gtp="),
        "Seite": body.count("Seite"),
        "Weiter": body.count("Weiter"),
        "page=": body.count("page="),
    }

    # Find a few PDF links to test direct PDF accessibility.
    pdf_links = [a.get("href") for a in soup.find_all("a") if a.get("href", "").endswith(".pdf")]
    out["pdf_link_count"] = len(pdf_links)
    out["pdf_link_samples"] = pdf_links[:5]

    return out


def probe_pdf(url: str) -> dict[str, object]:
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        resp = client.get(url, headers=HEADERS)
    return {
        "url": url,
        "status": resp.status_code,
        "final_url": str(resp.url),
        "content_type": resp.headers.get("content-type"),
        "bytes": len(resp.content),
        "is_pdf_magic": resp.content[:5] == b"%PDF-",
    }


def main() -> int:
    out_dir = Path("artifacts/phase-05")
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("STEP-0 PROBE 1 — LISTING PAGE")
    print("=" * 70)
    listing = probe_listing()
    print(json.dumps(listing, indent=2, ensure_ascii=False, default=str))

    # Persist the raw HTML fixture for future test reuse.
    if listing.get("status") == 200:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            raw = client.get(LISTING_URL, headers=HEADERS).text
        fix_dir = Path("tests/fixtures/bafin")
        fix_dir.mkdir(parents=True, exist_ok=True)
        (fix_dir / "angebotsunterlagen-listing.html").write_text(raw, encoding="utf-8")
        print(f"\nFixture saved: tests/fixtures/bafin/angebotsunterlagen-listing.html "
              f"({len(raw)} bytes)\n")

    print("=" * 70)
    print("STEP-0 PROBE 2 — PDF SAMPLES")
    print("=" * 70)
    pdf_samples = listing.get("pdf_link_samples") or []
    if not pdf_samples:
        print("(no PDF links found on listing — investigate)")
    else:
        for pdf_url in pdf_samples[:3]:
            if not pdf_url.startswith("http"):
                pdf_url = "https://www.bafin.de" + pdf_url
            result = probe_pdf(pdf_url)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            print("---")

    (out_dir / "step0-probe.json").write_text(
        json.dumps(
            {"listing": listing, "pdf_samples_count": len(pdf_samples)},
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
