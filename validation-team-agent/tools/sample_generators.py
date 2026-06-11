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
    obs_arr = pd.to_datetime(rng.choice(obs_dates, size=n))

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


def macro_stationary_series(n: int = 250, *, seed: int = 11) -> list[float]:
    """정상 시계열 (white noise)."""
    rng = np.random.default_rng(seed)
    return rng.normal(0.0, 1.0, size=n).tolist()


def macro_random_walk_series(n: int = 250, *, seed: int = 11) -> list[float]:
    """단위근 시계열 (random walk)."""
    rng = np.random.default_rng(seed)
    return np.cumsum(rng.normal(0.0, 1.0, size=n)).tolist()


def ifrs9_weight_panel(*, balanced: bool = True) -> pd.DataFrame:
    """IFRS 9 시나리오 가중치 패널 (4 시점 × 3 시나리오).

    balanced=False 면 두 번째 시점의 가중치 합이 1.1 로 위반.
    """
    rows = []
    for period in ("2024-Q1", "2024-Q2", "2024-Q3", "2024-Q4"):
        if balanced or period != "2024-Q2":
            rows.append({"period": period, "scenario": "base", "weight": 0.5})
            rows.append({"period": period, "scenario": "adverse", "weight": 0.3})
            rows.append({"period": period, "scenario": "severe", "weight": 0.2})
        else:
            rows.append({"period": period, "scenario": "base", "weight": 0.5})
            rows.append({"period": period, "scenario": "adverse", "weight": 0.4})
            rows.append({"period": period, "scenario": "severe", "weight": 0.2})
    return pd.DataFrame(rows)


def operational_bi_sample(*, large: bool = False) -> float:
    """운영리스크 Business Indicator (EUR bn)."""
    return 40.0 if large else 3.5


def cva_counterparty_sample(n: int = 25, *, seed: int = 13) -> list[dict]:
    """CVA counterparty list (BA-CVA 입력)."""
    rng = np.random.default_rng(seed)
    return [
        {"name": f"CP{i:03d}", "scva": float(rng.uniform(5.0, 50.0))}
        for i in range(n)
    ]


def ccr_exposure_sample(*, seed: int = 17) -> dict:
    """CCR (SA-CCR) RC / PFE 가정값."""
    rng = np.random.default_rng(seed)
    return {
        "ccr_rc": round(float(rng.uniform(50.0, 300.0)), 2),
        "ccr_pfe": round(float(rng.uniform(20.0, 200.0)), 2),
    }


def concentration_exposure_sample(*, breach: bool = False, seed: int = 23) -> dict:
    """신용집중리스크 익스포저 표본. breach=True 면 동일차주 한도 초과 1건 포함."""
    rng = np.random.default_rng(seed)
    tier1 = 10_000.0
    exposures = [
        {"counterparty_id": f"CP{i:03d}",
         "group_id": f"G{i % 12:02d}",
         "exposure": round(float(rng.uniform(50.0, 400.0)), 2)}
        for i in range(40)
    ]
    if breach:
        exposures.append(
            {"counterparty_id": "CP_BIG", "group_id": "G_BIG",
             "exposure": tier1 * 0.30}  # 동일차주 25% 초과
        )
    return {
        "concentration_exposures": exposures,
        "concentration_tier1": tier1,
        "concentration_equity": tier1 * 1.1,
    }


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


def icaap_sample(*, stressed: bool = False) -> dict:
    """ICAAP 입력 (가용/필요내부자본). stressed=True 면 스트레스 후 미달."""
    required = {
        "credit": 4_800.0,
        "market": 1_300.0,
        "operational": 900.0,
        "irrbb": 800.0,
        "concentration": 700.0,
    }
    if stressed:
        return {
            "icaap_available_capital": 8_000.0,
            "icaap_required_by_risk": required,
            "icaap_diversification": 500.0,
            "icaap_post_stress_available": 7_000.0,  # post-stress < required
        }
    return {
        "icaap_available_capital": 11_000.0,
        "icaap_required_by_risk": required,
        "icaap_diversification": 500.0,
        "icaap_post_stress_available": 9_500.0,
    }


def alm_sample(*, stressed: bool = False) -> dict:
    """ALM 입력 (만기갭 / 조달집중 / 예대율 / NSFR). 단위: 십억원 가정."""
    if stressed:
        return {
            "alm_gaps_by_bucket": {
                "1M": -9_000.0, "3M": -5_000.0, "6M": -2_000.0,
                "1Y": 1_000.0, "3Y": 6_000.0, "over_3Y": 10_000.0,
            },
            "alm_total_assets": 100_000.0,   # 누적 -16% @6M → 한도 위반
            "alm_funding_by_provider": [12_000.0] + [800.0] * 40,
            "alm_loans": 102_000.0,
            "alm_deposits": 100_000.0,       # 예대율 102% → 위반
            "liquidity_asf": 90_000.0,
            "liquidity_rsf": 100_000.0,      # NSFR 0.90 → below_min
        }
    return {
        "alm_gaps_by_bucket": {
            "1M": -2_000.0, "3M": -1_000.0, "6M": 500.0,
            "1Y": 1_500.0, "3Y": 4_000.0, "over_3Y": 8_000.0,
        },
        "alm_total_assets": 100_000.0,
        "alm_funding_by_provider": [2_000.0] + [1_600.0] * 40,
        "alm_loans": 93_000.0,
        "alm_deposits": 100_000.0,
        "liquidity_asf": 110_000.0,
        "liquidity_rsf": 100_000.0,
    }
