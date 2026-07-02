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
