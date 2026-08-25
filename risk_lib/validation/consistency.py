"""Self-verification (정합성 검증) across the harness outputs.

These checks catch the most common mistakes that silently corrupt regulatory
numbers — unit mismatches, negative RWA, PD floor violations, EL > EAD,
double-counting between SA and IRB, BIS ratio out of plausible range, etc.

Each check returns a ConsistencyCheck record; ValidationReport.passes() is
True only if every check has status == "PASS".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from risk_lib.capital.bis import AT1_ISSUED, BIS_MINIMUMS, PAID_IN_CAPITAL


@dataclass
class ConsistencyCheck:
    name: str
    status: str           # PASS | WARN | FAIL
    detail: str
    metric: float | None = None
    # 구성상 항상 성립하는 항등식인가. 항등식은 실패할 수 없으므로 통제가
    # 아니다. 통제 건수를 셀 때 이 표시가 있는 항목을 빼야 "63건을 통과했다"가
    # 실제 통제 63건을 뜻한다.
    is_identity: bool = False


@dataclass
class ValidationReport:
    checks: list[ConsistencyCheck] = field(default_factory=list)

    def add(self, c: ConsistencyCheck) -> None:
        self.checks.append(c)

    def passes(self) -> bool:
        return all(c.status != "FAIL" for c in self.checks)

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame([c.__dict__ for c in self.checks])

    def summary(self) -> dict[str, int]:
        from collections import Counter
        return dict(Counter(c.status for c in self.checks))

    def controls(self) -> list[ConsistencyCheck]:
        """항등식을 뺀 검사 목록. 통제 건수는 이 길이로 센다."""
        return [c for c in self.checks if not c.is_identity]


def _check_pd_bounds(df: pd.DataFrame, report: ValidationReport) -> None:
    if "pd" not in df.columns:
        return
    bad = df[(df["pd"] < 0) | (df["pd"] > 1)]
    if len(bad):
        report.add(ConsistencyCheck(
            "pd_in_[0,1]", "FAIL",
            f"{len(bad)} exposures have PD outside [0,1]",
            metric=float(len(bad)),
        ))
    else:
        report.add(ConsistencyCheck(
            "pd_in_[0,1]", "PASS",
            "all PDs within [0,1]",
            metric=0.0,
        ))

    from risk_lib.references import PD_FLOOR_BPS
    pd_floor = PD_FLOOR_BPS / 10_000
    floor_violations = df[(df["pd"] > 0) & (df["pd"] < pd_floor)]
    if len(floor_violations):
        report.add(ConsistencyCheck(
            f"pd_floor_{PD_FLOOR_BPS}bp", "WARN",
            f"{len(floor_violations)} exposures below {PD_FLOOR_BPS}bp PD floor "
            f"(will be floored in IRB)",
            metric=float(len(floor_violations)),
        ))


def _check_lgd_bounds(df: pd.DataFrame, report: ValidationReport) -> None:
    if "lgd" not in df.columns:
        return
    bad = df[(df["lgd"] < 0) | (df["lgd"] > 1)]
    if len(bad):
        report.add(ConsistencyCheck(
            "lgd_in_[0,1]", "FAIL",
            f"{len(bad)} exposures have LGD outside [0,1]",
            metric=float(len(bad)),
        ))
    else:
        report.add(ConsistencyCheck(
            "lgd_in_[0,1]", "PASS",
            "all LGDs within [0,1]",
        ))


def _check_ead_positive(df: pd.DataFrame, report: ValidationReport,
                        label: str = "") -> None:
    """EAD 비음수 검사.

    SA·IRB 북에 각각 호출되므로 **체크명이 달라야** 한다 — 같은 이름으로 두 번
    등록하면 이름으로 조회할 때 한쪽이 조용히 가려져, SA는 통과하고 IRB는
    실패한 상황이 통과로 보일 수 있다. (_check_rwa_nonneg와 동일 규약)
    """
    if "ead" not in df.columns:
        return
    name = f"ead_nonneg_{label}" if label else "ead_nonneg"
    bad = df[df["ead"] < 0]
    if len(bad):
        report.add(ConsistencyCheck(
            name, "FAIL",
            f"{len(bad)} exposures with negative EAD ({label or 'all'})",
            metric=float(len(bad)),
        ))
    else:
        report.add(ConsistencyCheck(
            name, "PASS",
            f"all EAD non-negative ({label or 'all'})",
        ))


def _check_rwa_nonneg(df: pd.DataFrame, report: ValidationReport, label: str) -> None:
    if "rwa" not in df.columns:
        return
    bad = df[df["rwa"] < -1e-6]
    if len(bad):
        report.add(ConsistencyCheck(
            f"{label}_rwa_nonneg", "FAIL",
            f"{len(bad)} exposures with negative RWA",
            metric=float(len(bad)),
        ))
    else:
        report.add(ConsistencyCheck(
            f"{label}_rwa_nonneg", "PASS",
            "all RWA non-negative",
        ))


def _check_el_le_ead(df: pd.DataFrame, report: ValidationReport) -> None:
    if not {"ead"}.issubset(df.columns):
        return
    if "el" in df.columns:
        bad = df[df["el"] > df["ead"] + 1e-6]
        if len(bad):
            report.add(ConsistencyCheck(
                "el_le_ead", "FAIL",
                f"{len(bad)} exposures with EL > EAD",
                metric=float(len(bad)),
            ))
        else:
            report.add(ConsistencyCheck("el_le_ead", "PASS", "EL <= EAD on every row"))


def _check_portfolio_intake(
    portfolio: pd.DataFrame | None, report: ValidationReport,
) -> None:
    """인제스트 완전성 — 들어온 것이 전부 산출에 들어갔는가.

    `_stage_split_books`는 자산군 5종으로 필터링한다. 목록에 없는 자산군의
    익스포저는 SA·IRB **양쪽에서 탈락**하고 RWA에서 소리 없이 사라진다.
    합성 데이터에서는 생기지 않지만 실데이터에서는 생기며, 지금까지 그것을 보는
    검사가 없었다. `exposure_id` 중복도 마찬가지다 — 중복 행이 있으면 RWA가
    경보 없이 이중계상된다.

    둘 다 advisory가 아니라 FAIL이다. 조용한 유실과 조용한 이중계상은 산출을
    무효로 만들지 결재자가 판단할 여지를 남기는 종류가 아니다.
    """
    if portfolio is None or not len(portfolio):
        return
    from risk_lib.pipeline import unbooked_exposures

    if "asset_class" in portfolio.columns:
        lost = unbooked_exposures(portfolio)
        if len(lost):
            kinds = sorted(set(lost["asset_class"].astype(str)))
            ead = float(lost["ead"].sum()) if "ead" in lost.columns else 0.0
            report.add(ConsistencyCheck(
                "intake_every_exposure_is_booked", "FAIL",
                f"{len(lost)}건 · EAD {ead:,.0f}이 SA·IRB 어느 북에도 없다 "
                f"— 자산군 {kinds}",
                metric=float(len(lost))))
        else:
            report.add(ConsistencyCheck(
                "intake_every_exposure_is_booked", "PASS",
                f"익스포저 {len(portfolio):,}건 전부 SA 또는 IRB 북에 들어갔다"))

    if "exposure_id" in portfolio.columns:
        dup = int(portfolio["exposure_id"].duplicated().sum())
        if dup:
            report.add(ConsistencyCheck(
                "intake_exposure_id_unique", "FAIL",
                f"exposure_id 중복 {dup}건 — RWA가 경보 없이 이중계상된다",
                metric=float(dup)))
        else:
            report.add(ConsistencyCheck(
                "intake_exposure_id_unique", "PASS",
                f"exposure_id {len(portfolio):,}건 유일"))


def _check_asof_provenance(meta: dict | None, report: ValidationReport) -> None:
    """기준일이 벽시계에서 왔는지 드러낸다.

    `run_pipeline(asof=None)`이면 `date.today()`가 들어가고, 같은 seed·같은
    데이터라도 실행 날짜가 다르면 헤드라인 지문이 달라진다. 기본값 자체를 막지는
    않되(호출부가 많다) 조용히 지나가지는 않게 한다.
    """
    if not meta:
        return
    src = meta.get("asof_source")
    if src == "wall_clock":
        report.add(ConsistencyCheck(
            "asof_is_explicit", "WARN",
            f"기준일 {meta.get('asof')}이 벽시계에서 왔다 (--asof 미지정) — "
            f"같은 seed라도 다른 날 실행하면 지문이 달라진다"))
    elif src == "explicit":
        report.add(ConsistencyCheck(
            "asof_is_explicit", "PASS",
            f"기준일 {meta.get('asof')}은 명시적으로 주어졌다"))


def _check_sa_irb_no_overlap(
    sa_df: pd.DataFrame, irb_df: pd.DataFrame, report: ValidationReport,
) -> None:
    sa_ids = set(sa_df["exposure_id"]) if "exposure_id" in sa_df.columns else set()
    irb_ids = set(irb_df["exposure_id"]) if "exposure_id" in irb_df.columns else set()
    overlap = sa_ids & irb_ids
    if overlap:
        report.add(ConsistencyCheck(
            "sa_irb_no_overlap", "FAIL",
            f"{len(overlap)} exposure_ids appear in both SA and IRB results",
            metric=float(len(overlap)),
        ))
    else:
        report.add(ConsistencyCheck(
            "sa_irb_no_overlap", "PASS",
            "SA and IRB exposure sets are disjoint",
        ))


def _check_bis_plausible(bis_result, report: ValidationReport) -> None:
    if bis_result is None:
        return
    # Each tier has its own Pillar 1 minimum (CRE10.4): CET1 4.5% / T1 6% / Total 8%.
    _MIN_KEY = {"cet1_ratio": "cet1", "tier1_ratio": "tier1", "total_ratio": "total"}
    for name, ratio in [
        ("cet1_ratio", bis_result.cet1_ratio),
        ("tier1_ratio", bis_result.tier1_ratio),
        ("total_ratio", bis_result.total_ratio),
    ]:
        if ratio < 0 or ratio > 1.0:
            report.add(ConsistencyCheck(
                f"bis_{name}_plausible", "FAIL",
                f"{name}={ratio:.4f} outside plausible [0,100%]", metric=ratio,
            ))
            continue
        minimum = BIS_MINIMUMS[_MIN_KEY[name]]
        if ratio < minimum:
            report.add(ConsistencyCheck(
                f"bis_{name}_min", "FAIL",
                f"{name} {ratio:.4f} below Pillar 1 minimum {minimum:.4f}",
                metric=ratio,
            ))
        else:
            report.add(ConsistencyCheck(
                f"bis_{name}_plausible", "PASS",
                f"{name}={ratio:.4f}", metric=ratio,
            ))

    # 완충자본 포함 요구치 대비 — Pillar 1 최저(4.5/6/8)만 보면 완충자본
    # 미달이 조용히 통과한다. 완충자본을 밑돌면 이익배당·자사주·성과급이
    # 제한되므로(자본보전완충자본 · 은행업감독규정 제26조), 산출이 맞더라도
    # **결과로서** 보고돼야 한다. 계산 결함이 아니므로 WARN이다 — Pillar 1
    # 미달은 위에서 이미 FAIL로 잡는다.
    short = {k: v for k, v in
             (getattr(bis_result, "surplus_shortfall", None) or {}).items()
             if v < 0}
    req = getattr(bis_result, "required", {}) or {}
    if short:
        report.add(ConsistencyCheck(
            "bis_buffer_requirement", "WARN",
            "완충자본 포함 요구치 미달 — " + " · ".join(
                f"{k} {v:+.2%} (요구 {req.get(k, 0.0):.2%})"
                for k, v in short.items())
            + " · 이익배당·성과급 제한 대상"))
    elif req:
        report.add(ConsistencyCheck(
            "bis_buffer_requirement", "PASS",
            "전 계층 완충자본 포함 요구치 충족"))

    # Ordering: Total >= Tier1 >= CET1 by construction
    # 세 비율이 같은 분모에 누적 분자를 쓰므로 순서는 구성상 성립한다. 통제로
    # 세지 않는다.
    if not (bis_result.total_ratio + 1e-9 >= bis_result.tier1_ratio
            >= bis_result.cet1_ratio - 1e-9):
        report.add(ConsistencyCheck(
            "bis_ratio_ordering", "FAIL",
            "expected total >= tier1 >= cet1 by construction",
            is_identity=True,
        ))
    else:
        report.add(ConsistencyCheck(
            "bis_ratio_ordering", "PASS",
            "구성상 성립. total >= tier1 >= cet1 (분자만 누적된다)",
            is_identity=True,
        ))


def _check_rwa_aggregate(
    rwa_total: float | None,
    bis_result,
    report: ValidationReport,
) -> None:
    """BIS 분모로 넘긴 RWA와 BIS 결과의 RWA가 같은가.

    파이프라인은 `compute_bis_ratios(capital, rwa_final)`로 만든 뒤 같은
    `rwa_final`을 이 검사에 넘긴다. 그때 두 항은 같은 float 객체이고 이 검사는
    실패할 수 없다. 그 경우를 `is_identity`로 표시해 통제 건수에서 뺀다.
    구성요소에서 다시 합산해 맞추는 대사는 `_check_rwa_components`가 한다.
    """
    if rwa_total is None or bis_result is None:
        return
    identity = rwa_total is bis_result.rwa
    diff = abs(rwa_total - bis_result.rwa) / max(rwa_total, 1.0)
    if diff > 1e-6:
        report.add(ConsistencyCheck(
            "rwa_matches_bis_input", "FAIL",
            f"sum(rwa)={rwa_total:.2f} vs BIS input rwa={bis_result.rwa:.2f}",
            metric=diff,
        ))
    else:
        report.add(ConsistencyCheck(
            "rwa_matches_bis_input", "PASS",
            ("구성상 성립. BIS 분모로 넘긴 값을 그대로 되받는다 "
             f"({rwa_total:.2f})") if identity
            else f"aggregate RWA reconciles ({rwa_total:.2f})",
            is_identity=identity,
        ))


def _check_rwa_components(
    sa_results: pd.DataFrame | None,
    irb_results: pd.DataFrame | None,
    market_rwa: float | None,
    op_rwa: float | None,
    ccr_rwa: float | None,
    structured_rwa: float | None,
    of_result,
    rwa_total_for_bis: float | None,
    report: ValidationReport,
) -> None:
    """구성요소 원장에서 다시 합산한 RWA가 최종 RWA와 맞는가.

    기존 검사는 부호·범위만 보거나 같은 값을 자기 자신과 비교해, SA·IRB 산출
    프레임을 통째로 변조해도 상태가 바뀌는 검사가 한 건도 없었다. 이 검사는
    **행 단위 프레임**에서 다시 합산해 헤드라인까지 잇는다.

    Σsa + Σirb + CCR + 시장 + 운영 + 구조화 + output floor 가산분 = 최종 RWA

    CCR·구조화가 넘어오지 않으면 그 둘을 `output_floor_result.rwa_internal`의
    잔여로만 확인할 수 있다. 그때는 대사가 부분적이라는 사실을 WARN으로 남긴다.
    "돌지 않았다"와 "통과했다"를 같은 칸에 넣지 않는다.
    """
    name = "rwa_components_reconcile"
    if of_result is None or rwa_total_for_bis is None:
        report.add(ConsistencyCheck(
            name, "WARN",
            "output floor 결과 또는 최종 RWA가 없어 구성요소 대사를 못 한다"))
        return

    parts: dict[str, float] = {}
    if sa_results is not None and "rwa" in getattr(sa_results, "columns", []):
        parts["신용SA"] = float(sa_results["rwa"].sum())
    if irb_results is not None and "rwa" in getattr(irb_results, "columns", []):
        parts["신용IRB"] = float(irb_results["rwa"].sum())
    if market_rwa is not None:
        parts["시장"] = float(market_rwa)
    if op_rwa is not None:
        parts["운영"] = float(op_rwa)

    internal = float(of_result.rwa_internal)
    add_on = float(getattr(of_result, "add_on", 0.0) or 0.0)
    partial = ccr_rwa is None or structured_rwa is None
    if not partial:
        parts["CCR"] = float(ccr_rwa)
        parts["구조화"] = float(structured_rwa)
        recomputed = sum(parts.values())
    else:
        # 잔여로만 확인한다. 음수가 나오면 구성요소 합이 내부 RWA를 넘은 것이다.
        residual = internal - sum(parts.values())
        parts["CCR+구조화 (잔여)"] = residual
        recomputed = internal

    contrib = " · ".join(f"{k} {v/1e12:,.2f}조" for k, v in parts.items())
    residual_negative = partial and parts["CCR+구조화 (잔여)"] < -max(
        1.0, 1e-9 * internal)
    gap = abs(recomputed + add_on - float(rwa_total_for_bis))
    rel = gap / max(float(rwa_total_for_bis), 1.0)

    if residual_negative:
        report.add(ConsistencyCheck(
            name, "FAIL",
            f"구성요소 합이 내부 RWA를 초과한다 (잔여 "
            f"{parts['CCR+구조화 (잔여)']:,.0f} KRW < 0). 기여도: {contrib}",
            metric=parts["CCR+구조화 (잔여)"]))
        return
    if rel > 1e-6:
        report.add(ConsistencyCheck(
            name, "FAIL",
            f"구성요소 합 + floor 가산분 {recomputed + add_on:,.0f} ≠ 최종 RWA "
            f"{float(rwa_total_for_bis):,.0f} (Δ {gap:,.0f} KRW). 기여도: {contrib}",
            metric=rel))
        return
    report.add(ConsistencyCheck(
        name, "WARN" if partial else "PASS",
        (f"부분 대사. CCR·구조화 RWA가 검사에 넘어오지 않아 잔여로 처리했다. "
         if partial else "")
        + f"{contrib} · floor 가산분 {add_on/1e12:,.2f}조 = 최종 RWA "
          f"{float(rwa_total_for_bis)/1e12:,.2f}조",
        metric=rel))


def _check_leverage(leverage_result, report: ValidationReport) -> None:
    if leverage_result is None:
        return
    lr = leverage_result.leverage_ratio
    if lr < 0 or lr > 1:
        report.add(ConsistencyCheck("leverage_plausible", "FAIL",
                   f"leverage ratio {lr:.4f} outside [0,1]", metric=lr))
        return
    if not leverage_result.passes():
        report.add(ConsistencyCheck("leverage_min_3pct", "FAIL",
                   f"leverage ratio {lr:.4%} below required {leverage_result.required:.4%}",
                   metric=lr))
    else:
        report.add(ConsistencyCheck("leverage_min_3pct", "PASS",
                   f"leverage ratio {lr:.4%} >= {leverage_result.required:.4%}",
                   metric=lr))


def _check_output_floor(of_result, report: ValidationReport) -> None:
    if of_result is None:
        return
    if of_result.rwa_final + 1e-6 < of_result.rwa_internal:
        report.add(ConsistencyCheck("output_floor_no_reduction", "FAIL",
                   "floored RWA is below internal RWA (floor must not reduce RWA)"))
    else:
        status = "WARN" if of_result.is_binding else "PASS"
        detail = (f"floor binding: +{of_result.add_on:,.0f} add-on"
                  if of_result.is_binding else "internal RWA above floor")
        report.add(ConsistencyCheck("output_floor_applied", status, detail,
                   metric=of_result.rwa_final))


def _check_market_op_rwa(market_rwa, op_rwa, report: ValidationReport,
                         total_ead: float | None = None) -> None:
    """시장·운영리스크 RWA. 부호만 보면 0으로 지워도 통과한다.

    운영리스크는 영업 중인 은행이면 0일 수 없다. OPE25의 사업지표(BI)가 수익·
    비용에서 나오므로 익스포저가 있는 한 양수다. 그래서 익스포저가 있는데 0이면
    FAIL이다. 시장리스크는 트레이딩계정이 없으면 0일 수 있으므로 WARN으로 둔다.
    """
    for label, val, zero_status in [("market_rwa_nonneg", market_rwa, "WARN"),
                                    ("op_rwa_nonneg", op_rwa, "FAIL")]:
        if val is None:
            continue
        if val < 0:
            report.add(ConsistencyCheck(label, "FAIL", f"{label} is negative", metric=val))
        elif val == 0 and total_ead:
            report.add(ConsistencyCheck(
                label, zero_status,
                f"익스포저 {float(total_ead):,.0f} KRW가 있는데 RWA가 0이다",
                metric=0.0))
        else:
            report.add(ConsistencyCheck(label, "PASS", f"{val:,.0f}", metric=val))


def _check_market_portfolio_split(market_positions, market_rwa,
                                  report: ValidationReport) -> None:
    """포트폴리오 분해가 시장 RWA 를 보존하는지 (일원화 대사).

    mkt_position 은 엔진 순포지션을 설정 가중치로 가른 것이고, 포트폴리오
    자본은 같은 SSA 산식으로 다시 계산된다. 가중치가 위험군별 합 1.0·전부
    양수라는 전제가 깨지면 이 합이 시장 RWA 와 갈라진다 — 그때 포지션은
    조용히 새거나 두 번 세어진 것이다. 입력이 없으면 검사하지 않았음을
    WARN 으로 남긴다 (fail-open 금지).
    """
    name = "market_portfolio_split_reconciles"
    if market_positions is None or market_rwa is None:
        report.add(ConsistencyCheck(
            name, "WARN", "시장 포지션이 넘어오지 않아 분해 대사를 하지 않았다"))
        return
    from risk_lib import market_portfolio as mp
    asof = "0000-00-00"                     # 대사에는 기준일이 필요 없다
    split = mp.split_positions(market_positions, asof=asof)
    got = float(mp.capital_frame(split)["rwa"].sum())
    want = float(market_rwa)
    tol = max(abs(want), 1.0) * 1e-9
    if abs(got - want) > tol:
        report.add(ConsistencyCheck(
            name, "FAIL",
            f"포트폴리오 자본 합 {got:,.0f} 이 시장 RWA {want:,.0f} 와 다르다",
            metric=got - want))
    else:
        report.add(ConsistencyCheck(name, "PASS",
                                    f"{len(split)}행 분해 · 합 보존", metric=got))


def _check_ecl(ecl_results: pd.DataFrame, report: ValidationReport) -> None:
    if ecl_results is None or "ecl" not in ecl_results.columns:
        return
    if (ecl_results["ecl"] < -1e-6).any():
        report.add(ConsistencyCheck("ecl_nonneg", "FAIL",
                   "negative ECL present", metric=float((ecl_results["ecl"] < 0).sum())))
    else:
        report.add(ConsistencyCheck("ecl_nonneg", "PASS", "all ECL non-negative"))

    if "stage" in ecl_results.columns and "coverage_ratio" in ecl_results.columns:
        cov = ecl_results.groupby("stage")["coverage_ratio"].mean()
        s1, s2, s3 = cov.get(1, 0.0), cov.get(2, 0.0), cov.get(3, 0.0)
        if s1 - 1e-9 <= s2 <= s3 + 1e-9 or (s3 >= s2 >= s1):
            report.add(ConsistencyCheck("ecl_stage_coverage_monotone", "PASS",
                       f"coverage S1={s1:.4f} <= S2={s2:.4f} <= S3={s3:.4f}"))
        else:
            report.add(ConsistencyCheck("ecl_stage_coverage_monotone", "WARN",
                       f"non-monotone coverage S1={s1:.4f} S2={s2:.4f} S3={s3:.4f}"))


def _check_concentration(conc_df: pd.DataFrame, report: ValidationReport,
                         threshold: float = 0.18) -> None:
    if conc_df is None or "hhi" not in conc_df.columns:
        return
    breached = conc_df[conc_df["hhi"] > threshold]
    if len(breached):
        dims = ", ".join(f"{r['dimension']}={r['hhi']:.3f}"
                         for _, r in breached.iterrows())
        report.add(ConsistencyCheck("concentration_hhi", "WARN",
                   f"HHI above {threshold} on: {dims}", metric=float(len(breached))))
    else:
        report.add(ConsistencyCheck("concentration_hhi", "PASS",
                   f"all dimensions below HHI {threshold}"))


def _check_stress_monotone(stress_df: pd.DataFrame, report: ValidationReport) -> None:
    if stress_df is None or "scenario" not in stress_df.columns:
        return
    df = stress_df.set_index("scenario")
    if "baseline" not in df.index:
        return
    base_rwa = df.loc["baseline", "rwa_total"]
    base_cet1 = df.loc["baseline", "cet1_ratio"]
    bad = []
    for sc in df.index:
        if sc == "baseline":
            continue
        if df.loc[sc, "rwa_total"] + 1e-6 < base_rwa:
            bad.append(f"{sc}: RWA fell under stress")
        if df.loc[sc, "cet1_ratio"] - 1e-9 > base_cet1:
            bad.append(f"{sc}: CET1 ratio rose under stress")
    if bad:
        report.add(ConsistencyCheck("stress_monotone", "FAIL", "; ".join(bad)))
    else:
        report.add(ConsistencyCheck("stress_monotone", "PASS",
                   "stressed RWA >= base and CET1 ratio <= base for all scenarios"))


def _check_macro_ecl(macro, report: ValidationReport) -> None:
    if macro is None:
        return
    raw_prob = sum(s.probability for s in macro.scenarios)
    if abs(raw_prob - 1.0) > 1e-6:
        report.add(ConsistencyCheck("macro_scenario_prob_sum", "WARN",
                   f"scenario probabilities sum to {raw_prob:.4f} (renormalised)",
                   metric=raw_prob))
    else:
        report.add(ConsistencyCheck("macro_scenario_prob_sum", "PASS",
                   "scenario probabilities sum to 1", metric=raw_prob))

    ecls = macro.by_scenario["ecl"].values
    lo, hi = float(ecls.min()), float(ecls.max())
    if not (lo - 1e-6 <= macro.weighted_total <= hi + 1e-6):
        report.add(ConsistencyCheck("macro_weighted_in_range", "FAIL",
                   f"weighted ECL {macro.weighted_total:.0f} outside scenario "
                   f"range [{lo:.0f}, {hi:.0f}]"))
    else:
        report.add(ConsistencyCheck("macro_weighted_in_range", "PASS",
                   f"weighted ECL within scenario range", metric=macro.weighted_total))

    # Worse macro state should not produce lower ECL.  Rank by the cumulative
    # systematic factor actually applied (z-path sum over a common horizon),
    # which accounts for path shape/length and reversion — not the bare GDP sum.
    horizon = max((len(s.gdp_path) for s in macro.scenarios), default=1)
    order = sorted(range(len(macro.scenarios)),
                   key=lambda i: float(macro.scenarios[i].z_path(horizon).sum()))
    ordered_ecl = [macro.by_scenario["ecl"].iloc[i] for i in order]
    monotone = all(ordered_ecl[k] <= ordered_ecl[k + 1] + 1e-6
                   for k in range(len(ordered_ecl) - 1))
    if monotone:
        report.add(ConsistencyCheck("macro_ecl_gdp_monotone", "PASS",
                   "ECL non-decreasing as GDP path worsens"))
    else:
        report.add(ConsistencyCheck("macro_ecl_gdp_monotone", "WARN",
                   "ECL not monotone in GDP severity"))


def _check_ecl_ttc_pit_gap(macro, ecl_total: float | None,
                           report: ValidationReport) -> None:
    """TTC(서식·충당금 기준)와 PIT(확률가중 KPI)의 관계를 드러낸다.

    두 값은 정의가 달라 다른 것이 정상이다. 문제는 그 차이가 **보고되지 않고**
    지나가는 것이다 — 어느 쪽이 결재 근거인지 묻지 않게 되면, 같은 이름의 ECL이
    화면마다 다른 값을 갖는 상태로 굳는다.

    forward-looking uplift가 음수면 거시연계가 완화 방향으로 작동한 것이라
    IFRS 9 취지와 어긋날 수 있으므로 WARN으로 올린다.
    """
    if macro is None or ecl_total is None:
        return
    ttc = float(ecl_total)
    pit = float(macro.weighted_total)
    if ttc <= 0:
        return
    uplift = pit - ttc
    detail = (f"TTC {ttc:,.0f} · PIT {pit:,.0f} · forward-looking uplift "
              f"{uplift:+,.0f} ({uplift / ttc:+.1%})")
    if uplift < 0:
        report.add(ConsistencyCheck("ecl_ttc_pit_gap", "WARN",
                   detail + " — 거시연계가 충당금을 낮추는 방향이다",
                   metric=uplift / ttc))
    else:
        report.add(ConsistencyCheck("ecl_ttc_pit_gap", "PASS", detail,
                   metric=uplift / ttc))


def _check_reverse_stress(rev, report: ValidationReport) -> None:
    if rev is None:
        return
    if rev.already_breached:
        report.add(ConsistencyCheck("reverse_base_above_target", "FAIL",
                   f"base {rev.metric} {rev.base_ratio:.4f} already at/below break "
                   f"{rev.target_ratio:.4f}", metric=rev.base_ratio))
        return
    if rev.resilient:
        report.add(ConsistencyCheck("reverse_stress_solved", "PASS",
                   f"resilient: {rev.metric} stays above {rev.target_ratio:.4f} "
                   f"at max severity {rev.critical_severity:.2f}",
                   metric=rev.critical_severity))
        return
    if rev.converged:
        report.add(ConsistencyCheck("reverse_stress_solved", "PASS",
                   f"break at severity {rev.critical_severity:.3f} "
                   f"(GDP {rev.implied_gdp_shock:+.1%}, LGD +{rev.implied_lgd_addon:.1%})",
                   metric=rev.critical_severity))
    else:
        report.add(ConsistencyCheck("reverse_stress_solved", "WARN",
                   f"bisection did not converge within max_iter "
                   f"(severity {rev.critical_severity:.3f})"))


def _check_stress_path(path_df: pd.DataFrame, report: ValidationReport) -> None:
    if path_df is None or "scenario" not in getattr(path_df, "columns", []):
        return
    # CET1 ratio must stay within [0,1] at every projected quarter.
    if ((path_df["cet1_ratio"] < 0) | (path_df["cet1_ratio"] > 1)).any():
        report.add(ConsistencyCheck("stress_path_cet1_plausible", "FAIL",
                   "projected CET1 ratio outside [0,1] in some quarter"))
    else:
        report.add(ConsistencyCheck("stress_path_cet1_plausible", "PASS",
                   "projected CET1 within [0,1] every quarter"))

    # Deeper narratives must trough no higher than milder ones.
    trough = path_df.groupby("scenario", sort=False)["cet1_ratio"].min()
    order = ["baseline", "adverse", "severely_adverse"]
    present = [s for s in order if s in trough.index]
    vals = [trough[s] for s in present]
    if all(vals[k] >= vals[k + 1] - 1e-9 for k in range(len(vals) - 1)):
        report.add(ConsistencyCheck("stress_path_trough_ordering", "PASS",
                   "trough CET1 non-increasing across baseline→adverse→severe"))
    else:
        report.add(ConsistencyCheck("stress_path_trough_ordering", "WARN",
                   f"trough CET1 not ordered by severity: "
                   f"{ {s: round(trough[s], 4) for s in present} }"))


def _check_pd_model_quality(
    pd_metrics: dict | None, report: ValidationReport,
) -> None:
    """Per-segment discrimination: Gini ≥ GINI_MIN_ACCEPTABLE (BCBS WP14)."""
    from risk_lib.references import GINI_MIN_ACCEPTABLE, GINI_MIN_GOOD
    if not pd_metrics:
        return
    for seg, m in pd_metrics.items():
        g = float(m.get("gini", 0.0))
        if g < GINI_MIN_ACCEPTABLE:
            report.add(ConsistencyCheck(
                f"pd_gini_{seg}", "FAIL",
                f"{seg} Gini {g:.3f} < 변별력 하한 {GINI_MIN_ACCEPTABLE} "
                f"(BCBS WP14)", metric=g))
        elif g < GINI_MIN_GOOD:
            report.add(ConsistencyCheck(
                f"pd_gini_{seg}", "WARN",
                f"{seg} Gini {g:.3f} acceptable but below 양호 기준 "
                f"{GINI_MIN_GOOD}", metric=g))
        else:
            report.add(ConsistencyCheck(
                f"pd_gini_{seg}", "PASS",
                f"{seg} Gini {g:.3f} ≥ {GINI_MIN_GOOD} 양호", metric=g))


def _check_hl_calibration(backtest: dict | None, report: ValidationReport) -> None:
    """Hosmer-Lemeshow PD calibration p-value ≥ 0.05 → PASS."""
    from risk_lib.references import HL_P_VALUE_MIN
    if not backtest or "hosmer_lemeshow" not in backtest:
        return
    hl = backtest["hosmer_lemeshow"]
    p = float(hl.get("p_value", 0.0))
    if p < HL_P_VALUE_MIN:
        report.add(ConsistencyCheck(
            "pd_hl_calibration", "WARN",
            f"HL p-value {p:.3f} < {HL_P_VALUE_MIN} — 캘리브레이션 의심 "
            f"(χ²={hl.get('chi_square', 0):.2f})", metric=p))
    else:
        report.add(ConsistencyCheck(
            "pd_hl_calibration", "PASS",
            f"HL p={p:.3f} ≥ {HL_P_VALUE_MIN}", metric=p))


def _check_backtest_traffic_light(
    backtest: dict | None, report: ValidationReport,
) -> None:
    """Per-grade binomial: zero RED zones; YELLOW count surfaced as WARN."""
    if not backtest or "per_grade" not in backtest:
        return
    z = backtest["per_grade"]["zone"].value_counts().to_dict()
    red = int(z.get("RED", 0))
    yellow = int(z.get("YELLOW", 0))
    if red > 0:
        report.add(ConsistencyCheck(
            "pd_backtest_zones", "FAIL",
            f"{red} grade(s) in RED zone — realised DR significantly above PD",
            metric=float(red)))
    elif yellow > 0:
        report.add(ConsistencyCheck(
            "pd_backtest_zones", "WARN",
            f"{yellow} grade(s) in YELLOW zone", metric=float(yellow)))
    else:
        report.add(ConsistencyCheck(
            "pd_backtest_zones", "PASS",
            "all grades in GREEN zone"))


def _lex_denominator_basis(ledgers: dict | None, framework: str) -> str | None:
    """거액익스포저 설정 원장에서 분모기준을 읽는다. 없으면 None."""
    if not ledgers:
        return None
    setting = ledgers.get("lex_setting")
    if not isinstance(setting, pd.DataFrame) or setting.empty:
        return None
    hit = setting.loc[setting["framework"] == framework, "denominator_basis"]
    return str(hit.iloc[0]) if len(hit) else None


def _check_large_exposure(limit_report: pd.DataFrame | None,
                          report: ValidationReport,
                          ledgers: dict | None = None) -> None:
    """동일차주 한도 위반 판정.

    이전 판은 `limit_report`가 없거나 비면 '위반 없음'으로 PASS를 냈다. 한도
    산출이 빠진 실행과 위반이 없는 실행이 같은 칸에 들어갔다 (fail-open).
    또 사유문에 '은행법 §35'라고 적었는데 이 축의 분모는 기본자본이고, 원장
    `lex_setting`이 확정한 은행법 §35의 분모는 자기자본이다. 분모기준은 원장에서
    읽어 적는다.
    """
    basis = _lex_denominator_basis(ledgers, "감독규정26조_기본자본")
    basis_txt = (f"분모기준 {basis} (감독규정 제26조, lex_setting)" if basis
                 else "분모기준 미확인 (lex_setting 원장이 검사에 없다)")
    if limit_report is None or limit_report.empty:
        report.add(ConsistencyCheck(
            "large_exposure_25pct", "WARN",
            f"한도 리포트 부재. 위반 없음과 구별되지 않는다. {basis_txt}"))
        return
    obligor_breaches = limit_report[
        (limit_report["limit"].astype(str).str.contains("동일차주"))
        & (limit_report["severity"].isin(["BREACH", "CRITICAL"]))
    ]
    if len(obligor_breaches):
        report.add(ConsistencyCheck(
            "large_exposure_25pct", "FAIL",
            f"{len(obligor_breaches)} 차주가 25% 한도 위반 · {basis_txt}",
            metric=float(len(obligor_breaches))))
    else:
        report.add(ConsistencyCheck(
            "large_exposure_25pct", "PASS",
            f"동일차주 축 전건 25% 한도 이내 · {basis_txt}"))


def _check_large_exposure_sources(limit_report: pd.DataFrame | None,
                                  ledgers: dict | None,
                                  report: ValidationReport) -> None:
    """거액익스포저 산출이 두 벌로 갈려 있지 않은가.

    한도엔진의 동일차주 축은 기본자본 25%로, 원장 `lex_position`의
    은행법35조_동일차주는 자기자본 25%로 판정한다. 두 산출이 같은 기준일에
    다른 위반 건수를 낸다. 지금은 어느 쪽이 정본인지 산출물에서 읽히지 않으므로
    두 값을 나란히 적어 남긴다.
    """
    name = "large_exposure_two_sources"
    pos = (ledgers or {}).get("lex_position")
    if not isinstance(pos, pd.DataFrame) or pos.empty:
        report.add(ConsistencyCheck(
            name, "WARN", "거액익스포저 원장(lex_position)이 검사에 없다"))
        return
    kr = pos[pos["framework"] == "은행법35조_동일차주"]
    n_ledger = int(kr["breach"].sum()) if "breach" in kr.columns else 0
    basis_ledger = _lex_denominator_basis(ledgers, "은행법35조_동일차주") or "미확인"
    if limit_report is None or limit_report.empty:
        n_engine = None
    else:
        n_engine = int(len(limit_report[
            (limit_report["limit"].astype(str).str.contains("동일차주"))
            & (limit_report["severity"].isin(["BREACH", "CRITICAL"]))]))
    basis_engine = _lex_denominator_basis(ledgers, "감독규정26조_기본자본") or "미확인"
    detail = (f"원장 은행법35조_동일차주({basis_ledger}) 위반 {n_ledger}건 · "
              f"한도엔진 동일차주({basis_engine}) 위반 "
              + ("미산출" if n_engine is None else f"{n_engine}건"))
    if n_engine is None or n_engine != n_ledger:
        report.add(ConsistencyCheck(
            name, "WARN",
            detail + ". 분모기준이 달라 두 산출이 어긋난다. 정본을 하나로 "
                     "정하지 않으면 어느 쪽이 결재 대상인지 산출물에서 읽히지 않는다",
            metric=float(n_ledger)))
    else:
        report.add(ConsistencyCheck(name, "PASS", detail,
                                    metric=float(n_ledger)))


def _check_macro_ecl_path(path_df: pd.DataFrame, report: ValidationReport) -> None:
    if path_df is None or "scenario" not in getattr(path_df, "columns", []):
        return
    if (path_df["ecl"] < -1e-6).any():
        report.add(ConsistencyCheck("macro_path_ecl_nonneg", "FAIL",
                   "negative ECL in quarterly allowance path"))
    else:
        report.add(ConsistencyCheck("macro_path_ecl_nonneg", "PASS",
                   "quarterly ECL path non-negative"))
    # The probability-weighted path must lie within the scenario envelope each quarter.
    scen = path_df[path_df["scenario"] != "weighted"]
    wq = path_df[path_df["scenario"] == "weighted"].set_index("q_index")["ecl"]
    if not wq.empty and not scen.empty:
        env = scen.groupby("q_index")["ecl"].agg(["min", "max"])
        ok = all(env.loc[i, "min"] - 1e-6 <= wq[i] <= env.loc[i, "max"] + 1e-6
                 for i in wq.index)
        if ok:
            report.add(ConsistencyCheck("macro_path_weighted_in_envelope", "PASS",
                       "weighted ECL within scenario envelope every quarter"))
        else:
            report.add(ConsistencyCheck("macro_path_weighted_in_envelope", "FAIL",
                       "weighted ECL outside scenario envelope in some quarter"))


def _check_alm(alm: dict | None, report: ValidationReport) -> None:
    """LCR/NSFR 100% 하한, IRRBB outlier test, 재무상태표-여신 정합."""
    if not alm:
        return
    from risk_lib.references import (
        LCR_MIN, NSFR_MIN, IRRBB_OUTLIER_EVE_PCT_TIER1,
    )

    lcr = alm.get("lcr")
    if lcr is not None:
        if lcr.lcr >= LCR_MIN:
            report.add(ConsistencyCheck(
                "lcr_min_100pct", "PASS",
                f"LCR {lcr.lcr:.1%} ≥ 100%", metric=lcr.lcr))
        else:
            report.add(ConsistencyCheck(
                "lcr_min_100pct", "FAIL",
                f"LCR {lcr.lcr:.1%} < 100% (LCR20.1)", metric=lcr.lcr))
        if lcr.inflow_capped >= 0.75 * lcr.gross_outflow - 1e-6 and \
                lcr.inflow_capped > 0:
            report.add(ConsistencyCheck(
                "lcr_inflow_cap", "PASS",
                "inflow cap (75% of outflows) binding — applied per LCR40"))
        else:
            report.add(ConsistencyCheck(
                "lcr_inflow_cap", "PASS",
                "inflows below 75% cap"))

    nsfr = alm.get("nsfr")
    if nsfr is not None:
        if nsfr.nsfr >= NSFR_MIN:
            report.add(ConsistencyCheck(
                "nsfr_min_100pct", "PASS",
                f"NSFR {nsfr.nsfr:.1%} ≥ 100%", metric=nsfr.nsfr))
        else:
            report.add(ConsistencyCheck(
                "nsfr_min_100pct", "FAIL",
                f"NSFR {nsfr.nsfr:.1%} < 100% (NSF20.1)", metric=nsfr.nsfr))

    irrbb = alm.get("irrbb")
    if irrbb is not None:
        pct = irrbb.worst_pct_tier1
        if pct > IRRBB_OUTLIER_EVE_PCT_TIER1:
            report.add(ConsistencyCheck(
                "irrbb_outlier_15pct", "FAIL",
                f"최대 ΔEVE 감소 {pct:.1%} of Tier1 > 15% (SRP31.92 outlier)",
                metric=pct))
        elif irrbb.early_warning():
            report.add(ConsistencyCheck(
                "irrbb_outlier_15pct", "WARN",
                f"최대 ΔEVE 감소 {pct:.1%} of Tier1 — 조기경보(12%) 초과",
                metric=pct))
        else:
            report.add(ConsistencyCheck(
                "irrbb_outlier_15pct", "PASS",
                f"최대 ΔEVE 감소 {pct:.1%} of Tier1 ≤ 15% "
                f"(worst: {irrbb.worst_eve_scenario})", metric=pct))

    bs = alm.get("balance_sheet")
    if bs is not None:
        gap_ok = abs(bs.total_assets - bs.funding_total() - bs.equity) \
            <= 1e-6 * bs.total_assets
        if gap_ok:
            report.add(ConsistencyCheck(
                "bs_balances", "PASS",
                "자산 = 부채 + 자본 (재무상태표 정합)"))
        else:
            report.add(ConsistencyCheck(
                "bs_balances", "FAIL",
                "재무상태표 차변/대변 불일치"))

    _check_alm_ledgers(alm, report)


# ---------------------------------------------------------------- ALM 원장 대사
#
# ALM 산출은 원장 여러 장을 거쳐 접힌다(계약 → 현금흐름 → 버킷 → ΔEVE·사다리).
# 접는 단계마다 합이 보존되는지 보지 않으면, 중간에서 흘린 금액이 헤드라인
# 한 줄에 흡수되어 보이지 않는다. 아래 세 검사가 그 세 단계의 항등식이다.
# 상대허용오차는 부동소수 누적오차만 흡수할 크기로 둔다 — 느슨하게 잡으면
# 실제 누락을 통과시킨다.
_ALM_TIE_RTOL = 1e-9


def _rel_gap(a: float, b: float) -> float:
    scale = max(abs(a), abs(b), 1.0)
    return abs(a - b) / scale


def _check_delta_eve_recalc(alm: dict, bp: pd.DataFrame, res: pd.DataFrame,
                            report: ValidationReport) -> None:
    """ΔEVE를 모수 원장에서 다시 만든 할인계수로 재계산해 결과 원장과 대사한다.

    결과 원장의 `delta_eve`는 버킷 원장의 `delta_pv` 합으로 **정의**되므로,
    같은 프레임 안에서 접어 비교하면 무엇을 망가뜨려도 통과한다. 여기서는
    `alm_rate_shock_param`·`alm_scenario_def`·`alm_post_shock_floor`와 기저곡선
    으로 충격곡선을 다시 만들어 `DF(t)`를 새로 계산한다. 현금흐름은 버킷
    원장의 것을 쓰되(그 합은 (1) 검사가 명목과 대사한다) **할인은 독립 경로**다.

    재계산은 현금흐름 할인분만 만든다. 제13항 나의 자동금리옵션 리스크가
    `delta_eve`에 반영되면(`auto_option_reflected=True`) 이 재계산에도 같은 항을
    더해야 하며, 그때까지는 옵션 항이 반영된 실행에서 이 검사가 그 금액만큼
    벌어진다. 배선이 옵션 원장을 넘기기 시작하면 여기도 함께 고쳐야 한다.
    """
    from risk_lib.alm.curves import discount_factors
    from risk_lib.alm.irrbb import build_shocked_curves

    name = "alm_delta_eve_independent_recalc"
    curve = alm.get("base_curve")
    tables = alm.get("tables") or {}
    need = ("alm_rate_shock_param", "alm_scenario_def", "alm_post_shock_floor")
    missing = [t for t in need if t not in tables]
    ccys = sorted({str(c) for c in bp["ccy"]})
    if curve is None or missing or len(ccys) != 1:
        report.add(ConsistencyCheck(
            name, "WARN",
            "ΔEVE 독립 재계산을 하지 못했다 — "
            + ("기저곡선 없음" if curve is None else "")
            + (f"모수 원장 누락 {missing}" if missing else "")
            + (f"통화 {len(ccys)}종에 기저곡선 1벌" if len(ccys) != 1 else "")))
        return

    shocked, _w = build_shocked_curves(
        {ccys[0]: curve},
        scenarios=tuple(dict.fromkeys(str(s) for s in bp["scenario"])),
        shock_param=tables[need[0]], scenario_def=tables[need[1]],
        floor=tables[need[2]],
        framework_version=str(res["framework_version"].iloc[0]),
        allow_proxy=True)

    # 통화별로 접은 뒤 **손실 통화만** 더한다 ([별표 9-1] 제13항 다). 통화 축을
    # 접기 전에 합산하면 이익 통화가 손실 통화를 상계하고, 그 값은 결과 원장의
    # `delta_eve`가 아니라 `delta_eve_gross`와 짝이 된다. 충격후 하한 0(제12항
    # 다)이 걸리면서 하락 시나리오가 이익으로 나오는 조합이 생겼고, 상계 규칙을
    # 빼고 대사하던 이 검사가 그때 FAIL을 냈다.
    per_ccy: dict[tuple[str, str, str], float] = {}
    for (basis, sc, ccy), g in bp.groupby(["basis", "scenario", "ccy"]):
        shk = shocked.get((str(ccy), str(sc)))
        if shk is None:
            continue
        t = g["t_mid"].to_numpy(dtype=float)
        per_ccy[(str(basis), str(sc), str(ccy))] = float(
            (g["cf"].to_numpy(dtype=float) * discount_factors(shk.curve, t)
             - g["cf_base"].to_numpy(dtype=float) * discount_factors(curve, t)
             ).sum())
    recalc: dict[tuple[str, str], float] = {}
    for (basis, sc, _ccy), v in per_ccy.items():
        recalc[(basis, sc)] = recalc.get((basis, sc), 0.0) + min(v, 0.0)

    want = res.set_index(["basis", "scenario"])["delta_eve"]
    skipped = [k for k in want.index if (str(k[0]), str(k[1])) not in recalc]
    worst, worst_key = 0.0, None
    for k, v in want.items():
        got = recalc.get((str(k[0]), str(k[1])))
        if got is None:
            continue
        gap = _rel_gap(float(v), got)
        if gap > worst:
            worst, worst_key = gap, k
    if worst > _ALM_TIE_RTOL:
        report.add(ConsistencyCheck(
            name, "FAIL",
            f"ΔEVE 재계산이 결과 원장과 어긋난다 — {worst_key} 상대오차 "
            f"{worst:.2e}. 충격곡선이 결과 원장에 반영되지 않았을 수 있다",
            metric=worst))
    elif skipped:
        report.add(ConsistencyCheck(
            name, "WARN",
            f"충격 모수가 없어 재계산하지 못한 조합 {len(skipped)}개 "
            f"({skipped[:3]})", metric=float(len(skipped))))
    else:
        report.add(ConsistencyCheck(
            name, "PASS",
            f"모수 원장에서 다시 만든 할인계수로 ΔEVE 재계산 일치 "
            f"({len(recalc)}개 산출기준×시나리오, 최대 상대오차 {worst:.2e})",
            metric=worst))


def _check_irrbb_single_source(alm: dict, stress_path, report: ValidationReport,
                               ) -> None:
    """이사회 팩에 실리는 ΔEVE가 ALM 엔진 한 곳에서 나오는지.

    `stress/multi_axis`는 할인 없는 갭 근사 `-(gap·t_mid·Δr)`로 ΔEVE를 자체
    산출해 왔고, 그 값이 `alm_irrbb_result`와 **부호까지** 갈린 채 같은 팩에
    실렸다. 모형이 두 벌인 것은 상수 별사본보다 상위의 결함이므로 검사로
    고정한다.
    """
    name = "alm_irrbb_engine_single_source"
    if stress_path is None or not len(stress_path):
        return
    if "irrbb_source" not in stress_path.columns:
        report.add(ConsistencyCheck(
            name, "FAIL",
            "stress_path에 ΔEVE 산출 출처 컬럼이 없다 — 엔진 값과 갭 근사가 "
            "같은 이름으로 섞인다"))
        return
    src = sorted({str(s) for s in stress_path["irrbb_source"]})
    if src == ["engine"]:
        report.add(ConsistencyCheck(
            name, "PASS",
            "스트레스 경로의 ΔEVE·ΔNII가 ALM 엔진 산출에서 나온다"))
    else:
        report.add(ConsistencyCheck(
            name, "WARN",
            f"스트레스 경로가 ALM 엔진이 아닌 갭 근사로 ΔEVE를 산출한다"
            f"({', '.join(src)}) — `alm_irrbb_result`와 다른 모형이며 두 값이 "
            "같은 이사회 팩에 실린다. StressBooks.irrbb 배선이 남았다"))


def _check_alm_ledgers(alm: dict, report: ValidationReport) -> None:
    """원장 대사 3건 + 미확인 모수 사용 · 행동모형 경고 승격 2건."""
    tables = alm.get("tables") or {}

    # (1) 계약현금흐름의 원금 합 = 계약원장 명목. 상환스케줄이 원금을 다
    # 갚아내지 못하면(잔액 전개 오류·버킷 절단) 여기서 갈라진다.
    con, cfc = tables.get("alm_contract"), tables.get("alm_cashflow_contract")
    if con is not None and cfc is not None and len(con) and len(cfc):
        by_c = cfc.groupby("contract_id")["principal_cf"].sum()
        notional = con.set_index("contract_id")["notional"]
        missing = set(notional.index) - set(by_c.index)
        gap = float((by_c - notional.reindex(by_c.index)).abs().max())
        scale = float(notional.abs().max())
        if missing or gap > _ALM_TIE_RTOL * scale:
            report.add(ConsistencyCheck(
                "alm_cf_ties_to_notional", "FAIL",
                f"계약현금흐름 원금 합이 명목과 어긋난다 — 최대 {gap:,.0f}원, "
                f"현금흐름 없는 계약 {len(missing)}건", metric=gap))
        else:
            report.add(ConsistencyCheck(
                "alm_cf_ties_to_notional", "PASS",
                f"계약 {len(notional):,}건의 원금 현금흐름 합 = 명목 "
                f"(최대 오차 {gap:,.2f}원)", metric=gap))

    # (2) ΔEVE 독립 재계산. **원장 안에서 접기만 하면 항등식이라 실패할 수
    # 없다** — `build_irrbb_result`가 delta_eve를 bucket_pv의 delta_pv 합으로
    # *정의*하므로, 같은 프레임에 같은 groupby를 다시 걸어 비교하면 충격곡선을
    # 통째로 무력화해도 통과한다. 그래서 할인계수를 결과 원장에서 읽지 않고
    # 모수 원장(alm_rate_shock_param·alm_scenario_def·alm_post_shock_floor)과
    # 기저곡선에서 **다시 만들어** 재계산한다. 검사가 잡겠다고 선언한 것은
    # "화면 막대와 이사회 팩 헤드라인이 같은 산출에서 나왔는가"이고, 그 답은
    # 재계산으로만 나온다.
    bp, res = tables.get("alm_irrbb_bucket_pv"), tables.get("alm_irrbb_result")
    if bp is not None and res is not None and len(bp) and len(res):
        _check_delta_eve_recalc(alm, bp, res, report)

    # (2b) 접기 자체의 항등식. 정의상 참이지만 짝 없는 (basis, scenario) 조합은
    # 이쪽에서만 잡히므로 남긴다 — 값 검증이 아니라 짝 검증이다.
    # 접기는 통화별로 먼저 하고 손실 통화만 더한다(제13항 다). 통화 축을 무시한
    # 단순 합은 상계값이며 결과 원장에서는 `delta_eve_gross`가 그 자리다.
    # 제13항 나의 자동금리옵션 리스크가 delta_eve에 반영되면 이 접기와 결과
    # 원장이 그 금액만큼 벌어진다. 그때는 짝만 보고 값 비교는 건너뛴다.
    # 규정이 더하라고 한 항을 더했다는 이유로 FAIL이 나면, 다음 사람이 그 항을
    # 빼서 검사를 통과시키게 된다.
    if bp is not None and res is not None and len(bp) and len(res):
        opt_on = bool(res.get("auto_option_reflected",
                              pd.Series(False, index=res.index)).any())
        got = (bp.groupby(["basis", "scenario", "ccy"])["delta_pv"].sum()
                 .clip(upper=0.0).groupby(level=["basis", "scenario"]).sum())
        want = res.set_index(["basis", "scenario"])["delta_eve"]
        joined = want.to_frame("eve").join(got.to_frame("pv"), how="outer")
        worst = 0.0 if opt_on else float(max(
            (_rel_gap(float(r["eve"]), float(r["pv"]))
             for _, r in joined.dropna().iterrows()), default=0.0))
        if joined.isna().any().any() or worst > _ALM_TIE_RTOL:
            report.add(ConsistencyCheck(
                "alm_bucket_pv_pairs_with_irrbb_result", "FAIL",
                f"버킷 PV와 결과 원장의 짝이 맞지 않는다 — 최대 상대오차 "
                f"{worst:.2e}, 짝 없는 조합 "
                f"{int(joined.isna().any(axis=1).sum())}개", metric=worst))
        else:
            report.add(ConsistencyCheck(
                "alm_bucket_pv_pairs_with_irrbb_result", "PASS",
                f"버킷 PV와 결과 원장의 (산출기준, 시나리오) 짝 {len(joined)}개 "
                "일치", metric=worst))

    # (3) 사다리 = 현금흐름 원장의 **버킷별** 접기. 총합으로 대사하면 사다리가
    # 존재하는 유일한 이유(버킷 배분)를 검증하지 못한다 — 버킷 순서를 통째로
    # 뒤집어도 총합은 같으므로 통과한다. (asof, scenario, basis, ccy, bucket)
    # 으로 조인해 행별로 보고, 누적갭은 버킷 순서의 함수이므로 따로 대사한다.
    lad, bkt = tables.get("alm_maturity_ladder"), tables.get("alm_cashflow_bucket")
    if lad is not None and bkt is not None and len(lad) and len(bkt):
        key = ["asof", "scenario", "basis", "ccy", "bucket"]
        is_asset = bkt["side"] == "asset"
        want = (bkt.assign(_in=bkt["total_cf"].where(is_asset, 0.0),
                           _out=bkt["total_cf"].where(~is_asset, 0.0))
                   .groupby(key)[["_in", "_out"]].sum())
        want["_net"] = want["_in"] - want["_out"]
        joined = want.join(lad.set_index(key)[["inflow", "outflow", "net_gap"]],
                           how="outer")
        pairs = (("_in", "inflow"), ("_out", "outflow"), ("_net", "net_gap"))
        worst = float(max(
            (_rel_gap(float(r[a]), float(r[b]))
             for _, r in joined.dropna().iterrows() for a, b in pairs),
            default=0.0))
        unpaired = int(joined.isna().any(axis=1).sum())
        cum_key = ["asof", "scenario", "basis", "ccy"]
        srt = lad.sort_values(cum_key + ["seq"])
        cum_gap = float((srt.groupby(cum_key)["net_gap"].cumsum()
                         - srt["cumulative_gap"]).abs().max())
        cum_scale = max(float(srt["cumulative_gap"].abs().max()), 1.0)
        if unpaired or worst > _ALM_TIE_RTOL or \
                cum_gap > _ALM_TIE_RTOL * cum_scale:
            report.add(ConsistencyCheck(
                "alm_ladder_ties_to_cashflow", "FAIL",
                f"버킷별 사다리와 현금흐름이 어긋난다 — 최대 상대오차 "
                f"{worst:.2e}, 짝 없는 버킷 {unpaired}개, 누적갭 오차 "
                f"{cum_gap:,.0f}원", metric=worst))
        else:
            report.add(ConsistencyCheck(
                "alm_ladder_ties_to_cashflow", "PASS",
                f"버킷별 유입·유출·순갭·누적갭 일치 ({len(joined)}개 버킷행)",
                metric=worst))

    # (4) 근거를 확인하지 못한 모수가 산출에 실제로 쓰였는지. 원장에 남은
    # 흔적(프록시 통화·미가중 계수·미산출 시나리오)을 모아 한 줄로 낸다.
    # 산출이 나왔다는 사실만 보면 이 공백이 보이지 않는다.
    used: list[str] = []
    if res is not None and "shock_source" in getattr(res, "columns", []):
        proxied = sorted({str(s) for s in res["shock_source"]
                          if str(s) != "직접"})
        if proxied:
            used.append(f"금리충격 모수 {', '.join(proxied)} "
                        "(alm_rate_shock_param의 KRW 행은 비어 있다)")
    flow = tables.get("alm_lcr_flow")
    if flow is not None and len(flow):
        unweighted = sorted(flow.loc[flow["weighted"].isna(), "category"]
                            .astype(str).unique())
        if unweighted:
            used.append(f"LCR 계수 미확인·미가중 {len(unweighted)}항목 "
                        f"({', '.join(unweighted[:3])})")
    survival = alm.get("survival")
    if survival is not None:
        skipped = [w.scope for w in survival.warnings]
        if skipped:
            used.append(f"생존기간 미산출 시나리오 {', '.join(sorted(set(skipped)))}")
    nsfr_skipped = getattr(alm.get("nsfr"), "skipped", None)
    if nsfr_skipped:
        used.append(f"NSFR 계수 미확인 {len(nsfr_skipped)}항목")
    # ΔNII는 다리가 결손이어도 값이 나온다 — 남은 다리 쪽으로 편향된 값이므로
    # 제외 비율이 여기 보이지 않으면 "산출됐다"는 사실만 읽힌다.
    nii = tables.get("alm_nii_result")
    if nii is not None and len(nii) and "excluded_notional_ratio" in nii:
        ex = float(nii["excluded_notional_ratio"].max())
        if ex > 0.0:
            used.append(f"ΔNII 전가율 결손 — 명목 {ex:.1%} 제외한 부분 산출")
    if used:
        report.add(ConsistencyCheck(
            "alm_unconfirmed_param_in_use", "WARN",
            "근거 미확인 모수가 산출에 관여했다 — " + " · ".join(used)
            + ". 절대수준은 결재 대상이 아니다",
            metric=float(len(used))))
    else:
        report.add(ConsistencyCheck(
            "alm_unconfirmed_param_in_use", "PASS",
            "산출에 쓰인 ALM 모수가 전부 근거 확인 상태다"))

    # (5) 행동모형 경고 승격. `ParamWarning`은 "그 조정을 건너뛰었다"는 기록
    # 이므로 산출물에 실려야 한다 — 로그로만 두면 없는 것과 같다.
    warns = alm.get("warnings") or []
    if warns:
        by_param = sorted({f"{w.model}/{w.param}" for w in warns})
        report.add(ConsistencyCheck(
            "alm_behaviour_param_warnings", "WARN",
            f"행동·곡선 모수 경고 {len(warns)}건 — "
            + ", ".join(by_param[:5])
            + (" 외" if len(by_param) > 5 else ""),
            metric=float(len(warns))))
    else:
        report.add(ConsistencyCheck(
            "alm_behaviour_param_warnings", "PASS",
            "행동·곡선 모수 경고 없음"))


def _check_icaap(icaap, report: ValidationReport) -> None:
    """내부자본: EC 통합 ≤ 가용자본, 분산효과 비음수."""
    if icaap is None:
        return
    if icaap.grade == "RED":
        report.add(ConsistencyCheck(
            "icaap_adequacy", "FAIL",
            f"경제자본 사용률 {icaap.utilisation:.1%} > 100% — 내부자본 부족",
            metric=icaap.utilisation))
    elif icaap.grade == "AMBER":
        report.add(ConsistencyCheck(
            "icaap_adequacy", "WARN",
            f"경제자본 사용률 {icaap.utilisation:.1%} (80~100%) — 주의",
            metric=icaap.utilisation))
    else:
        report.add(ConsistencyCheck(
            "icaap_adequacy", "PASS",
            f"경제자본 사용률 {icaap.utilisation:.1%} ≤ 80%",
            metric=icaap.utilisation))

    if icaap.diversification_benefit >= -1e-6 and \
            icaap.ec_diversified <= icaap.ec_standalone_sum + 1e-6:
        report.add(ConsistencyCheck(
            "icaap_diversification", "PASS",
            "분산 통합 EC ≤ 단순합 EC (상관 통합 정합)"))
    else:
        report.add(ConsistencyCheck(
            "icaap_diversification", "FAIL",
            "분산 통합 EC가 단순합을 초과 — 상관행렬 점검 필요"))


def _check_stress_trough_requirement(path_df, bis_result,
                                     report: ValidationReport) -> None:
    """위기상황 CET1 저점이 규제 요구치를 지키는지 — 침범을 침묵시키지 않는다.

    독립검증 F-003: 심각 시나리오 저점이 요구치를 3.4%p 밑도는데 자체검증에
    FAIL도 WARN도 없었다. 규제 최소자본 미달이 검증 결과 어디에도 남지 않으면
    "PASS 49 · FAIL 0"이 안전하다는 뜻으로 읽힌다.

    기준 시나리오 침범은 **FAIL**(현 상태로 이미 미달), 악화·심각 시나리오
    침범은 **WARN**(자본계획·회복계획 연계 대상)이다. 심각 시나리오에서
    견디는 것은 요구가 아니므로 FAIL로 만들면 거짓 경보가 된다.
    """
    if path_df is None or bis_result is None or "scenario" not in path_df:
        return
    required = float(getattr(bis_result, "required", {}).get("cet1", 0.0))
    breached = []
    for sc, g in path_df.groupby("scenario", sort=False):
        trough = g.loc[g["cet1_ratio"].idxmin()]
        if float(trough["cet1_ratio"]) < required:
            breached.append(
                f"{sc}: {float(trough['cet1_ratio']):.2%} < 요구 {required:.2%}"
                f" ({trough['quarter']}, 제약 {trough.get('binding', '—')})")
    if not breached:
        report.add(ConsistencyCheck(
            "stress_trough_meets_requirement", "PASS",
            f"전 시나리오 CET1 저점 >= 요구 {required:.2%}"))
        return
    base_breach = any(b.startswith("baseline") for b in breached)
    report.add(ConsistencyCheck(
        "stress_trough_meets_requirement", "FAIL" if base_breach else "WARN",
        ("기준 시나리오가 이미 요구치 미달 — " if base_breach
         else "위기상황 요구치 침범 (자본계획·회복계획 연계 필요) — ")
        + "; ".join(breached)))


RATIO_TO_EAD_BASIS = "ratio_to_ead"


def _check_capital_source(capital_source: str | None, capital: Any,
                          total_ead: float | None,
                          report: ValidationReport,
                          capital_basis: str | None = None) -> None:
    """자본이 어디서 왔는지, 그중 얼마가 규모 비례분인지 매 실행 드러낸다.

    독립검증 F-201·F-202: 합성 자본의 이익잉여금은 연간이익 × 4년인데 합성
    데이터의 수익이 `ead × spread`라 이익잉여금이 익스포저를 따라간다. 규모와
    무관한 축은 고정 발행자본뿐이고, 자산이 커지면 그 비중이 희석돼 레버리지
    비율의 반응성이 소멸한다. 지표가 상수로 수렴하는 구조는 조용히 진행되므로
    비중을 매번 결재선에 올린다 (3선 권고 — 2·3차 연속 제기).

    원장에서 왔다는 것만으로 이 검사가 꺼지지는 않는다. 원장 값이 총익스포저
    비율(`cet1_to_ead` 등)로 만들어진 것이면 규모 비례분이 100% 이므로 F-201·
    F-202 가 가리키는 상태는 합성기를 쓸 때보다 오히려 강하다. 그것을 "합성기
    미사용" PASS 로 적으면 검사가 잡으려던 상태에서 검사가 꺼진다. 자본의
    산출근거(`capital_basis`)를 함께 받아 그 경우를 WARN 으로 남긴다.

    산출근거가 아예 오지 않은 경우도 PASS 로 두지 않는다. 이 검사가 답해야
    하는 물음은 "합성기 함수를 호출했는가" 가 아니라 "이 값이 어디서 왔는가"
    인데, 근거가 비어 있으면 뒤쪽을 말할 수 없다. 말할 수 없는 것을 PASS 로
    적으면 그 문장이 자체검증 요약을 타고 독립검증 요청서까지 그대로 실린다.
    """
    if capital_source is None or capital is None:
        return
    if capital_source == "ledger":
        cet1 = float(getattr(capital, "cet1", 0.0))
        ratio = (f" (CET1/총익스포저 {cet1 / float(total_ead):.3f})"
                 if total_ead else "")
        if capital_basis == RATIO_TO_EAD_BASIS:
            detail = ("자본 원장 주입이나 산출근거가 총익스포저 비율이다. "
                      "규모 비례분 100%")
            if total_ead:
                detail += f" (CET1/총익스포저 {cet1 / float(total_ead):.3f} 고정)"
            detail += ". 레버리지 반응성이 소멸한다 (F-201·F-202)"
            report.add(ConsistencyCheck("capital_source", "WARN", detail))
            return
        if not capital_basis:
            report.add(ConsistencyCheck(
                "capital_source", "WARN",
                "자본 원장 주입이나 산출근거가 기재되지 않았다. 이 값이 실측 "
                f"자본인지 비율로 만든 값인지 이 결과로는 말할 수 없다{ratio}. "
                "주입한 쪽이 capital_basis 를 함께 넘겨야 한다 "
                "(F-201·F-202)"))
            return
        report.add(ConsistencyCheck(
            "capital_source", "PASS",
            f"자본 원장 주입 · 산출근거 {capital_basis}{ratio}"))
        return
    cet1 = float(getattr(capital, "cet1", 0.0))
    if cet1 <= 0:
        return
    scaled = max(cet1 - PAID_IN_CAPITAL, 0.0)      # 이익잉여금 = 규모 비례분
    share = scaled / cet1
    fixed = PAID_IN_CAPITAL + AT1_ISSUED
    tier1 = cet1 + AT1_ISSUED
    detail = (f"합성 자본 사용 — CET1 {cet1:,.0f} 중 규모 비례분(이익잉여금) "
              f"{share:.1%}, 고정 발행자본 기여 {fixed / tier1:.1%}")
    if total_ead:
        detail += (f" · 자산 대비 고정분 {fixed / float(total_ead):.2%}"
                   f" (희석될수록 레버리지 반응성이 소멸)")
    report.add(ConsistencyCheck(
        "capital_source", "WARN" if share >= 0.5 else "PASS", detail))


def _check_prudential_regime(meta: dict | None,
                             report: ValidationReport) -> None:
    """업권에 이 산출 체계가 적용되는가.

    이 파이프라인은 은행 기준 한 벌(BIS 비율·산출하한·LCR·NSFR·[별표 9-1]
    IRRBB)만 산출한다. 증권 기관은 순자본비율 체계이며 그 산출은 아직 없다.
    업권을 보지 않고 돌리면 증권 기관의 결과가 `cet1_ratio` 로 공시되는데,
    그것은 그 기관의 건전성 지표가 아니다. 매 실행 그 사실을 남긴다.

    업권이 넘어오지 않으면 검사를 지우지 않고 "판정할 수 없다"를 WARN 으로
    남긴다. 예전에는 조용히 반환해 검사 자체가 사라졌고, 그러면 업권을 안
    넘긴 실행과 은행 실행이 자체검증 결과에서 구별되지 않는다. 증권 기관을
    업권 없이 돌려도 검증이 아무 말을 하지 않는 상태가 그 결과다. 근거가
    없으면 WARN 을 남기는 `_check_capital_source` 와 방향을 맞춘다.
    """
    from risk_lib import institutions as _inst
    itype = meta.get("institution_type") if meta else None
    if itype is None or str(itype).strip() == "":
        report.add(ConsistencyCheck(
            "prudential_regime_applies", "WARN",
            "업권(institution_type)이 산출에 넘어오지 않아 이 산출 체계가 이 "
            "기관에 적용되는지 판정할 수 없다. 이 파이프라인은 "
            f"{_inst.IMPLEMENTED_REGIME} 기준 한 벌만 산출하므로, 다른 체계의 "
            "기관이면 여기 나온 자본비율·유동성비율은 그 기관의 건전성 지표가 "
            "아니다. 호출부가 institution_type 을 넘겨야 판정한다"))
        return
    try:
        regime = _inst.prudential_regime(str(itype))
    except ValueError as e:
        report.add(ConsistencyCheck(
            "prudential_regime_applies", "FAIL", str(e)))
        return
    if regime == _inst.IMPLEMENTED_REGIME:
        report.add(ConsistencyCheck(
            "prudential_regime_applies", "PASS",
            f"업권 {itype} · 적용 체계 {regime} · 산출 체계와 일치"))
        return
    report.add(ConsistencyCheck(
        "prudential_regime_applies", "WARN",
        f"업권 {itype} 의 건전성 체계는 {regime} 인데 산출은 "
        f"{_inst.IMPLEMENTED_REGIME} 기준 한 벌뿐이다. 이 결과의 자본비율·"
        "유동성비율은 이 기관의 건전성 지표가 아니라 참고치다"))


def _check_pillar2_evidence(meta: dict | None,
                            report: ValidationReport) -> None:
    """P2R·P2G 가 원장에 있는가. 없으면 0 으로 산출했다는 사실을 남긴다.

    감독당국의 개별 부과분이라 이 저장소에는 근거가 없다. 없는 것을 지어내
    넣으면 요구자본이 그만큼 부풀고, 조용히 0 으로 두면 OCR 이 과소 표시된
    채 결재선에 오른다. 어느 쪽도 하지 않고 사실을 적는다.
    """
    if not meta or "pillar2" not in meta:
        return
    p2 = meta["pillar2"] or {}
    missing = sorted(k for k in ("p2r", "p2g") if p2.get(k) is None)
    if missing:
        report.add(ConsistencyCheck(
            "pillar2_requirement_evidence", "WARN",
            f"{'·'.join(missing).upper()} 가 원장에 없어 0 으로 산출했다. "
            "OCR·SREP 요구치가 감독 부과분만큼 과소 표시된다"))
        return
    report.add(ConsistencyCheck(
        "pillar2_requirement_evidence", "PASS",
        f"P2R {float(p2['p2r']):.2%} · P2G {float(p2['p2g']):.2%} 원장 주입"))


def _check_doc_figures(built: list | None, asof: str | None,
                       doc_paths: tuple[str, ...],
                       report: ValidationReport) -> None:
    """문서의 생성 구간이 현재 산출과 일치하는지 — 손으로 적은 수치를 막는다.

    독립검증 지적 F-103 → F-201 → F-401 → F-501. 문서 수치가 코드 사실과
    어긋나는 결함이 **네 번 반복**됐고 매번 "다음엔 대조하겠다"로 끝났다.
    사람의 주의력에 기대는 한 다섯 번째가 온다. 6차 조건부 결재의 후속조건이
    이 대조를 기계에 맡기는 것이다 (이행기한 2026-08-10).

    검사 대상은 문서에 `<!-- generated: 이름 -->`으로 **표시한 구간뿐이다**.
    시정 문서에는 회차별 기록이 누적돼 있고 과거 절의 숫자는 그 시점에는
    옳았으므로, 전부 대조하면 거짓 경보가 쏟아지고 그러면 다음 사람이 검사를
    끈다. 꺼진 검사는 없는 검사다.
    """
    if not built or not asof or not doc_paths:
        return
    from risk_lib.validation.doc_figures import check_doc_figures
    from pathlib import Path
    for doc in doc_paths:
        if not Path(doc).exists():
            continue
        for c in check_doc_figures(doc, built, asof):
            report.add(c)


def _check_national_irrbb_basis(ledgers: dict | None, alm: dict | None,
                                report: ValidationReport) -> None:
    """[별표 9-1] 산출이 현행 계정으로 서고 폐지 계정이 헤드라인에 없는가.

    두 체계를 같은 값으로 대사하지 않는다. 2014년 판(금리 EaR·금리 VaR,
    자기자본 20%)과 현행 판(ΔEVE·ΔNII, 기본자본 15%)은 측정지표도 분모도
    다르므로 대사가 성립하지 않는다. 확인할 것은 셋이다.

      1. 헤드라인 ΔEVE가 폐지 계정으로 산출되지 않았는가
      2. 아웃라이어 판정이 기본자본 15% 기준으로 났는가
      3. 국내 고유 요건 원장(범주 판정·행동옵션 범위·거버넌스)이 실제로 있는가

    폐지된 자기자본 20% 기준이 어딘가에서 판정에 쓰이면 그 판정은 현행 규정과
    무관한 값이다.
    """
    if not alm or alm.get("irrbb") is None:
        return
    from risk_lib.references import IRRBB_OUTLIER_EVE_PCT_TIER1
    irrbb = alm["irrbb"]
    res = alm.get("tables", {}).get("alm_irrbb_result")
    if isinstance(res, pd.DataFrame) and "framework_status" in res.columns:
        bad = sorted(set(res.loc[res["framework_status"] == "폐지",
                                 "framework_version"]))
        if bad:
            report.add(ConsistencyCheck(
                "irrbb_headline_not_repealed", "FAIL",
                f"헤드라인 ΔEVE 원장에 폐지 계정 {bad}이 있다", metric=len(bad)))
        else:
            cur = sorted(set(res["framework_version"]))
            status = sorted(set(res["framework_status"]))
            report.add(ConsistencyCheck(
                "irrbb_headline_not_repealed",
                "PASS" if status == ["현행"] else "WARN",
                f"헤드라인 계정 {cur} (계정 상태 {status})"))

    pct = float(getattr(irrbb, "worst_pct_tier1", 0.0))
    thr = float(IRRBB_OUTLIER_EVE_PCT_TIER1)
    over = bool(getattr(irrbb, "outlier", lambda: False)())
    report.add(ConsistencyCheck(
        "irrbb_outlier_basis_tier1_15pct", "FAIL" if over else "PASS",
        f"ΔEVE/기본자본 {pct:.2%} 대 기준 {thr:.0%} ([별표 9-1] 제21항 나). "
        f"{'초과 — 제21항 다 감독원장 보고 의무' if over else '미초과'}",
        metric=pct))

    need = ("kr_nmd_category", "kr_retail_behavioural_scope",
            "kr_irrbb_governance")
    have = {k: int(len(ledgers.get(k, []))) for k in need} if ledgers else {}
    missing = [k for k in need if not have.get(k)]
    report.add(ConsistencyCheck(
        "kr_irrbb_national_ledgers_present",
        "FAIL" if missing else "PASS",
        f"국내 고유 요건 원장 {have}" if not missing
        else f"국내 고유 요건 원장 결손 {missing}",
        metric=float(len(need) - len(missing))))


def _check_limit_ledger_source(ledgers: dict | None,
                               limit_report: pd.DataFrame | None,
                               report: ValidationReport) -> None:
    """한도 산출이 한도 정의 원장에서 왔는가.

    원장 행 수가 0이면 한도 산출도 비어야 한다. 원장이 비었는데 한도 판정이
    나오면 임계가 코드 어딘가에 남아 있다는 뜻이고, 그러면 화면의 승인기구·
    승인일은 산출과 무관한 장식이 된다.
    """
    if ledgers is None:
        return
    led = ledgers.get("lim_limit_definition")
    if not isinstance(led, pd.DataFrame):
        report.add(ConsistencyCheck(
            "limit_definition_from_ledger", "FAIL",
            "한도 정의 원장이 산출물에 없다"))
        return
    n_def = int(len(led))
    n_axis = 0 if limit_report is None or limit_report.empty else int(
        limit_report["dimension"].nunique()
        if "dimension" in limit_report.columns else 0)
    if n_def == 0 and n_axis > 0:
        report.add(ConsistencyCheck(
            "limit_definition_from_ledger", "FAIL",
            f"한도 정의 원장이 비었는데 한도 판정이 {n_axis}축 나왔다",
            metric=float(n_axis)))
        return
    unapproved = int(len(led[(led["basis"] == "내부한도")
                             & (led["approved_on"].isna())]))
    report.add(ConsistencyCheck(
        "limit_definition_from_ledger", "WARN" if unapproved else "PASS",
        f"한도 정의 {n_def}건이 원장에서 왔고 판정 축은 {n_axis}개다"
        + (f". 내부한도 {unapproved}건이 승인일 미기재다" if unapproved else ""),
        metric=float(n_def)))


def _check_macro_master_source(ledgers: dict | None,
                               report: ValidationReport) -> None:
    """거시지표와 시나리오 충격 배수가 마스터 원장에서 오는가."""
    if ledgers is None:
        return
    master = ledgers.get("rdm_macro_indicator_master")
    shock = ledgers.get("st_macro_scenario_shock")
    if not isinstance(master, pd.DataFrame) or not isinstance(shock, pd.DataFrame):
        report.add(ConsistencyCheck(
            "macro_master_from_ledger", "FAIL",
            "거시지표 마스터 또는 시나리오 충격 원장이 산출물에 없다"))
        return
    orphan = sorted(set(shock["indicator_id"]) - set(master["indicator_id"]))
    if orphan:
        report.add(ConsistencyCheck(
            "macro_master_from_ledger", "FAIL",
            f"마스터에 없는 지표를 충격 원장이 가리킨다: {orphan[:5]}",
            metric=float(len(orphan))))
        return
    unapproved = int((master["evidence_status"] != "원문확인").sum())
    report.add(ConsistencyCheck(
        "macro_master_from_ledger", "WARN" if unapproved else "PASS",
        f"지표 {len(master)}종 · 충격 {len(shock)}행이 마스터 원장에서 왔다"
        + (f". 근거 미확인 {unapproved}종" if unapproved else ""),
        metric=float(len(master))))


def _check_backtest_censoring(ledgers: dict | None,
                              report: ValidationReport) -> None:
    """LGD·CCF 실측검증이 관측중단 건수를 보고하는가.

    관측중단(회수 진행 중인 부도건)을 세지 않으면 표본이 완결된 건만 남고,
    회수가 오래 걸리는 건이 빠져 실현 LGD가 낮게 나온다. 건수가 원장에
    없으면 그 편의가 얼마나 큰지 판단할 근거가 없다.
    """
    if ledgers is None:
        return
    lgd = ledgers.get("crm_lgd_backtest")
    if not isinstance(lgd, pd.DataFrame) or lgd.empty:
        report.add(ConsistencyCheck(
            "lgd_ccf_backtest_censoring_reported", "FAIL",
            "LGD 실측검증 원장이 산출물에 없다"))
        return
    if "n_censored" not in lgd.columns:
        report.add(ConsistencyCheck(
            "lgd_ccf_backtest_censoring_reported", "FAIL",
            "LGD 실측검증 원장에 관측중단 건수 컬럼이 없다"))
        return
    censored = int(lgd["n_censored"].fillna(0).sum())
    used = int(lgd["n_defaults"].fillna(0).sum())
    ccf = ledgers.get("crm_ccf_backtest")
    n_fac = 0 if not isinstance(ccf, pd.DataFrame) else int(
        ccf["n_facilities"].fillna(0).sum())
    share = censored / (censored + used) if (censored + used) else 0.0
    report.add(ConsistencyCheck(
        "lgd_ccf_backtest_censoring_reported", "PASS",
        f"LGD 표본 {used}건 · 관측중단 {censored}건(중단 비중 {share:.1%}) · "
        f"CCF 표본 {n_fac}건", metric=float(censored)))


#: 회수 할인율(CAPM) 검사가 읽는 원장. 한 장이라도 없으면 검사가 통째로
#: 돌지 않으므로 결손 자체를 FAIL로 잡는다.
_CAPM_LEDGERS = ("crm_capm_observation", "crm_capm_estimate",
                 "crm_lgd_discount_rate", "crm_recovery_history")
#: 부도자산 LGD(BEEL 곡선·PLGD) 검사가 읽는 원장.
_PLGD_LEDGERS = ("crm_beel_curve", "crm_plgd")


def _missing_ledgers(ledgers: dict, names: tuple[str, ...]) -> list[str]:
    return [n for n in names
            if not isinstance(ledgers.get(n), pd.DataFrame)]


def _check_irb_estimation_ledgers(ledgers: dict | None, asof: str | None,
                                  report: ValidationReport) -> None:
    """회수 할인율(CAPM)과 부도자산 LGD(BEEL·PLGD)의 자체검사를 합류시킨다.

    검사 본문은 산출 모듈이 들고 있다(`models.estimation.discount_capm`·
    `plgd`). 여기서 다시 쓰면 같은 규칙이 두 벌이 되고 한쪽만 고쳐지는 날이
    온다. 이 함수가 하는 일은 원장이 실제로 산출물에 실렸는지 확인하고
    모듈의 검사 묶음을 같은 보고서에 붙이는 것뿐이다.

    원장이 없으면 검사를 건너뛰지 않고 FAIL을 남긴다. 건너뛰면 "돌지 않았다"가
    보고서에서 "통과했다"와 구분되지 않는다.
    """
    if ledgers is None:
        return
    from risk_lib.models.estimation.discount_capm import run_capm_checks
    from risk_lib.models.estimation.plgd import run_plgd_checks

    missing = _missing_ledgers(ledgers, _CAPM_LEDGERS)
    if missing:
        report.add(ConsistencyCheck(
            "irb_discount_rate_ledgers_present", "FAIL",
            f"회수 할인율 검사가 읽을 원장이 산출물에 없다: {missing}",
            metric=float(len(missing))))
    else:
        run_capm_checks(ledgers, asof=asof, report=report)

    missing = _missing_ledgers(ledgers, _PLGD_LEDGERS)
    if missing:
        report.add(ConsistencyCheck(
            "irb_plgd_ledgers_present", "FAIL",
            f"부도자산 LGD 검사가 읽을 원장이 산출물에 없다: {missing}",
            metric=float(len(missing))))
    else:
        run_plgd_checks(ledgers, report=report)


def run_consistency_checks(
    *,
    sa_results: pd.DataFrame | None = None,
    irb_results: pd.DataFrame | None = None,
    bis_result: Any = None,
    rwa_total_for_bis: float | None = None,
    leverage_result: Any = None,
    output_floor_result: Any = None,
    market_rwa: float | None = None,
    market_positions: pd.DataFrame | None = None,
    op_rwa: float | None = None,
    # 구성요소 대사에 필요한 나머지 두 항. 넘어오지 않으면 대사가 부분적이며
    # `rwa_components_reconcile`이 그 사실을 WARN으로 남긴다.
    ccr_rwa: float | None = None,
    structured_rwa: float | None = None,
    ecl_results: pd.DataFrame | None = None,
    concentration: pd.DataFrame | None = None,
    stress_results: pd.DataFrame | None = None,
    macro_ecl_result: Any = None,
    reverse_stress_result: Any = None,
    stress_path_result: pd.DataFrame | None = None,
    macro_ecl_path_result: pd.DataFrame | None = None,
    pd_metrics: dict | None = None,
    backtest: dict | None = None,
    limit_report: pd.DataFrame | None = None,
    alm_results: dict | None = None,
    icaap_result: Any = None,
    capital_source: str | None = None,
    capital_basis: str | None = None,
    capital_stack: Any = None,
    total_ead: float | None = None,
    built_forms: list | None = None,
    asof: str | None = None,
    doc_paths: tuple[str, ...] = (),
    portfolio: pd.DataFrame | None = None,
    meta: dict | None = None,
    ledger_tables: dict | None = None,
) -> ValidationReport:
    """Run all available checks; missing inputs skip relevant checks."""
    rep = ValidationReport()

    # 인제스트 완전성이 먼저다 — 들어온 것이 다 산출에 들어갔는지 모르면
    # 그 뒤의 정합성 검사는 부분집합에 대한 정합성일 뿐이다.
    _check_portfolio_intake(portfolio, rep)
    _check_asof_provenance(meta, rep)

    _check_stress_trough_requirement(stress_path_result, bis_result, rep)
    _check_capital_source(capital_source, capital_stack, total_ead, rep,
                          capital_basis)
    _check_pillar2_evidence(meta, rep)
    _check_prudential_regime(meta, rep)
    _check_doc_figures(built_forms, asof, doc_paths, rep)

    if sa_results is not None:
        _check_ead_positive(sa_results, rep, "sa")
        _check_rwa_nonneg(sa_results, rep, "sa")

    if irb_results is not None:
        _check_pd_bounds(irb_results, rep)
        _check_lgd_bounds(irb_results, rep)
        _check_ead_positive(irb_results, rep, "irb")
        _check_rwa_nonneg(irb_results, rep, "irb")
        _check_el_le_ead(irb_results, rep)

    if sa_results is not None and irb_results is not None:
        _check_sa_irb_no_overlap(sa_results, irb_results, rep)

    if bis_result is not None:
        _check_bis_plausible(bis_result, rep)
        _check_rwa_aggregate(rwa_total_for_bis, bis_result, rep)

    _check_leverage(leverage_result, rep)
    _check_output_floor(output_floor_result, rep)
    _check_market_op_rwa(market_rwa, op_rwa, rep, total_ead)
    _check_market_portfolio_split(market_positions, market_rwa, rep)
    _check_rwa_components(sa_results, irb_results, market_rwa, op_rwa,
                          ccr_rwa, structured_rwa, output_floor_result,
                          rwa_total_for_bis, rep)
    _check_ecl(ecl_results, rep)
    _check_concentration(concentration, rep)
    _check_stress_monotone(stress_results, rep)
    _check_macro_ecl(macro_ecl_result, rep)
    _check_ecl_ttc_pit_gap(
        macro_ecl_result,
        None if ecl_results is None or "ecl" not in getattr(ecl_results, "columns", [])
        else float(ecl_results["ecl"].sum()),
        rep)
    _check_reverse_stress(reverse_stress_result, rep)
    _check_stress_path(stress_path_result, rep)
    _check_macro_ecl_path(macro_ecl_path_result, rep)
    _check_pd_model_quality(pd_metrics, rep)
    _check_hl_calibration(backtest, rep)
    _check_backtest_traffic_light(backtest, rep)
    _check_large_exposure(limit_report, rep, ledger_tables)
    _check_large_exposure_sources(limit_report, ledger_tables, rep)
    _check_alm(alm_results, rep)
    if alm_results:
        _check_irrbb_single_source(alm_results, stress_path_result, rep)
    _check_icaap(icaap_result, rep)

    # 신규 원장 — 원장이 없으면 검사가 돌지 않는다. "돌지 않았다"와 "통과했다"가
    # 같아지지 않게 각 검사가 원장 결손 자체를 FAIL로 잡는다.
    _check_national_irrbb_basis(ledger_tables, alm_results, rep)
    _check_limit_ledger_source(ledger_tables, limit_report, rep)
    _check_macro_master_source(ledger_tables, rep)
    _check_backtest_censoring(ledger_tables, rep)
    _check_irb_estimation_ledgers(ledger_tables, asof, rep)

    return rep
