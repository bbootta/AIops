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


def run_consistency_checks(
    *,
    sa_results: pd.DataFrame | None = None,
    irb_results: pd.DataFrame | None = None,
    bis_result: Any = None,
    rwa_total_for_bis: float | None = None,
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

    return rep
