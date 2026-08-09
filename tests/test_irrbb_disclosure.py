"""[별표 9-1] 제22항 공시서식 <표6>·<표7>. 구조 고정.

**이 양식은 자체 조정이 금지된다**(제22항 나). 그래서 이 파일의 첫 임무는
행·열의 이름과 순서를 그대로 잠그는 것이다. 빌더가 행을 하나 빼거나 순서를
바꾸면 아래 검사가 먼저 깨진다.

  · `test_table6_rows_are_fixed_in_name_and_order`
    `test_table6_columns_are_fixed_in_name_and_order`
    자체 조정 금지 대상. 이름·순서를 리터럴로 적어 두고 대조한다.
  · `test_table6_keeps_every_row_even_when_the_values_are_missing`
    자체 조정 금지 양식에서 행이 사라지면 그것도 조정에 해당한다.
  · `test_a_missing_scenario_stops_the_form`
    6개 시나리오가 전건 있어야 한다. 결손을 행 삭제로 넘기지 않는다.
  · `test_nii_is_blank_for_scenarios_three_to_six_by_rule`
    제14항. ΔNII는 평행 2개만 산출한다. 그 공란은 결측이 아니다.
  · `test_an_unfilled_qualitative_item_shows_as_empty`
    미입력 정성항목이 화면·서식에서 비어 보여야 한다. 지어내지 않는다.
"""

from __future__ import annotations

import pandas as pd
import pytest

from risk_lib.alm.params import IRRBB_SCENARIOS
from risk_lib.datamodel.spec import validate
from risk_lib.regulatory import forms_irrbb_disclosure as D

ASOF = "2026-08-08"

# 자체 조정 금지 양식의 행·열. 원문 <표6>의 순서를 리터럴로 적어 둔다. 코드가
# 바뀌면 이 리스트가 먼저 어긋난다.
TABLE6_ROW_CODES = ["1", "2", "3", "4", "5", "6", "최대값", "기본자본"]
TABLE6_ROW_NAMES = [
    "평행상승", "평행하락", "단기하락·장기상승(스티프너)",
    "단기상승·장기하락(플래트너)", "단기상승", "단기하락",
    "1~6 중 최대값", "기본자본"]
TABLE6_SCENARIOS = [
    "parallel_up", "parallel_down", "steepener", "flattener",
    "short_up", "short_down", None, None]
TABLE6_COL_CODES = ["당기_ΔEVE", "전기_ΔEVE", "당기_ΔNII", "전기_ΔNII"]

QUALITATIVE_COUNT = 8
QUANTITATIVE_CODES = ["NMD_평균_금리개정만기", "NMD_최장_금리개정만기"]

# 제14항. ΔNII는 목표관리기간 1년의 평행상승·평행하락 2개만 산출한다.
NII_SCENARIOS = ("parallel_up", "parallel_down")


# ---------------------------------------------------------------- 도우미

def _result(eve: dict[str, float] | None = None,
            nii: dict[str, float] | None = None) -> pd.DataFrame:
    """`alm_irrbb_result`를 산출기준 하나로 좁힌 모양. 부호 있는 값이다.

    손실이 음수다. 공시는 감소액을 양수로 적으므로 두 표의 부호가 뒤집혀야
    한다는 사실이 검사 대상이 된다.
    """
    eve = eve or {s: -1000.0 - i * 100.0 for i, s in enumerate(IRRBB_SCENARIOS)}
    nii = nii if nii is not None else {s: -50.0 for s in NII_SCENARIOS}
    return pd.DataFrame([{
        "scenario": s, "delta_eve": float(eve[s]),
        "delta_nii": (None if s not in nii else float(nii[s])),
    } for s in IRRBB_SCENARIOS])


def _cell(t6: pd.DataFrame, row_code: str, col_code: str) -> pd.Series:
    hit = t6[(t6["row_code"] == row_code) & (t6["col_code"] == col_code)]
    assert len(hit) == 1, (row_code, col_code)
    return hit.iloc[0]


def _reasons(warns) -> str:
    return " / ".join(w.reason for w in warns)


# ---------------------------------------------------------------- 구조 고정

