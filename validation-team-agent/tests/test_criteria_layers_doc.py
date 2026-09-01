"""docs/criteria_layers.md 의 집계 숫자가 카탈로그와 같은지 본다.

문서의 숫자는 손으로 적는다. 카탈로그가 바뀌면 낡는다는 사실을 테스트가
드러내지 않으면 아무도 모른다: 실제로 63건·임계 10건이라 적힌 채 69건·11건이
된 적이 있다.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from tools import domain_criteria as dcr
from tools import regulatory_criteria as rc

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "criteria_layers.md"


def _doc() -> str:
    return DOC.read_text(encoding="utf-8")


def test_regulatory_totals_in_the_doc_match_the_catalog():
    cat = rc.load()
    items = cat["criteria"]
    auto = Counter(c["automation"] for c in items)
    gov = Counter(c["governing"] for c in items)
    src = Counter(c["source_key"] for c in items)
    text = _doc()
    assert f"{len(items)}건 (자동 {auto['automated']} · 수동 {auto['manual']})" in text
    assert f"계량 임계 {len(cat['thresholds'])}건" in text
    assert re.search(rf"총 {len(items)}건 · 자동 {auto['automated']} · 수동 {auto['manual']}\s+"
                     rf"\(규정 {src['규정']} · 세칙 {src['세칙']} · 바젤 {src['바젤']}\)", text)
    assert re.search(rf"지배 국내\s+{gov['국내']}건", text)
    assert re.search(rf"지배 바젤\s+{gov['바젤']}건", text)
    assert re.search(rf"지배 국내\+바젤보충\s+{gov['국내+바젤보충']}건", text)


def test_domain_totals_in_the_doc_match_the_catalog():
    cat = dcr.load()
    items = cat["criteria"]
    auto = Counter(c["automation"] for c in items)
    assert (f"총 {len(items)}건 · 자동 {auto['automated']} · 수동 {auto['manual']} "
            f"· 범위밖 {auto['out_of_scope']}") in _doc()


def test_threshold_count_in_the_doc_matches_everywhere_it_is_written():
    n = len(rc.load()["thresholds"])
    text = _doc()
    stale = {m for m in re.findall(r"계량 임계 (\d+)건", text)} | \
            {m for m in re.findall(r"임계 (\d+)건을 하니스", text)} | \
            {m for m in re.findall(r"현재 (\d+)건 전부 일치", text)}
    assert stale == {str(n)}, f"문서의 임계 건수 {sorted(stale)} 이 카탈로그 {n} 과 다르다"
