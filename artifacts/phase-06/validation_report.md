# Phase 6 V1 — Validation report
## Cross-validation (date-ordered, gap=90 j)
| Fold | Train n | Valid n | Valid pos/neg | AUC | Brier | Train range | Valid range |
|---|---:|---:|---|---:|---:|---|---|
| 0 | 22 | 32 | 32/0 | n/a | 0.471 | 2022-01-21 → 2023-11-06 | 2024-06-14 → 2024-10-22 |
| 1 | 40 | 32 | 32/0 | n/a | 0.021 | 2022-01-21 → 2024-07-15 | 2024-10-25 → 2025-04-07 |
| 2 | 84 | 32 | 31/1 | 0.935 | 0.027 | 2022-01-21 → 2024-12-23 | 2025-04-07 → 2026-02-05 |

**Overall pooled AUC:** 0.611
**Overall pooled Brier:** 0.173

## Calibration deciles (in-sample on full training set)
| Predicted-prob bin (mid) | Empirical rate | n |
|---:|---:|---:|
| 0.50 | 0.429 | 7 |
| 0.70 | 0.833 | 18 |
| 0.90 | 1.000 | 103 |

## Top positive contributors (full-data refit)
- `deal_type_opa` → +1.347
- `events_count` → +1.034
- `payment_type_cash` → +0.933
- `acquirer_type_corporate` → +0.774
- `deal_type_opa_volontaire_totalitaria` → +0.502

## Top negative contributors (full-data refit)
- `acquirer_type_family` → -1.977
- `deal_type_opra` → -1.676
- `jurisdiction_FR` → -1.400
- `deal_type_opa_simplifiee` → -1.108
- `payment_type_stock` → -0.906

## Notes
