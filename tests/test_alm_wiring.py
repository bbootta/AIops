"""ALM 원장 배선 — 카탈로그·파이프라인·실체화·독립검증이 한 벌인지 고정한다.

엔진이 맞는 값을 내도 배선이 끊기면 산출물에는 아무것도 남지 않는다. 이
저장소가 실제로 그 상태였다:

  · `materialize.py:327,342`가 `IRRBBResult`에 없는 `by_scenario`·`worst_eve`를
    `getattr`로 찾다 실패해 `alm_irrbb_shock`이 6행이 아니라 **1행,
    delta_eve=0.0**이었고, 화면은 그 원장에서 막대를 그려 전 구간 0을 그렸다.
  · `catalog.ALM_METRICS`가 선언한 `IRRBB_NII` 행은 **어디에서도 만들어지지
    않았다** — 4개 중 3개만 존재했다.
  · `independent.RECALC_SCOPE`에 IRRBB가 없어 이사회 KPI·제출서식으로 나가는
    수치를 3선이 다시 계산하지 않았다.

따라서 이 파일의 검사는 값이 아니라 **연결**을 본다. 각 검사는 위 결함을
되돌리면 실패한다.
"""

from __future__ import annotations

import pandas as pd
import pytest

from risk_lib.datamodel import catalog as cat
from risk_lib.datamodel.spec import validate


@pytest.fixture(scope="module")
def studio(result, portfolio):
    from risk_lib.ui_studio.studio import build_studio
    return build_studio(result, portfolio)


# ---------------------------------------------------------------- 카탈로그

def test_alm_ledger_specs_are_defined_once_in_the_engine_modules():
    """스펙 객체가 엔진 모듈의 것과 **같은 객체**여야 한다.

    카탈로그가 컬럼을 옮겨 적으면 스펙과 그것을 채우는 코드가 갈라진다.
    실제로 `alm_nsfr_item`은 정의가 둘이었고(카탈로그 6컬럼 / 엔진 9컬럼),
    검증이 어느 쪽을 쓰는지가 import 순서에 달려 있었다.
    """
    from risk_lib.alm import cashflow, curves, irrbb, lcr, liquidity, nii, nsfr
    from risk_lib.alm import params
    from risk_lib.alm.contracts import CONTRACT

    engine = {s.name: s for group in (
        params.PARAM_TABLES, (CONTRACT,), cashflow.CASHFLOW_TABLES,
        curves.CURVE_TABLES, irrbb.IRRBB_TABLES, (nii.NII_RESULT,),
        lcr.LCR_TABLES, nsfr.NSFR_TABLES, liquidity.LIQUIDITY_TABLES,
    ) for s in group}
    registered = {s.name: s for s in cat.ALM_LEDGER_TABLES}

    assert set(registered) == set(engine)
    for name, spec in registered.items():
        assert spec is engine[name], f"{name}: 카탈로그가 스펙을 복사했다"


def test_catalog_declares_each_table_exactly_once():
    """같은 이름의 TableSpec이 둘이면 마지막 것이 조용히 이긴다."""
    names = [s.name for s in cat.ALL_TABLES]
    dupes = sorted({n for n in names if names.count(n) > 1})
    assert dupes == [], f"중복 선언: {dupes}"


def test_every_alm_ledger_has_grain_and_primary_key():
    for s in cat.ALM_LEDGER_TABLES:
        assert s.grain, f"{s.name}: grain 없음"
        assert s.primary_key, f"{s.name}: primary_key 없음"
        for c in s.columns:
            if c.dtype == "float":
                assert c.unit, f"{s.name}.{c.name}: float인데 unit 없음"


def test_alm_foreign_keys_point_at_registered_tables():
    declared = {s.name for s in cat.ALL_TABLES}
    for s in cat.ALM_LEDGER_TABLES:
        for fk in s.foreign_keys:
            assert fk.ref_table in declared, (
                f"{s.name} → {fk.ref_table}: FK 대상이 카탈로그에 없다")


