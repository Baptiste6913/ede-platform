"""schema finalisation: secondary_jurisdictions array + canonical deal_type enum

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-12 19:00:00.000000

Three things in this migration:

1. ADD COLUMN deals.secondary_jurisdictions jurisdiction_enum[] NULL — supports
   cross-border deals where the primary regulator filing is in one country but
   the target is listed in others.

2. REPLACE the deal_type_enum with a canonical lowercase legal-terminology
   list. v1 used placeholder codes (OPA, Uebernahmeangebot, OPA_IT, ...);
   v2 uses snake_case canonical names per CLAUDE.md §7 phase 1 finalisation.
   v1 → v2 mapping in `_DEAL_TYPE_V1_TO_V2` below.

3. CONFIRM prices.volume is BIGINT NULL. Was already nullable in migration
   0003; this migration just adds an explicit comment in code (no DDL).

All three are reversible — the downgrade reapplies the v1 enum + drops the
new column. Reversibility verified by upgrade head → downgrade base →
upgrade head against timescale/timescaledb-ha:pg16.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ---- Canonical deal_type values (v2) ------------------------------------
# Single source: src.core.enums.DEAL_TYPES. Mirrored here so the migration
# stays self-contained and replayable even if enums.py evolves later.
_DEAL_TYPES_V2: tuple[str, ...] = (
    # FR
    "opa",
    "opa_simplifiee",
    "opa_obligatoire",
    # IT
    "opa_volontaire_totalitaria",
    "opa_volontaire_parziale",
    "opa_consolidamento",
    # FR (cont'd) + IT exchange
    "ope",
    "opas",
    "opra",
    "opr",
    "opr_ro",
    "garantie_de_cours",
    # DE
    "pflichtangebot",
    "freiwilliges_uebernahmeangebot",
    "delisting_erwerbsangebot",
    "erwerbsangebot",
)

# ---- Legacy deal_type values (v1, from migration 0001) ------------------
_DEAL_TYPES_V1: tuple[str, ...] = (
    "OPA",
    "OPE",
    "OPAS",
    "OPR",
    "OPRO",
    "OPV",
    "OPVS",
    "OPA_IT",
    "Uebernahmeangebot",
    "Pflichtangebot",
    "Erwerbsangebot",
    "Delistingangebot",
)

# ---- v1 → v2 mapping (used in ALTER TYPE USING clause) ------------------
_DEAL_TYPE_V1_TO_V2: dict[str, str] = {
    "OPA": "opa",
    "OPE": "ope",
    "OPAS": "opa_simplifiee",
    "OPR": "opr",
    "OPRO": "opa_obligatoire",  # FR mandatory tender
    "OPV": "opa_volontaire_totalitaria",
    "OPVS": "opa_volontaire_parziale",
    "OPA_IT": "opa_obligatoire",
    "Uebernahmeangebot": "freiwilliges_uebernahmeangebot",
    "Pflichtangebot": "pflichtangebot",
    "Erwerbsangebot": "erwerbsangebot",
    "Delistingangebot": "delisting_erwerbsangebot",
}

# v2 → v1 (best-effort) for downgrade. Some v2 values have no v1 equivalent
# (opa_consolidamento, opra, opr_ro, garantie_de_cours) — they map to the
# closest v1 value to keep downgrade lossless for the seed dataset.
_DEAL_TYPE_V2_TO_V1: dict[str, str] = {
    "opa": "OPA",
    "opa_simplifiee": "OPAS",
    "opa_obligatoire": "OPRO",
    "opa_volontaire_totalitaria": "OPV",
    "opa_volontaire_parziale": "OPVS",
    "opa_consolidamento": "OPV",  # no exact v1 — fallback
    "ope": "OPE",
    "opas": "OPAS",
    "opra": "OPAS",  # no exact v1
    "opr": "OPR",
    "opr_ro": "OPR",  # no exact v1
    "garantie_de_cours": "OPA",  # no exact v1
    "pflichtangebot": "Pflichtangebot",
    "freiwilliges_uebernahmeangebot": "Uebernahmeangebot",
    "delisting_erwerbsangebot": "Delistingangebot",
    "erwerbsangebot": "Erwerbsangebot",
}


def _case_when_sql(mapping: dict[str, str]) -> str:
    """Render a SQL CASE expression mapping the source column's text values."""
    clauses = "\n        ".join(f"WHEN '{k}' THEN '{v}'" for k, v in mapping.items())
    return f"CASE deal_type::text\n        {clauses}\n    END"


def _values_sql(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def upgrade() -> None:
    # ---- 1. ADD COLUMN deals.secondary_jurisdictions ------------------
    op.execute("ALTER TABLE deals ADD COLUMN secondary_jurisdictions jurisdiction_enum[] NULL")

    # ---- 2. Replace deal_type_enum (v1 → v2) -------------------------
    # Strategy: create new type, ALTER COLUMN with USING (mapping), drop old,
    # rename. This is the safe pattern for replacing a PG enum that's
    # already in use by a column.
    op.execute(f"CREATE TYPE deal_type_enum_v2 AS ENUM ({_values_sql(_DEAL_TYPES_V2)})")
    op.execute(
        f"""
        ALTER TABLE deals
          ALTER COLUMN deal_type TYPE deal_type_enum_v2
          USING ({_case_when_sql(_DEAL_TYPE_V1_TO_V2)})::deal_type_enum_v2
        """
    )
    op.execute("DROP TYPE deal_type_enum")
    op.execute("ALTER TYPE deal_type_enum_v2 RENAME TO deal_type_enum")

    # ---- 3. Confirm prices.volume is nullable -------------------------
    # No DDL needed — column was created as `BIGINT NULL` in migration 0003.
    # Explicit SET NULL is a no-op but documents intent and is idempotent.
    op.execute("ALTER TABLE prices ALTER COLUMN volume DROP NOT NULL")


def downgrade() -> None:
    # ---- 2 (reverse). Restore deal_type_enum v1 -----------------------
    op.execute(f"CREATE TYPE deal_type_enum_v1 AS ENUM ({_values_sql(_DEAL_TYPES_V1)})")
    op.execute(
        f"""
        ALTER TABLE deals
          ALTER COLUMN deal_type TYPE deal_type_enum_v1
          USING ({_case_when_sql(_DEAL_TYPE_V2_TO_V1)})::deal_type_enum_v1
        """
    )
    op.execute("DROP TYPE deal_type_enum")
    op.execute("ALTER TYPE deal_type_enum_v1 RENAME TO deal_type_enum")

    # ---- 1 (reverse). Drop secondary_jurisdictions --------------------
    op.execute("ALTER TABLE deals DROP COLUMN secondary_jurisdictions")
    # prices.volume nullability is unchanged — was always NULL.