def test_table6_rows_are_fixed_in_name_and_order():
    """제22항 나. 자체 조정 금지 양식이므로 행 이름과 순서를 잠근다."""
    assert [c for c, _n, _s in D.TABLE6_ROWS] == TABLE6_ROW_CODES
    assert [n for _c, n, _s in D.TABLE6_ROWS] == TABLE6_ROW_NAMES
    assert [s for _c, _n, s in D.TABLE6_ROWS] == TABLE6_SCENARIOS
    # 시나리오 6행은 <표4>의 1~6 번호 순서이며 산출엔진 어휘와 같아야 한다.
    assert TABLE6_SCENARIOS[:6] == list(IRRBB_SCENARIOS)


def test_table6_columns_are_fixed_in_name_and_order():
    assert [c for c, _m, _p in D.TABLE6_COLUMNS] == TABLE6_COL_CODES
    assert [m for _c, m, _p in D.TABLE6_COLUMNS] == [
        "ΔEVE", "ΔEVE", "ΔNII", "ΔNII"]
    assert [p for _c, _m, p in D.TABLE6_COLUMNS] == [
        "당기", "전기", "당기", "전기"]


def test_the_built_form_is_eight_rows_by_four_columns():
    t6, _w = D.build_table6(_result(), _result(), asof=ASOF,
                            tier1_current=1.0e12, tier1_prior=0.9e12)
    assert len(t6) == len(TABLE6_ROW_CODES) * len(TABLE6_COL_CODES) == 32
    assert list(t6["row_code"].drop_duplicates()) == TABLE6_ROW_CODES
    assert list(t6["col_code"].drop_duplicates()) == TABLE6_COL_CODES
    assert list(t6["row_seq"].drop_duplicates()) == list(range(1, 9))
    assert list(t6["col_seq"].drop_duplicates()) == list(range(1, 5))
    # 제22항 나가 자체 조정을 금지하므로 전 행 False다.
    assert not t6["is_adjustable"].any()


def test_the_matrix_view_keeps_the_same_row_and_column_order():
    t6, _w = D.build_table6(_result(), asof=ASOF, tier1_current=1.0e12)
    m = D.table6_matrix(t6)
    assert list(m.index) == TABLE6_ROW_CODES
    assert list(m.columns) == ["row_name"] + TABLE6_COL_CODES
    assert list(m["row_name"]) == TABLE6_ROW_NAMES


def test_table6_keeps_every_row_even_when_the_values_are_missing():
    """값이 하나도 없어도 32행이 나온다. 행이 사라지면 자체 조정에 해당한다."""
    t6, warns = D.build_table6(None, None, asof=ASOF)
    assert len(t6) == 32
    assert t6["value"].isna().all()
    assert t6["blank_reason"].notna().all()
    assert "당기 산출값이 제공되지 않았다" in _reasons(warns)
    m = D.table6_matrix(t6)
    assert list(m.index) == TABLE6_ROW_CODES


def test_a_missing_scenario_stops_the_form():
    partial = _result().iloc[:5]
    with pytest.raises(ValueError, match="자체 조정이 금지"):
        D.build_table6(partial, asof=ASOF)


def test_the_form_validates_against_its_spec():
    specs = {s.name: s for s in D.IRRBB_DISCLOSURE_TABLES}
    t6, _w = D.build_table6(_result(), _result(), asof=ASOF,
                            tier1_current=1.0e12, tier1_prior=0.9e12)
    q, _w2 = D.build_table7_qualitative(asof=ASOF)
    n, _w3 = D.build_table7_quantitative({"NMD_평균_금리개정만기": 2.5},
                                         asof=ASOF)
    assert validate(t6, specs["disc_irrbb_table6"]) == []
    assert validate(q, specs["disc_irrbb_table7_qualitative"]) == []
    assert validate(n, specs["disc_irrbb_table7_quantitative"]) == []


# ---------------------------------------------------------------- <표6> 값

def test_a_loss_is_disclosed_as_a_positive_decline():
    """별표가 부호 규약을 정하지 않는다. 감소액을 양수로 적고 그 사실을 남긴다."""
    t6, _w = D.build_table6(
        _result(eve={s: -1000.0 for s in IRRBB_SCENARIOS}), asof=ASOF)
    assert float(_cell(t6, "1", "당기_ΔEVE")["value"]) == 1000.0
    assert set(t6["sign_convention"]) == {D.SIGN_CONVENTION}