# ---------------------------------------------------------------- 파이프라인

def test_pipeline_exposes_every_alm_ledger(result):
    """`PipelineResult.alm_tables`가 등재된 23장을 전부 들고 나온다.

    화면이 산출 객체에서 원장을 다시 만들면 자본비율이 쓴 산출과 화면이 두
    벌이 된다 — 구조화 원장이 이미 이 규약을 쓰고 있다.
    """
    want = {s.name for s in cat.ALM_LEDGER_TABLES}
    assert set(result.alm_tables) == want
    empty = sorted(n for n, df in result.alm_tables.items() if not len(df))
    assert empty == [], f"비어 있는 원장: {empty}"


def test_alm_ledgers_are_all_materialised(studio):
    """조립 결과에 23장이 다 있고 스펙 검증을 통과한다."""
    specs = {s.name: s for s in cat.ALM_LEDGER_TABLES}
    missing = sorted(set(specs) - set(studio.tables))
    assert missing == [], f"실체화되지 않은 ALM 원장: {missing}"
    for name, spec in specs.items():
        assert validate(studio.tables[name], spec) == [], name


def test_pipeline_and_studio_share_the_same_alm_frames(result, studio):
    """실체화가 원장을 다시 만들면 같은 값이 나올 것이라는 기대에 기대게 된다.
    기대는 통제가 아니므로 **같은 객체**인지 본다."""
    for name in result.alm_tables:
        assert studio.tables[name] is result.alm_tables[name], name


# ---------------------------------------------------------------- 산출 원장

def test_irrbb_shock_ledger_has_all_six_scenarios(studio):
    """`getattr` 폴백 결함이 되돌아오면 1행·delta_eve=0으로 떨어진다."""
    s = studio.tables["alm_irrbb_shock"]
    assert set(s["scenario"]) == set(cat.IRRBB_SCENARIOS)
    assert len(s) == len(cat.IRRBB_SCENARIOS)
    assert (s["delta_eve"].abs() > 0).all(), "전 시나리오 ΔEVE가 0이다"


def test_irrbb_result_carries_both_bases(studio):
    """계약기준과 행동조정기준을 나란히 담아야 감독당국 비교가 성립한다."""
    r = studio.tables["alm_irrbb_result"]
    assert set(r["basis"]) == {"계약", "행동조정"}
    assert len(r) == 2 * len(cat.IRRBB_SCENARIOS)
    # 비만기예금이 계약기준에서는 최단 버킷, 행동기준에서는 수년에 퍼진다 —
    # 두 값이 같으면 행동모형이 ΔEVE에 닿지 않고 있다는 뜻이다.
    worst = r.groupby("basis")["delta_eve"].min()
    assert worst["계약"] != pytest.approx(worst["행동조정"], rel=1e-3)


def test_alm_result_covers_every_declared_metric(studio):
    """`ALM_METRICS`가 선언한 IRRBB_NII 행이 실제로 만들어진다."""
    a = studio.tables["alm_result"]
    assert set(a["metric"]) == set(cat.ALM_METRICS)
    nii = a[a["metric"] == "IRRBB_NII"].iloc[0]
    assert nii["denominator"] > 0
    assert nii["value"] == pytest.approx(
        nii["numerator"] / nii["denominator"], rel=1e-9)
    # ΔNII 한도의 1차자료를 확인하지 못했다 — 판정은 보류다.
    assert pd.isna(nii["passes"])


def test_repricing_gap_stays_a_balance_ladder(studio, result):
    """`alm_repricing_gap`은 잔액 사다리다 — 서식 B2601이 "잔액기준"이다.

    현금흐름 사다리(`alm_maturity_ladder`)를 여기에 넣으면 이자 현금흐름이
    잔액에 섞여 "배분 자산 = 대출채권 + HQLA" 대사가 깨진다. 실제로 깨졌다.
    """
    bs = result.alm["balance_sheet"]
    g = studio.tables["alm_repricing_gap"]
    assert float(g["asset"].sum()) == pytest.approx(
        bs.loans + sum(bs.hqla.values()), rel=1e-9)


