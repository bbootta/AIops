"""신규 원장 배선 — 카탈로그·파이프라인·검증·요건추적이 같은 사실을 말하는가.

이 파일이 겨냥하는 결함은 하나다. **원장이 존재하는 것과 실행이 그 원장을
만드는 것은 다르다.** 스펙만 등재해 두면 화면은 빈 표를 그리고, 반대로 산출만
하고 등재하지 않으면 검증·DQ 규칙이 그 원장을 보지 못한다. 여기서는 둘이
붙어 있는지를 본다.

  · `test_every_new_ledger_spec_is_registered_or_excluded_with_a_reason`
    등재하지 않은 신규 스펙이 있으면 그 사유가 카탈로그에 적혀 있어야 한다.
    조용히 빠지면 "만들었는데 아무도 안 쓴다"가 발견되지 않는다.
  · `test_limit_definitions_come_from_the_ledger`
    원장을 비우면 한도 산출도 비어야 한다. 비지 않으면 임계가 코드에 남아
    있다는 뜻이다.
  · `test_irrbb_headline_account_is_not_the_repealed_one`
    파이프라인 헤드라인이 d368_2016(KRW 300/400/200 · 하한 없음)으로 돌아가면
    폐지된 기준으로 산출한 ΔEVE가 결재로 넘어간다.
"""

from __future__ import annotations

import warnings

import pandas as pd
import pytest

from risk_lib.datamodel import catalog as cat


# ---------------------------------------------------------------- 카탈로그 등재

def test_new_ledger_tables_are_all_in_all_tables():
    """R15 묶음이 `ALL_TABLES`에 빠짐없이 들어갔는가."""
    registered = {t.name for t in cat.ALL_TABLES}
    missing = sorted({t.name for t in cat.NEW_LEDGER_TABLES} - registered)
    assert not missing, f"R15 묶음에 있으나 ALL_TABLES에 없는 테이블: {missing}"


def test_every_new_ledger_spec_is_registered_or_excluded_with_a_reason():
    """등재하지 않은 신규 스펙은 카탈로그에 사유가 적혀 있어야 한다.

    모듈에 TableSpec을 만들어 두고 카탈로그에 넣지 않으면 그 원장은 검증·DQ
    규칙·화면 어디에도 나타나지 않는다. 만든 사람만 아는 원장이 되는 것이므로,
    빼는 것 자체는 괜찮아도 **왜 뺐는지가 소스에 있어야** 한다.
    """
    import importlib
    import pkgutil
    from pathlib import Path

    import risk_lib
    from risk_lib.datamodel.spec import TableSpec

    registered = {t.name for t in cat.ALL_TABLES}
    unregistered: set[str] = set()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for m in pkgutil.walk_packages(risk_lib.__path__, "risk_lib."):
            try:
                mod = importlib.import_module(m.name)
            except Exception:                              # noqa: BLE001
                continue
            for v in vars(mod).values():
                if isinstance(v, TableSpec) and v.name not in registered:
                    unregistered.add(v.name)

    src = (Path(cat.__file__)).read_text(encoding="utf-8")
    undocumented = sorted(n for n in unregistered if n not in src)
    assert not undocumented, (
        f"카탈로그에 등재도 사유 기재도 없는 스펙: {undocumented}")

    # 사유가 적혀 있다고 아무 테이블이나 빼도 되는 것은 아니다. 이번 회차에
    # 뺀 것은 폐지된 2014년 체계 6장과 입력 원천이 없는 자동금리옵션 2장뿐이다.
    assert unregistered == {
        "kr_irrbb_bucket", "kr_irrbb_gap", "kr_irrbb_result",
        "kr_irrbb_shock_param", "kr_core_deposit", "kr_core_deposit_weight",
        "kr_auto_option", "kr_auto_option_risk",
    }, f"미등재 집합이 바뀌었다: {sorted(unregistered)}"


def test_the_repealed_2014_ledgers_stay_out_of_the_catalog():
    """폐지된 체계의 산출 원장이 카탈로그에 들어오면 실체화 대상이 된다."""
    registered = {t.name for t in cat.ALL_TABLES}
    assert "kr_irrbb_result" not in registered
    assert "kr_irrbb_shock_param" not in registered
    # 국내 고유 요건 원장은 반대로 반드시 있어야 한다.
    for name in ("kr_retail_criteria", "kr_nmd_category",
                 "kr_retail_behavioural_scope", "kr_irrbb_governance"):
        assert name in registered, name