def test_the_max_row_is_the_largest_decline_among_the_six_scenarios():
    eve = {"parallel_up": -1000.0, "parallel_down": 300.0,
           "steepener": -2500.0, "flattener": -700.0,
           "short_up": -100.0, "short_down": 50.0}
    t6, _w = D.build_table6(_result(eve=eve), asof=ASOF)
    assert float(_cell(t6, "최대값", "당기_ΔEVE")["value"]) == 2500.0
    # 이익 시나리오는 음의 감소액으로 남고 최대값에 오르지 않는다.
    assert float(_cell(t6, "2", "당기_ΔEVE")["value"]) == -300.0


def test_nii_is_blank_for_scenarios_three_to_six_by_rule():
    """제14항. ΔNII는 평행상승·평행하락 2개만 산출한다. 결측이 아니다."""
    t6, _w = D.build_table6(_result(), asof=ASOF)
    for code in ("1", "2"):
        assert _cell(t6, code, "당기_ΔNII")["value"] == 50.0
    for code in ("3", "4", "5", "6"):
        cell = _cell(t6, code, "당기_ΔNII")
        assert pd.isna(cell["value"])
        assert "제14항" in cell["blank_reason"]


def test_the_prior_period_is_left_empty_not_copied_from_the_current():
    t6, warns = D.build_table6(_result(), None, asof=ASOF,
                               tier1_current=1.0e12)
    assert float(_cell(t6, "1", "당기_ΔEVE")["value"]) == 1000.0
    prior = _cell(t6, "1", "전기_ΔEVE")
    assert pd.isna(prior["value"])
    assert prior["blank_reason"] == "전기 산출값이 제공되지 않았다"
    assert "전기 산출값이 제공되지 않았다" in _reasons(warns)


def test_tier1_sits_in_the_eve_columns_and_the_nii_columns_stay_blank():
    t6, _w = D.build_table6(_result(), _result(), asof=ASOF,
                            tier1_current=1.0e12, tier1_prior=0.9e12)
    assert float(_cell(t6, "기본자본", "당기_ΔEVE")["value"]) == 1.0e12
    assert float(_cell(t6, "기본자본", "전기_ΔEVE")["value"]) == 0.9e12
    nii = _cell(t6, "기본자본", "당기_ΔNII")
    assert pd.isna(nii["value"])
    assert "기간별 값 하나" in nii["blank_reason"]
    # 기본자본 행의 지표는 ΔEVE가 아니라 기본자본으로 남는다.
    tier = t6[t6["row_code"] == "기본자본"]
    assert set(tier["measure"]) == {"기본자본"}


def test_a_missing_tier1_leaves_the_row_empty_and_warns():
    t6, warns = D.build_table6(_result(), asof=ASOF)
    cell = _cell(t6, "기본자본", "당기_ΔEVE")
    assert pd.isna(cell["value"])
    assert cell["blank_reason"] == "기본자본이 제공되지 않았다"
    assert "기본자본이 제공되지 않았다" in _reasons(warns)


# ---------------------------------------------------------------- <표7> 정성

def test_the_qualitative_form_has_eight_items_and_only_the_last_is_optional():
    q, _w = D.build_table7_qualitative(asof=ASOF)
    assert list(q["item_no"]) == list(range(1, QUALITATIVE_COUNT + 1))
    assert list(q["is_optional"]) == [False] * 7 + [True]
    assert "IRRBB의 정의" in q["item_name"].iloc[0]
    assert "기타 정보" in q["item_name"].iloc[7]


def test_an_unfilled_qualitative_item_shows_as_empty():
    """미입력 항목이 화면·서식에서 비어 보여야 한다. 문안을 지어내지 않는다."""
    q, warns = D.build_table7_qualitative(asof=ASOF)
    assert len(q) == QUALITATIVE_COUNT
    assert q["narrative"].isna().all()
    assert not q["is_disclosed"].any()
    assert not q["is_approved"].any()
    # 필수 7항목만 경고가 나간다. 8번(기타 정보)은 선택사항이다.
    assert {w.scope for w in warns} == {
        f"정성공시 {n}" for n in range(1, QUALITATIVE_COUNT)}


