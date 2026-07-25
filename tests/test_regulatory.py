"""금감원 업무보고서 — 서식 구조·값·자체대사·엑셀 산출.

핵심 명제 세 가지:
  1) 서식 값은 파이프라인 공표값과 **정확히** 일치한다(따로 계산하지 않는다).
  2) 모든 소계·비율은 서식이 스스로 대사하고, 실패가 있으면 제출 상태로
     올라가지 않는다.
  3) 모든 라인은 산출 근거(모듈)를 갖거나, 근거가 없는 이유가 분명하다.
"""

from __future__ import annotations

import pytest
from openpyxl import load_workbook

from risk_lib.datamodel import catalog as cat
from risk_lib.datamodel.spec import validate
from risk_lib.regulatory import build_forms, form_frames, write_workbook
from risk_lib.regulatory.forms import FORMS, FormCheck, submission_digest


@pytest.fixture(scope="module")
def tables(result, portfolio):
    from risk_lib.ui_studio.studio import build_studio
    return build_studio(result, portfolio).tables


@pytest.fixture(scope="module")
def built(result, portfolio, tables):
    return build_forms(result, portfolio, tables)


# ----- 구조 -------------------------------------------------------------------

def test_every_form_builds_with_lines(built):
    assert len(built) == len(FORMS)
    for b in built:
        assert b.lines, f"{b.spec.form_id} 라인 없음"
        assert b.spec.citation, f"{b.spec.form_id} 근거 규정 없음"


def test_line_codes_unique_within_form(built):
    for b in built:
        codes = [ln.line_code for ln in b.lines]
        assert len(codes) == len(set(codes)), f"{b.spec.form_id} 라인코드 중복"


def test_sheet_order_is_unique_and_dense():
    orders = sorted(f.sheet_order for f in FORMS)
    assert orders == list(range(1, len(FORMS) + 1))


def test_units_are_declared_and_values_match_unit(built):
    for b in built:
        for ln in b.lines:
            assert ln.unit in ("KRW", "ratio", "count", "text")
            if ln.unit == "text":
                assert ln.value is None and ln.text_value
            else:
                assert ln.value is not None, f"{b.spec.form_id}/{ln.line_code}"


def test_ratio_lines_are_fractions_not_percents(built):
    """비율은 0.115로 담는다. 11.5로 담으면 엑셀 서식이 1150%로 표시된다."""
    for b in built:
        for ln in b.lines:
            if ln.unit == "ratio" and ln.value is not None:
                assert -5.0 <= ln.value <= 5.0, f"{b.spec.form_id}/{ln.line_code}"


# ----- 자체 대사 --------------------------------------------------------------

def test_all_form_checks_pass(built):
    failed = [(b.spec.form_id, c.check_name, c.expected, c.actual)
              for b in built for c in b.checks if c.status == "FAIL"]
    assert failed == [], failed


def test_every_form_has_at_least_one_check(built):
    for b in built:
        assert b.checks, f"{b.spec.form_id} 자체대사 없음 — 제출 전 오류를 못 잡는다"


def test_failed_check_blocks_approval_status(built):
    """검증 실패가 있으면 제출 상태가 approved로 올라가지 않는다."""
    frames = form_frames(built, "2026-06-11")
    subs = frames["reg_submission"]
    assert (subs.loc[subs["n_failed_checks"] > 0, "status"] == "draft").all()
    assert (subs.loc[subs["n_failed_checks"] == 0, "status"] == "approved").all()


def test_check_status_is_tolerance_driven():
    assert FormCheck("t", 100.0, 100.5, tolerance=1.0).status == "PASS"
    assert FormCheck("t", 100.0, 102.0, tolerance=1.0).status == "FAIL"


# ----- 공표값 대사 ------------------------------------------------------------

def _line(built, form_id, code):
    b = next(x for x in built if x.spec.form_id == form_id)
    return next(ln for ln in b.lines if ln.line_code == code)


def test_capital_ratio_lines_match_pipeline(built, result):
    assert _line(built, "BR-01", "3100").value == pytest.approx(
        result.bis.cet1_ratio, rel=1e-15)
    assert _line(built, "BR-01", "3300").value == pytest.approx(
        result.bis.total_ratio, rel=1e-15)
    assert _line(built, "BR-01", "2000").value == pytest.approx(
        result.rwa["final_total"], rel=1e-15)


def test_sa_form_total_matches_pipeline_sa_rwa(built, result):
    assert _line(built, "BR-03", "1000").value == pytest.approx(
        result.rwa["sa"], rel=1e-9)