# ---------------------------------------------------------------- 파이프라인 산출

def test_pipeline_ledger_stage_builds_every_registered_new_table(result):
    """등재한 R15 테이블은 파이프라인 또는 실체화 단계가 실제로 만든다.

    파이프라인이 만드는 것과 실체화가 만드는 것을 나눠 본다. 둘을 합쳐서만
    보면 파이프라인 스테이지가 통째로 죽어도 실체화가 메우는 것처럼 보인다.
    """
    from_pipeline = set(result.ledger_tables)
    assert from_pipeline, "파이프라인이 신규 원장을 하나도 만들지 않았다"
    declared = {t.name for t in cat.NEW_LEDGER_TABLES}
    # 파이프라인이 만들지만 등재 대상이 아닌 프레임은 없어야 한다.
    assert from_pipeline <= declared, (
        f"등재되지 않은 프레임을 파이프라인이 내보낸다: "
        f"{sorted(from_pipeline - declared)}")


def test_ledger_warnings_are_carried_out_of_the_pipeline(result):
    """근거가 없어 건너뛴 항목이 결과에 남는가.

    경고가 0건이면 의심해야 한다. 이 저장소의 신규 원장은 승인·원천이 없는
    칸을 여럿 안고 있고, 그 사실이 사라지면 화면이 완결된 산출처럼 보인다.
    """
    assert result.ledger_warnings, "신규 원장 경고가 0건 — 공백이 사라졌다"
    assert any("승인" in w for w in result.ledger_warnings)


# ---------------------------------------------------------------- 원장이 산출을 준다

def test_limit_definitions_come_from_the_ledger(portfolio, result):
    """원장을 비우면 한도 산출도 비어야 한다.

    임계가 코드에 남아 있으면 원장을 비워도 판정이 계속 나온다. 그 상태에서
    화면의 승인기구·승인일은 산출과 무관한 장식이다.
    """
    from risk_lib.limits_master import LimitLedgerWarning, build_limit_definitions
    from risk_lib.pipeline import _stage_limits_concentration

    tier1 = float(result.meta["capital"].tier1)
    full = build_limit_definitions()
    rep, _full, _conc = _stage_limits_concentration(portfolio, tier1, full)
    assert len(rep) > 0 or _full is not None

    empty = full.iloc[0:0]
    rep0, full0, _c0 = _stage_limits_concentration(portfolio, tier1, empty)
    assert rep0.empty, "한도 정의 원장이 비었는데 위반 보고서가 나왔다"
    assert full0.empty, "한도 정의 원장이 비었는데 소진율 표가 나왔다"

    # 임계가 NULL인 행은 싣지 않고 경고를 남긴다 — 조용히 기본값을 쓰지 않는다.
    nulled = full.copy()
    nulled["threshold_value"] = None
    with pytest.warns(LimitLedgerWarning):
        rep_null, _f, _c = _stage_limits_concentration(portfolio, tier1, nulled)
    assert rep_null.empty


def test_macro_indicators_come_from_the_master_ledger(result):
    """관측 계열이 마스터 원장의 지표만 담는가."""
    master = result.ledger_tables["rdm_macro_indicator_master"]
    shock = result.ledger_tables["st_macro_scenario_shock"]
    assert len(master) > 0 and len(shock) > 0
    assert set(shock["indicator_id"]) <= set(master["indicator_id"])

    from risk_lib.macro_monitor import observations
    obs = observations(result.meta["asof"], seed=42, master=master)
    assert set(obs["indicator_id"]) <= set(master["indicator_id"])
    # 마스터에서 한 행을 빼면 그 지표의 관측도 사라져야 한다.
    trimmed = master.iloc[1:]
    obs2 = observations(result.meta["asof"], seed=42, master=trimmed)
    dropped = str(master.iloc[0]["indicator_id"])
    assert dropped not in set(obs2["indicator_id"])


