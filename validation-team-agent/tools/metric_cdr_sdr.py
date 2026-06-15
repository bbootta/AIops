"""CDR / SDR 계산 및 비교.

본 모듈에서 SDR 은 **Survival Rate (생존율)** 을 의미한다. 즉 관측 표본 중
부도(default)가 발생하지 않은 비율이다. 일부 문헌에서 SDR 을 *Spread Default
Rate* 또는 *Specific Default Rate* 로 쓰는 경우가 있으나, 본 프로젝트에서는
혼동을 피하기 위해 항상 *Survival Rate* 만을 가리킨다.

정의:
    CDR (Cumulative Default Rate) = default_count / exposure_count
    SDR (Survival Rate)           = 1 - CDR
                                  = (exposure_count - default_count) / exposure_count

표본 부족 또는 0 division 상황은 명시적 오류로 처리한다.

함수 명명:
    - ``calculate_cdr``            : 부도율 계산.
    - ``calculate_survival_rate``  : 생존율 계산 (canonical name).
    - ``calculate_sdr``            : ``calculate_survival_rate`` 의 backwards-compat alias.
    - ``compare_cdr_sdr``          : 기준 시점과 현재 시점 비교. 반환 dict 의
      ``*_sdr`` 키는 survival rate 를 의미한다.
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


def calculate_survival_rate(survival_count: int, exposure_count: int) -> float:
    """Survival rate = survival_count / exposure_count 반환.

    본 모듈에서 SDR 의 canonical 이름. ``calculate_sdr`` 는 backwards-compat alias.
    """
    if exposure_count <= 0:
        raise ValueError("exposure_count must be > 0")
    if survival_count < 0:
        raise ValueError("survival_count must be >= 0")
    if survival_count > exposure_count:
        raise ValueError("survival_count cannot exceed exposure_count")
    return float(survival_count) / float(exposure_count)


def calculate_sdr(survival_count: int, exposure_count: int) -> float:
    """Backwards-compat alias of :func:`calculate_survival_rate`.

    본 모듈의 SDR 은 항상 Survival Rate 를 의미한다 (모듈 docstring 참조).
    """
    return calculate_survival_rate(survival_count, exposure_count)


def compare_cdr_sdr(base: dict, current: dict) -> dict:
    """기준 시점과 현재 시점의 CDR / Survival Rate 를 비교한다.

    base, current 각각 다음 키를 갖는다고 가정:
        default_count, exposure_count
    반환 dict 키: base_cdr, current_cdr, delta_cdr, base_sdr, current_sdr, delta_sdr
    (``*_sdr`` 는 survival rate.)
    """
    required = {"default_count", "exposure_count"}
    for label, d in (("base", base), ("current", current)):
        if not required.issubset(d.keys()):
            raise KeyError(
                f"{label} must contain keys {sorted(required)}, got {sorted(d.keys())}"
            )

    base_cdr = calculate_cdr(base["default_count"], base["exposure_count"])
    cur_cdr = calculate_cdr(current["default_count"], current["exposure_count"])
    base_survival_rate = 1.0 - base_cdr
    cur_survival_rate = 1.0 - cur_cdr

    return {
        "base_cdr": base_cdr,
        "current_cdr": cur_cdr,
        "delta_cdr": cur_cdr - base_cdr,
        "base_sdr": base_survival_rate,
        "current_sdr": cur_survival_rate,
        "delta_sdr": cur_survival_rate - base_survival_rate,
    }
