# P9.2 02a — Pipeline audit (Step 0 A)

**Goal.** Locate the exact line where `extract_pdf_metadata` should
be wired into the AMF ingestion path, characterize the API delta
between the AMF parser today and the BaFin parser (which already
wires correctly in P9.1a), and confirm the prerequisites for the
extended dry-run [02a-Step0-B] (PDF availability on disk + DB
`pdf_path` coverage).

## a) Prerequisites — PDF availability

| Metric | Value |
|---|---|
| Total FR deals in DB | **730** |
| Deals with `pdf_path IS NOT NULL` | **730 (100 %)** |
| Deals where local file exists | **730 / 730** (filesystem check on all paths via stripped `/repo/` prefix) |
| Missing PDFs (DB says path, file absent) | **0** |

The 450/730 volume target estimated in P9.2 Step 0 is **not
discounted** by any PDF-availability shortfall. Every FR deal has
a parseable file on disk.

## b) Smoking gun confirmed

`src/ingestion/amf/service.py:216-218`:

```python
# kept for backwards compat with tests/callers expecting Decimal handling — no
# longer used since BDIF doesn't expose price in the API; price is extracted
# from the PDF by the analyst/parser layer later (phase 6).
```

Grep across the entire codebase for AMF parser usage:

```
src/ingestion/amf/parser.py:131  def extract_pdf_metadata(...)   # definition
src/ingestion/amf/parser.py:295   "extract_pdf_metadata",        # __all__
scripts/p92_amf_parser_dryrun.py:28  from src.ingestion.amf.parser import extract_pdf_metadata
```

→ **No callsite in any of the four `src/ingestion/amf/*.py` files
outside `parser.py` itself.** The parser is fully implemented but
disconnected from the ingestion pipeline.

For comparison:
- `src/ingestion/bafin/poller.py:135` calls `extract_pdf_metadata`
  on every poll.
- `src/ingestion/consob/poller.py:165` calls `extract_pdf_metadata`
  on every poll.

## c) Exact wiring point

The fix lives in **two files** with **one new keyword argument** on the service signature, mirroring BaFin's pattern exactly.

### File 1 — `src/ingestion/amf/bdif_poller.py`

Current (lines 99-116):

```python
async with self._session_factory() as session:
    async for item in self._api.iter_all(...):
        discovered += 1
        pdf_path = await self._download_safe(item)
        if pdf_path is not None:
            pdf_dl += 1
        elif item.first_pdf is not None:
            pdf_fail += 1

        result = await upsert_deal_from_bdif(session, item, pdf_path=pdf_path)
```

Diff sketch (mirror of `bafin/poller.py:134-143`):

```python
        pdf_path = await self._download_safe(item)
        if pdf_path is not None:
            pdf_dl += 1
        elif item.first_pdf is not None:
            pdf_fail += 1

+       pdf_md = (
+           amf_parser.extract_pdf_metadata(pdf_path) if pdf_path is not None else None
+       )

-       result = await upsert_deal_from_bdif(session, item, pdf_path=pdf_path)
+       result = await upsert_deal_from_bdif(
+           session, item, pdf_path=pdf_path, pdf_metadata=pdf_md,
+       )
```

Plus the import: `from src.ingestion.amf import parser as amf_parser`.

### File 2 — `src/ingestion/amf/service.py`

Two paths need updating in `upsert_deal_from_bdif`:

- **New-deal path (lines 82-93)**: populate `offer_price`,
  `currency`, `offer_price_quality_flag` from `pdf_metadata` at
  Deal creation time.
- **Existing-deal path (lines 73-80)**: currently only promotes
  `pdf_path` when missing. Should *also* re-parse and back-fill
  `offer_price` / quality flag if the existing row has the
  migration default (`suspect_low_unverified`) and we now have a
  downloaded PDF.

Diff sketch:

```python
 async def upsert_deal_from_bdif(
     session: AsyncSession,
     bdif_item: BdifItem,
     *,
     pdf_path: Path | None,
+    pdf_metadata: ParsedMetadata | None = None,
 ) -> UpsertResult:
     ...
     if existing is not None:
         if pdf_path is not None and not existing.pdf_path:
             existing.pdf_path = str(pdf_path)
+        if pdf_metadata is not None and (
+            existing.offer_price_quality_flag == "suspect_low_unverified"
+        ):
+            existing.offer_price = pdf_metadata.offer_price
+            existing.currency = pdf_metadata.currency or existing.currency
+            existing.offer_price_quality_flag = _derive_quality_flag(pdf_metadata)
+            existing.parser_version = PARSER_VERSION_02A
         await session.commit()
         return UpsertResult(deal_id=existing.id, created=False)

     deal = Deal(
         juridiction="FR",
         ...
         currency="EUR",
+        offer_price=pdf_metadata.offer_price if pdf_metadata else None,
+        offer_price_quality_flag=(
+            _derive_quality_flag(pdf_metadata)
+            if pdf_metadata is not None
+            else "suspect_low_unverified"
+        ),
+        parser_version=PARSER_VERSION_02A,
         ...
     )
```

### File 3 — `scripts/backfill_p92_02a.py` (new)

