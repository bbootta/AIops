"""RYNTA v9.0 수식 카탈로그 ↔ 하니스 엔진 정합성 (BRD GOV-003 산식·계산엔진 통제).

원본: `02_RYNTA_내부개발용_합성데이터_수식랩_v9.0_한국어.xlsx` 시트
`12_Formula_Catalog` (sha256 1462077f…6585). 카탈로그의 정식 산식과 risk_lib
구현이 같은 결과를 내는지 검증한다.

카탈로그 자체가 "데모 수식이며 운영 적용 전 기관 승인 사양과 독립검증으로
교체해야 한다"고 명시하므로, 여기서는 **구조적 항등식**(입력→출력 관계)을
검증하고 캘리브레이션 상수는 검증 대상에서 제외한다.

의도적 이탈은 `DEVIATIONS`에 사유와 함께 명시한다 — 조용한 이탈은
추적성 위반이다 (AIMS_POLICY §8-4).
"""

from __future__ import annotations

import numpy as np
import pytest


# 카탈로그 대비 의도적 이탈 — 사유를 명시하고 테스트로 고정한다.
DEVIATIONS = {
    "CR-F003": (
        "PD 하한: 카탈로그 0.0003(3bp) vs 하니스 0.0005(5bp). "
        "Basel III 최종안(BCBS d424 / CRE32.42)이 기업·리테일 PD 하한을 "
        "5bp로 상향했으므로 하니스는 현행 규정을 따른다. 카탈로그는 데모값."
    ),
}


# ----- CR-F001 · EAD = Drawn + CCF × Undrawn -------------------------------

def test_crf001_ead_identity():
    from risk_lib.capital.crm import ccf_ead, CCF_BUCKETS
    for ccf_type, ccf in CCF_BUCKETS.items():
        drawn, undrawn = 1_000.0, 500.0
        assert ccf_ead(drawn, undrawn, ccf_type) == pytest.approx(
            drawn + ccf * undrawn), f"{ccf_type} EAD 항등식 위반"


def test_crf001_ead_is_non_negative_and_monotone():
    """핵심 통제: 비음수, 미인출액에 대해 단조증가."""
    from risk_lib.capital.crm import ccf_ead
    prev = -1.0
    for undrawn in (0.0, 100.0, 500.0, 1_000.0):
        v = ccf_ead(100.0, undrawn, "commitment_gt_1y")
        assert v >= 0
        assert v >= prev
        prev = v


# ----- CR-F003 · PD 하한/상한 ----------------------------------------------

def test_crf003_pd_bounds_with_documented_deviation():
    """PD는 하한으로 클립된다. 하한값은 의도적 이탈(위 DEVIATIONS 참조)."""
    from risk_lib.references import PD_FLOOR_BPS
    assert "CR-F003" in DEVIATIONS
    assert PD_FLOOR_BPS == 5, "PD 하한이 바뀌면 DEVIATIONS 설명도 갱신해야 한다"
    # 카탈로그 데모값(3bp)보다 보수적(높음)이어야 한다 — 자본 과소계상 방지
    assert PD_FLOOR_BPS >= 3


def test_crf003_pipeline_pd_respects_floor(result):
    """자체검증의 PD 하한 체크가 실제로 수행되고 통과/경고 상태여야 한다."""
    from risk_lib.references import PD_FLOOR_BPS
    checks = {c.name: c for c in result.validation.checks}
    floor_checks = [n for n in checks if "pd_floor" in n]
    assert floor_checks, "PD 하한 검증 체크가 없다"
    for n in floor_checks:
        assert checks[n].status in ("PASS", "WARN"), f"{n}: FAIL"
        assert str(PD_FLOOR_BPS) in n or "bp" in n


# ----- CR-F007 · 실현 LGD = 1 − PV(순회수)/EAD ------------------------------

def test_crf007_workout_lgd_identity():
    from risk_lib.models.lgd_model import workout_lgd
    ead, disc = 1_000.0, 0.05
    recoveries = [(1.0, 300.0), (2.0, 200.0)]
    costs = 50.0
    pv = -costs + 300.0 / 1.05 + 200.0 / 1.05 ** 2
    assert workout_lgd(ead, recoveries, costs, disc) == pytest.approx(
        1 - pv / ead)


