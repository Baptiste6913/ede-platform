# P9.1a parser-bug fixtures

Five BaFin *Angebotsunterlage* PDFs used to diagnose the two `offer_price`
parser bugs (see `docs/phase-09/p91a_cluster_1_diagnosis.md` and
`p91a_pattern_mixed_diagnosis.md`).

The PDFs themselves are **gitignored** (~18 MB, public regulatory filings).
Re-fetch them from the BaFin URLs below, or copy from `data/pdfs/de/<year>/`.

| deal_id | file | bug | BaFin source |
|--:|---|---|---|
| 348 | `BAFIN-DE000CBK1001-20260505.pdf` | Cluster A + Pattern B | https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/commerzbank.html?nn=151388 |
| 1070 | `BAFIN-DE000A2QRHL6-20241112.pdf` | Cluster A | https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/Linus.html?nn=151388 |
| 1079 | `BAFIN-DE0006097108-20241007.pdf` | Cluster A | https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/infas.html?nn=151388 |
| 1080 | `BAFIN-philomaxcap-20241004.pdf` | Cluster A (false positive — real EUR 1.00) | https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/Philomaxcap.html?nn=151388 |
| 1059 | `BAFIN-DE000PSM7770-20250508.pdf` | Pattern B (cash + shares) | https://www.bafin.de/SharedDocs/Downloads/DE/Angebotsunterlage/MFE-MEDIAFOREUROPE.html?nn=151388 |
