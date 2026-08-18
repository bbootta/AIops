"""부도자산 예상외손실 추가분 PLGD ([별표 3] 185.바 후단, 120.가(2)·(5)).

185.바는 두 문장이다. 앞 문장 "예상손실의 최적 추정치를 산출하여야 하며"가
ELBE이고, 뒤 문장 "회수기간동안 발생할 수 있는 예상외 손실 가능성을 추가적으로
반영하여야 한다"가 이 모듈이 만드는 값이다. FRME 교안(2016)은 그 값을
PLGD(Potential LGD)라 부르고 "BEEL 분포의 일정 신뢰수준에 해당하는 극단값"으로
정의한다. 정의는 확인됐고 산식 모수 넷이 자료에 없었다. 이 모듈은 그중 둘을
관측 데이터로 결정하고, 하나는 정책 선택이라 비워 두며, 하나는 조문 문언으로
좁힌다. 결정 근거와 수치는 ``docs/PLGD_시뮬레이션.md``에 있다.

산식
    BEEL(s, k) = 1 − PV_k(경과월 k 이후 회수 − 비용) / 분모
    PLGD(s, k) = Quantile_q( BEEL_i(s, k) )            방법 '분포직접'
    PLGD(s, k) = min(1, BEEL(s, k) × DSF(s))           방법 'DSF반영'
    예상외손실 추가분 = PLGD − ELBE
    소요자기자본율 K = max(0, LGD_in_default − EL_default)

마지막 줄은 [별표 3] 120.가(2)에서 나온다. 주2)가 PD 100%일 때 N{x}를 1로
두고, 주4)가 EL을 185.바의 부도자산 예상손실로 두며, 주1)이 0 미만을 0으로
자른다. 즉 부도자산의 소요자기자본은 PLGD와 ELBE의 차이만큼만 남는다. 유효만기
조정은 원장에 만기 자료가 없어 적용하지 않았고 그 사실을 컬럼이 들고 있다.

**q는 비어 있다.** 교안은 "일정 신뢰수준"이라고만 적고 값을 주지 않으며 규정도
주지 않는다. 시뮬레이션은 q를 정해 주지 못한다. ``build_crm_plgd``는 승인
기록 없이는 q를 받지 않고, q가 없으면 PLGD를 계산하지 않고 경고를 남긴다.
``build_crm_plgd_sensitivity``가 후보 q별로 PLGD·RWA가 얼마나 움직이는지만
보인다. 민감도표의 q는 적용값이 아니다.

**결정론.** 이 모듈은 난수를 쓰지 않는다. 같은 (asof, seed, 할인율)이면 결과가
바이트 동일하다.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec
from risk_lib.models.estimation.common import cast_to_spec
from risk_lib.models.estimation.params import (
    IRB_EVIDENCE_STATUS, ParamWarning, discount_rate_for,
)

__all__ = [
    "BEEL_DENOMINATORS", "DSF_FORMS", "PLGD_METHODS", "MONOTONICITY_VERDICTS",
    "SENSITIVITY_Q_GRID",
    "BEEL_CURVE", "PLGD", "PLGD_SENSITIVITY", "PLGD_TABLES",
    "beel_by_default", "build_crm_beel_curve",
    "decide_beel_denominator", "decide_dsf_form",
    "defaulted_capital_requirement",
    "build_crm_plgd", "build_crm_plgd_sensitivity", "build_plgd_ledgers",
    "check_plgd_not_below_elbe", "check_plgd_provision_justification",
    "check_beel_monotonicity", "run_plgd_checks",
]


# ---------------------------------------------------------------- 어휘

# BEEL 경과월 산식의 분모. 교안은 분모를 적지 않는다. 두 후보를 어휘로 두고
# 어느 쪽을 썼는지가 원장 PK에 들어간다. 한쪽만 계산하면 선택의 영향이 화면에
# 나오지 않는다.
BEEL_DENOMINATORS: tuple[str, ...] = ("부도시익스포저", "잔여익스포저")
# 교안은 "BEEL 추정치에 Downturn Scaling Factor를 반영"이라고만 적는다.
# 승산인지 가산인지는 문언에서 갈리지 않는다.
DSF_FORMS: tuple[str, ...] = ("승산", "가산")
PLGD_METHODS: tuple[str, ...] = ("분포직접", "DSF반영", "미산출")
MONOTONICITY_VERDICTS: tuple[str, ...] = ("단조증가", "단조증가아님", "판정불가")
PLGD_STATUS: tuple[str, ...] = (
    "산출완료", "산출완료(표본부족)", "산출불가(신뢰수준미승인)",
    "산출불가(할인율미승인)", "산출불가(표본없음)")

# ---------------------------------------------------------------- 규제 상수
# 아래 값은 이 모듈의 원장 빌더만 읽고 엔진 함수는 인자로 받는다. 값은 원장
# 컬럼으로 나가므로 화면과 검증이 근거와 함께 본다.

# 위험가중자산 = 소요자기자본율 × 12.5 × EAD. 최저비율 8%의 역수다.
_RWA_MULTIPLIER = 12.5
_RWA_CITE = ("[별표 3] 120.가(1)·127.가·129. 신용위험가중자산 산식. "
             "소요자기자본율에 12.5를 곱한다(239. 운영위험가중자산 산식이 같은 "
             "배수를 명시적으로 적는다)")
_K_CITE = ("[별표 3] 120.가(2) 주1)·주2)·주4) 및 120.가(5). PD가 100%이면 "
           "N{x}=1이고 EL은 185.바의 부도자산 예상손실이므로 소요자기자본율은 "
           "max(0, 부도자산 LGD − ELBE)로 남는다")
_TEXTBOOK = ("FRME 2016 3기 교안 「5강) (LGD) 교안.ppt」 슬라이드 '6. PL(G)D "
             "추정'. 교육자료(2016)이며 규정이 아니다")
_CLAUSE = "[별표 3] 185.바 후단 '회수기간동안 발생할 수 있는 예상외 손실 가능성'"

# 민감도 격자. **적용값이 아니다.** 이 값들은 crm_plgd_sensitivity에만 들어가고
# crm_plgd.confidence_q로는 승인 경로를 거친 값만 들어간다.
SENSITIVITY_Q_GRID: tuple[float, ...] = (0.75, 0.90, 0.95, 0.99)


# ---------------------------------------------------------------- 스펙

BEEL_CURVE = TableSpec(
    name="crm_beel_curve", korean="BEEL 경과월 곡선", product="PRD-RWA",
    grain="기준일 × 세그먼트 × 분모구분 × 부도후 경과월 1건당 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("segment", "string", "세그먼트", nullable=False),
        C("beel_denominator", "string", "분모구분", nullable=False,
          allowed=BEEL_DENOMINATORS,
          note="교안이 분모를 적지 않아 두 후보를 모두 산출한다. PK에 들어가야 "
               "두 곡선이 한 원장에서 나란히 보인다"),
        C("months_since_default", "int", "부도후 경과월", nullable=False,
          min_value=0),
        C("n_defaults", "int", "코호트 건수", nullable=False, min_value=0,
          note="경과월 k에 아직 부도상태이고 회수가 종결된 건. k가 커질수록 "
               "회수가 빨랐던 건이 빠져나가 잔존 표본이 열위로 치우친다"),
        C("observation_censored", "int", "관측중단 건수", nullable=False,
          min_value=0,
          note="같은 경과월에 부도상태이나 회수가 진행 중인 건. 이 건들의 미래 "
               "회수는 관측되지 않았으므로 평균에서 빼고 건수만 남긴다"),
        C("beel_mean", "float", "BEEL 평균", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0,
          citation="[별표 3] 185.바 전단 예상손실의 최적 추정치"),
        C("beel_median", "float", "BEEL 중위값", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("beel_std", "float", "BEEL 표준편차", nullable=True, unit="ratio",
          min_value=0.0),
        C("beel_q", "float", "BEEL 분위수", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0, citation=_CLAUSE,
          note="confidence_q가 승인되기 전에는 비어 있다"),
        C("confidence_q", "float", "신뢰수준", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0,
          note="규정 미제시. 승인 전에는 NULL이다"),
        C("tail_observations", "int", "분위수 위쪽 표본수", nullable=True,
          min_value=0,
          note="floor(n × (1−q)). 0이면 분위수가 표본 밖 순서통계량이다"),
        C("beel_mean_incl_censored", "float", "관측중단 포함 평균",
          nullable=True, unit="ratio", min_value=0.0, max_value=1.0,
          note="미종결 건의 관측된 회수만으로 계산한 값을 함께 넣은 평균. "
               "보수 방향이며 두 값의 차이가 관측중단 처리의 영향이다"),
        C("censoring_impact", "float", "관측중단 처리 차이", nullable=True,
          unit="ratio", note="포함 − 제외. 양수면 제외 처리가 낙관적이다"),
        C("ead_at_default_total", "float", "부도시 익스포저 합계",
          nullable=True, unit="KRW", min_value=0.0),
        C("residual_exposure_total", "float", "잔여 익스포저 합계",
          nullable=True, unit="KRW", min_value=0.0),
        C("monotonicity_verdict", "string", "단조성 판정", nullable=False,
          allowed=MONOTONICITY_VERDICTS,
          note="세그먼트 × 분모구분 단위 판정이라 그 곡선의 모든 행에 같은 값이 "
               "들어간다. 곡선을 골라 읽을 때 판정이 함께 따라오게 하려는 것이다"),
        C("monotonicity_rho", "float", "스피어만 상관", nullable=True,
          unit="ratio", min_value=-1.0, max_value=1.0),
        C("monotonicity_pvalue", "float", "상관 p값", nullable=True,
          unit="ratio", min_value=0.0, max_value=1.0),
        C("is_applied_denominator", "bool", "적용 분모", nullable=False,
          note="decide_beel_denominator의 판정 결과. 두 곡선 중 하나만 True다"),
        C("discount_rate", "float", "할인율", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0,
          citation="[별표 3] 184.(1) 할인효과"),
        C("citation", "text", "근거", nullable=False),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=IRB_EVIDENCE_STATUS),
        C("status", "string", "상태", nullable=False),
    ),
    primary_key=("asof", "segment", "beel_denominator",
                 "months_since_default"),
    note="교안은 BEEL을 부도후 경과월 축으로 그린다. 부도 3개월 된 건과 30개월 "
         "된 건은 남은 회수 가능성이 다르므로 한 값을 쓸 수 없다.",
)

PLGD = TableSpec(
    name="crm_plgd", korean="부도자산 PLGD", product="PRD-RWA",
    grain="기준일 × 세그먼트 1건당 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("segment", "string", "세그먼트", nullable=False),
        C("n_defaulted_open", "int", "부도상태 건수", nullable=False,
          min_value=0),
        C("ead_at_default_open", "float", "부도상태 익스포저", nullable=True,
          unit="KRW", min_value=0.0),
        C("beel_denominator", "string", "분모구분", nullable=False,
          allowed=BEEL_DENOMINATORS),
        C("elbe", "float", "예상손실 최적추정치", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0,
          citation="[별표 3] 185.바 전단"),
        C("plgd", "float", "PLGD", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0, citation=_CLAUSE),
        C("unexpected_loss_addon", "float", "예상외손실 추가분", nullable=True,
          unit="ratio", citation=_CLAUSE,
          note="PLGD − ELBE. 음수면 조문이 요구하는 '추가 반영'이 아니므로 "
               "검사가 잡는다"),
        C("lgd_in_default", "float", "부도자산 적용 LGD", nullable=True,
          unit="ratio", min_value=0.0, max_value=1.0),
        C("lgd_in_default_basis", "text", "적용 LGD 근거", nullable=False),
        C("dsf", "float", "Downturn Scaling Factor", nullable=True,
          unit="ratio",
          note="dsf_form이 '승산'이면 배수, '가산'이면 절대 가산폭이다. 단위가 "
               "형태에 따라 달라지므로 두 컬럼을 떼어 읽으면 안 된다"),
        C("dsf_form", "string", "DSF 반영형태", nullable=True,
          allowed=DSF_FORMS),
        C("dsf_form_basis", "text", "반영형태 판정근거", nullable=True),
        C("confidence_q", "float", "신뢰수준", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0,
          note="규정 미제시. 승인 전에는 NULL이고 그러면 PLGD도 NULL이다"),
        C("confidence_q_status", "string", "신뢰수준 상태", nullable=False),
        C("method", "string", "산출방법", nullable=False,
          allowed=PLGD_METHODS),
        C("capital_requirement_k", "float", "부도자산 소요자기자본율",
          nullable=True, unit="ratio", min_value=0.0, max_value=1.0,
          citation=_K_CITE),
        C("maturity_adjustment_applied", "bool", "유효만기 조정 반영",
          nullable=False,
          note="원장에 유효만기 자료가 없어 반영하지 않았다. 기업 익스포저는 "
               "120.가(4)의 조정이 걸리므로 이 값은 그만큼 과소다"),
        C("elbe_amount", "float", "ELBE 금액", nullable=True, unit="KRW",
          min_value=0.0),
        C("elbe_amount_alt_denominator", "float", "다른 분모 기준 ELBE 금액",
          nullable=True, unit="KRW", min_value=0.0,
          note="분모 선택이 금액을 얼마나 움직이는지 보이려고 함께 둔다. "
               "185.바 비교는 elbe_amount로 한다"),
        C("specific_provision", "float", "개별충당금", nullable=True,
          unit="KRW", min_value=0.0),
        C("partial_writeoff", "float", "부분상각", nullable=True, unit="KRW",
          min_value=0.0),
        C("shortfall", "float", "충당금+상각 − ELBE", nullable=True,
          unit="KRW",
          note="양수면 ELBE가 작다는 뜻이고 185.바 후단의 입증책임이 붙는다. "
               "반대 방향에는 입증책임이 없다"),
        C("justification_required", "bool", "정당성 입증 필요", nullable=True,
          citation="[별표 3] 185.바 후단"),
        C("justification_ref", "text", "입증 문서", nullable=True),
        C("insufficient_sample", "bool", "표본부족", nullable=False),
        C("citation", "text", "근거", nullable=False),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=IRB_EVIDENCE_STATUS),
        C("approved_by", "string", "승인자", nullable=True),
        C("approval_date", "date", "승인일", nullable=True),
        C("status", "string", "상태", nullable=False, allowed=PLGD_STATUS),
        C("note", "text", "비고", nullable=True),
    ),
    primary_key=("asof", "segment"),
    foreign_keys=(FK(("asof", "segment", "beel_denominator"),
                     "crm_beel_curve",
                     ("asof", "segment", "beel_denominator")),),
    note="185.바의 두 문장이 elbe와 plgd 두 컬럼으로 갈라져 있고 그 차이가 "
         "unexpected_loss_addon이다. 신뢰수준이 승인되기 전에는 plgd가 비어 "
         "있고 그 사실이 confidence_q_status에 남는다.",
)

PLGD_SENSITIVITY = TableSpec(
    name="crm_plgd_sensitivity", korean="PLGD 신뢰수준 민감도",
    product="PRD-RWA",
    grain="기준일 × 세그먼트 × 후보 신뢰수준 1건당 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("segment", "string", "세그먼트", nullable=False),
        C("confidence_q", "float", "후보 신뢰수준", nullable=False,
          unit="ratio", min_value=0.0, max_value=1.0,
          note="민감도 격자의 후보다. 적용값이 아니며 crm_plgd로 넘어가지 않는다"),
        C("n_defaulted_open", "int", "부도상태 건수", nullable=False,
          min_value=0),
        C("ead_at_default_open", "float", "부도상태 익스포저", nullable=True,
          unit="KRW", min_value=0.0),
        C("elbe", "float", "ELBE", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("plgd", "float", "PLGD", nullable=True, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("unexpected_loss_addon", "float", "예상외손실 추가분", nullable=True,
          unit="ratio"),
        C("capital_requirement_k", "float", "소요자기자본율", nullable=True,
          unit="ratio", min_value=0.0, max_value=1.0, citation=_K_CITE),
        C("rwa", "float", "위험가중자산", nullable=True, unit="KRW",
          min_value=0.0, citation=_RWA_CITE),
        C("rwa_multiplier", "float", "RWA 배수", nullable=False, unit="ratio",
          citation=_RWA_CITE),
        C("rwa_delta_vs_lowest_q", "float", "최저 q 대비 RWA 증가",
          nullable=True, unit="KRW"),
        C("provision_requirement", "float", "충당금 소요", nullable=True,
          unit="KRW", min_value=0.0,
          note="ELBE 금액이다. 120.가(2) 주4)가 부도자산 EL을 185.바 최적추정치로 "
               "정하므로 q를 바꿔도 이 값은 움직이지 않는다"),
        C("provision_delta_vs_lowest_q", "float", "최저 q 대비 충당금 증가",
          nullable=True, unit="KRW"),
        C("min_tail_observations", "int", "최소 꼬리 표본수", nullable=True,
          min_value=0,
          note="경과월 코호트별 floor(n×(1−q))의 최소값. 0이면 그 q의 분위수가 "
               "표본 밖 순서통계량이라 관측이 뒷받침하지 않는다"),
        C("provision_basis", "text", "충당금 산식", nullable=False),
        C("citation", "text", "근거", nullable=False),
        C("status", "string", "상태", nullable=False),
    ),
    primary_key=("asof", "segment", "confidence_q"),
    note="q는 정책 선택이라 시뮬레이션이 값을 정해 주지 않는다. 이 원장은 "
         "선택이 자본과 충당금을 각각 얼마나 움직이는지만 보인다.",
)

PLGD_TABLES: dict[str, TableSpec] = {
    BEEL_CURVE.name: BEEL_CURVE,
    PLGD.name: PLGD,
    PLGD_SENSITIVITY.name: PLGD_SENSITIVITY,
}


# ---------------------------------------------------------------- 건별 BEEL

def beel_by_default(recovery: pd.DataFrame, *, discount_rate: float,
                    asof: str) -> pd.DataFrame:
    """부도건 × 경과월 단위 BEEL. 두 분모를 한 번에 만든다.

    경과월 ``k``에서 아직 부도상태인 건만 행을 만든다. 회수가 종결된 건은
    마지막 회수월에 부도상태를 벗어나므로 ``k < T_i``까지, 미종결 건은 기준일
    까지의 경과월 ``k <= months_since_default``까지 남는다.

    분자는 경과월 ``k`` 이후의 회수에서 비용을 뺀 값을 ``k`` 시점으로 할인한
    것이다. ``k`` 이전에 이미 받은 회수는 분자에서 빠지고, 분모가
    ``'잔여익스포저'``이면 분모에서도 빠진다. 두 분모의 차이가 정확히 그
    "이미 받은 회수"를 어떻게 볼 것인가의 차이다.

    미종결 건의 BEEL은 관측된 회수만으로 계산되므로 미래 회수를 0으로 본 값이
    된다. 그 사실을 ``workout_open``으로 남기고 평균에서는 빼며, 관측중단 포함
    평균을 따로 낸다.
    """
    if discount_rate is None or not np.isfinite(discount_rate):
        raise ValueError("discount_rate는 유한한 값이어야 한다")
    need = {"asof", "default_id", "segment", "ead_at_default",
            "recovery_years", "recovery_amount", "direct_cost",
            "indirect_cost", "workout_open", "months_since_default"}
    missing = need - set(recovery.columns)
    if missing:
        raise ValueError(f"crm_recovery_history에 없는 컬럼: {sorted(missing)}")
    r = recovery[recovery["asof"] == asof]
    cols = ["segment", "default_id", "months_since_default", "workout_open",
            "ead_at_default", "residual_exposure", "pv_future",
            "beel_부도시익스포저", "beel_잔여익스포저"]
    if r.empty:
        return pd.DataFrame(columns=cols)

    work = r.copy()
    work["_m"] = np.rint(
        pd.to_numeric(work["recovery_years"]).to_numpy() * 12.0).astype(int)
    work["_net"] = (pd.to_numeric(work["recovery_amount"]).to_numpy()
                    - pd.to_numeric(work["direct_cost"]).to_numpy()
                    - pd.to_numeric(work["indirect_cost"]).to_numpy())
    d = float(discount_rate)
    rows: list[tuple] = []
    for did, g in work.groupby("default_id", sort=True):
        ead = float(g["ead_at_default"].iloc[0])
        if not np.isfinite(ead) or ead <= 0.0:
            continue
        seg = str(g["segment"].iloc[0])
        is_open = bool(g["workout_open"].astype(bool).max())
        msd = int(g["months_since_default"].iloc[0])
        m = g["_m"].to_numpy()
        net = g["_net"].to_numpy()
        gross = pd.to_numeric(g["recovery_amount"]).to_numpy()
        horizon = int(m.max()) if not is_open else max(int(m.max()), msd)
        for k in range(0, horizon):
            future = m > k
            pv = float(np.sum(net[future] * (1.0 + d) ** (-(m[future] - k)
                                                          / 12.0)))
            residual = ead - float(gross[~future].sum())
            beel_ead = float(np.clip(1.0 - pv / ead, 0.0, 1.0))
            beel_res = (float(np.clip(1.0 - pv / residual, 0.0, 1.0))
                        if residual > 0.0 else np.nan)
            rows.append((seg, did, k, is_open, ead, residual, pv,
                         beel_ead, beel_res))
    return pd.DataFrame(rows, columns=cols)


# ---------------------------------------------------------------- 곡선

def _curve_stats(sub: pd.DataFrame, col: str, q: float | None) -> dict:
    """한 경과월 코호트의 요약. 회수종결 건만 통계에 넣는다."""
    closed = sub[~sub["workout_open"].astype(bool)]
    vals = pd.to_numeric(closed[col], errors="coerce").dropna().to_numpy()
    allv = pd.to_numeric(sub[col], errors="coerce").dropna().to_numpy()
    n = int(len(vals))
    out = {
        "n_defaults": n,
        "observation_censored": int(sub["workout_open"].astype(bool).sum()),
        "beel_mean": float(vals.mean()) if n else None,
        "beel_median": float(np.median(vals)) if n else None,
        "beel_std": float(vals.std(ddof=1)) if n >= 2 else None,
        "beel_q": None, "tail_observations": None,
        "beel_mean_incl_censored": (float(allv.mean()) if len(allv) else None),
    }
    if q is not None and n:
        out["beel_q"] = float(np.quantile(vals, q, method="linear"))
        out["tail_observations"] = int(np.floor(n * (1.0 - q)))
    if out["beel_mean"] is not None and out["beel_mean_incl_censored"] is not None:
        out["censoring_impact"] = float(out["beel_mean_incl_censored"]
                                        - out["beel_mean"])
    else:
        out["censoring_impact"] = None
    return out


def _monotonicity(months: np.ndarray, means: np.ndarray
                  ) -> tuple[str, float | None, float | None]:
    """경과월에 대한 BEEL 평균의 단조증가 여부.

    판정 기준은 스피어만 순위상관의 **부호**다. 임계값을 세우면 그 임계가 규정
    처럼 보이므로 두지 않고, 상관계수와 p값을 사실로 남긴다. 점이 4개 미만이면
    판정하지 않는다.
    """
    ok = np.isfinite(means)
    x, y = months[ok], means[ok]
    if len(x) < 4:
        return "판정불가", None, None
    rho, p = spearmanr(x, y)
    if not np.isfinite(rho):
        return "판정불가", None, None
    return ("단조증가" if rho > 0.0 else "단조증가아님"), float(rho), float(p)


def _segment_panels(recovery: pd.DataFrame, *, asof: str, rates: pd.DataFrame
                    ) -> dict[str, tuple[float | None, pd.DataFrame]]:
    """세그먼트별 (할인율, 건별 BEEL 패널).

    건별 BEEL은 신뢰수준과 무관하므로 한 번만 만든다. 민감도 산출이 q마다 이
    패널을 다시 만들면 같은 계산을 후보 수만큼 반복한다.
    """
    r = recovery[recovery["asof"] == asof]
    segments = sorted(set(r["segment"])) if not r.empty else []
    out: dict[str, tuple[float | None, pd.DataFrame]] = {}
    for seg in segments:
        try:
            rate = discount_rate_for(rates, asof=asof, segment=seg)
        except KeyError:
            rate = None
            warnings.warn(
                f"crm_lgd_discount_rate에 행이 없다 (segment={seg}). BEEL "
                "곡선을 만들지 않는다", ParamWarning, stacklevel=3)
        if rate is None:
            warnings.warn(
                f"회수 할인율이 없다 (segment={seg}). [별표 3] 184.는 값을 주지 "
                "않고 내부기준은 승인 전이다. BEEL 곡선 산출을 건너뛴다",
                ParamWarning, stacklevel=3)
            out[seg] = (None, pd.DataFrame())
            continue
        out[seg] = (rate, beel_by_default(r[r["segment"] == seg],
                                          discount_rate=rate, asof=asof))
    return out


def _curve_rows(panels: dict[str, tuple[float | None, pd.DataFrame]], *,
                asof: str, confidence_q: float | None) -> list[dict]:
    """패널에서 곡선 행을 만든다. 신뢰수준만 바꿔 여러 번 부를 수 있다."""
    rows: list[dict] = []
    for seg in sorted(panels):
        rate, per = panels[seg]
        if rate is None:
            for den in BEEL_DENOMINATORS:
                rows.append(_empty_curve_row(asof, seg, den))
            continue
        for den in BEEL_DENOMINATORS:
            col = f"beel_{den}"
            cells: list[dict] = []
            for k, sub in per.groupby("months_since_default", sort=True):
                st = _curve_stats(sub, col, confidence_q)
                st.update({
                    "months_since_default": int(k),
                    "ead_at_default_total": float(
                        sub["ead_at_default"].sum()),
                    "residual_exposure_total": float(
                        max(sub["residual_exposure"].sum(), 0.0)),
                })
                cells.append(st)
            verdict, rho, pval = _monotonicity(
                np.array([c["months_since_default"] for c in cells], float),
                np.array([np.nan if c["beel_mean"] is None else c["beel_mean"]
                          for c in cells], float))
            for c in cells:
                rows.append({
                    "asof": asof, "segment": seg, "beel_denominator": den,
                    "confidence_q": confidence_q,
                    "monotonicity_verdict": verdict,
                    "monotonicity_rho": rho, "monotonicity_pvalue": pval,
                    "is_applied_denominator": False,
                    "discount_rate": rate,
                    "citation": f"{_TEXTBOOK}. 조문 대응은 {_CLAUSE}",
                    "evidence_status": "추론",
                    "status": "산출완료", **c})
    return rows


def build_crm_beel_curve(recovery: pd.DataFrame, *, asof: str,
                         rates: pd.DataFrame,
                         confidence_q: float | None = None,
                         applied_denominator: str | None = None
                         ) -> pd.DataFrame:
    """세그먼트 × 분모구분 × 경과월 BEEL 곡선 원장.

    ``applied_denominator``를 주지 않으면 :func:`decide_beel_denominator`가
    단조성 판정으로 고른다. 두 곡선은 언제나 모두 산출되고, 적용 여부만
    ``is_applied_denominator``로 표시된다.
    """
    if confidence_q is not None and not (0.0 < confidence_q < 1.0):
        raise ValueError("confidence_q는 0과 1 사이여야 한다")
    if (applied_denominator is not None
            and applied_denominator not in BEEL_DENOMINATORS):
        raise ValueError(f"분모구분은 {BEEL_DENOMINATORS} 중 하나여야 한다")
    panels = _segment_panels(recovery, asof=asof, rates=rates)
    rows = _curve_rows(panels, asof=asof, confidence_q=confidence_q)
    out = pd.DataFrame(rows, columns=[c.name for c in BEEL_CURVE.columns])
    if out.empty:
        return cast_to_spec(out, BEEL_CURVE)
    chosen = applied_denominator
    if chosen is None:
        chosen = decide_beel_denominator(out)["denominator"]
    out["is_applied_denominator"] = out["beel_denominator"] == chosen
    return cast_to_spec(out, BEEL_CURVE)


def _empty_curve_row(asof: str, segment: str, denominator: str) -> dict:
    """할인율이 없어 산출하지 못한 세그먼트의 자리행."""
    return {
        "asof": asof, "segment": segment, "beel_denominator": denominator,
        "months_since_default": 0, "n_defaults": 0,
        "observation_censored": 0, "beel_mean": None, "beel_median": None,
        "beel_std": None, "beel_q": None, "confidence_q": None,
        "tail_observations": None, "beel_mean_incl_censored": None,
        "censoring_impact": None, "ead_at_default_total": None,
        "residual_exposure_total": None,
        "monotonicity_verdict": "판정불가", "monotonicity_rho": None,
        "monotonicity_pvalue": None, "is_applied_denominator": False,
        "discount_rate": None,
        "citation": f"{_TEXTBOOK}. 조문 대응은 {_CLAUSE}",
        "evidence_status": "추론", "status": "산출불가(할인율미승인)",
    }


# ---------------------------------------------------------------- 판정

def decide_beel_denominator(curve: pd.DataFrame) -> dict[str, object]:
    """분모 두 후보 중 어느 쪽이 단조증가 곡선을 만드는지로 고른다.

    신한 카드론 LGD 개선 종료보고(2022)가 "BEEL 그래프가 우상향의 일반 조건을
    만족한다"고 적는다. 실무는 BEEL이 부도 경과월에 대해 단조증가할 것을
    기대하고, 곡선이 꺾이면 회수데이터 누락을 의심한다. 그래서 단조성을 만드는
    분모를 고른다.

    세그먼트마다 판정이 갈리면 **단조증가 세그먼트가 더 많은 쪽**을 고르고, 그
    수까지 같으면 판정하지 않고 ``'판정불가'``를 돌려준다. 어느 쪽도 만족하지
    못하는 상태를 조용히 한쪽으로 밀면 판정 자체가 없어진다.
    """
    if curve.empty:
        return {"denominator": None, "verdict": "판정불가",
                "rationale": "곡선이 비어 있다", "detail": {}}
    detail: dict[str, dict] = {}
    for den in BEEL_DENOMINATORS:
        sub = curve[curve["beel_denominator"] == den]
        per_seg = (sub.groupby("segment")[
            ["monotonicity_verdict", "monotonicity_rho"]].first())
        detail[den] = {
            "n_monotone": int((per_seg["monotonicity_verdict"]
                               == "단조증가").sum()),
            "n_segments": int(len(per_seg)),
            "rho": {str(s): (None if pd.isna(v) else float(v))
                    for s, v in per_seg["monotonicity_rho"].items()},
        }
    a, b = BEEL_DENOMINATORS
    na, nb = detail[a]["n_monotone"], detail[b]["n_monotone"]
    if na == nb:
        return {"denominator": None, "verdict": "판정불가",
                "rationale": (f"두 분모 모두 단조증가 세그먼트가 {na}개로 같다. "
                              "단조성만으로는 갈리지 않는다"),
                "detail": detail}
    win = a if na > nb else b
    lose = b if na > nb else a
    return {
        "denominator": win, "verdict": "판정완료",
        "rationale": (
            f"단조증가 세그먼트가 '{win}' 분모에서 "
            f"{detail[win]['n_monotone']}/{detail[win]['n_segments']}개, "
            f"'{lose}' 분모에서 "
            f"{detail[lose]['n_monotone']}/{detail[lose]['n_segments']}개다. "
            "판정 기준은 경과월과 BEEL 평균의 스피어만 순위상관 부호이며 "
            "임계값을 세우지 않았다"),
        "detail": detail,
    }


def decide_dsf_form(curve: pd.DataFrame, *, confidence_q: float,
                    denominator: str) -> dict[str, object]:
    """DSF 반영이 승산인지 가산인지를 경과월에 걸친 안정성으로 고른다.

    교안은 "BEEL 추정치에 Downturn Scaling Factor를 반영"이라고만 적어 두 형태가
    모두 읽힌다. 경과월별로 BEEL 분포의 q분위수와 평균을 구한 뒤

        승산 가설  quantile / mean 이 경과월에 걸쳐 안정적인가
        가산 가설  quantile − mean 이 경과월에 걸쳐 안정적인가

    를 변동계수로 비교하고 작은 쪽을 택한다. 분위수가 1.0에 붙어 포화된 구간은
    두 지표가 모두 퇴화하므로 포화 구간을 뺀 값도 함께 돌려준다.
    """
    if not (0.0 < confidence_q < 1.0):
        raise ValueError("confidence_q는 0과 1 사이여야 한다")
    sub = curve[(curve["beel_denominator"] == denominator)
                & curve["beel_mean"].notna() & curve["beel_q"].notna()].copy()
    if sub.empty:
        return {"form": None, "verdict": "판정불가",
                "rationale": "분위수가 산출되지 않았다", "detail": {}}
    sub["_ratio"] = sub["beel_q"] / sub["beel_mean"].replace(0.0, np.nan)
    sub["_diff"] = sub["beel_q"] - sub["beel_mean"]
    sub["_saturated"] = sub["beel_q"] >= 1.0 - 1e-9
    detail: dict[str, dict] = {}
    votes = {"승산": 0, "가산": 0}
    for seg, g in sub.groupby("segment"):
        entry: dict[str, object] = {"n_months": int(len(g)),
                                    "n_saturated": int(g["_saturated"].sum())}
        for label, frame in (("전구간", g), ("비포화", g[~g["_saturated"]])):
            entry[f"cv_승산_{label}"] = _cv(frame["_ratio"])
            entry[f"cv_가산_{label}"] = _cv(frame["_diff"])
        cv_m, cv_a = entry["cv_승산_전구간"], entry["cv_가산_전구간"]
        if cv_m is not None and cv_a is not None:
            votes["승산" if cv_m < cv_a else "가산"] += 1
        detail[str(seg)] = entry
    if votes["승산"] == votes["가산"]:
        return {"form": None, "verdict": "판정불가",
                "rationale": (f"승산 {votes['승산']}개 세그먼트, 가산 "
                              f"{votes['가산']}개로 같다"),
                "detail": detail}
    form = "승산" if votes["승산"] > votes["가산"] else "가산"
    return {
        "form": form, "verdict": "판정완료",
        "rationale": (
            f"경과월에 걸친 변동계수가 작은 쪽이 '{form}'인 세그먼트가 "
            f"{votes[form]}/{len(detail)}개다. 신뢰수준 q={confidence_q:g}, "
            f"분모 '{denominator}' 기준이다"),
        "detail": detail,
    }


def _cv(s: pd.Series) -> float | None:
    """변동계수. 평균이 0에 붙거나 표본이 2 미만이면 판정하지 않는다."""
    v = pd.to_numeric(s, errors="coerce").dropna().to_numpy()
    if len(v) < 2:
        return None
    mean = float(v.mean())
    if abs(mean) < 1e-12:
        return None
    return float(v.std(ddof=1) / abs(mean))


# ---------------------------------------------------------------- 소요자본

def defaulted_capital_requirement(lgd_in_default: float | None,
                                  elbe: float | None) -> float | None:
    """부도자산의 소요자기자본율 K = max(0, LGD_in_default − ELBE).

    [별표 3] 120.가(2)에서 나온다. 주2)가 PD 100%일 때 N{x}를 1로 두므로
    ``LGD × N{...}``가 ``LGD``가 되고, 주4)가 EL을 185.바의 부도자산 예상손실로
    두며, 주1)이 0 미만을 0으로 자른다. 유효만기 조정은 여기서 곱하지 않는다.
    """
    if lgd_in_default is None or elbe is None:
        return None
    if not (np.isfinite(lgd_in_default) and np.isfinite(elbe)):
        return None
    return float(max(0.0, float(lgd_in_default) - float(elbe)))


# ---------------------------------------------------------------- PLGD 원장

def _open_positions(recovery: pd.DataFrame, *, asof: str) -> pd.DataFrame:
    """기준일에 부도상태인 건. 세그먼트·경과월·부도시 익스포저만 남긴다."""
    r = recovery[(recovery["asof"] == asof)
                 & recovery["workout_open"].astype(bool)]
    if r.empty:
        return pd.DataFrame(columns=["segment", "default_id",
                                     "months_since_default",
                                     "ead_at_default"])
    return (r.drop_duplicates("default_id")
            [["segment", "default_id", "months_since_default",
              "ead_at_default"]]
            .sort_values("default_id").reset_index(drop=True))


def _curve_lookup(curve: pd.DataFrame, *, segment: str, denominator: str
                  ) -> pd.DataFrame:
    c = curve[(curve["segment"] == segment)
              & (curve["beel_denominator"] == denominator)]
    return c.set_index("months_since_default")


def _map_positions(pos: pd.DataFrame, cur: pd.DataFrame, column: str
                   ) -> np.ndarray:
    """부도상태 건의 경과월을 곡선에 붙인다.

    경과월이 곡선 범위를 넘으면 가장 긴 경과월의 값을 쓴다. 관측이 없는 구간을
    외삽하는 것이므로 그 건수는 호출부가 표본부족으로 표시한다.
    """
    if cur.empty or column not in cur.columns:
        return np.full(len(pos), np.nan)
    idx = cur.index.to_numpy()
    vals = pd.to_numeric(cur[column], errors="coerce").to_numpy()
    ok = np.isfinite(vals)
    if not ok.any():
        return np.full(len(pos), np.nan)
    idx, vals = idx[ok], vals[ok]
    order = np.argsort(idx)
    idx, vals = idx[order], vals[order]
    k = pd.to_numeric(pos["months_since_default"]).to_numpy()
    pick = np.clip(np.searchsorted(idx, k, side="right") - 1, 0, len(idx) - 1)
    return vals[pick]


def build_crm_plgd(recovery: pd.DataFrame, curve: pd.DataFrame, *, asof: str,
                   denominator: str | None = None,
                   confidence_q: float | None = None,
                   approved_by: str | None = None,
                   approval_date: str | None = None,
                   provisions: pd.DataFrame | None = None,
                   method: str = "분포직접") -> pd.DataFrame:
    """부도자산 PLGD 원장 (185.바).

    ``confidence_q``는 승인 기록 없이 들어오지 못한다. 값만 넘기고 승인자를
    비우면 ``ValueError``다. 규정이 주지 않는 값이 승인 흔적 없이 산출에 들어가면
    화면에는 숫자가 보이는데 그 숫자를 결정한 사람이 없다.

    ``provisions``는 ``segment``·``specific_provision``·``partial_writeoff``를
    갖는 프레임이다. 없으면 185.바 후단 비교를 하지 않고 ``justification_required``
    를 NULL로 둔다. 비교 대상이 없는데 False로 두면 '입증이 필요 없음을
    확인했다'가 되어 판정하지 않은 것과 구분되지 않는다.
    """
    if method not in PLGD_METHODS:
        raise ValueError(f"method는 {PLGD_METHODS} 중 하나여야 한다")
    if confidence_q is not None:
        if not (0.0 < confidence_q < 1.0):
            raise ValueError("confidence_q는 0과 1 사이여야 한다")
        if not approved_by or not approval_date:
            raise ValueError(
                "confidence_q는 승인자·승인일 없이 넣을 수 없다. 규정이 주지 "
                "않는 값이므로 내부기준 승인이 효력 요건이다")
    if denominator is None:
        decision = decide_beel_denominator(curve)
        denominator = decision["denominator"]
    if denominator is None:
        raise ValueError("분모구분을 판정하지 못했다. denominator를 명시하라")
    if denominator not in BEEL_DENOMINATORS:
        raise ValueError(f"분모구분은 {BEEL_DENOMINATORS} 중 하나여야 한다")
    alt = [d for d in BEEL_DENOMINATORS if d != denominator][0]

    pos = _open_positions(recovery, asof=asof)
    prov = (provisions.set_index("segment")
            if provisions is not None and not provisions.empty else None)
    dsf_note = None
    if confidence_q is not None:
        form = decide_dsf_form(curve, confidence_q=confidence_q,
                               denominator=denominator)
        dsf_form, dsf_note = form["form"], form["rationale"]
    else:
        dsf_form = None

    segments = sorted(set(curve["segment"])) if not curve.empty else []
    rows: list[dict] = []
    for seg in segments:
        cur = _curve_lookup(curve, segment=seg, denominator=denominator)
        cur_alt = _curve_lookup(curve, segment=seg, denominator=alt)
        p = pos[pos["segment"] == seg]
        n_open = int(len(p))
        ead_open = float(p["ead_at_default"].sum()) if n_open else 0.0
        rate_missing = bool(
            (cur["status"] == "산출불가(할인율미승인)").any()) if len(cur) else True

        elbe = plgd = addon = dsf = k_req = None
        elbe_amt = elbe_amt_alt = None
        status = "산출완료"
        note_bits: list[str] = []
        if rate_missing:
            status = "산출불가(할인율미승인)"
        elif n_open == 0:
            status = "산출불가(표본없음)"
            note_bits.append("기준일에 부도상태인 건이 없다")
        else:
            beel_i = _map_positions(p, cur, "beel_mean")
            if np.isfinite(beel_i).any():
                elbe = float(np.nanmean(beel_i))
                elbe_amt = float(elbe * ead_open)
            alt_i = _map_positions(p, cur_alt, "beel_mean")
            if np.isfinite(alt_i).any():
                elbe_amt_alt = float(np.nanmean(alt_i) * ead_open)
            if confidence_q is None:
                status = "산출불가(신뢰수준미승인)"
                note_bits.append(
                    "교안은 '일정 신뢰수준'이라고만 적고 값을 주지 않는다. "
                    "승인 전이므로 PLGD를 계산하지 않는다")
            else:
                q_i = _map_positions(p, cur, "beel_q")
                if np.isfinite(q_i).any():
                    plgd = float(np.nanmean(q_i))
                    if elbe is not None:
                        addon = float(plgd - elbe)
                        k_req = defaulted_capital_requirement(plgd, elbe)
                        if dsf_form == "승산" and elbe > 0.0:
                            dsf = float(plgd / elbe)
                        elif dsf_form == "가산":
                            dsf = float(plgd - elbe)

        thin = bool(0 < n_open < 30)
        if thin:
            note_bits.append(
                f"부도상태 건이 {n_open}건이라 분위수 추정이 불안정하다")
            if status == "산출완료":
                status = "산출완료(표본부족)"

        sp = wo = shortfall = None
        required = None
        if prov is not None and seg in prov.index:
            sp = float(prov.loc[seg, "specific_provision"])
            wo = float(prov.loc[seg, "partial_writeoff"])
            if elbe_amt is not None:
                shortfall = float(sp + wo - elbe_amt)
                required = bool(shortfall > 0.0)

        rows.append({
            "asof": asof, "segment": seg, "n_defaulted_open": n_open,
            "ead_at_default_open": (ead_open if n_open else None),
            "beel_denominator": denominator,
            "elbe": elbe, "plgd": plgd, "unexpected_loss_addon": addon,
            "lgd_in_default": plgd,
            "lgd_in_default_basis": (
                "185.바가 요구하는 것은 ELBE에 예상외 손실 가능성을 추가 반영한 "
                "값이고 그것이 부도자산에 적용되는 LGD다. 그래서 "
                "LGD in-default = PLGD로 읽었다. 이 대응을 명시한 문장은 어느 "
                "자료에도 없고 조문 구조와 교안 문장의 대응으로 세운 추론이다"),
            "dsf": dsf, "dsf_form": dsf_form, "dsf_form_basis": dsf_note,
            "confidence_q": confidence_q,
            "confidence_q_status": ("승인" if confidence_q is not None
                                    else "미승인"),
            "method": (method if plgd is not None else "미산출"),
            "capital_requirement_k": k_req,
            "maturity_adjustment_applied": False,
            "elbe_amount": elbe_amt,
            "elbe_amount_alt_denominator": elbe_amt_alt,
            "specific_provision": sp, "partial_writeoff": wo,
            "shortfall": shortfall, "justification_required": required,
            "justification_ref": None,
            "insufficient_sample": thin,
            "citation": f"{_CLAUSE}. {_TEXTBOOK}",
            "evidence_status": "추론",
            "approved_by": approved_by, "approval_date": approval_date,
            "status": status,
            "note": ("; ".join(note_bits) if note_bits else None),
        })
    return cast_to_spec(pd.DataFrame(
        rows, columns=[c.name for c in PLGD.columns]), PLGD)


# ---------------------------------------------------------------- 민감도

def build_crm_plgd_sensitivity(recovery: pd.DataFrame, *, asof: str,
                               rates: pd.DataFrame,
                               denominator: str,
                               q_grid: tuple[float, ...] = SENSITIVITY_Q_GRID
                               ) -> pd.DataFrame:
    """후보 신뢰수준별 PLGD·RWA·충당금 민감도.

    q는 정책 선택이고 시뮬레이션이 값을 정해 주지 않는다. 이 원장은 선택이
    자본을 얼마나 움직이는지, 충당금을 얼마나 움직이는지를 나란히 보인다.

    **충당금은 q에 반응하지 않는다.** 120.가(2) 주4)가 부도자산의 EL을 185.바의
    예상손실 최적추정치로 정하므로 q가 바뀌어도 EL은 ELBE 그대로이고, 움직이는
    것은 ``max(0, PLGD − ELBE)``인 소요자기자본율뿐이다. 이 원장이 그 사실을
    수치로 보인다.
    """
    if not q_grid:
        raise ValueError("q_grid가 비어 있다")
    for q in q_grid:
        if not (0.0 < q < 1.0):
            raise ValueError(f"신뢰수준 후보가 0과 1 사이가 아니다: {q}")
    grid = tuple(sorted(set(float(q) for q in q_grid)))
    pos = _open_positions(recovery, asof=asof)
    panels = _segment_panels(recovery, asof=asof, rates=rates)
    curves: dict[float, pd.DataFrame] = {}
    for q in grid:
        curves[q] = pd.DataFrame(
            _curve_rows(panels, asof=asof, confidence_q=q),
            columns=[c.name for c in BEEL_CURVE.columns])
    segments = sorted(panels)

    rows: list[dict] = []
    for seg in segments:
        p = pos[pos["segment"] == seg]
        n_open = int(len(p))
        ead_open = float(p["ead_at_default"].sum()) if n_open else 0.0
        base_rwa = base_prov = None
        for q in grid:
            cur = _curve_lookup(curves[q], segment=seg,
                                denominator=denominator)
            elbe = plgd = addon = k_req = rwa = prov = None
            tail = None
            status = "산출완료"
            if n_open == 0:
                status = "산출불가(표본없음)"
            else:
                beel_i = _map_positions(p, cur, "beel_mean")
                q_i = _map_positions(p, cur, "beel_q")
                if np.isfinite(beel_i).any():
                    elbe = float(np.nanmean(beel_i))
                    prov = float(elbe * ead_open)
                if np.isfinite(q_i).any():
                    plgd = float(np.nanmean(q_i))
                if elbe is not None and plgd is not None:
                    addon = float(plgd - elbe)
                    k_req = defaulted_capital_requirement(plgd, elbe)
                    rwa = float(k_req * _RWA_MULTIPLIER * ead_open)
                # 꼬리 표본수는 부도상태 건이 실제로 올라타는 경과월 칸에서만
                # 센다. 곡선 전체의 최소값을 쓰면 산출에 쓰이지도 않는 맨 끝
                # 칸 하나가 지표를 지배한다.
                used = _map_positions(p, cur, "tail_observations")
                if np.isfinite(used).any():
                    tail = int(np.nanmin(used))
                if elbe is None or plgd is None:
                    status = "산출불가(할인율미승인)"
            if base_rwa is None and rwa is not None:
                base_rwa = rwa
            if base_prov is None and prov is not None:
                base_prov = prov
            rows.append({
                "asof": asof, "segment": seg, "confidence_q": q,
                "n_defaulted_open": n_open,
                "ead_at_default_open": (ead_open if n_open else None),
                "elbe": elbe, "plgd": plgd, "unexpected_loss_addon": addon,
                "capital_requirement_k": k_req, "rwa": rwa,
                "rwa_multiplier": _RWA_MULTIPLIER,
                "rwa_delta_vs_lowest_q": (
                    None if (rwa is None or base_rwa is None)
                    else float(rwa - base_rwa)),
                "provision_requirement": prov,
                "provision_delta_vs_lowest_q": (
                    None if (prov is None or base_prov is None)
                    else float(prov - base_prov)),
                "min_tail_observations": tail,
                "provision_basis": (
                    "충당금 소요 = ELBE × 부도상태 익스포저. 120.가(2) 주4)가 "
                    "부도자산 EL을 185.바의 최적추정치로 정하므로 신뢰수준 q는 "
                    "이 값을 움직이지 않는다"),
                "citation": f"{_K_CITE}. {_RWA_CITE}",
                "status": status,
            })
    return cast_to_spec(pd.DataFrame(
        rows, columns=[c.name for c in PLGD_SENSITIVITY.columns]),
        PLGD_SENSITIVITY)


# ---------------------------------------------------------------- 검사

def _pass(report, name, detail, metric=0.0):
    from risk_lib.validation.consistency import ConsistencyCheck
    report.add(ConsistencyCheck(name, "PASS", detail, metric=float(metric)))


def _fail(report, name, detail, metric):
    from risk_lib.validation.consistency import ConsistencyCheck
    report.add(ConsistencyCheck(name, "FAIL", detail, metric=float(metric)))


def _warn(report, name, detail, metric=0.0):
    from risk_lib.validation.consistency import ConsistencyCheck
    report.add(ConsistencyCheck(name, "WARN", detail, metric=float(metric)))


def check_plgd_not_below_elbe(plgd: pd.DataFrame, report) -> None:
    """PLGD가 ELBE보다 작은 행 (185.바 후단).

    FAIL 조건: ``plgd``와 ``elbe``가 모두 있는데 ``plgd < elbe``일 때. 조문은
    최적추정치에 예상외 손실을 **추가로** 반영하라고 요구하므로 추가분이 음수인
    상태는 조문 위반이다. 분위수를 평균보다 낮은 쪽에서 잡거나 DSF를 1 미만으로
    두면 이 위반이 난다.
    """
    if plgd.empty:
        # 조용히 사라지면 "검사를 통과했다" 와 "검사가 아예 없었다" 가 산출물에서
        # 구분되지 않는다. 원장이 비는 것은 정상 경로(분모 판정불가·q 미승인)일
        # 수 있으나 그 사실은 남아야 한다.
        _warn(report, "PLGD 예상외손실 추가분 부호",
              "PLGD 원장이 비어 판정하지 않았다 (분모 판정불가 또는 q 미승인)")
        return
    d = plgd.dropna(subset=["plgd", "elbe"])
    if d.empty:
        _warn(report, "PLGD 예상외손실 추가분 부호",
              "PLGD가 산출된 행이 없어 판정하지 않았다")
        return
    bad = d[d["plgd"] < d["elbe"] - 1e-12]
    if len(bad):
        _fail(report, "PLGD 예상외손실 추가분 부호",
              f"PLGD가 ELBE보다 작은 세그먼트 {len(bad)}건: "
              f"{sorted(set(bad['segment']))}", len(bad))
        return
    _pass(report, "PLGD 예상외손실 추가분 부호",
          f"{len(d)}건 전건에서 PLGD ≥ ELBE", len(d))


def check_plgd_provision_justification(plgd: pd.DataFrame, report) -> None:
    """ELBE가 개별충당금+부분상각보다 작을 때 입증 문서가 있는지 (185.바 후단).

    FAIL 조건: ``justification_required=True``인데 ``justification_ref``가
    비어 있을 때. 비대칭 규칙이라 반대 방향(ELBE가 더 큼)에는 입증책임이 없고,
    양방향으로 검사를 걸면 정상 건에 거짓 경보가 난다.
    """
    if plgd.empty:
        _warn(report, "PLGD 부도자산 ELBE 대 충당금",
              "PLGD 원장이 비어 판정하지 않았다 (분모 판정불가 또는 q 미승인)")
        return
    need = plgd[plgd["justification_required"] == True]      # noqa: E712
    missing = need[need["justification_ref"].isna()]
    if len(missing):
        _fail(report, "PLGD 부도자산 ELBE 대 충당금",
              f"ELBE가 개별충당금+부분상각보다 작은데 입증 문서가 없다 "
              f"{len(missing)}건: {sorted(set(missing['segment']))}",
              len(missing))
        return
    n_undecided = int(plgd["justification_required"].isna().sum())
    _pass(report, "PLGD 부도자산 ELBE 대 충당금",
          f"입증 필요 {len(need)}건 전건 문서 있음, 충당금 자료 없어 미판정 "
          f"{n_undecided}건", n_undecided)


def check_beel_monotonicity(curve: pd.DataFrame, report) -> None:
    """적용 분모의 BEEL 곡선이 경과월에 대해 단조증가인지.

    WARN 조건: 적용 분모 곡선의 단조성 판정이 ``'단조증가아님'``인 세그먼트가
    있을 때. 신한 프로젝트에서 우상향이 깨진 원인은 상각 부도·연체 정보 누락
    이었다. 즉 이 검사는 데이터 품질 신호이며, 곡선을 강제로 단조화하라는 뜻이
    아니라서 FAIL이 아니라 WARN이다.
    """
    if curve.empty:
        return
    applied = curve[curve["is_applied_denominator"].astype(bool)]
    if applied.empty:
        _warn(report, "BEEL 곡선 단조성", "적용 분모가 지정되지 않았다")
        return
    per_seg = applied.groupby("segment")["monotonicity_verdict"].first()
    broken = sorted(per_seg.index[per_seg == "단조증가아님"])
    undecided = sorted(per_seg.index[per_seg == "판정불가"])
    if broken:
        _warn(report, "BEEL 곡선 단조성",
              f"적용 분모 곡선이 우상향하지 않는 세그먼트 {len(broken)}건: "
              f"{broken}. 회수데이터 누락을 점검하라", len(broken))
        return
    _pass(report, "BEEL 곡선 단조성",
          f"{int((per_seg == '단조증가').sum())}개 세그먼트 우상향, 미판정 "
          f"{len(undecided)}개", len(undecided))


def run_plgd_checks(ledgers: dict[str, pd.DataFrame], *, report=None):
    """PLGD 원장 묶음에 대한 자체 정합성 검사 일괄 실행."""
    from risk_lib.validation.consistency import ValidationReport
    rep = report or ValidationReport()
    curve = ledgers.get(BEEL_CURVE.name, pd.DataFrame())
    plgd = ledgers.get(PLGD.name, pd.DataFrame())
    check_beel_monotonicity(curve, rep)
    check_plgd_not_below_elbe(plgd, rep)
    check_plgd_provision_justification(plgd, rep)
    return rep


# ---------------------------------------------------------------- 묶음

def build_plgd_ledgers(recovery: pd.DataFrame, *, asof: str,
                       rates: pd.DataFrame,
                       confidence_q: float | None = None,
                       approved_by: str | None = None,
                       approval_date: str | None = None,
                       provisions: pd.DataFrame | None = None,
                       q_grid: tuple[float, ...] = SENSITIVITY_Q_GRID
                       ) -> dict[str, pd.DataFrame]:
    """PLGD 원장 석 장을 한 번에 만든다.

    분모구분은 :func:`decide_beel_denominator`가 관측 데이터로 판정하고, 판정이
    갈리지 않으면 민감도 원장을 만들지 않는다. 어느 쪽인지 정하지 못한 상태를
    한쪽으로 밀지 않는다.
    """
    curve = build_crm_beel_curve(recovery, asof=asof, rates=rates,
                                 confidence_q=confidence_q)
    decision = decide_beel_denominator(curve)
    den = decision["denominator"]
    plgd = (build_crm_plgd(recovery, curve, asof=asof, denominator=den,
                           confidence_q=confidence_q, approved_by=approved_by,
                           approval_date=approval_date, provisions=provisions)
            if den is not None
            else cast_to_spec(pd.DataFrame(
                columns=[c.name for c in PLGD.columns]), PLGD))
    sens = (build_crm_plgd_sensitivity(recovery, asof=asof, rates=rates,
                                       denominator=den, q_grid=q_grid)
            if den is not None
            else cast_to_spec(pd.DataFrame(
                columns=[c.name for c in PLGD_SENSITIVITY.columns]),
                PLGD_SENSITIVITY))
    return {BEEL_CURVE.name: curve, PLGD.name: plgd,
            PLGD_SENSITIVITY.name: sens}
