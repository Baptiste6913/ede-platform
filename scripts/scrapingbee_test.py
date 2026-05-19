"""Phase 4 — Step 1 mandatory ScrapingBee test.

Single request to ScrapingBee targeting Consob's documenti-opa listing.
Verifies that:
  - the API key is valid (HTTP 200, no 401/402)
  - ScrapingBee renders JS and bypasses Radware Bot Manager
  - the returned HTML contains the `<ul class="consobResult">` block
    that the Step 0 spec mapping identified as the data carrier

Reads `SCRAPINGBEE_API_KEY` from the environment via `src.core.settings`.
Costs 5 credits (premium_proxy=true + country_code=it + render_js=true).
Documented in ScrapingBee pricing: https://www.scrapingbee.com/documentation/

Usage:
    SCRAPINGBEE_API_KEY=... python scripts/scrapingbee_test.py

Exit codes:
  0  Consob HTML returned successfully → proceed to Step 2
  1  ScrapingBee returned a non-2xx (likely auth or quota issue)
  2  ScrapingBee returned 200 but Radware fired through it (CAPTCHA page)
  3  Missing/empty SCRAPINGBEE_API_KEY in environment
  4  Network / other unexpected failure
"""

from __future__ import annotations

import json
import sys
from typing import Any

import httpx

from src.core.settings import get_settings

CONSOB_TARGET = "https://www.consob.it/web/area-pubblica/documenti-opa"
SUCCESS_NEEDLE = "consobResult"  # the <ul class="consobResult"> from Step 0 spec
RADWARE_NEEDLES = ("validate.perfdrive.com", "Radware Captcha")
HTTP_OK = 200


def main() -> int:
    settings = get_settings()
    key = settings.scrapingbee_api_key.get_secret_value()
    if not key or key in {"", "your_scrapingbee_api_key_here"}:
        print("ERROR: SCRAPINGBEE_API_KEY not set in environment", file=sys.stderr)
        return 3

    # Cost optimisation: test cheap config first (render_js=true,
    # premium_proxy=false → 5 credits instead of 25). Override via
    # SCRAPINGBEE_PREMIUM_PROXY env var if user wants premium.
    import os

    premium = os.environ.get("SCRAPINGBEE_PREMIUM_PROXY", "false").lower() == "true"
    render_js = os.environ.get("SCRAPINGBEE_RENDER_JS", "true").lower() == "true"
    params: dict[str, str] = {
        "api_key": key,
        "url": CONSOB_TARGET,
        "render_js": "true" if render_js else "false",
    }
    if premium:
        params["premium_proxy"] = "true"
        params["country_code"] = "it"
    headers_to_log: dict[str, Any] = {}
    body_len = 0

    try:
        with httpx.Client(timeout=settings.scrapingbee_timeout_seconds) as client:
            resp = client.get(settings.scrapingbee_base_url, params=params)
            body_len = len(resp.content)
            headers_to_log = {
                "Spb-Cost": resp.headers.get("Spb-Cost", "?"),
                "Spb-Original-Status": resp.headers.get("Spb-Original-Status", "?"),
                "Spb-Resolved-Url": resp.headers.get("Spb-Resolved-Url", "?"),
                "Spb-Initial-Status-Code": resp.headers.get("Spb-Initial-Status-Code", "?"),
            }
    except httpx.HTTPError as exc:
        print(f"ERROR: HTTP failure → {type(exc).__name__}: {exc}", file=sys.stderr)
        return 4

    summary = {
        "status_code": resp.status_code,
        "body_bytes": body_len,
        "headers": headers_to_log,
    }

    if resp.status_code != HTTP_OK:
        summary["verdict"] = "non-200"
        summary["body_preview"] = resp.text[:600]
        print(json.dumps(summary, indent=2))
        return 1

    text = resp.text
    radware_hit = any(needle in text for needle in RADWARE_NEEDLES)
    success_hit = SUCCESS_NEEDLE in text

    if radware_hit and not success_hit:
        summary["verdict"] = "radware_via_scrapingbee"
        summary["body_preview"] = text[:600]
        print(json.dumps(summary, indent=2))
        return 2

    if not success_hit:
        summary["verdict"] = "unexpected-html"
        summary["body_preview"] = text[:600]
        print(json.dumps(summary, indent=2))
        return 2

    # Count <li> data rows for an early-confidence check.
    row_count = text.count('<li>\n\t\t\t\t\t<div class="div20 center">')
    if row_count == 0:
        # Permissive fallback (the rendered HTML may differ slightly from
        # what we captured in Step 0).
        row_count = text.count("div20")

    summary["verdict"] = "ok"
    summary["consob_rows_estimated"] = row_count
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
