"""대규모 합성 데이터 생성기 (검증 하니스 데모용).

운영 데이터를 사용하지 않는다. 모든 데이터는 결정론적 numpy 난수(seed 명시)로
생성되며 민감정보 패턴(주민/계좌/이메일)을 포함하지 않는다.

가장 일반적 용도:
    df = credit_scoring_sample(n=100_000, seed=42)
    # columns: customer_id, obs_date, score, target, grade, pd, set
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# pd by grade (a~e): 합리적 신용평가 등급 분포
_GRADES = list("ABCDE")
_PD_BY_GRADE = {"A": 0.01, "B": 0.03, "C": 0.07, "D": 0.15, "E": 0.30}
# 등급별 표본 비중 (총합 1.0)
_GRADE_MIX = {"A": 0.30, "B": 0.30, "C": 0.20, "D": 0.15, "E": 0.05}


def credit_scoring_sample(
    n: int = 100_000,
    *,
    seed: int = 42,
    dev_ratio: float = 0.625,
    psi_shift: float = 0.0,
) -> pd.DataFrame:
    """신용평가 검증용 합성 데이터.

    psi_shift > 0 이면 OOT score 분포에 우측 shift 를 가해 PSI 가 상승하도록 한다.
    target 은 등급별 PD 의 Bernoulli. score 는 (높을수록 위험) 규약.

    반환 컬럼: customer_id, obs_date, score, target, grade, pd, set
    """
    if n < 100:
        raise ValueError("n must be >= 100")
    if not 0 < dev_ratio < 1:
        raise ValueError("dev_ratio must be in (0,1)")

    rng = np.random.default_rng(seed)
    n_dev = int(n * dev_ratio)
    n_oot = n - n_dev

    grades = rng.choice(_GRADES, size=n, p=[_GRADE_MIX[g] for g in _GRADES])
    pd_est = np.array([_PD_BY_GRADE[g] for g in grades], dtype=float)
    target = (rng.uniform(size=n) < pd_est).astype(int)

    # score: 양호(target=0)는 0근방, 부실(target=1)은 +1.5 근방. 등급이 낮을수록
    # (예: E) 평균 score 가 더 높도록 grade index shift 추가.
    grade_idx = np.array([_GRADES.index(g) for g in grades], dtype=float)
    base_score = rng.normal(0.0, 1.0, size=n) + 0.2 * grade_idx
    bad_lift = rng.normal(1.5, 0.6, size=n)
    score = np.where(target == 1, base_score + bad_lift, base_score)

    set_arr = np.array(["dev"] * n_dev + ["oot"] * n_oot)
    # OOT 분포 우측 shift (PSI 시연용)
    if psi_shift > 0:
        score[n_dev:] = score[n_dev:] + psi_shift

    obs_dates = (
        pd.date_range("2022-01-01", periods=24, freq="MS").strftime("%Y-%m-%d").tolist()
    )
    obs_arr = rng.choice(obs_dates, size=n)

    customer_ids = [f"C{(i + 1):07d}" for i in range(n)]

    df = pd.DataFrame(
        {
            "customer_id": customer_ids,
            "obs_date": obs_arr,
            "score": score,
            "target": target,
            "grade": grades,
            "pd": pd_est,
            "set": set_arr,
        }
    )
    return df


def capital_ratio_sample(*, seed: int = 7) -> dict:
    """가상의 인터넷전문은행 X 자본비율 (unverified, demo only)."""
    rng = np.random.default_rng(seed)
    cet1 = float(rng.uniform(0.10, 0.16))
    tier1 = cet1 + float(rng.uniform(0.005, 0.015))
    total = tier1 + float(rng.uniform(0.005, 0.020))
    leverage = float(rng.uniform(0.04, 0.08))
    return {
        "capital_cet1": round(cet1, 4),
        "capital_tier1": round(tier1, 4),
        "capital_total": round(total, 4),
        "capital_leverage": round(leverage, 4),
    }


def capital_stress_sample() -> dict:
    """자본 미달 시나리오 (escalation 시연용)."""
    return {
        "capital_cet1": 0.030,
        "capital_tier1": 0.040,
        "capital_total": 0.050,
        "capital_leverage": 0.020,
    }