def test_crf007_lgd_in_unit_interval():
    """핵심 통제: 회수가 EAD를 초과해도 LGD는 [0,1]."""
    from risk_lib.models.lgd_model import workout_lgd
    assert 0.0 <= workout_lgd(1_000.0, [(0.5, 5_000.0)]) <= 1.0
    assert 0.0 <= workout_lgd(1_000.0, []) <= 1.0


# ----- CR-F013 · CRM 적용 후 PD 불변 (PD_Delta = 0) -------------------------

def test_crf013_crm_does_not_change_pd(portfolio):
    """담보배분은 차주의 부도가능성을 자동변경하지 않는다 — Negative Test."""
    from risk_lib.capital.crm import apply_crm
    before = portfolio.copy()
    after = apply_crm(before)
    if "pd" in before.columns and "pd" in after.columns:
        np.testing.assert_allclose(
            after["pd"].to_numpy(dtype=float),
            before["pd"].to_numpy(dtype=float),
            rtol=0, atol=0,
            err_msg="CRM이 PD를 변경했다 — CR-F013 위반")


def test_crf008_crm_allocation_never_exceeds_exposure(portfolio):
    """CRM 조정 EAD는 음수가 아니고 gross EAD를 초과하지 않는다 (초과배분 방지)."""
    from risk_lib.capital.crm import apply_crm
    df = apply_crm(portfolio.copy())
    ead = df["ead"].to_numpy(dtype=float)
    gross = df["ead_gross"].to_numpy(dtype=float)
    assert (ead >= -1e-9).all(), "CRM 조정 EAD 음수"
    assert (ead <= gross + 1e-6).all(), "CRM 조정 EAD가 gross 초과 — 초과배분"


# ----- OR-F001 · 순손실 = MAX(0, 총손실 − 직접회수 − 보험) ------------------

def test_orf001_net_loss_identity(result):
    reg = result.op_loss.register
    gross = reg["gross"].to_numpy(dtype=float)
    rec = reg["recovery"].to_numpy(dtype=float)
    net = reg["net"].to_numpy(dtype=float)
    np.testing.assert_allclose(net, np.maximum(0.0, gross - rec), rtol=1e-9)
    assert (net >= 0).all(), "순손실 음수 — OR-F001 위반"


def test_orf001_recovery_never_exceeds_gross(result):
    """핵심 통제: 회수액이 총손실을 초과하지 않도록 회계대사."""
    reg = result.op_loss.register
    assert (reg["recovery"] <= reg["gross"] + 1e-9).all()


# ----- MR-F005 · 백테스트 예외 = 손실이 VaR 초과 ----------------------------

def test_mrf005_backtest_exception_rule(result):
    """예외는 실손실이 VaR 임계를 초과한 경우로만 카운트된다."""
    bt = result.frtb.backtest if hasattr(result, "frtb") else None
    if bt is None:
        pytest.skip("FRTB 백테스트 미산출")
    assert bt.exceptions_99 >= 0
    assert bt.exceptions_99 <= bt.n_days


# ----- MR-F006 · PLA 잔차 = HPL − RTPL --------------------------------------

def test_mrf006_pla_residual_definition(result):
    if not hasattr(result, "frtb"):
        pytest.skip("FRTB 미산출")
    plat = result.frtb.plat
    hpl = plat["hpl"].to_numpy(dtype=float)
    rtpl = plat["rtpl"].to_numpy(dtype=float)
    resid = plat["residual"].to_numpy(dtype=float)
    np.testing.assert_allclose(resid, hpl - rtpl, rtol=1e-9)


# ----- ST-F001 · 충격형태 (정점 → 회복 경로) --------------------------------

