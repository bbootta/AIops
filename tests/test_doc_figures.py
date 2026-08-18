"""문서 수치 ↔ 코드 사실 대조 — 손으로 옮겨 적은 값이 다시 새지 않게 한다.

핵심 명제:
  1) 표시된 생성 구간이 최신이면 PASS, 낡으면 FAIL이다.
  2) 표시 **밖**의 과거 회차 기록은 대조하지 않는다 — 거짓 경보가 없다.
     시끄러운 체크는 무시되고, 무시되는 체크는 없는 체크와 같다.
  3) 표시를 지우거나 깨뜨려 침묵시킬 수 없다 — 검사 대상이 사라진 것은
     일치가 아니다.
  4) 다른 기준일 실행으로 만든 표는 통과하지 못한다 (F-501의 원인).

파이프라인을 돌리지 않는다. 세션 픽스처의 `asof`는 2026-06-11(테스트 고정일)
인데 제출본은 2026-06-30이며, 그 차이가 곧 F-501이었다. 이 체크의 시험이
그 고정일에 매달리면 안 된다.
"""

from __future__ import annotations

from types import SimpleNamespace

from risk_lib.validation.doc_figures import (
    check_blocks, check_doc_figures, fill_blocks, generated_blocks,
)

ASOF = "2026-06-30"

# 표시 밖에 있는 과거 회차 기록 — 그 시점에는 옳았고 지금 산출과는 다르다.
_PAST = """# 부적합 시정조치

## 5차 검증 요청

| | 서식 | 라인 |
|---|---:|---:|
| 5차 | 290 | 5,842 |

전체 5,842라인 기준 실측 68.2% · 파생 18.3%.
"""

# 정본 구간이 둘이다 — 표(provenance)와 산문 문장(provenance_sentence).
# F-501이 실제로 틀렸던 것은 문장 쪽이므로 시험 문서도 둘 다 갖는다.
_TEMPLATE = _PAST + """
## 6차 — 산출 근거

<!-- generated: provenance -->
(표가 정본으로 채워진다)
<!-- /generated -->

<!-- generated: provenance_sentence -->
(문장이 정본으로 채워진다)
<!-- /generated -->
"""


_EXPLAINS = """
## 통제 설명

표시 구간은 `<!-- generated: provenance -->` 로 열고 `<!-- /generated -->` 로 닫는다.

```
<!-- generated: provenance -->
(정본으로 채워진다)
<!-- /generated -->
```
"""


def _line(code: str, formula: str):
    return SimpleNamespace(line_code=code, line_name=f"라인 {code}",
                           formula=formula, text_value=None, value=1.0,
                           source_module="test", citation="")


def _built():
    """실측 2 · 파생 1 = 3라인, 서식 2건짜리 최소 빌드."""
    return [
        SimpleNamespace(
            spec=SimpleNamespace(form_id="B1000", form_no_display="B1000",
                                 form_name="서식1", section="제1편"),
            lines=[_line("100", "원장 합계"), _line("200", "원장 합계")]),
        SimpleNamespace(
            spec=SimpleNamespace(form_id="B2000", form_no_display="B2000",
                                 form_name="서식2", section="제1편"),
            lines=[_line("100", "월말 잔액 × exp(σ×z) — 파생값")]),
    ]


def _doc(tmp_path, text: str):
    p = tmp_path / "remediation.md"
    p.write_text(text, encoding="utf-8")
    return p


def _fresh_doc(tmp_path, asof: str = ASOF):
    return _doc(tmp_path, fill_blocks(_TEMPLATE, generated_blocks(_built(), asof)))


def _status(checks) -> dict[str, str]:
    return {c.name: c.status for c in checks}


def test_fresh_block_passes(tmp_path):
    st = _status(check_blocks(_fresh_doc(tmp_path), generated_blocks(_built(), ASOF)))
    assert st == {"doc_figures_provenance": "PASS",
                  "doc_figures_provenance_sentence": "PASS"}


def test_a_single_stale_figure_fails(tmp_path):
    """한 칸만 낡아도 FAIL이고, 어느 행이 어떻게 다른지 말해 준다.

    다른 실행의 실측 라인 수(4,000)를 손으로 옮겨 적은 상황이다.
    """
    blocks = generated_blocks(_built(), ASOF)
    stale = _doc(tmp_path, fill_blocks(_TEMPLATE, {
        **blocks,
        "provenance": blocks["provenance"].replace("| 실측 | 2 |",
                                                   "| 실측 | 4,000 |")}))
    checks = check_blocks(stale, blocks)
    st = _status(checks)
    assert st["doc_figures_provenance"] == "FAIL"
    assert st["doc_figures_provenance_sentence"] == "PASS"   # 낡은 구간만 잡는다
    detail = next(c.detail for c in checks if c.name == "doc_figures_provenance")
    assert "4,000" in detail and "| 실측 | 2 |" in detail


def test_the_block_counts_come_from_the_code():
    """정본은 빌드 결과에서 나온다 — 사람이 고른 숫자가 아니다."""
    body = generated_blocks(_built(), ASOF)["provenance"]
    assert f"기준일 {ASOF} · 서식 2건" in body
    assert "| 실측 | 2 | 66.67% |" in body
    assert "| 파생 | 1 | 33.33% |" in body


