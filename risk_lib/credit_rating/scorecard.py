"""스코어카드 엔진과 원장 (BNK-CRM-004·006·007·008).

**무엇이 없었나.** `models/pd_model.py`는 원시 변수에 로지스틱을 적합해 PD를
바로 낸다. 그 구조로는 [별표 3] 153.라("제3자가 등급부여 절차를 재현하여 동일하게
적용할 수 있을 정도로 명확하고 상세하게")를 만족하는 배점표가 나오지 않고,
기업평가모형의 재무·비재무·대표자 축 결합(BNK-CRM-006·007·008)도 표현되지
않는다. 계수 하나가 원시 단위에 걸려 있을 뿐이라 구간별 점수가 없다.

**이 모듈이 만드는 것은 두 단계다.**

  1단계 축별 배점. 변수를 구간(bin)으로 나누고 구간별 WOE를 계산해, 축(재무·
  비재무·대표자)마다 로지스틱을 적합한다. 구간·WOE·배점이 `crm_scorecard_bin`에
  행으로 남으므로 차주 한 명의 점수를 손으로 재계산할 수 있다.

  2단계 축 결합. 축 점수에 다시 로지스틱을 적합해 결합 PD를 낸다. 결합
  가중치(`crm_scorecard_axis.weight`)는 이 적합의 결과다. 규정도 1차자료도
  재무·비재무 가중을 주지 않으므로 표본에서 추정하며, 표본이 바뀌면 가중도
  반드시 움직인다.

**모수는 원장에서 온다.** 구간 수·최소 구간비중·배점 스케일(base_points·PDO·
base_odds)·WOE 평활은 규정이 정하지 않는 모형 설계 선택이다. 엔진 본문에 숫자로
두지 않고 `crm_scorecard_param` 원장에서 읽으며, 그 행들은
`evidence_status='재량·미규정'`이고 `approval_status='미승인'`이다. 승인 상태는
차주 점수 원장(`crm_obligor_score.param_approval`)까지 따라가므로, 미승인 모수로
산출된 등급이 승인된 것처럼 읽히지 않는다.

**배점 스케일은 순위를 바꾸지 않는다.** points = base_points + factor·(WOE·계수)
형태의 선형 변환이므로 PD와 등급은 스케일 모수와 무관하다. 스케일은 표시
단위일 뿐이라는 사실을 `crm_scorecard_param.rationale`에 적는다.

**미등재.** TableSpec은 배선 단계에서 카탈로그에 등재한다.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from risk_lib.credit_rating.requirements import EVIDENCE_STATUS
from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec
from risk_lib.models.rating import DEFAULT_MASTER_SCALE, pd_to_rating

__all__ = [
    "AXES", "APPROVAL_STATUS", "PARAM_NAMES", "QUAL_AXES",
    "SCORECARD_PARAM", "SCORECARD_BIN", "SCORECARD_FACTOR", "SCORECARD_AXIS",
    "QUALITATIVE_ITEM", "QUALITATIVE_ASSESSMENT",
    "OBLIGOR_AXIS_SCORE", "OBLIGOR_SCORE", "SCORECARD_TABLES",
    "ScorecardFit", "build_scorecard_param", "build_qualitative_items",
    "build_qualitative_assessment", "fit_scorecard", "score_obligors",
    "non_default_grades",
]

# 축은 기업평가모형의 결합 구조다. 재무·비재무·대표자는 국내 은행 기업신용평가의
# 통상 구성이며 [별표 3]이 축을 열거하지는 않는다.
AXES: tuple[str, ...] = ("재무", "비재무", "대표자")
APPROVAL_STATUS: tuple[str, ...] = ("승인", "미승인")
PARAM_NAMES: tuple[str, ...] = (
    "n_bins", "min_bin_share", "woe_smoothing", "base_points", "pdo",
    "base_odds")
QUAL_AXES: tuple[str, ...] = ("비재무", "대표자")


# ---------------------------------------------------------------- 스펙

SCORECARD_PARAM = TableSpec(
    name="crm_scorecard_param", korean="스코어카드 설계 모수", product="PRD-CRM",
    grain="모형 × 모수 1행",
    columns=(
        C("model_id", "string", "모형 식별자", nullable=False),
        C("parameter", "string", "모수", nullable=False, allowed=PARAM_NAMES),
        C("value", "float", "값", nullable=True, unit="mixed",
          note="구간 수는 count, 최소 구간비중은 ratio, 배점 모수는 points다. "
               "단위가 모수마다 다르므로 unit 컬럼을 따로 둔다"),
        C("value_unit", "string", "값 단위", nullable=False,
          allowed=("count", "ratio", "points", "odds")),
        C("approval_status", "string", "승인 상태", nullable=False,
          allowed=APPROVAL_STATUS),
        C("approved_by", "text", "승인자", nullable=True,
          note="승인 원장이 없으면 NULL이다. NULL인 모수로 산출한 등급은 "
               "산출 원장에 미승인으로 표시된다"),
        C("rationale", "text", "선택 근거", nullable=False),
        C("citation", "text", "근거", nullable=False),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("model_id", "parameter"),
    foreign_keys=(FK(("model_id",), "crm_model", ("model_id",)),),
    note="규정이 정하지 않는 모형 설계 선택을 모으는 곳. 엔진 함수 본문과 "
         "기본값에는 이 숫자들이 없다.",
)

SCORECARD_BIN = TableSpec(
    name="crm_scorecard_bin", korean="스코어카드 구간·배점", product="PRD-CRM",
    grain="모형 × 변수 × 구간 1행",
    columns=(
        C("model_id", "string", "모형 식별자", nullable=False),
        C("factor", "string", "변수", nullable=False),
        C("bin_seq", "int", "구간 순서", nullable=False, min_value=1),
        C("lower", "float", "구간 하한", nullable=True, unit="mixed",
          note="첫 구간의 하한은 −inf이므로 NULL로 둔다"),
        C("upper", "float", "구간 상한", nullable=True, unit="mixed"),
        C("n_obs", "int", "구간 관측수", nullable=False, min_value=0),
        C("n_default", "int", "구간 부도수", nullable=False, min_value=0),
        C("share", "float", "구간 비중", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("default_rate", "float", "구간 부도율", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("woe", "float", "WOE", nullable=False, unit="log_odds",
          citation="WOE = ln(정상비중 / 부도비중)"),
        C("iv_contrib", "float", "IV 기여", nullable=False, unit="ratio",
          min_value=0.0, citation="IV = Σ(정상비중 − 부도비중)·WOE"),
        C("points", "float", "배점", nullable=False, unit="points",
          note="배점 스케일은 선형 변환이므로 PD·등급을 바꾸지 않는다"),
    ),
    primary_key=("model_id", "factor", "bin_seq"),
    foreign_keys=(FK(("model_id",), "crm_model", ("model_id",)),),
    note="153.라(제3자 재현 가능성)의 증적. 구간과 배점이 행으로 있어야 차주 "
         "한 명의 점수를 손으로 다시 계산할 수 있다.",
)

SCORECARD_FACTOR = TableSpec(
    name="crm_scorecard_factor", korean="스코어카드 변수", product="PRD-CRM",
    grain="모형 × 변수 1행",
    columns=(
        C("model_id", "string", "모형 식별자", nullable=False),
        C("factor", "string", "변수", nullable=False),
        C("korean", "text", "변수명", nullable=False),
        C("axis", "string", "축", nullable=False, allowed=AXES),
        C("coefficient", "float", "WOE 계수", nullable=False, unit="log_odds"),
        C("iv", "float", "정보값(IV)", nullable=False, unit="ratio",
          min_value=0.0),
        C("n_bins", "int", "구간 수", nullable=False, min_value=1),
        C("monotonic", "bool", "구간 부도율 단조", nullable=False,
          note="단조가 아니면 구간 순서와 리스크 방향이 어긋난다는 신호다. "
               "158.(1)의 예측력·편의 점검에서 먼저 보는 항목"),
        C("sign_expected", "string", "예상 방향", nullable=False,
          allowed=("증가", "감소", "미정")),
        C("sign_observed", "string", "관측 방향", nullable=False,
          allowed=("증가", "감소", "혼재")),
        C("sign_agrees", "bool", "방향 일치", nullable=False,
          note="예상 방향이 '미정'이면 True로 두지 않고 별도로 본다"),
    ),
    primary_key=("model_id", "factor"),
    foreign_keys=(FK(("model_id",), "crm_model", ("model_id",)),),
    note="158.(1)·160.(통계모형 문서화)의 증적.",
)

SCORECARD_AXIS = TableSpec(
    name="crm_scorecard_axis", korean="스코어카드 축 결합", product="PRD-CRM",
    grain="모형 × 축 1행",
    columns=(
        C("model_id", "string", "모형 식별자", nullable=False),
        C("axis", "string", "축", nullable=False, allowed=AXES),
        C("n_factors", "int", "변수 수", nullable=False, min_value=0),
        C("weight", "float", "결합 가중", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0,
          note="축 로지스틱 계수의 절대값 정규화. 외부에서 가져온 정책 가중이 "
               "아니라 표본에서 추정한 값이다"),
        C("coefficient", "float", "결합 로지스틱 계수", nullable=False,
          unit="log_odds"),
        C("score_mean", "float", "축 점수 평균", nullable=False, unit="points"),
        C("score_std", "float", "축 점수 표준편차", nullable=False, unit="points",
          min_value=0.0),
        C("basis", "text", "산출 근거", nullable=False),
    ),
    primary_key=("model_id", "axis"),
    foreign_keys=(FK(("model_id",), "crm_model", ("model_id",)),),
    note="BNK-CRM-008 결합. 가중이 적합 결과이므로 표본이 바뀌면 반드시 움직인다.",
)

QUALITATIVE_ITEM = TableSpec(
    name="crm_qualitative_item", korean="비재무·대표자 평가항목",
    product="PRD-CRM",
    grain="평가항목 1개당 1행",
    columns=(
        C("item_code", "string", "항목코드", nullable=False),
        C("korean", "text", "항목명", nullable=False),
        C("axis", "string", "축", nullable=False, allowed=QUAL_AXES),
        C("definition", "text", "평가기준", nullable=False,
          note="153.가는 등급 부여 기준·절차를 갖출 것을 요구한다. 항목 정의가 "
               "없으면 평가자마다 다른 척도를 쓴다"),
        C("scale_min", "int", "척도 하한", nullable=False, min_value=1),
        C("scale_max", "int", "척도 상한", nullable=False, min_value=1),
        C("direction", "string", "척도 방향", nullable=False,
          allowed=("높을수록 위험", "낮을수록 위험")),
        C("citation", "text", "근거", nullable=False),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("item_code",),
    note="항목을 갖출 의무는 [별표 3] 153.가로 원문확인이고, 항목 구성과 척도는 "
         "은행 내부기준이라 규정이 정하지 않는다.",
)

QUALITATIVE_ASSESSMENT = TableSpec(
    name="crm_qualitative_assessment", korean="비재무·대표자 평가",
    product="PRD-CRM",
    grain="차주 × 기준일 × 평가항목 1행",
    columns=(
        C("obligor_id", "string", "차주 식별자", nullable=False),
        C("asof", "date", "기준일", nullable=False),
        C("item_code", "string", "항목코드", nullable=False),
        C("score", "int", "평가점수", nullable=False, min_value=1),
        C("assessor", "text", "평가자", nullable=False),
        C("recorded_by", "string", "기록 출처", nullable=False,
          allowed=("synthetic", "manual", "workflow"),
          note="synthetic은 이 하네스가 만든 값이며 실제 평가 기록이 아니다"),
    ),
    primary_key=("obligor_id", "asof", "item_code"),
    foreign_keys=(FK(("obligor_id",), "rdm_obligor", ("obligor_id",)),
                  FK(("item_code",), "crm_qualitative_item", ("item_code",))),
)

OBLIGOR_AXIS_SCORE = TableSpec(
    name="crm_obligor_axis_score", korean="차주 축별 점수", product="PRD-CRM",
    grain="차주 × 기준일 × 축 1행",
    columns=(
        C("obligor_id", "string", "차주 식별자", nullable=False),
        C("asof", "date", "기준일", nullable=False),
        C("model_id", "string", "모형 식별자", nullable=False),
        C("axis", "string", "축", nullable=False, allowed=AXES),
        C("score", "float", "축 점수", nullable=False, unit="points"),
        C("n_factors", "int", "반영 변수 수", nullable=False, min_value=0),
    ),
    primary_key=("obligor_id", "asof", "axis"),
    foreign_keys=(FK(("obligor_id",), "rdm_obligor", ("obligor_id",)),
                  FK(("model_id",), "crm_model", ("model_id",))),
    note="결합 전 축 점수를 남기지 않으면 어느 축에서 등급이 결정됐는지 사후에 "
         "볼 수 없다.",
)

OBLIGOR_SCORE = TableSpec(
    name="crm_obligor_score", korean="차주 결합점수·모형등급", product="PRD-CRM",
    grain="차주 × 기준일 1행",
    columns=(
        C("obligor_id", "string", "차주 식별자", nullable=False),
        C("asof", "date", "기준일", nullable=False),
        C("model_id", "string", "모형 식별자", nullable=False),
        C("total_score", "float", "결합점수", nullable=False, unit="points"),
        C("model_pd", "float", "모형 PD", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0),
        C("model_grade", "string", "모형등급", nullable=False,
          citation="master scale 17등급 매핑"),
        C("n_axes", "int", "결합 축 수", nullable=False, min_value=1),
        C("param_approval", "string", "설계모수 승인 상태", nullable=False,
          allowed=APPROVAL_STATUS,
          note="스코어카드 설계모수 중 하나라도 미승인이면 미승인이다"),
    ),
    primary_key=("obligor_id", "asof"),
    foreign_keys=(FK(("obligor_id",), "rdm_obligor", ("obligor_id",)),
                  FK(("model_id",), "crm_model", ("model_id",))),
    note="등급변경(override) 전의 모형등급. 최종등급은 crm_override에서 나온다.",
)

SCORECARD_TABLES = (SCORECARD_PARAM, SCORECARD_BIN, SCORECARD_FACTOR,
                    SCORECARD_AXIS, QUALITATIVE_ITEM, QUALITATIVE_ASSESSMENT,
                    OBLIGOR_AXIS_SCORE, OBLIGOR_SCORE)


# ---------------------------------------------------------------- 모수 빌더

# (모수, 값, 단위, 선택 근거)
_PARAMS: tuple[tuple[str, float, str, str], ...] = (
    ("n_bins", 5.0, "count",
     "구간이 적으면 리스크 차별화가 죽고 많으면 구간별 표본이 얇아진다. "
     "규정은 구간 수를 정하지 않는다"),
    ("min_bin_share", 0.05, "ratio",
     "구간 비중이 이보다 작으면 인접 구간에 병합한다. 얇은 구간의 WOE는 "
     "표본오차가 지배한다"),
    ("woe_smoothing", 0.5, "count",
     "구간 부도수가 0이면 WOE가 발산한다. 분자·분모에 더하는 평활 상수"),
    ("base_points", 600.0, "points",
     "배점 원점. 선형 변환이므로 PD·등급을 바꾸지 않는다"),
    ("pdo", 20.0, "points",
     "odds가 두 배가 되는 점수 폭(points to double the odds). 표시 척도"),
    ("base_odds", 50.0, "odds",
     "base_points에 대응하는 정상:부도 승산. 표시 척도"),
)


def build_scorecard_param(model_id: str) -> pd.DataFrame:
    """스코어카드 설계 모수 원장.

    이 값들은 규정이 정하지 않는 모형 설계 선택이므로 근거 상태가
    '재량·미규정'이고, 이 하네스에는 모형 승인 원장이 없으므로 승인 상태는
    '미승인'이다. 승인자 칸은 비운다.
    """
    rows = [{
        "model_id": model_id,
        "parameter": name,
        "value": float(value),
        "value_unit": unit,
        "approval_status": "미승인",
        "approved_by": None,
        "rationale": rationale,
        "citation": "[별표 3] 158.·160. 모형 요건. 설계 모수 값은 규정 미규정",
        "evidence_status": "재량·미규정",
    } for name, value, unit, rationale in _PARAMS]
    return pd.DataFrame(rows, columns=SCORECARD_PARAM.column_names)


def _param(params: pd.DataFrame, name: str) -> float:
    hit = params[params["parameter"] == name]
    if hit.empty or pd.isna(hit.iloc[0]["value"]):
        raise ValueError(f"스코어카드 모수 {name} 이 원장에 없다. 엔진은 "
                         f"기본값을 쓰지 않는다")
    return float(hit.iloc[0]["value"])


# ---------------------------------------------------------------- 비재무·대표자

# (항목코드, 항목명, 축, 평가기준)
_QUAL_ITEMS: tuple[tuple[str, str, str, str], ...] = (
    ("QL-IND", "산업 전망", "비재무",
     "영위 업종의 향후 1년 수급·규제 환경. 1 매우 우호 ~ 5 매우 비우호"),
    ("QL-POS", "시장 지위", "비재무",
     "주요 시장 점유율과 교섭력. 1 선도 ~ 5 열위"),
    ("QL-GOV", "경영 투명성", "비재무",
     "회계 신뢰성·공시 성실성·내부통제. 1 우수 ~ 5 미흡"),
    ("QL-LAB", "노사 관계", "비재무",
     "쟁의 이력과 인력 이탈. 1 안정 ~ 5 불안정"),
    ("QL-CEO-EXP", "대표자 경력", "대표자",
     "동종업 경력과 경영 성과 이력. 1 충분 ~ 5 부족"),
    ("QL-CEO-CR", "대표자 신용도", "대표자",
     "대표자 개인 신용 상태와 보증 이력. 1 양호 ~ 5 불량"),
)
_QUAL_SCALE_MIN = 1
_QUAL_SCALE_MAX = 5


def build_qualitative_items() -> pd.DataFrame:
    """비재무·대표자 평가항목 정의 원장 (153.가)."""
    rows = [{
        "item_code": code,
        "korean": korean,
        "axis": axis,
        "definition": definition,
        "scale_min": _QUAL_SCALE_MIN,
        "scale_max": _QUAL_SCALE_MAX,
        "direction": "높을수록 위험",
        "citation": "[별표 3] 153.가 (기준 보유 의무는 원문확인, "
                    "항목 구성·척도는 내부기준)",
        "evidence_status": "재량·미규정",
    } for code, korean, axis, definition in _QUAL_ITEMS]
    return pd.DataFrame(rows, columns=QUALITATIVE_ITEM.column_names)


def build_qualitative_assessment(obligors: pd.DataFrame, items: pd.DataFrame, *,
                                 asof: str, seed: int) -> pd.DataFrame:
    """차주별 비재무·대표자 평가 원장(합성).

    실제 은행은 심사역이 입력한다. 이 하네스에는 그 입력 화면이 없으므로
    차주의 부도위험 순위에 잡음을 섞은 순서통계로 만들고 `recorded_by='synthetic'`
    을 남긴다. 평가가 순수 잡음이면 비재무 축이 결합에서 0 가중을 받아
    BNK-CRM-007을 만든 의미가 사라지고, 완전 상관이면 재무 축과 구분되지 않는다.
    """
    if obligors.empty or items.empty:
        return pd.DataFrame(columns=QUALITATIVE_ASSESSMENT.column_names)
    rng = np.random.default_rng(seed + 8200)
    base = pd.to_numeric(obligors["pd"], errors="coerce").fillna(0.01).to_numpy()
    # 부도위험 로그오즈를 잠재변수로 쓰고 항목마다 다른 잡음을 더한다.
    latent = np.log(np.clip(base, 1e-6, 1 - 1e-6) / (1 - np.clip(base, 1e-6, 1 - 1e-6)))
    z = (latent - latent.mean()) / (latent.std() if latent.std() > 0 else 1.0)
    n = len(obligors)
    rows = []
    for item in items.itertuples(index=False):
        noisy = z + rng.normal(0.0, 1.2, n)
        # 5분위로 잘라 1~5 척도를 만든다. 척도 경계는 항목 정의의 5단계에서 온다.
        ranks = pd.Series(noisy).rank(pct=True).to_numpy()
        n_levels = int(item.scale_max) - int(item.scale_min) + 1
        score = np.clip((ranks * n_levels).astype(int) + int(item.scale_min),
                        int(item.scale_min), int(item.scale_max))
        for oid, s in zip(obligors["obligor_id"].to_numpy(), score):
            rows.append({
                "obligor_id": oid, "asof": asof, "item_code": item.item_code,
                "score": int(s), "assessor": "여신심사부",
                "recorded_by": "synthetic",
            })
    return pd.DataFrame(rows, columns=QUALITATIVE_ASSESSMENT.column_names)


# ---------------------------------------------------------------- 적합

@dataclass(frozen=True)
class ScorecardFit:
    """적합 결과. 원장 4장과 재적용에 필요한 객체를 함께 담는다."""
    model_id: str
    bins: pd.DataFrame
    factors: pd.DataFrame
    axes: pd.DataFrame
    axis_models: dict[str, LogisticRegression]
    combine_model: LogisticRegression
    factor_axis: dict[str, str]
    edges: dict[str, np.ndarray]
    woe: dict[str, np.ndarray]
    axis_stats: dict[str, tuple[float, float]]
    param_approval: str


def _bin_edges(x: np.ndarray, n_bins: int, min_share: float) -> np.ndarray:
    """분위 경계를 만들고 비중이 얇은 구간을 병합한다."""
    qs = np.quantile(x, np.linspace(0.0, 1.0, n_bins + 1))
    edges = np.unique(qs)
    if len(edges) < 2:
        return np.array([-np.inf, np.inf])
    edges[0], edges[-1] = -np.inf, np.inf
    # 얇은 구간 병합. 앞에서부터 훑으며 비중 미달 경계를 지운다.
    changed = True
    while changed and len(edges) > 2:
        changed = False
        idx = np.digitize(x, edges[1:-1], right=True)
        counts = np.bincount(idx, minlength=len(edges) - 1)
        shares = counts / max(len(x), 1)
        thin = np.where(shares < min_share)[0]
        if len(thin) > 0:
            drop = thin[0]
            cut = drop if drop < len(edges) - 2 else drop - 1
            edges = np.delete(edges, cut + 1)
            changed = True
    return edges


def _woe_table(x: np.ndarray, y: np.ndarray, edges: np.ndarray,
               smoothing: float) -> tuple[np.ndarray, list[dict]]:
    idx = np.digitize(x, edges[1:-1], right=True)
    n_bin = len(edges) - 1
    good_total = float((y == 0).sum()) + smoothing * n_bin
    bad_total = float((y == 1).sum()) + smoothing * n_bin
    woe = np.zeros(n_bin, dtype=float)
    rows = []
    for b in range(n_bin):
        m = idx == b
        n_obs = int(m.sum())
        n_def = int(y[m].sum()) if n_obs else 0
        good = (n_obs - n_def) + smoothing
        bad = n_def + smoothing
        w = float(np.log((good / good_total) / (bad / bad_total)))
        woe[b] = w
        iv = float((good / good_total - bad / bad_total) * w)
        rows.append({
            "bin_seq": b + 1,
            "lower": None if not np.isfinite(edges[b]) else float(edges[b]),
            "upper": None if not np.isfinite(edges[b + 1]) else float(edges[b + 1]),
            "n_obs": n_obs, "n_default": n_def,
            "share": float(n_obs / len(x)) if len(x) else 0.0,
            "default_rate": float(n_def / n_obs) if n_obs else 0.0,
            "woe": w, "iv_contrib": abs(iv),
        })
    return woe, rows


def _monotonic(rates: list[float]) -> bool:
    """구간 부도율이 한 방향으로만 움직이는가."""
    d = np.diff(np.asarray(rates, dtype=float))
    return bool(np.all(d >= 0) or np.all(d <= 0))


def _direction(rates: list[float], weights: list[int]) -> str:
    """구간 순서에 대한 부도율의 전체 기울기 방향.

    인접 구간 비교로 방향을 정하면 구간 하나의 잡음이 전체 방향을 '혼재'로
    바꾼다. 부도 건수가 적은 표본에서는 그 일이 늘 일어난다. 기울기 부호는
    임계값을 요구하지 않으므로 지어낸 숫자 없이 방향을 정할 수 있다.
    """
    x = np.arange(1, len(rates) + 1, dtype=float)
    y = np.asarray(rates, dtype=float)
    w = np.asarray(weights, dtype=float)
    if w.sum() <= 0 or len(x) < 2:
        return "혼재"
    xm = float(np.average(x, weights=w))
    ym = float(np.average(y, weights=w))
    cov = float(np.average((x - xm) * (y - ym), weights=w))
    if cov > 0:
        return "증가"
    if cov < 0:
        return "감소"
    return "혼재"


def fit_scorecard(dev: pd.DataFrame, factor_axis: dict[str, str],
                  factor_korean: dict[str, str],
                  expected_sign: dict[str, str], *,
                  target: str, params: pd.DataFrame, model_id: str,
                  seed: int) -> ScorecardFit:
    """축별 WOE 스코어카드를 적합하고 축을 결합한다.

    구간 수·최소 구간비중·평활·배점 스케일은 전부 params 원장에서 온다.
    이 함수 본문에 그 숫자가 없으므로 모수를 바꾸려면 원장을 고쳐야 한다.
    """
    n_bins = int(_param(params, "n_bins"))
    min_share = _param(params, "min_bin_share")
    smoothing = _param(params, "woe_smoothing")
    base_points = _param(params, "base_points")
    pdo = _param(params, "pdo")
    base_odds = _param(params, "base_odds")
    approval = ("미승인" if (params["approval_status"] == "미승인").any()
                else "승인")
    factor_scale = pdo / np.log(2.0)

    y = dev[target].astype(int).to_numpy()
    edges: dict[str, np.ndarray] = {}
    woes: dict[str, np.ndarray] = {}
    bin_rows: list[dict] = []
    factor_rows: list[dict] = []
    axis_models: dict[str, LogisticRegression] = {}
    axis_scores: dict[str, np.ndarray] = {}

    for axis in AXES:
        cols = [f for f, a in factor_axis.items() if a == axis]
        cols = [c for c in cols if c in dev.columns]
        if not cols:
            continue
        woe_mat = []
        for f in cols:
            x = pd.to_numeric(dev[f], errors="coerce").to_numpy(dtype=float)
            x = np.where(np.isnan(x), np.nanmedian(x), x)
            e = _bin_edges(x, n_bins, min_share)
            w, rows = _woe_table(x, y, e, smoothing)
            edges[f], woes[f] = e, w
            idx = np.digitize(x, e[1:-1], right=True)
            woe_mat.append(w[idx])
            for r in rows:
                r.update({"model_id": model_id, "factor": f})
            bin_rows.extend(rows)
        X = np.column_stack(woe_mat)
        clf = LogisticRegression(max_iter=1000, random_state=seed).fit(X, y)
        axis_models[axis] = clf
        # 축 점수 = base_points − scale·(계수·WOE 합). 목표변수가 부도이므로
        # WOE 계수는 음수이고, 부호를 뒤집어야 '점수가 높을수록 우량'이 된다.
        lin = X @ clf.coef_[0]
        axis_scores[axis] = base_points - factor_scale * lin
        for j, f in enumerate(cols):
            coef = float(clf.coef_[0][j])
            fbins = sorted([r for r in bin_rows if r["factor"] == f],
                           key=lambda r: r["bin_seq"])
            obs = _direction([r["default_rate"] for r in fbins],
                             [r["n_obs"] for r in fbins])
            exp = expected_sign.get(f, "미정")
            for r in fbins:
                r["points"] = float(-factor_scale * coef * r["woe"])
            factor_rows.append({
                "model_id": model_id, "factor": f,
                "korean": factor_korean.get(f, f), "axis": axis,
                "coefficient": coef,
                "iv": float(sum(r["iv_contrib"] for r in fbins)),
                "n_bins": len(fbins),
                "monotonic": _monotonic([r["default_rate"] for r in fbins]),
                "sign_expected": exp,
                "sign_observed": obs,
                "sign_agrees": bool(exp != "미정" and exp == obs),
            })

    if not axis_scores:
        raise ValueError("적합할 축이 하나도 없다. factor_axis와 dev 컬럼을 확인하라")

    used_axes = [a for a in AXES if a in axis_scores]
    # 결합은 표준화한 축 점수에 적합한다. 로지스틱에 L2 정칙화가 걸려 있어
    # 표준화하지 않으면 배점 스케일(base_points·PDO)이 결합 계수를 미세하게
    # 움직이고, 표시 척도를 바꿨을 뿐인데 PD가 달라진다.
    axis_stats: dict[str, tuple[float, float]] = {}
    cols_std = []
    for a in used_axes:
        s = axis_scores[a]
        mu = float(np.mean(s))
        sd = float(np.std(s)) or 1.0
        axis_stats[a] = (mu, sd)
        cols_std.append((s - mu) / sd)
    S = np.column_stack(cols_std)
    combine = LogisticRegression(max_iter=1000, random_state=seed).fit(S, y)
    coefs = combine.coef_[0]
    denom = float(np.abs(coefs).sum()) or 1.0

    axis_rows = []
    for a, c in zip(used_axes, coefs):
        s = axis_scores[a]
        axis_rows.append({
            "model_id": model_id, "axis": a,
            "n_factors": int(sum(1 for f, ax in factor_axis.items()
                                 if ax == a and f in edges)),
            "weight": float(abs(c) / denom),
            "coefficient": float(c),
            "score_mean": float(np.mean(s)),
            "score_std": float(np.std(s)),
            "basis": "표준화한 축 점수에 대한 로지스틱 적합 계수. "
                     "정책 가중이 아니다",
        })

    bins = pd.DataFrame(bin_rows, columns=SCORECARD_BIN.column_names)
    bins = bins.sort_values(["factor", "bin_seq"]).reset_index(drop=True)
    return ScorecardFit(
        model_id=model_id,
        bins=bins,
        factors=pd.DataFrame(factor_rows, columns=SCORECARD_FACTOR.column_names),
        axes=pd.DataFrame(axis_rows, columns=SCORECARD_AXIS.column_names),
        axis_models=axis_models, combine_model=combine,
        factor_axis={f: a for f, a in factor_axis.items() if f in edges},
        edges=edges, woe=woes, axis_stats=axis_stats, param_approval=approval,
    )


def score_obligors(fit: ScorecardFit, current: pd.DataFrame, *,
                   params: pd.DataFrame, asof: str
                   ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """적합된 스코어카드를 적용 모집단에 적용한다.

    구간 경계와 WOE는 적합 결과를 그대로 쓴다. 적용 시점에 다시 구간을 나누면
    개발표본과 다른 배점이 되어 153.라의 재현 가능성이 깨진다.
    """
    base_points = _param(params, "base_points")
    pdo = _param(params, "pdo")
    factor_scale = pdo / np.log(2.0)

    axis_scores: dict[str, np.ndarray] = {}
    axis_nfac: dict[str, int] = {}
    for axis, clf in fit.axis_models.items():
        cols = [f for f, a in fit.factor_axis.items() if a == axis]
        mat = []
        for f in cols:
            x = pd.to_numeric(current[f], errors="coerce").to_numpy(dtype=float)
            x = np.where(np.isnan(x), np.nanmedian(x), x)
            idx = np.digitize(x, fit.edges[f][1:-1], right=True)
            mat.append(fit.woe[f][idx])
        X = np.column_stack(mat)
        axis_scores[axis] = base_points - factor_scale * (X @ clf.coef_[0])
        axis_nfac[axis] = len(cols)

    used = [a for a in AXES if a in axis_scores]
    # 표준화 통계는 적합 시점의 값을 쓴다. 적용 모집단으로 다시 표준화하면
    # 모집단이 나빠져도 평균이 다시 0이 되어 PD가 움직이지 않는다.
    S = np.column_stack([(axis_scores[a] - fit.axis_stats[a][0])
                         / fit.axis_stats[a][1] for a in used])
    p = fit.combine_model.predict_proba(S)[:, 1]
    p = np.clip(p, 1e-6, 1 - 1e-6)
    raw = np.column_stack([axis_scores[a] for a in used])
    w = np.abs(fit.combine_model.coef_[0])
    total = raw @ w / max(float(w.sum()), 1e-12)

    oid = current["obligor_id"].to_numpy()
    axis_rows = []
    for a in used:
        for o, s in zip(oid, axis_scores[a]):
            axis_rows.append({"obligor_id": o, "asof": asof,
                              "model_id": fit.model_id, "axis": a,
                              "score": float(s), "n_factors": axis_nfac[a]})
    score = pd.DataFrame({
        "obligor_id": oid,
        "asof": asof,
        "model_id": fit.model_id,
        "total_score": total.astype(float),
        "model_pd": p.astype(float),
        "model_grade": [pd_to_rating(float(v)).grade for v in p],
        "n_axes": len(used),
        "param_approval": fit.param_approval,
    }, columns=OBLIGOR_SCORE.column_names)
    axes = pd.DataFrame(axis_rows, columns=OBLIGOR_AXIS_SCORE.column_names)
    return score, axes


def non_default_grades() -> list[str]:
    """master scale의 비부도 등급 목록. 151.나 판정의 입력이다."""
    return [g.grade for g in DEFAULT_MASTER_SCALE]
