"""Self-review: enumerate tests + classify assertion nature.

Robust parser using `ast` (handles multi-line signatures correctly, unlike
the regex approach in the phase-0 audit).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TEST_DIRS = [REPO / "tests"]

ASSERT_LIKE = re.compile(
    r"\b(assert|pytest\.raises|assert_(awaited|called|not_called|not_awaited)"
    r"|mock\.\w*assert)\b"
)


def classify_test(node: ast.FunctionDef | ast.AsyncFunctionDef, src: str) -> str:
    body_src = ast.get_source_segment(src, node) or ""
    n_assert = sum(1 for line in body_src.splitlines() if ASSERT_LIKE.search(line))
    if n_assert == 0:
        return "NO ASSERT"
    return f"{n_assert} assert(s)"


def main() -> None:
    rows: list[tuple[str, str, str]] = []
    for d in TEST_DIRS:
        for f in sorted(d.rglob("test_*.py")):
            src = f.read_text(encoding="utf-8")
            tree = ast.parse(src)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                    node.name.startswith("test_")
                ):
                    rel = f.relative_to(REPO).as_posix()
                    rows.append((rel, node.name, classify_test(node, src)))

    rows.sort()
    for rel, name, klass in rows:
        print(f"{rel:35s} {name:60s} {klass}")
    print(f"\nTOTAL: {len(rows)} tests")
    cosmetic = [r for r in rows if r[2] == "NO ASSERT"]
    print(f"COSMETIC (no assert): {len(cosmetic)}")
    for r in cosmetic:
        print(f"  - {r[0]}::{r[1]}")


if __name__ == "__main__":
    main()
