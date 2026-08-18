"""PD 모형 설명(XAI) — odds ratio + permutation importance + 등급 migration.

근거
----
* SR 11-7 / 금감원 「모형리스크관리 모범규준」: 모형 설명력·해석성 요건.
* Basel III CRE36.31: 등급화 시스템의 변수별 기여도 문서화.

산출
----
* ``coefficient_table`` — 로지스틱 회귀 계수, odds ratio, 표준화된 영향력.
* ``permutation_importance`` — Breiman(2001) permutation importance를 적용,
  교란 후 Gini drop 평균(시드 고정).
* ``grade_migration_psi`` — train vs recent 등급 분포의 PSI(grade-level).
* ``grade_transition_matrix`` — 두 시점 등급 매핑(이주율).
* ``master_scale_calibration`` — 등급별 (mid PD, mean predicted PD, 실현 DR).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from risk_lib.models.pd_model import PDModel, gini
from risk_lib.models.rating import DEFAULT_MASTER_SCALE


def coefficient_table(model: PDModel) -> pd.DataFrame:
    """로지스틱 회귀 계수 → odds ratio · 표준화 영향력.

    `feature_effect` = |β| × σ(feature) — 표준화 영향력 (이미 스케일링된 변수
    위에서 적합했으므로 β의 절댓값과 동일).  음수 부호는 PD 감소 방향.
    """
    coefs = model.clf.coef_.ravel()
    rows = []
    for feat, c in zip(model.features, coefs):
        rows.append({
            "feature": feat,
            "coef": float(c),
            "odds_ratio": float(np.exp(c)),
            "abs_effect": float(abs(c)),
            "direction": "위험↑" if c > 0 else "위험↓",
        })
    df = pd.DataFrame(rows).sort_values("abs_effect", ascending=False)
    total = df["abs_effect"].sum() or 1.0
    df["contribution_pct"] = df["abs_effect"] / total
    return df.reset_index(drop=True)


def permutation_importance(
    model: PDModel,
    df: pd.DataFrame,
    target: str = "default_12m",
    n_repeats: int = 5,
    seed: int = 42,
) -> pd.DataFrame:
    """Permutation importance ranked by Gini drop.

    Returns one row per feature with mean/std Gini drop across ``n_repeats``
    shuffles.  Large drop ⇒ feature carries discriminatory signal.
    """
    rng = np.random.default_rng(seed)
    base_p = model.predict_pd(df)
    base_gini = gini(df[target].values, base_p)
    rows = []
    for feat in model.features:
        drops = []
        for _ in range(n_repeats):
            shuffled = df.copy()
            shuffled[feat] = rng.permutation(shuffled[feat].to_numpy())
            p = model.predict_pd(shuffled)
            drops.append(base_gini - gini(df[target].values, p))
        drops = np.asarray(drops, dtype=float)
        rows.append({"feature": feat,
                     "gini_drop_mean": float(drops.mean()),
                     "gini_drop_std": float(drops.std(ddof=0))})
    out = pd.DataFrame(rows).sort_values("gini_drop_mean", ascending=False)
    out["base_gini"] = base_gini
    return out.reset_index(drop=True)


def grade_migration_psi(
    train_grades: pd.Series, recent_grades: pd.Series,
) -> dict[str, float | pd.DataFrame]:
    """등급(category) 분포 안정성.

    PSI = Σ (a_i - e_i) ln(a_i / e_i) — bins이 등급 카테고리.  zone:
      <0.10 GREEN, 0.10–0.25 AMBER, ≥0.25 RED.
    """
    cats = [g.grade for g in DEFAULT_MASTER_SCALE]
    e_counts = train_grades.value_counts().reindex(cats, fill_value=0)
    a_counts = recent_grades.value_counts().reindex(cats, fill_value=0)
    e = np.clip(e_counts.values / max(len(train_grades), 1), 1e-6, None)
    a = np.clip(a_counts.values / max(len(recent_grades), 1), 1e-6, None)
    contributions = (a - e) * np.log(a / e)
    psi_val = float(contributions.sum())
    zone = "GREEN" if psi_val < 0.10 else ("AMBER" if psi_val < 0.25 else "RED")
    detail = pd.DataFrame({
        "grade": cats,
        "train_pct": e_counts.values / max(len(train_grades), 1),
        "recent_pct": a_counts.values / max(len(recent_grades), 1),
        "psi_contrib": contributions,
    })
    return {"psi": psi_val, "zone": zone, "detail": detail}


def grade_transition_matrix(
    grades_t0: pd.Series, grades_t1: pd.Series,
) -> pd.DataFrame:
    """동일 차주의 t0→t1 등급 이동 행렬(행별 정규화).

    표본 차주 수가 같지 않으면 짧은 쪽을 truncate.  반환은 [from_grade,
    to_grade, n, pct] long-format.
    """
    cats = [g.grade for g in DEFAULT_MASTER_SCALE]
    n = min(len(grades_t0), len(grades_t1))
    g0 = pd.Categorical(grades_t0.iloc[:n], categories=cats, ordered=True)
    g1 = pd.Categorical(grades_t1.iloc[:n], categories=cats, ordered=True)
    ct = pd.crosstab(g0, g1, dropna=False)
    rows = []
    for g_from in cats:
        if g_from not in ct.index:
            continue
        total = ct.loc[g_from].sum()
        for g_to in cats:
            if g_to not in ct.columns:
                continue
            n_ij = int(ct.loc[g_from, g_to])
            rows.append({"from_grade": g_from, "to_grade": g_to,
                         "n": n_ij,
                         "pct": (n_ij / total) if total else 0.0})
    return pd.DataFrame(rows)


def master_scale_calibration(
    pd_predicted: np.ndarray,
    y_true: np.ndarray,
    grades: pd.Series,
) -> pd.DataFrame:
    """등급별 (mid PD, 평균 모형 PD, 실현 DR, 표본 수).

    Basel CRE36 등급 시스템 캘리브레이션 plot 데이터.  미드 PD 대비 실현 DR
    이 일관되게 작으면 보수적, 크면 위반.
    """
    p = np.asarray(pd_predicted, dtype=float)
    y = np.asarray(y_true, dtype=int)
    g = pd.Series(grades).reset_index(drop=True)
    mid_map = {gr.grade: gr.pd_midpoint for gr in DEFAULT_MASTER_SCALE}
    rows = []
    for grade_lbl in [gr.grade for gr in DEFAULT_MASTER_SCALE]:
        mask = (g == grade_lbl).to_numpy()
        if not mask.any():
            continue
        rows.append({
            "grade": grade_lbl,
            "pd_midpoint": mid_map[grade_lbl],
            "mean_pd_predicted": float(p[mask].mean()),
            "realised_dr": float(y[mask].mean()),
            "n": int(mask.sum()),
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df["bias"] = df["mean_pd_predicted"] - df["realised_dr"]
    return df