def test_maturity_ladder_is_a_separate_axis_from_the_repricing_gap(studio):
    """두 사다리가 같으면 축 혼용이 재발한 것이다 (설계 §2.7)."""
    gap = studio.tables["alm_repricing_gap"].set_index("bucket")["asset"]
    lad = studio.tables["alm_maturity_ladder"]
    lad = lad[(lad["basis"] == "행동조정") & (lad["scenario"] == "base")]
    inflow = lad.set_index("bucket")["inflow"]
    common = gap.index.intersection(inflow.index)
    assert len(common) > 0
    assert not all(gap[b] == pytest.approx(inflow[b]) for b in common)


# ---------------------------------------------------------------- 정합성 검사

# `alm_bucket_pv_ties_to_delta_eve`는 이름을 바꿨다. 결과 원장의 delta_eve가
# 버킷 원장 delta_pv의 합으로 **정의**되므로 같은 프레임을 다시 접어 비교하는
# 것은 항등식이었고, 충격곡선을 통째로 무력화해도 통과했다. 그 자리는 짝
# 검증(`..._pairs_with_irrbb_result`)으로 남기고, 값 검증은 모수 원장에서
# 할인계수를 다시 만드는 `alm_delta_eve_independent_recalc`가 맡는다.
_TIE_CHECKS = ("alm_cf_ties_to_notional",
               "alm_bucket_pv_pairs_with_irrbb_result",
               "alm_delta_eve_independent_recalc",
               "alm_ladder_ties_to_cashflow")


def test_alm_ledger_ties_run_and_pass(result):
    by_name = {c.name: c for c in result.validation.checks}
    for name in _TIE_CHECKS:
        assert name in by_name, f"{name} 검사가 돌지 않았다"
        assert by_name[name].status == "PASS", by_name[name].detail


def test_unconfirmed_parameters_are_reported_not_swallowed(result):
    """KRW 충격 모수가 비어 USD 프록시를 쓰는 사실이 매 실행 드러나야 한다."""
    by_name = {c.name: c for c in result.validation.checks}
    used = by_name["alm_unconfirmed_param_in_use"]
    assert used.status == "WARN"
    assert "프록시" in used.detail
    warned = by_name["alm_behaviour_param_warnings"]
    assert warned.status == "WARN"
    assert warned.metric == pytest.approx(len(result.alm["warnings"]))


# ---------------------------------------------------------------- 독립검증

def test_recalc_scope_covers_the_alm_headlines():
    from risk_lib.validation.independent import RECALC_SCOPE
    keys = {k for k, _ko, _c in RECALC_SCOPE}
    assert {"lcr", "nsfr", "irrbb_worst_pct_tier1",
            "irrbb_delta_nii_parallel", "survival_days"} <= keys


def test_independent_request_carries_the_alm_values(studio, result):
    """범위에 넣기만 하고 값이 비면 3선이 대조할 것이 없다."""
    targets = {t["key"]: t for t in studio.iv_request.recalc_targets}
    assert targets["irrbb_worst_pct_tier1"]["value"] == pytest.approx(
        result.alm["irrbb"].worst_pct_tier1)
    assert targets["irrbb_delta_nii_parallel"]["value"] == pytest.approx(
        float(result.alm["nii"].result["delta_nii"].min()))
    # 생존기간은 시계에서 우측절단된다 — 소진일이 없으면 시계 길이가 값이고,
    # 그 사실이 대상의 근거란에 적혀 있어야 절단값이 소진일로 읽히지 않는다.
    sv = result.alm["survival"]
    breach = sv.survival_days.get("기관고유")
    path = sv.path[sv.path["scenario"] == "기관고유"]
    expected = float(breach) if breach is not None else float(path["day"].max())
    assert targets["survival_days"]["value"] == pytest.approx(expected)
    assert "절단" in targets["survival_days"]["citation"]
