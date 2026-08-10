"""사후검증·대표성·모형 거버넌스 원장 ([별표 3] 203.·180.·179.나).

원장 세 장

  ``crm_backtest_result``    등급·자산군별 실제 부도율 대 추정 PD, LGD·CCF 실적
  ``crm_representativeness`` 추정 표본과 현재 포트폴리오의 분포 비교
  ``crm_model_governance``   승인·재검토 이력과 연 1회 점검 이행

**표본외로 검증한다.** 203.가는 "실제 부도율이 해당 등급의 예상 부도율 범위
내에 있음을 검증"하라고 한다. 추정에 쓴 해로 검증하면 그 해의 부도율이 평균에
이미 들어가 있어 범위 안에 있는 것이 당연해진다. 그래서 추정 표본에서 마지막
연도를 빼고, 그 해로 검증한다.

**임계가 없으면 판정하지 않는다.** 예상 부도율 범위의 신뢰수준과 이항검정
유의수준, PSI 임계는 규정이 주지 않는 내부기준이다. 승인 전에는 지표만 내고
판정 컬럼을 비운다. 임의의 임계로 '적합'을 찍으면 그 판정이 규정 판정처럼
보인다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import binom, binomtest, t as _student_t

from risk_lib.datamodel.spec import ColumnSpec as C, TableSpec
from risk_lib.models.estimation.common import PARAMETERS, cast_to_spec
from risk_lib.models.estimation.params import param_value

__all__ = [
    "BACKTEST_RESULT", "REPRESENTATIVENESS", "MODEL_GOVERNANCE",
    "JUDGMENT_STATUS",
    "build_backtest_result", "build_representativeness",
    "build_model_governance", "record_governance_review", "population_psi",
]

# 판정 상태를 판정 결과와 분리한다. 결과가 비어 있는 이유가 원장에 없으면
# 화면이 '판정 안 됨'과 '판정 통과'를 섞는다.
JUDGMENT_STATUS: tuple[str, ...] = (
    "판정완료", "기준미승인", "표본부족", "추정치없음")


BACKTEST_RESULT = TableSpec(
    name="crm_backtest_result", korean="사후검증 결과", product="PRD-RWA",
    grain="기준일 × 모수 × 세그먼트 × 등급 1건당 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("parameter", "string", "모수", nullable=False, allowed=PARAMETERS),
        C("segment", "string", "세그먼트", nullable=False),
        C("grade", "string", "등급 또는 자산군", nullable=False),
        C("backtest_year", "int", "검증 대상연도", nullable=False,
          min_value=1900, max_value=2200),
        C("estimation_window_end", "int", "추정 표본 마지막 연도", nullable=True,
          min_value=1900, max_value=2200),
        C("out_of_sample", "bool", "표본외 여부", nullable=False,
          citation="[별표 3] 203.라(1)",
          note="검증 대상연도가 추정 표본에 들어 있으면 표본내 검증이고, "
               "그때는 범위 안에 있는 것이 당연해진다"),
        C("n_observations", "int", "관측 건수", nullable=False, min_value=0),
        C("n_defaults", "int", "실제 부도수", nullable=True, min_value=0),
        C("realised_value", "float", "실적치", nullable=True, unit="ratio"),
        C("estimated_value", "float", "추정치", nullable=True, unit="ratio"),
        C("expected_count", "float", "예상 부도수", nullable=True,
          unit="count", min_value=0.0),
        C("test_method", "text", "검정방법", nullable=False),
        C("ci_level", "float", "신뢰수준", nullable=True, unit="ratio"),
        C("range_lower", "float", "예상 범위 하한", nullable=True,
          unit="ratio", citation="[별표 3] 203.가 예상 부도율 범위"),
        C("range_upper", "float", "예상 범위 상한", nullable=True,
          unit="ratio"),
        C("inside_range", "bool", "범위 내", nullable=True,
          citation="[별표 3] 203.가"),
        C("p_value", "float", "p값", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("significance_level", "float", "유의수준", nullable=True,
          unit="ratio"),
        C("test_pass", "bool", "검정 통과", nullable=True),
        C("judgment_status", "string", "판정 상태", nullable=False,
          allowed=JUDGMENT_STATUS),
        C("data_note", "text", "데이터·방법 문서화", nullable=False,
          citation="[별표 3] 203.라(2)"),
    ),
    primary_key=("asof", "parameter", "segment", "grade"),
    note="203.가·나·다는 연 1회 이상을 요구한다. 수행 이력은 "
         "crm_model_governance가 들고 있다.",
)

REPRESENTATIVENESS = TableSpec(
    name="crm_representativeness", korean="표본 대표성", product="PRD-RWA",
    grain="기준일 × 모수 × 세그먼트 × 비교축 1건당 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("parameter", "string", "모수", nullable=False, allowed=PARAMETERS),
        C("segment", "string", "세그먼트", nullable=False),
        C("axis", "string", "비교축", nullable=False,
          note="등급·업종·규모·담보 등. 축을 하나만 보면 다른 축의 이동이 "
               "숨는다"),
        C("psi", "float", "PSI", nullable=True, unit="ratio", min_value=0.0),
        C("n_estimation", "int", "추정 표본 건수", nullable=False, min_value=0),
        C("n_current", "int", "현재 포트폴리오 건수", nullable=False,
          min_value=0),
        C("warn_threshold", "float", "경고 임계", nullable=True, unit="ratio"),
        C("fail_threshold", "float", "불합격 임계", nullable=True,
          unit="ratio"),
        C("judgment", "string", "판정", nullable=True,
          allowed=("적합", "경고", "불합격")),
        C("judgment_status", "string", "판정 상태", nullable=False,
          allowed=JUDGMENT_STATUS),
        C("evidence", "text", "대표성 근거", nullable=False,
          citation="[별표 3] 180."),
    ),
    primary_key=("asof", "parameter", "segment", "axis"),
    note="180.은 대표성 입증을 요구하되 지표도 임계도 주지 않는다. 지표는 "
         "내부기준이며 임계가 승인 전이면 판정하지 않는다.",
)

MODEL_GOVERNANCE = TableSpec(
    name="crm_model_governance", korean="추정모형 거버넌스", product="PRD-RWA",
    grain="기준일 × 모수 × 세그먼트 1건당 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("parameter", "string", "모수", nullable=False, allowed=PARAMETERS),
        C("segment", "string", "세그먼트", nullable=False),
        C("model_id", "string", "모형 식별자", nullable=False),
        C("approval_date", "date", "승인일", nullable=True),
        C("approved_by", "string", "승인자", nullable=True),
        C("approval_body", "string", "승인기구", nullable=True),
        C("last_review_date", "date", "최근 점검일", nullable=True,
          citation="[별표 3] 179.나 · 193.마"),
        C("next_review_due", "date", "다음 점검기한", nullable=True),
        C("review_interval_months", "float", "점검주기", nullable=True,
          unit="months", min_value=0.0),
        C("review_overdue", "bool", "점검 기한 경과", nullable=True,
          note="최근 점검일이 없으면 NULL이다. 점검 기록이 없는 것을 '기한 내'로 "
               "두면 미이행이 통과로 둔갑한다"),
        C("last_backtest_date", "date", "최근 사후검증일", nullable=True,
          citation="[별표 3] 203."),
        C("n_reviews", "int", "점검 횟수", nullable=False, min_value=0),
        C("status", "string", "상태", nullable=False),
        C("citation", "text", "근거", nullable=False),
    ),
    primary_key=("asof", "parameter", "segment"),
    note="승인·점검 기록이 없으면 비운다. 179.나와 193.마의 연 1회 점검은 "
         "기록이 있어야 이행으로 본다.",
)

_DOC_NOTE = (
    "[별표 3] 203.라(2) 데이터·방법론 문서화. 관측이력은 crm_default_history · "
    "crm_recovery_history · crm_facility_drawdown_history이며 전건 합성이다. "
    "추정 표본에서 마지막 연도를 뺀 뒤 그 해로 검증한다")


def _month_add(asof: str, months: float | None) -> str | None:
    if months is None or not np.isfinite(months):
        return None
    y, m = int(asof[:4]), int(asof[5:7])
    idx = y * 12 + (m - 1) + int(round(months))
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}-{asof[8:10]}"


# ---------------------------------------------------------------- 사후검증

def build_backtest_result(*, asof: str, param: pd.DataFrame,
                          yearly_dr: pd.DataFrame,
                          pd_estimate: pd.DataFrame,
                          lgd_realised: pd.DataFrame | None = None,
                          lgd_estimate: pd.DataFrame | None = None,
                          ccf_observed: pd.DataFrame | None = None,
                          ccf_estimate: pd.DataFrame | None = None,
                          ) -> pd.DataFrame:
    """사후검증 원장 (203.).

    PD는 유보연도의 등급별 실제 부도율을 추정 PD가 만드는 이항분포 범위와
    비교한다. LGD·CCF는 유보연도 부도건의 실적 평균을 추정치와 t검정으로
    비교한다.

    ``lgd_realised``는 ``segment``·``default_year``·``lgd_realised`` 컬럼을,
    ``ccf_observed``는 ``segment``·``ccf_type``·``default_year``·
    ``ccf_observed`` 컬럼을 가져야 한다.
    """
    ci_level = param_value(param, "backtest_ci_level")
    alpha = param_value(param, "backtest_significance_level")
    rows: list[dict] = []

    holdout = yearly_dr[~yearly_dr["in_estimation_sample"]]
    window_end = (int(yearly_dr[yearly_dr["in_estimation_sample"]]
                      ["cohort_year"].max())
                  if (yearly_dr["in_estimation_sample"]).any() else None)
    est_idx = pd_estimate.set_index(["segment", "grade"])

    for _, r in holdout.iterrows():
        key = (r["segment"], r["grade"])
        est = (float(est_idx.loc[key, "final_applied"])
               if key in est_idx.index else None)
        n = int(r["n_obligors"])
        d = int(r["n_defaults"])
        realised = float(r["default_rate"]) if n else None
        lo = hi = inside = p = None
        status = "판정완료"
        if est is None or not np.isfinite(est):
            status = "추정치없음"
        elif n == 0:
            status = "표본부족"
        else:
            p = float(binomtest(d, n, est).pvalue)
            if ci_level is None:
                status = "기준미승인"
            else:
                tail = (1.0 - ci_level) / 2.0
                lo = float(binom.ppf(tail, n, est) / n)
                hi = float(binom.ppf(1.0 - tail, n, est) / n)
                inside = bool(lo <= realised <= hi)
        rows.append({
            "asof": asof, "parameter": "PD", "segment": r["segment"],
            "grade": r["grade"], "backtest_year": int(r["cohort_year"]),
            "estimation_window_end": window_end,
            "out_of_sample": (window_end is None
                              or int(r["cohort_year"]) > window_end),
            "n_observations": n, "n_defaults": d,
            "realised_value": realised, "estimated_value": est,
            "expected_count": (None if est is None else float(est * n)),
            "test_method": ("추정 PD를 성공확률로 하는 이항분포의 신뢰구간과 "
                            "실제 부도율을 비교한다(203.가). p값은 양측 "
                            "이항검정"),
            "ci_level": ci_level, "range_lower": lo, "range_upper": hi,
            "inside_range": inside, "p_value": p,
            "significance_level": alpha,
            "test_pass": (None if (p is None or alpha is None)
                          else bool(p >= alpha)),
            "judgment_status": status, "data_note": _DOC_NOTE,
        })

    holdout_years = sorted(set(int(y) for y in holdout["cohort_year"]))
    if lgd_realised is not None and lgd_estimate is not None:
        rows.extend(_ttest_rows(
            asof=asof, parameter="LGD", alpha=alpha, ci_level=ci_level,
            realised=lgd_realised, value_col="lgd_realised",
            group_cols=["segment"], estimate=lgd_estimate,
            est_key=["segment"], years=holdout_years,
            method=("유보연도 부도건의 실현 LGD 평균과 추정 LGD의 차이에 대한 "
                    "일표본 t검정(203.나)")))
    if ccf_observed is not None and ccf_estimate is not None:
        rows.extend(_ttest_rows(
            asof=asof, parameter="CCF", alpha=alpha, ci_level=ci_level,
            realised=ccf_observed, value_col="ccf_observed",
            group_cols=["segment", "ccf_type"], estimate=ccf_estimate,
            est_key=["segment", "ccf_type"], years=holdout_years,
            method=("유보연도 부도 한도거래의 실측 CCF 평균과 추정 CCF의 "
                    "차이에 대한 일표본 t검정(203.나)")))
    return cast_to_spec(pd.DataFrame(rows, columns=[
        c.name for c in BACKTEST_RESULT.columns]), BACKTEST_RESULT)


def _ttest_rows(*, asof, parameter, alpha, ci_level, realised, value_col,
                group_cols, estimate, est_key, years, method) -> list[dict]:
    """LGD·CCF 사후검증 행. 표본이 2건 미만이면 검정하지 않는다."""
    out: list[dict] = []
    if realised is None or realised.empty or not years:
        return out
    sub = realised[realised["default_year"].isin(years)]
    if sub.empty:
        return out
    est_idx = estimate.set_index(est_key)
    for key, grp in sub.groupby(group_cols):
        key_t = key if isinstance(key, tuple) else (key,)
        vals = pd.to_numeric(grp[value_col], errors="coerce").dropna()
        est = None
        if key_t in est_idx.index or (len(key_t) == 1 and key_t[0]
                                      in est_idx.index):
            k = key_t if len(key_t) > 1 else key_t[0]
            est_v = est_idx.loc[k, "final_applied"]
            est = (None if pd.isna(est_v) else float(est_v))
        n = int(len(vals))
        status = "판정완료"
        p = lo = hi = inside = None
        realised_mean = float(vals.mean()) if n else None
        if est is None:
            status = "추정치없음"
        elif n < 2:
            status = "표본부족"
        else:
            se = float(vals.std(ddof=1) / np.sqrt(n))
            if se > 0:
                tstat = (realised_mean - est) / se
                p = float(2.0 * (1.0 - _student_t.cdf(abs(tstat), df=n - 1)))
            if ci_level is None:
                status = "기준미승인"
            elif se > 0:
                half = float(_student_t.ppf(0.5 + ci_level / 2.0, df=n - 1) * se)
                lo, hi = est - half, est + half
                inside = bool(lo <= realised_mean <= hi)
        out.append({
            "asof": asof, "parameter": parameter, "segment": key_t[0],
            "grade": (key_t[1] if len(key_t) > 1 else key_t[0]),
            "backtest_year": int(max(years)),
            "estimation_window_end": int(min(years)) - 1,
            "out_of_sample": True, "n_observations": n, "n_defaults": None,
            "realised_value": realised_mean, "estimated_value": est,
            "expected_count": None, "test_method": method,
            "ci_level": ci_level, "range_lower": lo, "range_upper": hi,
            "inside_range": inside, "p_value": p,
            "significance_level": alpha,
            "test_pass": (None if (p is None or alpha is None)
                          else bool(p >= alpha)),
            "judgment_status": status, "data_note": _DOC_NOTE,
        })
    return out


# ---------------------------------------------------------------- 대표성

def population_psi(expected: pd.Series, actual: pd.Series) -> float | None:
    """범주형 분포의 PSI.

    양쪽 어느 한쪽에만 있는 범주도 분모에 넣는다. 교집합만 쓰면 새로 생긴
    범주가 지수에서 사라져 이동이 0으로 나온다.
    """
    e = expected.value_counts(normalize=True)
    a = actual.value_counts(normalize=True)
    cats = sorted(set(e.index) | set(a.index), key=str)
    if not cats:
        return None
    ev = np.clip(np.array([e.get(c, 0.0) for c in cats], dtype=float), 1e-6, None)
    av = np.clip(np.array([a.get(c, 0.0) for c in cats], dtype=float), 1e-6, None)
    return float(np.sum((av - ev) * np.log(av / ev)))


def build_representativeness(history: pd.DataFrame, current: pd.DataFrame, *,
                             asof: str, param: pd.DataFrame,
                             parameter: str = "PD",
                             axes: tuple[str, ...] = ("grade",),
                             current_label: str = "현재 포트폴리오",
                             ) -> pd.DataFrame:
    """추정 표본과 현재 포트폴리오의 분포를 비교한다 (180.).

    ``current``는 ``segment``와 비교축 컬럼을 가져야 한다. 축이 현재
    포트폴리오에 없으면 그 축의 행은 만들되 PSI를 비우고 사유를 남긴다.
    """
    warn = param_value(param, "psi_threshold_warn")
    fail = param_value(param, "psi_threshold_fail")
    h = history[history["asof"] == asof]
    rows: list[dict] = []
    for segment in sorted(set(h["segment"])):
        hs = h[h["segment"] == segment]
        cs = current[current["segment"] == segment] if "segment" in current \
            else current
        for axis in axes:
            psi = None
            evidence = (f"추정 표본 {len(hs)}건과 {current_label} {len(cs)}건의 "
                        f"{axis} 분포를 PSI로 비교했다 (180.)")
            if axis not in hs.columns or axis not in cs.columns or cs.empty:
                evidence = (f"{axis} 축이 추정 표본 또는 {current_label}에 "
                            "없어 비교하지 못했다. 지표를 0으로 두지 않는다")
                status, judgment = "표본부족", None
            else:
                psi = population_psi(hs[axis], cs[axis])
                if warn is None or fail is None:
                    status, judgment = "기준미승인", None
                else:
                    status = "판정완료"
                    judgment = ("불합격" if psi >= fail
                                else ("경고" if psi >= warn else "적합"))
            rows.append({
                "asof": asof, "parameter": parameter, "segment": segment,
                "axis": axis, "psi": psi, "n_estimation": int(len(hs)),
                "n_current": int(len(cs)), "warn_threshold": warn,
                "fail_threshold": fail, "judgment": judgment,
                "judgment_status": status, "evidence": evidence})
    return cast_to_spec(pd.DataFrame(rows, columns=[
        c.name for c in REPRESENTATIVENESS.columns]), REPRESENTATIVENESS)


# ---------------------------------------------------------------- 거버넌스

def build_model_governance(run: pd.DataFrame, *, asof: str,
                           param: pd.DataFrame) -> pd.DataFrame:
    """추정모형 거버넌스 원장. 승인·점검 기록이 없으면 비운다."""
    interval = param_value(param, "review_interval_months")
    rows = []
    for _, r in run.iterrows():
        rows.append({
            "asof": asof, "parameter": r["parameter"], "segment": r["segment"],
            "model_id": f"IRB_{r['parameter']}_{r['segment']}",
            "approval_date": None, "approved_by": None,
            "approval_body": None, "last_review_date": None,
            "next_review_due": None, "review_interval_months": interval,
            "review_overdue": None, "last_backtest_date": None,
            "n_reviews": 0, "status": "이력없음",
            "citation": ("[별표 3] 179.나 추정치 적정 여부 연 1회 이상 점검, "
                         "193.마 EAD 추정기준 연 1회 이상 검토, 203. 사후검증 "
                         "연 1회 이상"),
        })
    return cast_to_spec(pd.DataFrame(rows, columns=[
        c.name for c in MODEL_GOVERNANCE.columns]), MODEL_GOVERNANCE)


def record_governance_review(ledger: pd.DataFrame, *, parameter: str,
                             segment: str, review_date: str,
                             approved_by: str | None = None,
                             approval_date: str | None = None,
                             approval_body: str | None = None,
                             backtest_date: str | None = None
                             ) -> pd.DataFrame:
    """점검·승인 기록을 넣은 사본을 돌려준다.

    이 함수가 곧 수기 점검 프로세스가 원장에 남기는 형태다. 점검이 기록되면
    다음 점검기한과 기한 경과 여부가 계산된다.
    """
    out = ledger.copy()
    m = (out["parameter"] == parameter) & (out["segment"] == segment)
    if not m.any():
        raise KeyError(f"crm_model_governance에 행이 없다: {parameter}/{segment}")
    out.loc[m, "last_review_date"] = review_date
    out.loc[m, "n_reviews"] = out.loc[m, "n_reviews"].fillna(0) + 1
    interval = out.loc[m, "review_interval_months"].iloc[0]
    due = _month_add(review_date, None if pd.isna(interval) else float(interval))
    out.loc[m, "next_review_due"] = due
    if due is not None:
        asof = out.loc[m, "asof"].iloc[0]
        out.loc[m, "review_overdue"] = bool(str(asof) > due)
    if approved_by is not None:
        out.loc[m, "approved_by"] = approved_by
        out.loc[m, "approval_date"] = approval_date
        out.loc[m, "approval_body"] = approval_body
    if backtest_date is not None:
        out.loc[m, "last_backtest_date"] = backtest_date
    out.loc[m, "status"] = "점검이행"
    return out
