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

from risk_lib.capital.bis import BIS_MINIMUMS


@dataclass
class ConsistencyCheck:
    name: str
    status: str           # PASS | WARN | FAIL
    detail: str
    metric: float | None = None


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

    floor_violations = df[(df["pd"] > 0) & (df["pd"] < 0.0003)]
    if len(floor_violations):
        report.add(ConsistencyCheck(
            "pd_floor_3bp", "WARN",
            f"{len(floor_violations)} exposures below 3bp PD floor (will be floored in IRB)",
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


def _check_ead_positive(df: pd.DataFrame, report: ValidationReport) -> None:
    if "ead" not in df.columns:
        return
    bad = df[df["ead"] < 0]
    if len(bad):
        report.add(ConsistencyCheck(
            "ead_nonneg", "FAIL",
            f"{len(bad)} exposures with negative EAD",
            metric=float(len(bad)),
        ))
    else:
        report.add(ConsistencyCheck(
            "ead_nonneg", "PASS",
            "all EAD non-negative",
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
        elif ratio < BIS_MINIMUMS["cet1"] and name == "cet1_ratio":
            report.add(ConsistencyCheck(
                f"bis_{name}_min", "FAIL",
                f"CET1 ratio {ratio:.4f} below Pillar 1 minimum {BIS_MINIMUMS['cet1']:.4f}",
                metric=ratio,
            ))
        else:
            report.add(ConsistencyCheck(
                f"bis_{name}_plausible", "PASS",
                f"{name}={ratio:.4f}", metric=ratio,
            ))

    # Ordering: Total >= Tier1 >= CET1 by construction
    if not (bis_result.total_ratio + 1e-9 >= bis_result.tier1_ratio
            >= bis_result.cet1_ratio - 1e-9):
        report.add(ConsistencyCheck(
            "bis_ratio_ordering", "FAIL",
            "expected total >= tier1 >= cet1 by construction",
        ))
    else:
        report.add(ConsistencyCheck(
            "bis_ratio_ordering", "PASS",
            "total >= tier1 >= cet1",
        ))


def _check_rwa_aggregate(
    rwa_total: float | None,
    bis_result,
    report: ValidationReport,
) -> None:
    if rwa_total is None or bis_result is None:
        return
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
            f"aggregate RWA reconciles ({rwa_total:.2f})",
        ))


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


def _check_market_op_rwa(market_rwa, op_rwa, report: ValidationReport) -> None:
    for label, val in [("market_rwa_nonneg", market_rwa), ("op_rwa_nonneg", op_rwa)]:
        if val is None:
            continue
        if val < 0:
            report.add(ConsistencyCheck(label, "FAIL", f"{label} is negative", metric=val))
        else:
            report.add(ConsistencyCheck(label, "PASS", f"{val:,.0f}", metric=val))


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


def run_consistency_checks(
    *,
    sa_results: pd.DataFrame | None = None,
    irb_results: pd.DataFrame | None = None,
    bis_result: Any = None,
    rwa_total_for_bis: float | None = None,
    leverage_result: Any = None,
    output_floor_result: Any = None,
    market_rwa: float | None = None,
    op_rwa: float | None = None,
    ecl_results: pd.DataFrame | None = None,
    concentration: pd.DataFrame | None = None,
    stress_results: pd.DataFrame | None = None,
) -> ValidationReport:
    """Run all available checks; missing inputs skip relevant checks."""
    rep = ValidationReport()

    if sa_results is not None:
        _check_ead_positive(sa_results, rep)
        _check_rwa_nonneg(sa_results, rep, "sa")

    if irb_results is not None:
        _check_pd_bounds(irb_results, rep)
        _check_lgd_bounds(irb_results, rep)
        _check_ead_positive(irb_results, rep)
        _check_rwa_nonneg(irb_results, rep, "irb")
        _check_el_le_ead(irb_results, rep)

    if sa_results is not None and irb_results is not None:
        _check_sa_irb_no_overlap(sa_results, irb_results, rep)

    if bis_result is not None:
        _check_bis_plausible(bis_result, rep)
        _check_rwa_aggregate(rwa_total_for_bis, bis_result, rep)

    _check_leverage(leverage_result, rep)
    _check_output_floor(output_floor_result, rep)
    _check_market_op_rwa(market_rwa, op_rwa, rep)
    _check_ecl(ecl_results, rep)
    _check_concentration(concentration, rep)
    _check_stress_monotone(stress_results, rep)

    return rep