def test_stf001_shock_path_peaks_then_decays():
    """0 → 정점 → 감쇠. 카탈로그는 (q/peak)·exp(1−q/peak) 형태를 제시하고,
    하니스는 선형상승 + 지수감쇠를 쓴다 — 두 구현 모두 동일한 구조적 성질
    (정점에서 최대, 이후 단조감소, 비음수)을 만족해야 한다."""
    from risk_lib.stress.ccar import hump_severities
    path = hump_severities(peak=1.0, peak_q=3, n=10)
    assert len(path) == 10
    assert all(v >= 0 for v in path), "충격 경로 음수"
    assert path[3] == pytest.approx(max(path)), "정점 분기가 최대가 아님"
    tail = path[3:]
    assert all(b <= a + 1e-12 for a, b in zip(tail, tail[1:])), "정점 이후 비단조"


# ----- ST-F004 · CET1 Roll-forward -----------------------------------------

def test_stf004_cet1_rollforward_is_path_consistent(result):
    """분기 CET1 경로는 시나리오별로 연속이어야 한다 (경계에서 리셋)."""
    sp = result.stress_path
    for scen, g in sp.groupby("scenario"):
        g = g.sort_values("q_index")
        assert len(g) == len(result.meta["quarters"])
        assert (g["cet1_ratio"] > 0).all(), f"{scen}: CET1 비율 비양수"


# ----- ST-F006 · 임계값 위반 판정 -------------------------------------------

def test_stf006_breach_flag_names_the_binding_ratio(result):
    """침범 표기가 있으면 어느 요구치(CET1/Tier1/총자본)인지 명시돼야 한다.

    CET1에 여유가 있어도 Tier1·총자본 요구치 때문에 침범이 발생할 수 있으므로,
    비율 이름 없이 '요구치 침범'만 적으면 CRO가 CET1 침범으로 오독한다.
    """
    trough = result.stress_path_trough
    assert "breach_ratio" in trough.columns
    for _, row in trough.iterrows():
        if isinstance(row.get("first_breach"), str):
            assert row["breach_ratio"] in ("cet1", "tier1", "total"), (
                f"{row['scenario']}: 침범 비율 미표기")
        else:
            assert row["breach_ratio"] is None or (
                isinstance(row["breach_ratio"], float)), (
                f"{row['scenario']}: 침범 없음인데 비율이 표기됨")


def test_stf006_breach_is_consistent_with_all_three_requirements(result):
    """passes=False인 분기는 세 비율 중 최소 하나가 요구치 미만이어야 한다."""
    sp = result.stress_path
    req = result.bis.required
    for _, row in sp.iterrows():
        below = [k for k in ("cet1", "tier1", "total")
                 if float(row[f"{k}_ratio"]) < req[k] - 1e-12]
        assert bool(below) == (not bool(row["passes"])), (
            f"{row['scenario']} {row['quarter']}: passes={row['passes']}이나 "
            f"요구치 미달 비율={below}")
        if below:
            assert row["binding"] in below, (
                f"binding={row['binding']}가 실제 미달 비율 {below}에 없다")


# ----- SCN-F002 · Loss → RWA 대용치 (12.5배 = 1/8%) -------------------------

def test_scnf002_rwa_conversion_factor():
    """카탈로그의 6.25는 데모 계수이고, 하니스는 규제 정식 12.5배(=1/0.08)를
    쓴다. 자본요구액 → RWA 환산은 규정상 12.5가 맞다 (CRE20.1)."""
    from risk_lib.capital.op_risk import compute_op_risk_rwa, BusinessIndicator
    r = compute_op_risk_rwa(BusinessIndicator(1e12, 5e11, 3e11),
                            avg_annual_losses_10y=1e10, use_ilm=True)
    assert r.rwa == pytest.approx(r.orc * 12.5, rel=1e-9)


# ----- AIG-F001 · 권한경계 (Read-only → Recommend-only → Approval-first) ----

def test_aigf001_guardrail_chain_declared():
    from risk_lib import rynta
    names = [g[0] for g in rynta.GUARDRAILS]
    assert names[:3] == ["조회 전용", "제안 전용", "승인 우선"], (
        "가드레일 순서가 AIG-F001 권한경계와 다르다")


# ----- 이탈 문서화 강제 -----------------------------------------------------

def test_every_deviation_states_a_reason():
    for fid, reason in DEVIATIONS.items():
        assert len(reason) > 40, f"{fid}: 이탈 사유가 불충분"
        assert "카탈로그" in reason and "하니스" in reason
