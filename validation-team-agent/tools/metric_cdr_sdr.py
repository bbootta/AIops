"""CDR / SDR 계산 및 비교.

CDR = default_count / exposure_count
SDR = (exposure_count - default_count) / exposure_count
표본 부족 또는 0 division 상황은 명시적 오류로 처리한다.
"""

from __future__ import annotations


def _validate_counts(default_count: int, exposure_count: int) -> None:
    if exposure_count <= 0:
        raise ValueError("exposure_count must be > 0")
    if default_count < 0:
        raise ValueError("default_count must be >= 0")
    if default_count > exposure_count:
        raise ValueError("default_count cannot exceed exposure_count")


def calculate_cdr(default_count: int, exposure_count: int) -> float:
    """CDR (cumulative default rate) 반환."""
    _validate_counts(default_count, exposure_count)
    return float(default_count) / float(exposure_count)


def calculate_sdr(survival_count: int, exposure_count: int) -> float:
    """SDR (survival rate) 반환."""
    if exposure_count <= 0:
        raise ValueError("exposure_count must be > 0")
    if survival_count < 0:
        raise ValueError("survival_count must be >= 0")
    if survival_count > exposure_count:
        raise ValueError("survival_count cannot exceed exposure_count")
    return float(survival_count) / float(exposure_count)


def compare_cdr_sdr(base: dict, current: dict) -> dict:
    """기준 시점과 현재 시점의 CDR/SDR을 비교한다.

    base, current 각각 다음 키를 갖는다고 가정:
        default_count, exposure_count
    반환 dict 키: base_cdr, current_cdr, delta_cdr, base_sdr, current_sdr, delta_sdr
    """
    required = {"default_count", "exposure_count"}
    for label, d in (("base", base), ("current", current)):
        if not required.issubset(d.keys()):
            raise KeyError(
                f"{label} must contain keys {sorted(required)}, got {sorted(d.keys())}"
            )

    base_cdr = calculate_cdr(base["default_count"], base["exposure_count"])
    cur_cdr = calculate_cdr(current["default_count"], current["exposure_count"])
    base_sdr = 1.0 - base_cdr
    cur_sdr = 1.0 - cur_cdr

    return {
        "base_cdr": base_cdr,
        "current_cdr": cur_cdr,
        "delta_cdr": cur_cdr - base_cdr,
        "base_sdr": base_sdr,
        "current_sdr": cur_sdr,
        "delta_sdr": cur_sdr - base_sdr,
    }
