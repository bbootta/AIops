"""내부등급법 추정의 자체 정합성 검사 (2선).

검사는 **위반을 만들면 실제로 FAIL해야** 통제다. 항등식을 다시 쓴 검사는 언제나
통과하므로 아무것도 지키지 못한다. 아래 각 함수의 docstring에 "이 검사를
FAIL시키려면 무엇이 깨져야 하는가"를 적었고, ``tests/test_irb_estimation.py``가
검사마다 위반을 주입해 FAIL이 뜨는지 확인한다.

이 모듈은 ``risk_lib.validation.consistency``의 ``ValidationReport``에 결과를
싣는다. 배선 담당이 ``run_consistency_checks``에서
:func:`run_irb_estimation_checks`를 부르면 전체 자체검증에 합류한다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from risk_lib.validation.consistency import ConsistencyCheck, ValidationReport

__all__ = [
    "ATOL",
    "check_observation_minimum", "check_pd_floor", "check_lgd_floor",
    "check_downturn_floor", "check_moc_direction", "check_basis_domain",
    "check_backtest_out_of_sample", "check_backtest_inside_range",
    "check_censoring_disclosure", "check_ccf_denominator_accounting",
    "check_ccf_floor_is_derived", "check_elbe_provision_justification",
    "check_pd_estimate_wired", "run_irb_estimation_checks",
]

# 비율 비교의 허용오차. 하한 비교는 부동소수 잔차로 뒤집히면 안 된다.
ATOL = 1e-12


def _pass(report, name, detail, metric=0.0):
    report.add(ConsistencyCheck(name, "PASS", detail, metric=float(metric)))


def _fail(report, name, detail, metric):
    report.add(ConsistencyCheck(name, "FAIL", detail, metric=float(metric)))


def _warn(report, name, detail, metric=0.0):
    report.add(ConsistencyCheck(name, "WARN", detail, metric=float(metric)))


# ---------------------------------------------------------------- 관측기간

def check_observation_minimum(run: pd.DataFrame,
                              report: ValidationReport) -> None:
    """관측기간 미달인데 충족으로 표시된 행 (182.라·마, 186., 195.).

    FAIL 조건: 산출이력이 ``meets_minimum=True``인데 ``observation_years``가
    ``min_observation_years``보다 작을 때. 최소요건 판정을 세그먼트별 모수가
    아니라 한 값으로 하면 소매 5년 기준을 기업 7년 행에 적용해 이 위반이 난다.
    """
    if run.empty or "meets_minimum" not in run.columns:
        return
    d = run.dropna(subset=["min_observation_years", "observation_years"])
    bad = d[(d["meets_minimum"] == True)                       # noqa: E712
            & (d["observation_years"] < d["min_observation_years"])]
    if len(bad):
        _fail(report, "IRB 관측기간 최소요건",
              f"관측기간 미달인데 충족 표시 {len(bad)}건: "
              f"{sorted(set(bad['parameter'] + '/' + bad['segment']))[:5]}",
              len(bad))
        return
    undecided = int(run["meets_minimum"].isna().sum())
    _pass(report, "IRB 관측기간 최소요건",
          f"{len(d)}건 판정, 미판정 {undecided}건(최소요건 모수 미확인)",
          undecided)


# ---------------------------------------------------------------- 하한

def _floor_violation(df: pd.DataFrame, value_col: str) -> pd.DataFrame:
    d = df.dropna(subset=["floor_value", value_col])
    return d[d[value_col] < d["floor_value"] - ATOL]


def check_pd_floor(pd_estimate: pd.DataFrame,
                   report: ValidationReport) -> None:
    """PD 최종치가 하한 미만인 행 (123.·131.).

    FAIL 조건: 하한이 원장에 있는데 최종 적용치가 그보다 작을 때. 하한을 원시
    추정치에만 걸고 MoC 뒤에 다시 비교하지 않으면 이 위반은 나지 않지만,
    하한 적용 순서를 바꾸거나 하한을 곱셈으로 잘못 적용하면 즉시 드러난다.
    """
    if pd_estimate.empty:
        return
    bad = _floor_violation(pd_estimate, "final_applied")
    if len(bad):
        _fail(report, "IRB PD 하한",
              f"PD 최종치가 하한 미만 {len(bad)}건: "
              f"{sorted(set(bad['segment'] + '/' + bad['grade']))[:5]}",
              len(bad))
        return
    n_bind = int(pd_estimate["floor_binding"].fillna(False).sum())
    n_null = int(pd_estimate["floor_value"].isna().sum())
    _pass(report, "IRB PD 하한",
          f"{len(pd_estimate)}건 중 하한이 문 건 {n_bind}건, 하한 미확인 "
          f"{n_null}건", n_bind)


def check_lgd_floor(lgd_estimate: pd.DataFrame,
                    report: ValidationReport) -> None:
    """LGD 최종치가 하한 미만인 행 (132.가, 개정 전 185.가(1) 주거용 10%).

    FAIL 조건: 주거용주택담보 하한(최종안 5%)이 원장에 있는데 최종치가 그보다
    작을 때. 세그먼트별 담보유형 조회를 무담보 하한으로 잘못 걸면 주담대에
    25%나 30%가 걸려 반대로 과대해지고, 조회를 빠뜨리면 하한이 사라진다.
    """
    if lgd_estimate.empty:
        return
    bad = _floor_violation(lgd_estimate, "final_applied")
    if len(bad):
        _fail(report, "IRB LGD 하한",
              f"LGD 최종치가 하한 미만 {len(bad)}건: "
              f"{sorted(set(bad['segment']))}", len(bad))
        return
    _pass(report, "IRB LGD 하한",
          f"{len(lgd_estimate)}건 점검, 하한 미확인 "
          f"{int(lgd_estimate['floor_value'].isna().sum())}건")


def check_downturn_floor(lgd_estimate: pd.DataFrame,
                         report: ValidationReport) -> None:
    """경기침체 LGD가 장기 부도가중평균보다 작은데 그대로 쓰인 행 (185.가(1)).

    FAIL 조건: ``raw_estimate``가 ``longrun_default_weighted_lgd``나
    ``downturn_lgd``보다 작을 때. 185.가(1)은 장기 부도가중평균을 **하한**으로
    두므로 두 값 중 큰 값이어야 한다. max를 min으로 잘못 쓰면 즉시 뜬다.
    """
    if lgd_estimate.empty:
        return
    d = lgd_estimate.dropna(subset=["raw_estimate"])
    lr = d.dropna(subset=["longrun_default_weighted_lgd"])
    bad_lr = lr[lr["raw_estimate"]
                < lr["longrun_default_weighted_lgd"] - ATOL]
    dt = d.dropna(subset=["downturn_lgd"])
    bad_dt = dt[dt["raw_estimate"] < dt["downturn_lgd"] - ATOL]
    n = len(bad_lr) + len(bad_dt)
    if n:
        _fail(report, "IRB 경기침체 LGD 하한",
              f"원시추정치가 장기평균 또는 침체치보다 작다 {n}건: "
              f"{sorted(set(list(bad_lr['segment']) + list(bad_dt['segment'])))}",
              n)
        return
    n_dt = int(d["downturn_lgd"].notna().sum())
    _pass(report, "IRB 경기침체 LGD 하한",
          f"{len(d)}건 중 침체치 산출 {n_dt}건, 전건 max(침체, 장기평균) 성립",
          n_dt)


# ---------------------------------------------------------------- MoC

def check_moc_direction(estimates: dict[str, pd.DataFrame],
                        report: ValidationReport) -> None:
    """MoC가 보수적 방향으로만 움직였는지 (181.).

    FAIL 조건: ``after_moc``가 ``after_floor``보다 작을 때. PD·LGD·CCF 모두
    상향이 보수적 방향이다. MoC를 음수로 적재하거나 신뢰구간 하한을 상한으로
    잘못 쓰면 완화 방향으로 움직이고 이 검사가 잡는다.
    """
    total_bad = 0
    detail: list[str] = []
    for name, df in estimates.items():
        if df is None or df.empty:
            continue
        d = df.dropna(subset=["after_floor", "after_moc"])
        bad = d[d["after_moc"] < d["after_floor"] - ATOL]
        total_bad += len(bad)
        if len(bad):
            detail.append(f"{name} {len(bad)}건")
    if total_bad:
        _fail(report, "IRB MoC 보수성 방향",
              f"MoC 적용 후가 적용 전보다 작다: {', '.join(detail)}", total_bad)
        return
    _pass(report, "IRB MoC 보수성 방향",
          "PD·LGD·CCF 전건에서 MoC 적용 후 ≥ 적용 전")


def check_basis_domain(run: pd.DataFrame, report: ValidationReport) -> None:
    """모수별 평균 기준의 값 도메인 (182.바 대 185.가(1)·195.다).

    FAIL 조건: PD 행에 '부도가중평균'이 적혔을 때. 182.바는 PD에 차주수 기준
    단순평균을 요구한다. 부도가중을 PD에 쓰면 침체기 부도율로 수렴하고 위험가중
    함수의 조건부 부도율과 이중계상이 된다. 반대로 LGD·CCF 행에 연도동일가중이
    적히면 185.가(1)·195.다 위반이다.
    """
    if run.empty:
        return
    bad_pd = run[(run["parameter"] == "PD")
                 & (run["estimation_basis"] == "부도가중평균")]
    bad_other = run[(run["parameter"].isin(["LGD", "CCF"]))
                    & (run["estimation_basis"] == "장기평균(연도동일가중)")]
    n = len(bad_pd) + len(bad_other)
    if n:
        _fail(report, "IRB 평균 기준 도메인",
              f"모수와 평균 기준이 어긋난 산출이력 {n}건 "
              f"(PD 부도가중 {len(bad_pd)}건, LGD·CCF 연도동일가중 "
              f"{len(bad_other)}건)", n)
        return
    _pass(report, "IRB 평균 기준 도메인",
          f"{len(run)}건 전건에서 모수와 평균 기준이 조문에 맞다")


# ---------------------------------------------------------------- 사후검증

def check_backtest_out_of_sample(backtest: pd.DataFrame,
                                 report: ValidationReport) -> None:
    """사후검증이 표본외인지 (203.라(1)).

    FAIL 조건: ``out_of_sample=False``인 행이 있을 때. 추정에 쓴 해로 검증하면
    그 해의 부도율이 추정치에 이미 들어가 있어 범위 안에 있는 것이 당연해진다.
    유보연도를 빼지 않고 검증하면 즉시 뜬다.
    """
    if backtest.empty:
        return
    bad = backtest[~backtest["out_of_sample"].astype(bool)]
    if len(bad):
        _fail(report, "IRB 사후검증 표본외",
              f"추정 표본 안의 연도로 검증한 행 {len(bad)}건", len(bad))
        return
    _pass(report, "IRB 사후검증 표본외",
          f"{len(backtest)}건 전건 표본외", len(backtest))


def check_backtest_inside_range(backtest: pd.DataFrame,
                                report: ValidationReport) -> None:
    """등급별 실제 부도율이 예상 부도율 범위 안인지 (203.가).

    FAIL 조건: ``judgment_status='판정완료'``이면서 ``inside_range=False``인
    행이 있을 때. 임계(신뢰수준)가 승인 전이면 판정하지 않고 미판정 건수만
    보고한다. 임의의 신뢰수준으로 통과를 찍지 않는다.
    """
    if backtest.empty:
        return
    judged = backtest[backtest["judgment_status"] == "판정완료"]
    outside = judged[judged["inside_range"] == False]            # noqa: E712
    if len(outside):
        _fail(report, "IRB 사후검증 범위",
              f"실적이 예상 범위 밖 {len(outside)}건: "
              f"{sorted(set(outside['parameter'] + '/' + outside['segment'] + '/' + outside['grade']))[:5]}",
              len(outside))
        return
    n_unjudged = int((backtest["judgment_status"] != "판정완료").sum())
    if len(judged) == 0:
        _warn(report, "IRB 사후검증 범위",
              f"판정 임계가 승인 전이라 {n_unjudged}건 전건 미판정 (203.가)",
              n_unjudged)
        return
    _pass(report, "IRB 사후검증 범위",
          f"판정 {len(judged)}건 전건 범위 내, 미판정 {n_unjudged}건",
          n_unjudged)


# ---------------------------------------------------------------- 관측중단

def check_censoring_disclosure(lgd_estimate: pd.DataFrame,
                               report: ValidationReport) -> None:
    """관측중단 건수와 처리 영향이 원장에 남았는지 (184.).

    FAIL 조건: 관측중단 건이 있는데 ``censoring_impact``가 비어 있을 때. 회수
    미종료 건을 조용히 빼면 회수가 잘 된 건만 남아 LGD가 낙관적으로 나오고,
    그 영향이 원장에 없으면 화면에서 드러나지 않는다.
    """
    if lgd_estimate.empty:
        return
    d = lgd_estimate[lgd_estimate["status"] != "산출불가"]
    bad = d[(d["n_censored"].fillna(0) > 0) & d["censoring_impact"].isna()]
    if len(bad):
        _fail(report, "IRB 관측중단 공시",
              f"관측중단 건이 있는데 처리 영향이 비어 있다 {len(bad)}건: "
              f"{sorted(set(bad['segment']))}", len(bad))
        return
    n_cens = int(d["n_censored"].fillna(0).sum())
    _pass(report, "IRB 관측중단 공시",
          f"관측중단 {n_cens}건, 제외·포함 두 처리의 값이 모두 원장에 있다",
          n_cens)


# ---------------------------------------------------------------- CCF

def check_ccf_denominator_accounting(ccf_estimate: pd.DataFrame,
                                     report: ValidationReport) -> None:
    """CCF 분모 0·음수 건이 집계에서 사라지지 않았는지 (193.).

    FAIL 조건: ``n_valid + n_zero_denominator + n_negative_denominator``가
    ``n_facilities``와 다를 때. 분모가 0 이하인 건을 행째로 잘라내면 이 항등식이
    깨지고, 제외된 건수가 화면에서 사라진다. 제외 자체는 불가피하지만 조용한
    제외는 표본을 좋은 쪽으로 치우치게 한다.
    """
    if ccf_estimate.empty:
        return
    total = (ccf_estimate["n_valid"] + ccf_estimate["n_zero_denominator"]
             + ccf_estimate["n_negative_denominator"])
    bad = ccf_estimate[total != ccf_estimate["n_facilities"]]
    if len(bad):
        _fail(report, "IRB CCF 분모 처리",
              f"제외 건수 합이 전체 건수와 다르다 {len(bad)}건", len(bad))
        return
    n_excl = int((ccf_estimate["n_zero_denominator"]
                  + ccf_estimate["n_negative_denominator"]).sum())
    _pass(report, "IRB CCF 분모 처리",
          f"분모 0·음수 {n_excl}건이 건수와 금액으로 원장에 남아 있다", n_excl)


def check_ccf_floor_is_derived(ccf_estimate: pd.DataFrame,
                               report: ValidationReport) -> None:
    """CCF 하한이 표준방법 환산율의 배수로 계산됐는지.

    FAIL 조건: ``floor_value``가 ``sa_ccf × floor_multiplier``와 다를 때.
    20%를 상수로 박으면 취소가능 약정(표준방법 10%)에서 0.10×0.5=0.05와 어긋나
    즉시 뜬다. 하한이 상수가 아니라 파생값이라는 사실을 이 검사가 지킨다.
    """
    if ccf_estimate.empty:
        return
    d = ccf_estimate.dropna(subset=["floor_value", "sa_ccf",
                                    "floor_multiplier"])
    if d.empty:
        _warn(report, "IRB CCF 하한 파생",
              "하한을 계산할 수 있는 행이 없다 (표준방법 환산율 또는 배수 미확인)")
        return
    bad = d[np.abs(d["floor_value"] - d["sa_ccf"] * d["floor_multiplier"])
            > 1e-9]
    if len(bad):
        _fail(report, "IRB CCF 하한 파생",
              f"하한이 표준방법 환산율×배수와 다르다 {len(bad)}건", len(bad))
        return
    _pass(report, "IRB CCF 하한 파생",
          f"{len(d)}건 전건에서 하한 = 표준방법 CCF × 배수", len(d))


# ---------------------------------------------------------------- 부도자산

def check_elbe_provision_justification(defaulted: pd.DataFrame,
                                       report: ValidationReport) -> None:
    """ELBE가 개별충당금+부분상각보다 작을 때 입증 문서가 있는지 (185.바).

    FAIL 조건: ``justification_required=True``인데 ``justification_ref``가
    비어 있을 때. 비대칭 규칙이라 반대 방향(ELBE가 더 큼)에는 입증책임이 없다.
    양방향으로 검사를 걸면 정상 건에 거짓 경보가 난다.
    """
    if defaulted.empty:
        return
    need = defaulted[defaulted["justification_required"] == True]  # noqa: E712
    missing = need[need["justification_ref"].isna()]
    if len(missing):
        _fail(report, "IRB 부도자산 ELBE 대 충당금",
              f"ELBE가 개별충당금+부분상각보다 작은데 입증 문서가 없다 "
              f"{len(missing)}건: {sorted(set(missing['segment']))}",
              len(missing))
        return
    n_undecided = int(defaulted["justification_required"].isna().sum())
    _pass(report, "IRB 부도자산 ELBE 대 충당금",
          f"입증 필요 {len(need)}건 전건 문서 있음, 충당금 자료 없어 미판정 "
          f"{n_undecided}건", n_undecided)


# ---------------------------------------------------------------- 배선

def check_pd_estimate_wired(pd_estimate: pd.DataFrame,
                            rwa_input: pd.DataFrame | None,
                            report: ValidationReport, *,
                            pd_column: str = "pd",
                            tol: float = 1e-9) -> None:
    """추정 PD 최종치가 RWA 산출에 실제로 쓰이는지.

    FAIL 조건: RWA 산출 입력의 PD 값 중 어느 것도 ``crm_pd_estimate``의
    ``final_applied``와 일치하지 않을 때. 추정 원장을 만들어 놓고 RWA는 다른
    경로의 PD를 쓰면 원장이 화면 장식이 된다. 배선이 끊긴 상태가 조용히 지나가지
    않게 하는 검사다.
    """
    if pd_estimate.empty:
        return
    if rwa_input is None or pd_column not in getattr(rwa_input, "columns", []):
        _warn(report, "IRB PD 추정치 배선",
              "RWA 산출 입력이 주어지지 않아 배선을 확인하지 못했다")
        return
    finals = pd_estimate["final_applied"].dropna().to_numpy(dtype=float)
    used = pd.to_numeric(rwa_input[pd_column], errors="coerce").dropna()
    if len(finals) == 0 or used.empty:
        _warn(report, "IRB PD 추정치 배선", "비교할 값이 없다")
        return
    matched = int(sum(
        bool(np.any(np.abs(finals - v) <= tol)) for v in used.to_numpy()))
    if matched == 0:
        _fail(report, "IRB PD 추정치 배선",
              f"RWA 입력 {len(used)}건 중 추정 PD 최종치와 일치하는 건이 없다. "
              "추정 원장이 산출에 연결되지 않았다", len(used))
        return
    _pass(report, "IRB PD 추정치 배선",
          f"RWA 입력 {len(used)}건 중 {matched}건이 추정 PD 최종치와 일치",
          matched)


def run_irb_estimation_checks(ledgers: dict[str, pd.DataFrame], *,
                              rwa_input: pd.DataFrame | None = None,
                              report: ValidationReport | None = None
                              ) -> ValidationReport:
    """내부등급법 추정 원장 묶음에 대한 자체 정합성 검사 일괄 실행."""
    rep = report or ValidationReport()
    run = ledgers.get("crm_estimation_run", pd.DataFrame())
    pd_est = ledgers.get("crm_pd_estimate", pd.DataFrame())
    lgd_est = ledgers.get("crm_lgd_estimate", pd.DataFrame())
    ccf_est = ledgers.get("crm_ccf_estimate", pd.DataFrame())
    check_observation_minimum(run, rep)
    check_basis_domain(run, rep)
    check_pd_floor(pd_est, rep)
    check_lgd_floor(lgd_est, rep)
    check_downturn_floor(lgd_est, rep)
    check_moc_direction({"crm_pd_estimate": pd_est,
                         "crm_lgd_estimate": lgd_est,
                         "crm_ccf_estimate": ccf_est}, rep)
    check_censoring_disclosure(lgd_est, rep)
    check_ccf_denominator_accounting(ccf_est, rep)
    check_ccf_floor_is_derived(ccf_est, rep)
    check_backtest_out_of_sample(
        ledgers.get("crm_backtest_result", pd.DataFrame()), rep)
    check_backtest_inside_range(
        ledgers.get("crm_backtest_result", pd.DataFrame()), rep)
    check_elbe_provision_justification(
        ledgers.get("crm_defaulted_lgd", pd.DataFrame()), rep)
    check_pd_estimate_wired(pd_est, rwa_input, rep)
    return rep