Mirror `scripts/backfill_p91a.py`. Reads every FR deal with
`parser_version < PARSER_VERSION_02A`, re-parses the PDF, writes
`offer_price` + flag + version. Transactional per deal, idempotent.

## d) API delta — BaFin vs AMF parser

BaFin parser returns `ParsedBafinMetadata` which **already sets**
`offer_price_quality_flag` (see `bafin/parser.py:183` default,
`:232` actual assignment). The poller passes this through to the
service unchanged.

AMF parser returns `ParsedMetadata` (`amf/parser.py:96-110`) which
has **no `offer_price_quality_flag` field**. The wiring layer
needs to derive the flag.

**Two options to reconcile:**

| Option | Effort | Risk | Reuse path |
|---|---|---|---|
| **A. Wiring-only** — derive `offer_price_quality_flag` in service.py from `(offer_price is None, bounds check)` | Smaller — 1-file diff in service.py | Low | Doesn't change parser API; 02b regex hardening can later move the logic into the parser |
| **B. Parser-extends** — extend `ParsedMetadata` to carry the flag, parser computes it (mirror BaFin convention) | Larger — touches parser + dataclass + tests | Low to medium | Cleaner API, matches BaFin |

**Recommendation:** **Option A in 02a** to keep the wire-up commit small and not entangle with 02b regex changes. 02b will extend `ParsedMetadata` to also carry the flag (mirror BaFin) as part of the regex hardening pass.

The 02a `_derive_quality_flag(pdf_md)` helper mirrors the 02d
Consob promotion logic:

```python
def _derive_quality_flag(md: ParsedMetadata) -> str:
    if md.offer_price is None:
        return "suspect_low_unverified"  # parser ran, no price found
    if md.offer_price < PRICE_LOWER or md.offer_price > PRICE_UPPER:
        return "failed_validation"
    return "verified_cash"
```

(Bounds calibrated in `[02a-Step0-B]` from the AMF price distribution; see open question (3) of the brief.)

## e) `pdf_text_extraction_failed` flag

User-validated decision (brief response): default Option B — route
silent-miss deals to `manual_review` (reuse existing flag), no
migration in 02a. Reconsider only if `[02a-Step0-B]` shows silent
miss splits into two clearly distinct populations (e.g. broken
PDFs vs response-note legitimate empties).

The fallback chain in `_derive_quality_flag` will be:

| Parser outcome | Flag |
|---|---|
| `offer_price` extracted, in bounds | `verified_cash` |
| `offer_price` extracted, out of bounds | `failed_validation` |
| `offer_price IS NONE` (no extraction) | **`suspect_low_unverified`** (kept — the existing migration default works here) |
| PyMuPDF crash / IO error on the PDF | `manual_review` (caught at poller level) |

## f) Acquirer / target / date metadata

The AMF parser also returns `target_name`, `acquirer_name`,
`announcement_date`. In the service.py upsert path the BDIF
metadata is the **authoritative source** for `target_name` /
`acquirer_name` / `announcement_date`. The parser's values are
only useful as a fallback when BDIF returned `[pending parse]` or
similar placeholders.

**Decision for 02a:** preserve current BDIF-wins behavior for the
non-price fields. Only `offer_price` + `currency` +
`offer_price_quality_flag` + `parser_version` are populated from
the parser. The `[pending parse]` cleanup is out of scope (it's a
separate re-ingestion debt logged in 02d closure summary).

## g) Open questions resolved at [02a-Step0-A]

- ✅ Wiring point: `bdif_poller.py:110-112` (the line between PDF
  download and `upsert_deal_from_bdif` call).
- ✅ Service signature change: add
  `pdf_metadata: ParsedMetadata | None = None`.
- ✅ Flag derivation: **Option A** (wiring-only `_derive_quality_flag`
  helper in service.py).
- ✅ 100 % PDF availability — no upstream blockers.

## h) Carry-forward to [02a-Step0-B]

The extended dry-run brief is unblocked. It will:
1. Sample 80 FR deals stratified by year + heuristic doc type.
2. Run the current parser on each, capture `(offer_price, currency,
   target_name, acquirer_name, announcement_date, raw_text_sample[:200])`
   plus a heuristic `doc_type` (note d'information / response note /
   complément / other) derived from the raw text.
3. Calibrate AMF bounds on the empirical price distribution.
4. Categorize each error type (silent miss legit vs silent miss
   bug, dividend trap, block-purchase trap, `\xa0` bug, multi-tranche).
5. Estimate `verified_cash` post-wire (without regex hardening).

## STOP — checkpoint [02a-Step0-A]

Pipeline audit complete. Awaiting user validation on:
1. The exact wiring point (`bdif_poller.py:110-112`).
2. Option A (wiring-only flag derivation) vs Option B
   (parser-extends `ParsedMetadata`).
3. Bounds calibration scope for `[02a-Step0-B]` — keep
   `[0.01, 10 000]` Consob bounds as a starting hypothesis, OR
   compute fresh from the AMF distribution and only adopt if it
   differs significantly?
4. `_derive_quality_flag` behavior on `offer_price IS NONE` —
   `suspect_low_unverified` (kept as default, parser legitimately
   found nothing) or downgrade to `manual_review`?

Then proceed to `[02a-Step0-B]` (extended dry-run on 80 deals).
