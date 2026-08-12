"""Architecture invariants — structural rules the codebase must keep.

Currently: no duplicate dict keys in the abbreviation glossary. Python
silently keeps the last duplicate, so an accidental re-add of an existing
abbreviation would shadow the original entry with no error anywhere else.
"""

from __future__ import annotations

import ast
from pathlib import Path



RISK_LIB = Path(__file__).resolve().parent.parent / "risk_lib"


def test_abbreviation_dict_has_no_duplicate_keys():
    tree = ast.parse((RISK_LIB / "abbreviations.py").read_text(encoding="utf-8"))
    dicts = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.value, ast.Dict)
        and isinstance(node.target, ast.Name)
        and node.target.id == "ABBREVIATIONS"
    ]
    assert len(dicts) == 1, "expected exactly one ABBREVIATIONS dict literal"
    keys = [k.value for k in dicts[0].keys if isinstance(k, ast.Constant)]
    assert len(keys) == len(dicts[0].keys), "non-literal key in ABBREVIATIONS"
    dupes = sorted({k for k in keys if keys.count(k) > 1})
    assert not dupes, f"duplicate abbreviation keys (later shadows earlier): {dupes}"


def test_page_registry_is_consistent():
    """Every PageSpec resolves to a callable and filenames are unique."""
    from risk_lib.page_registry import PAGES

    filenames = [p.filename for p in PAGES]
    assert len(filenames) == len(set(filenames)), "duplicate page filename"
    for spec in PAGES:
        fn = spec.resolve()
        assert callable(fn), f"{spec.module}.{spec.func} is not callable"


def test_nav_matches_registry_order():
    from risk_lib.html_report import NAV
    from risk_lib.page_registry import PAGES

    assert NAV == [(p.filename, p.label) for p in PAGES if p.in_nav]
    # ALM sub pages are in the registry but not the main nav
    nav_files = {f for f, _ in NAV}
    assert {"11a_irrbb.html", "11b_lcr.html", "11c_nsfr.html"}.isdisjoint(nav_files)


def test_architecture_doc_table_and_column_counts_match_the_catalog():
    """ARCHITECTURE.md의 테이블·컬럼 수가 카탈로그와 일치한다.

    문서는 81테이블/594컬럼이라 적고 있었고 실제는 107/930이었다 — 26장·336컬럼이
    늘도록 아무도 눈치채지 못했다. `ALL_TABLES`가 5회 append로 재구성되는 구조라
    한 곳만 보고 세면 틀린다.

    이 저장소는 "문서의 주장이 코드와 갈라짐"으로 다섯 번 데였다(F-103·F-201·
    F-401·F-501·F-B02). 숫자를 손으로 고치면 다음 판에 또 낡으므로 검사로 고정한다.
    """
    from pathlib import Path
    import re

    from risk_lib.datamodel import catalog as cat

    n_tables = len(cat.ALL_TABLES)
    n_cols = sum(len(t.columns) for t in cat.ALL_TABLES)
    doc = (Path(__file__).parent.parent / "ARCHITECTURE.md").read_text(encoding="utf-8")

    claims = re.findall(r"(\d+)\s*테이블\s*/\s*(\d+)\s*컬럼", doc)
    claims += re.findall(r"테이블\s*(\d+)장\s*/\s*컬럼\s*(\d+)개", doc)
    assert claims, "ARCHITECTURE.md에 테이블·컬럼 수 주장이 없다 — 검사가 무의미하다"
    for t, c in claims:
        assert (int(t), int(c)) == (n_tables, n_cols), (
            f"문서가 {t}테이블/{c}컬럼이라 적었으나 카탈로그는 "
            f"{n_tables}테이블/{n_cols}컬럼이다")
