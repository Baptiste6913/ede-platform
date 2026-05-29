# P9.2 02a end-to-end fixtures

Two AMF *D&I / BDIF* text excerpts used by
`tests/ingestion/amf/test_pipeline_p92_02a_e2e.py` (cases `a` and `b`) to
exercise the parser → service → DB chain on real corpus text without
shipping the binary PDFs to CI.

The source PDFs are **gitignored** (corpus lives under `data/pdfs/fr/`,
re-fetchable via the BDIF poller). The excerpts below are the minimal
text chunks needed to reproduce the parser behaviour on CI:

| ref | file | scenario | parser output |
|---|---|---|---|
| 224C0830 | `tipiak_224C0830_excerpt.txt` | extractable price (block-acquisition clause around "prix unitaire de 82 €") | `Decimal("82")`, `"EUR"` |
| 226C0020 | `balyo_226C0020_excerpt.txt` | silent miss (cover page of a "complément à D&I" without an offer-price clause) | `None`, `None` |

Pattern mirrors `tests/fixtures/p91a/*_excerpt.txt` (BaFin P9.1a).