def test_irb_form_total_matches_pipeline_irb_rwa(built, result):
    assert _line(built, "BR-04", "1000").value == pytest.approx(
        result.rwa["irb"], rel=1e-9)


def test_lcr_form_matches_alm_engine(built, result):
    assert _line(built, "BR-08", "5000").value == pytest.approx(
        result.alm["lcr"].lcr, rel=1e-15)


def test_leverage_form_matches_engine(built, result):
    assert _line(built, "BR-07", "3000").value == pytest.approx(
        result.leverage.leverage_ratio, rel=1e-15)


def test_irrbb_outlier_flag_uses_the_method_not_the_bound_method(built, result):
    """`bool(irr.outlier)`는 바운드 메서드라 항상 참이다 — 실제 판정과 대사한다."""
    flag = _line(built, "BR-13", "3300").value
    assert flag == (1.0 if result.alm["irrbb"].outlier() else 0.0)


def test_asset_quality_form_matches_the_canonical_table(built, tables):
    aq = tables["rdm_asset_quality"]
    assert _line(built, "BR-10", "1000").value == pytest.approx(
        float(aq["balance"].sum()), rel=1e-12)
    assert _line(built, "BR-10", "1010").value == float(len(aq))


def test_reserve_shortfall_is_exposure_level_not_netted(built, tables):
    """익스포저 단위 max(0, ·) 합계는 총액 기준 차액보다 작을 수 없다.

    총액에서 상계하면 과대충당 익스포저가 과소충당을 가려 대손준비금이 과소산정된다.
    """
    per_exposure = _line(built, "BR-11", "3000").value
    netted = _line(built, "BR-11", "4000").value
    assert per_exposure >= netted - 1.0


# ----- 근거·재현 --------------------------------------------------------------

def test_value_lines_carry_a_source_module_or_a_citation(built):
    for b in built:
        for ln in b.lines:
            if ln.unit == "text":
                continue
            assert ln.source_module or ln.citation, \
                f"{b.spec.form_id}/{ln.line_code} 근거 없음"


def test_digest_is_stable_and_value_sensitive(built):
    d1 = submission_digest(built)
    assert d1 == submission_digest(built)
    import copy
    mutated = copy.deepcopy(built)
    object.__setattr__(mutated[0].lines[0], "value",
                       (mutated[0].lines[0].value or 0.0) + 1.0)
    assert submission_digest(mutated) != d1


# ----- 정규 테이블 실체화 ------------------------------------------------------

def test_form_frames_satisfy_the_catalog_spec(built):
    frames = form_frames(built, "2026-06-11")
    specs = {s.name: s for s in cat.ALL_TABLES}
    for name, df in frames.items():
        bad = [v for v in validate(df, specs[name]) if v.severity == "FAIL"]
        assert bad == [], (name, bad)


def test_form_lines_reference_registered_forms(built):
    frames = form_frames(built, "2026-06-11")
    assert set(frames["reg_form_line"]["form_id"]) <= set(frames["reg_form"]["form_id"])


# ----- 엑셀 -------------------------------------------------------------------

def test_workbook_has_a_sheet_per_form_plus_control_sheets(built, tmp_path):
    p = write_workbook(built, tmp_path / "br.xlsx", asof="2026-06-11",
                       meta={"seed": 42})
    wb = load_workbook(p)
    assert wb.sheetnames[0] == "표지"
    assert wb.sheetnames[1] == "목차"
    for b in built:
        assert b.spec.form_id in wb.sheetnames
    assert "검증" in wb.sheetnames and "산출근거" in wb.sheetnames


def test_workbook_values_round_trip(built, tmp_path):
    p = write_workbook(built, tmp_path / "br.xlsx", asof="2026-06-11",
                       meta={"seed": 42})
    wb = load_workbook(p, data_only=True)
    ws = wb["BR-01"]
    found = {}
    for row in ws.iter_rows(min_row=5, values_only=True):
        if row[0]:
            found[str(row[0])] = row[3]
    b = next(x for x in built if x.spec.form_id == "BR-01")
    for ln in b.lines:
        if ln.unit != "text":
            assert found[ln.line_code] == pytest.approx(ln.value, rel=1e-12)


def test_workbook_cover_carries_the_digest(built, tmp_path):
    p = write_workbook(built, tmp_path / "br.xlsx", asof="2026-06-11",
                       meta={"seed": 42})
    wb = load_workbook(p)
    text = "\n".join(str(c.value) for row in wb["표지"].iter_rows()
                     for c in row if c.value)
    assert submission_digest(built) in text
    # 서식번호 전제를 표지에 남기지 않으면 배포본 매핑 시 잘못 대응된다.
    assert "서식번호" in text
