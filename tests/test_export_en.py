"""공개 배포용 영문 빌드 변환기 (risk_lib/ui_studio/export_en.py).

원장 값은 전부 옮길 수 있을 때만 옮기고, 모르는 낱말이 섞인 문장은 원문 그대로 둔다.
SHA-256 지문은 표의 컬럼째로 빠지고, 경영진 요약은 틀째로 옮긴다.
"""
from __future__ import annotations

from risk_lib.ui_studio import export_en as ex


def _tr():
    return ex.Translator({"여신": "Loans", "위험가중자산": "Risk-weighted assets", "국가 HHI": "Country HHI",
                          "자본 스택": "Capital stack", "귀속분석": "Attribution", "신용 IRB": "Credit IRB"})


def test_all_or_nothing_translation():
    t = _tr()
    assert t.text("여신 (Level 2A) — 위험가중자산") == "Loans (Level 2A) — Risk-weighted assets"
    assert t.text("US · 여신 · 1,080건") == "US · Loans · 1,080"
    assert t.text("제26조의2") == "Article 26-2"
    untouched = "여신은 모르는 낱말과 함께 있다"
    assert t.text(untouched) == untouched                # 문장꼴은 통째로 사전에 있을 때만
    assert t.text("여신 · 알수없는낱말") == "여신 · 알수없는낱말"   # 낱말 하나라도 모르면 원문
    assert t.text("plain ascii") == "plain ascii"


def test_executive_briefing_is_translated_by_template():
    t = _tr()
    s = ("<b>자본</b> — CET1 11.29%로 요구치 대비 +1.79%p 여유. RWA의 최대 구성은 <b>신용 IRB</b>(49%)로, "
         "자본비율 방어의 1차 레버는 이 부문의 한도·성장 관리다. "
         '<a href="ops/32_capital_stack.html">→ 자본 스택</a> · <a href="ops/23_attribution.html">→ 귀속분석</a>')
    out = t.text(s)
    assert out.startswith("<b>Capital</b>: CET1 11.29%, +1.79%p above the requirement")
    assert "<b>Credit IRB</b> (49%)" in out and "→ Capital stack</a>" in out and "→ Attribution</a>" in out
    a = t.text("[RED] <b>국가 HHI</b> 즉시 대응 — 실측 0.630 vs board 한계 0.250 (concentration, DOJ/FTC)")
    assert a == "[RED] <b>Country HHI</b> immediate action: actual 0.630 vs board limit 0.250 (concentration, DOJ/FTC)"


def test_scrub_hashes_drops_columns_and_hex():
    h = "a" * 64
    pl = {"meta": {"digest": h, "run_id": "R1"},
          "data": {"t": {"columns": ["x", "sha256", "fingerprint"], "labels": ["X", "S", "F"],
                         "rows": [[1, h, h]], "total": 1, "shown": 1}},
          "note": f"지문 {h} 끝"}
    out = ex.scrub_hashes(pl)
    assert out["meta"]["digest"] == "" and out["meta"]["run_id"] == "R1"
    assert out["data"]["t"]["columns"] == ["x"] and out["data"]["t"]["labels"] == ["X"]
    assert out["data"]["t"]["rows"] == [[1]]
    assert out["note"] == "지문  끝"


def test_dictionary_file_is_clean():
    d = ex.load_dictionary()
    assert len(d) >= 3000
    assert all(ex.HANGUL.search(k) for k in d)
    assert not any(ex.HANGUL.search(v) for v in d.values())
    assert not any("—" in v or "–" in v for v in d.values())
