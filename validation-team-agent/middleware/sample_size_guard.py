"""표본 적정성 점검.

전체 표본 수, 부도 건수, 등급별 표본 수의 최소 기준을 점검한다. 임계는 참고용이며
모형/정책별로 호출자가 인자로 전달하여 조정할 수 있다.
"""

from __future__ import annotations

from typing import Mapping


DEFAULTS = {
    "min_total": 1000,
    "min_defaults": 50,
    "min_per_grade": 30,
}


def check_sample_size(
    total: int,
    default_count: int,
    per_grade_counts: Mapping[str, int] | None = None,
    thresholds: Mapping[str, int] | None = None,
) -> dict:
    """표본 적정성을 평가한다.

    반환 dict 키:
        passed, total_ok, defaults_ok, per_grade_ok, violations (list)
    """
    th = dict(DEFAULTS)
    if thresholds:
        th.update(thresholds)

    if total < 0 or default_count < 0:
        raise ValueError("total / default_count must be >= 0")
    if default_count > total:
        raise ValueError("default_count cannot exceed total")

    violations = []
    total_ok = total >= th["min_total"]
    if not total_ok:
        violations.append(
            {"type": "total", "actual": total, "threshold": th["min_total"]}
        )
    defaults_ok = default_count >= th["min_defaults"]
    if not defaults_ok:
        violations.append(
            {"type": "defaults", "actual": default_count, "threshold": th["min_defaults"]}
        )

    per_grade_ok = True
    if per_grade_counts:
        for grade, cnt in per_grade_counts.items():
            if cnt < 0:
                raise ValueError(f"grade {grade} count must be >= 0")
            if cnt < th["min_per_grade"]:
                per_grade_ok = False
                violations.append(
                    {
                        "type": "per_grade",
                        "grade": grade,
                        "actual": cnt,
                        "threshold": th["min_per_grade"],
                    }
                )

    return {
        "passed": total_ok and defaults_ok and per_grade_ok,
        "total_ok": total_ok,
        "defaults_ok": defaults_ok,
        "per_grade_ok": per_grade_ok,
        "violations": violations,
        "thresholds": th,
    }
