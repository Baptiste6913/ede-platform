# P9.2 02b — regression test fixtures (anchoring)

Text excerpts used by
``tests/ingestion/amf/test_anchoring_fixtures_p92_02b.py`` to pin the
behaviour of the AMF parser after the Step 1 positional-anchoring fix
ships. The source PDFs are gitignored (`data/pdfs/fr/<year>/<ref>.pdf`);
the excerpts below are the minimal text chunks needed to reproduce the
extraction on CI. Pattern mirrors ``tests/fixtures/p92_02a/``.

Two scenarios:

- **FP fixtures (14)** — the legacy parser stores a wrong price on these
  PDFs; the Step 1 fix must return the corrected price.
- **False-alarm fixtures (3)** — the legacy parser already returns the
  correct price; the Step 1 fix must NOT regress these.

Each excerpt was sized (script
``scripts/p92_02b_extract_fixtures.py``) just large enough that the
legacy ``_extract_first_price`` reproduces the production-DB
behaviour on the excerpt alone — without the fix, the FP excerpts
return the stored wrong price; with the fix, they must return the
corrected price.

## FP fixtures

| Ref | Target | Legacy (wrong) | Expected (corrected) | Pattern |
|---|---|---|---|---|
| 224C0915 | TRAVEL TECHNOLOGY INTERACTIVE | 2.34 | **2.85** | BLOCK_PURCHASE |
| 224C1289 | TRAVEL TECHNOLOGY INTERACTIVE | 2.34 | **2.85** | BLOCK_PURCHASE |
| 218C1907 | SERMA GROUP | 229.19 | **235** | BLOCK_PURCHASE |
| 218C2028 | SERMA GROUP | 229.19 | **235** | BLOCK_PURCHASE |
| 221C1910 | GENKYOTEX | 2.80 | **2.85** | DIVIDEND_TRAP |
| 218C1043 | CFI | 0.83 | **1.00** | SURENCHERE |
| 220C4135 | LE BELIER | 35.12 | **38.18** | DIVIDEND_TRAP |
| 224C1700 | GALIMMO | 9.02 | **14.83** | BLOCK_PURCHASE |
| 224C2193 | NHOA | 1.10 | **1.25** | SURENCHERE |
| 224C1145 | OSMOZIS | 13.50 | **15** | DIVIDEND_TRAP |
| 223C2035 | TECHNICOLOR CREATIVE STUDIOS | 0.01 | **1.63** | OCEANE_BSA |
| 226C0661 | MEDIA 6 | 9.69 | **9.89** | SURENCHERE |
| 226C0645 | MEDIA 6 | 9.69 | **9.89** | SURENCHERE |
| 225C1227 | GROUPE ETPO | 61 | **82.33** | DIVIDEND_TRAP (+ BLOCK_PURCHASE) |

## False-alarm fixtures

| Ref | Target | Stored = expected | Reason |
|---|---|---|---|
| 226C0550 | TERACT | 3.12 | Multi-bullet `au prix de :\n- 3,12 €` formulation |
| 226C0157 | TERACT | 3.12 | Same multi-bullet shape |
| 224C1861 | NHOA | 1.25 | `visées dorénavant au prix unitaire de 1,25 €` phrasing |

## Regenerate

```
.venv/Scripts/python.exe scripts/p92_02b_extract_fixtures.py
```

Idempotent: re-running the script overwrites the excerpts from the
current PDFs and verifies the legacy parser still produces the
reference values; if the legacy parser drifts (e.g. another regex
change lands first), the script widens the window automatically.