def test_irrbb_headline_account_is_not_the_repealed_one(result):
    """헤드라인 ΔEVE가 현행 계정으로 산출되는가.

    d368_2016 계정은 KRW 300/400/200이고 충격후 하한이 없다. 둘 다 개정으로
    대체된 값이므로 그 계정으로 산출한 ΔEVE는 폐지된 기준의 수치다.
    """
    from risk_lib.alm.curves import HEADLINE_FRAMEWORK_VERSION
    from risk_lib.pipeline import ALM_FRAMEWORK_VERSION

    assert ALM_FRAMEWORK_VERSION == HEADLINE_FRAMEWORK_VERSION
    res = result.alm_tables["alm_irrbb_result"]
    assert set(res["framework_version"]) == {HEADLINE_FRAMEWORK_VERSION}
    assert set(res["framework_status"]) == {"현행"}
    # 충격 모수는 프록시가 아니라 직접값이어야 한다.
    assert set(res["shock_source"]) == {"직접"}


def test_disclosure_table6_is_narrowed_to_one_basis(result):
    """<표6>이 산출기준 하나의 표에서 만들어졌는가.

    결과 원장의 낟알은 (기준일, 산출기준, 시나리오)다. 좁히지 않고 넘기면
    시나리오마다 행이 여럿이고 어느 행이 공시값인지 정해지지 않는다.
    """
    t6 = result.ledger_tables["disc_irrbb_table6"]
    assert len(t6) > 0
    assert set(t6["framework_version"]) == {"별표9의1_2026"}
    cur = t6[(t6["measure"] == "ΔEVE") & (t6["period"] == "당기")]
    assert not cur.duplicated(subset=["row_code", "col_code"]).any()


# ---------------------------------------------------------------- 자체검증

def test_new_consistency_checks_are_in_the_report(result):
    """신규 검사 4종이 실제로 실행됐는가."""
    names = {c.name for c in result.validation.checks}
    for want in ("irrbb_headline_not_repealed",
                 "irrbb_outlier_basis_tier1_15pct",
                 "kr_irrbb_national_ledgers_present",
                 "limit_definition_from_ledger",
                 "macro_master_from_ledger",
                 "lgd_ccf_backtest_censoring_reported"):
        assert want in names, f"{want} 검사가 돌지 않았다"


def test_backtest_censoring_check_reports_a_count(result):
    """관측중단 건수가 검사 본문에 실제 수치로 나오는가."""
    hit = [c for c in result.validation.checks
           if c.name == "lgd_ccf_backtest_censoring_reported"]
    assert hit and hit[0].status == "PASS"
    assert hit[0].metric is not None and hit[0].metric > 0


def test_missing_ledgers_make_the_new_checks_fail_not_pass():
    """원장이 없으면 통과가 아니라 실패다 — fail-closed."""
    from risk_lib.validation.consistency import (
        ValidationReport, _check_backtest_censoring, _check_limit_ledger_source,
        _check_macro_master_source,
    )
    rep = ValidationReport()
    _check_limit_ledger_source({}, None, rep)
    _check_macro_master_source({}, rep)
    _check_backtest_censoring({}, rep)
    assert [c.status for c in rep.checks] == ["FAIL", "FAIL", "FAIL"]


def test_delta_eve_recalc_applies_the_currency_rule():
    """ΔEVE 독립 재계산이 통화 간 상계 금지를 반영하는가.

    제13항 다는 통화별 EVE 리스크가 손실일 때만 합산하라고 정한다. 재계산이
    그 규칙을 빼면 이익 통화가 손실 통화를 상계한 값과 대사하게 되고, 충격후
    하한 0이 걸려 하락 시나리오가 이익으로 나오는 조합에서 어긋난다.
    """
    import inspect

    from risk_lib.validation import consistency as C
    src = inspect.getsource(C._check_delta_eve_recalc)
    assert "ccy" in src and "min(" in src


# ---------------------------------------------------------------- 독립검증 범위

def test_recalc_scope_covers_the_new_headline_figures():
    """새 headline 수치가 3선 재계산 대상에 있는가.

    `RECALC_SCOPE`에 없으면 3선이 그 수치를 다시 계산하지 않는다.
    """
    from risk_lib.validation.independent import RECALC_SCOPE

    keys = {k for k, _ko, _c in RECALC_SCOPE}
    for want in ("kr_irrbb_table6_max_delta_eve",
                 "kr_irrbb_table6_max_delta_nii",
                 "lgd_backtest_bias", "lgd_backtest_n_censored",
                 "ccf_realised_mean"):
        assert want in keys, f"{want}가 재계산 대상에 없다"