def test_a_block_from_another_run_date_does_not_pass(tmp_path):
    """F-501 그 자체 — 다른 기준일 실행의 표를 제출본 설명으로 쓸 수 없다."""
    doc = _fresh_doc(tmp_path, asof="2026-06-11")     # 테스트 고정일로 만든 표
    checks = check_blocks(doc, generated_blocks(_built(), "2026-06-30"))
    st = _status(checks)
    assert st["doc_figures_provenance"] == "FAIL"
    detail = next(c.detail for c in checks if c.name == "doc_figures_provenance")
    assert "2026-06-11" in detail


def test_past_rounds_outside_the_markers_are_never_compared(tmp_path):
    """표시 밖 과거 기록은 현재 산출과 달라도 경보가 되지 않는다."""
    doc = _fresh_doc(tmp_path)
    text = doc.read_text(encoding="utf-8")
    assert _PAST in text                    # 5,842 · 68.2%가 그대로 남아 있다
    assert all(c.status == "PASS"
               for c in check_blocks(doc, generated_blocks(_built(), ASOF)))


def test_filling_does_not_touch_anything_outside_the_markers():
    filled = fill_blocks(_TEMPLATE, generated_blocks(_built(), ASOF))
    assert filled.startswith(_PAST)
    assert filled.count("<!-- generated: provenance -->") == 1
    assert filled.count("<!-- generated: provenance_sentence -->") == 1


def test_filling_does_not_overwrite_the_convention_example():
    """갱신은 대조와 같은 눈으로 읽는다 — 설명 속 예시는 정본이 아니다."""
    filled = fill_blocks(_TEMPLATE + _EXPLAINS, generated_blocks(_built(), ASOF))
    assert filled.count("(정본으로 채워진다)") == 1     # 설명 속 예시만 남는다
    assert filled.endswith(_EXPLAINS)


def test_a_document_without_the_block_is_not_a_silent_pass(tmp_path):
    """검사 대상이 사라진 것과 일치하는 것은 다르다."""
    checks = check_blocks(_doc(tmp_path, _PAST), generated_blocks(_built(), ASOF))
    assert set(_status(checks).values()) == {"FAIL"}         # 구간 전부가 없다
    assert all("생성 구간이 없다" in c.detail for c in checks)


def test_an_unclosed_marker_fails(tmp_path):
    """표시자를 깨뜨려 구간을 대조에서 빼낼 수 없다."""
    doc = _doc(tmp_path, _PAST + "\n<!-- generated: provenance -->\n낡은 표\n")
    statuses = {c.name: c.status for c in
                check_blocks(doc, generated_blocks(_built(), ASOF))}
    assert statuses["doc_figures_marker_closed"] == "FAIL"
    assert statuses["doc_figures_provenance"] == "FAIL"


def test_a_marker_with_no_canonical_source_fails(tmp_path):
    """정본이 없는 이름은 아무도 대조하지 않는다 — 조용히 두지 않는다."""
    doc = _doc(tmp_path, fill_blocks(_TEMPLATE, generated_blocks(_built(), ASOF))
               + "\n<!-- generated: headline -->\n임의의 표\n<!-- /generated -->\n")
    bad = [c for c in check_blocks(doc, generated_blocks(_built(), ASOF))
           if c.status == "FAIL"]
    assert len(bad) == 1 and "headline" in bad[0].detail


def test_the_document_may_explain_the_convention_without_false_alarm(tmp_path):
    """규약을 서술한 문장·예시가 거짓 FAIL을 만들지 않는다.

    시정 문서는 통제를 설명하는 문서라 표시자 문구가 예시로 실린다. 그것을
    실제 구간으로 세면 정본이 최신인데도 FAIL이 풀리지 않고, 그런 체크는
    꺼진다 — 꺼진 체크는 재발을 막지 못한다.
    """
    doc = _doc(tmp_path, fill_blocks(_TEMPLATE + _EXPLAINS,
                                     generated_blocks(_built(), ASOF)))
    assert "(정본으로 채워진다)" in doc.read_text(encoding="utf-8")  # 예시는 그대로
    assert set(_status(check_blocks(
        doc, generated_blocks(_built(), ASOF))).values()) == {"PASS"}


def test_hiding_the_real_block_in_a_code_fence_is_not_a_pass(tmp_path):
    """예시를 봐주는 완화가 침묵 경로가 되지 않는다 — 숨기면 없는 것이다."""
    doc = _doc(tmp_path, "```\n" + fill_blocks(
        _TEMPLATE, generated_blocks(_built(), ASOF)) + "\n```\n")
    checks = check_blocks(doc, generated_blocks(_built(), ASOF))
    assert set(_status(checks).values()) == {"FAIL"}
    assert all("생성 구간이 없다" in c.detail for c in checks)


def test_a_missing_document_fails(tmp_path):
    checks = check_blocks(tmp_path / "없는문서.md", generated_blocks(_built(), ASOF))
    assert [c.status for c in checks] == ["FAIL"]


def test_the_check_is_skipped_when_no_forms_were_built(tmp_path):
    """서식을 빌드하지 않은 실행에는 붙지 않는다 (자체검증의 기존 규약)."""
    assert check_doc_figures(_fresh_doc(tmp_path), None, ASOF) == []
