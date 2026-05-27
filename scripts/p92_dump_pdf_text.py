"""P9.2 Step 0 — dump first N pages of selected PDFs to plain text for
manual pattern audit. No DB required, offline.

Usage:
    python scripts/p92_dump_pdf_text.py fr 2022/216C1735.pdf,2022/216C2789.pdf,...
    python scripts/p92_dump_pdf_text.py it CONSOB-opa_cir_20241125.pdf,...

Output:
    data/audits/p92_text_dumps/<jurisdiction>/<basename>.txt
"""

from __future__ import annotations

import sys
from pathlib import Path

import fitz

REPO = Path(__file__).resolve().parents[1]
PDF_ROOT = REPO / "data" / "pdfs"
OUT_ROOT = REPO / "data" / "audits" / "p92_text_dumps"


def dump(jur: str, rel_paths: list[str], max_pages: int = 5) -> None:
    src_dir = PDF_ROOT / jur
    out_dir = OUT_ROOT / jur
    out_dir.mkdir(parents=True, exist_ok=True)

    for rel in rel_paths:
        pdf = src_dir / rel
        if not pdf.exists():
            print(f"MISSING: {pdf}")
            continue
        try:
            doc = fitz.open(pdf)
        except Exception as e:
            print(f"ERROR opening {pdf}: {e}")
            continue
        text_chunks: list[str] = []
        total_pages = doc.page_count
        n = min(max_pages, total_pages)
        for i in range(n):
            text_chunks.append(f"\n===== PAGE {i + 1} =====\n")
            text_chunks.append(doc.load_page(i).get_text())  # type: ignore[no-untyped-call]
        doc.close()
        out_path = out_dir / (pdf.stem + ".txt")
        out_path.write_text("".join(text_chunks), encoding="utf-8")
        print(f"OK  {rel} -> {out_path.relative_to(REPO)} ({n}/{total_pages} pages)")


if __name__ == "__main__":
    jur = sys.argv[1]
    rel_paths = sys.argv[2].split(",")
    dump(jur, rel_paths)