def test_recalc_scope_does_not_carry_the_repealed_metrics():
    """폐지된 2014년 지표(금리 EaR·금리 VaR)를 재계산 대상에 두지 않는다.

    산출하지 않는 값을 대상에 두면 3선이 매 회차 NULL을 확인하게 되고,
    폐지된 체계가 살아 있는 것처럼 보인다.
    """
    from risk_lib.validation.independent import RECALC_SCOPE

    keys = {k for k, _ko, _c in RECALC_SCOPE}
    assert not {"kr_irrbb_ear", "kr_irrbb_var", "kr_irrbb_pct_own_capital"} & keys


def test_new_recalc_targets_carry_values(result, portfolio):
    """대상에 올려 두고 값이 NULL이면 3선이 대조할 것이 없다."""
    from risk_lib.validation.independent import _headline

    head = _headline(result, {**result.ledger_tables, **result.alm_tables})
    for key in ("kr_irrbb_table6_max_delta_eve", "lgd_backtest_bias",
                "lgd_backtest_n_censored", "ccf_realised_mean"):
        assert head.get(key) is not None, f"{key}가 비어 있다"


def test_lgd_bias_uses_one_segment_axis_only():
    """세 축을 섞어 평균하면 같은 부도건이 세 번 들어간다."""
    from risk_lib.validation.independent import _lgd_bias

    frame = pd.DataFrame([
        {"segment_axis": "segment", "bias": 0.10, "n_defaults": 100},
        {"segment_axis": "grade", "bias": -0.90, "n_defaults": 100},
        {"segment_axis": "collateral_type", "bias": -0.90, "n_defaults": 100},
    ])
    assert _lgd_bias({"crm_lgd_backtest": frame}) == pytest.approx(0.10)


# ---------------------------------------------------------------- 요건추적

def test_requirement_trace_matches_what_is_actually_registered():
    """요건추적이 증빙으로 든 테이블은 카탈로그에 실재해야 한다.

    `test_req_trace.py`가 전건을 보지만, 이번 회차에 상태가 바뀐 요건은
    신규 원장에 걸려 있으므로 여기서도 못박는다. 등재를 되돌리면 두 곳에서
    걸린다.
    """
    from risk_lib.ui_studio.req_trace import TRACE

    names = {t.name for t in cat.ALL_TABLES}
    moved = ("NFR-003", "NFR-004", "INT-001", "INT-002", "INT-003", "INT-004",
             "INT-008", "DAT-008", "SEC-OAI-003", "SEC-PRC-002",
             "BNK-CRM-002", "BNK-CRM-006", "BNK-CRM-007",
             "SEC-CCR-003", "SEC-LIQ-001", "BNK-CRM-003")
    for rid in moved:
        assert rid in TRACE, f"{rid}가 TRACE로 옮겨지지 않았다"
        status, evidence, note = TRACE[rid]
        assert status in ("반영", "부분")
        tables = [ref for kind, ref in evidence if kind == "table"]
        assert tables, f"{rid}에 원장 증빙이 없다"
        for ref in tables:
            assert ref in names, f"{rid}: 카탈로그에 없는 테이블 {ref}"


def test_irrbb_requirement_stays_partial_and_says_why():
    """BNK-OTH-003은 아직 '반영'이 아니다.

    KRW 충격이 원문확인이 됐고 국내기준 계정으로 산출되지만, 제11항
    자동금리옵션 리스크가 ΔEVE에서 빠져 있다. 그 사실이 note에 없으면
    "구조가 갖춰졌으니 반영"으로 읽힌다.
    """
    from risk_lib.ui_studio.req_trace import TRACE

    status, evidence, note = TRACE["BNK-OTH-003"]
    assert status == "부분"
    assert "자동금리옵션" in note
    assert "225" in note
    tables = {ref for kind, ref in evidence if kind == "table"}
    assert {"kr_nmd_category", "disc_irrbb_table6"} <= tables