def test_a_filled_item_is_disclosed_and_the_rest_stay_visible_as_blanks():
    q, _w = D.build_table7_qualitative(pd.DataFrame([{
        "item_no": 1, "narrative": "IRRBB는 금리변동이 은행계정에 미치는 영향이다",
        "input_by": "ALM팀 김", "approved_by": "리스크관리책임자 이",
        "approved_date": "2026-08-01"}]), asof=ASOF)
    assert len(q) == QUALITATIVE_COUNT
    first = q[q["item_no"] == 1].iloc[0]
    assert bool(first["is_disclosed"]) is True
    assert bool(first["is_approved"]) is True
    assert first["input_by"] == "ALM팀 김"
    rest = q[q["item_no"] != 1]
    assert not rest["is_disclosed"].any()
    assert rest["narrative"].isna().all()


def test_an_unapproved_narrative_is_flagged():
    q, warns = D.build_table7_qualitative(pd.DataFrame([{
        "item_no": 3, "narrative": "분기 1회 이상 측정한다", "input_by": "ALM팀 김",
        "approved_by": None, "approved_date": None}]), asof=ASOF)
    row = q[q["item_no"] == 3].iloc[0]
    assert bool(row["is_disclosed"]) is True
    assert bool(row["is_approved"]) is False
    assert "승인자 또는 승인일이 없다" in _reasons(warns)


def test_a_blank_narrative_string_counts_as_unfilled():
    q, _w = D.build_table7_qualitative(pd.DataFrame([
        {"item_no": 2, "narrative": "   "}]), asof=ASOF)
    row = q[q["item_no"] == 2].iloc[0]
    assert row["narrative"] is None
    assert bool(row["is_disclosed"]) is False


def test_an_unknown_qualitative_item_number_is_refused():
    with pytest.raises(ValueError, match="자체 조정이 금지"):
        D.build_table7_qualitative(
            pd.DataFrame([{"item_no": 9, "narrative": "추가 항목"}]), asof=ASOF)


# ---------------------------------------------------------------- <표7> 정량

def test_the_quantitative_form_has_the_two_repricing_maturities():
    n, _w = D.build_table7_quantitative(asof=ASOF)
    assert list(n["item_code"]) == QUANTITATIVE_CODES
    assert set(n["value_unit"]) == {"years"}
    assert n["value"].isna().all()
    assert not n["is_disclosed"].any()


def test_a_missing_quantitative_value_stays_empty_and_warns():
    n, warns = D.build_table7_quantitative(
        {"NMD_평균_금리개정만기": 2.5}, asof=ASOF,
        basis={"NMD_평균_금리개정만기": "핵심예금 슬로팅 가중평균"})
    avg = n[n["item_code"] == "NMD_평균_금리개정만기"].iloc[0]
    longest = n[n["item_code"] == "NMD_최장_금리개정만기"].iloc[0]
    assert float(avg["value"]) == 2.5
    assert bool(avg["is_disclosed"]) is True
    assert avg["basis"] == "핵심예금 슬로팅 가중평균"
    assert pd.isna(longest["value"])
    assert bool(longest["is_disclosed"]) is False
    assert "넘어오지 않았다" in _reasons(warns)


def test_an_unknown_quantitative_code_is_refused():
    with pytest.raises(ValueError, match="자체 조정이 금지"):
        D.build_table7_quantitative({"NMD_중앙값_금리개정만기": 1.0}, asof=ASOF)


# ---------------------------------------------------------------- 결정론

def test_the_disclosure_ledgers_are_byte_identical_for_the_same_asof():
    entries = pd.DataFrame([{
        "item_no": 1, "narrative": "정의", "input_by": "김",
        "approved_by": "이", "approved_date": "2026-08-01"}])

    def _run() -> list[str]:
        t6, _w1 = D.build_table6(_result(), _result(), asof=ASOF,
                                 tier1_current=1.0e12, tier1_prior=0.9e12)
        q, _w2 = D.build_table7_qualitative(entries, asof=ASOF)
        n, _w3 = D.build_table7_quantitative({"NMD_평균_금리개정만기": 2.5},
                                             asof=ASOF)
        return [d.to_csv(index=False) for d in (t6, q, n)]

    assert _run() == _run()
