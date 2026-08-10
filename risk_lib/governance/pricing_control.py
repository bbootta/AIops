"""시장데이터·가격 통제 대장 (GOV-006).

이 저장소에는 통제를 수행하는 엔진이 이미 있다. `risk_lib.ipv`가 소스 위계와
가격차이를, `risk_lib.frtb`가 손익귀속(PLA)과 VaR 백테스트를 판정한다. 없던
것은 그 판정들을 한 자리에 모아 **어느 통제가 어느 기준일에 실제로 돌았는가**를
남기는 대장이다. 엔진이 있어도 실행 기록이 없으면 통제를 안 한 것과 감사에서
구분되지 않는다.

원장 네 장과 판정 한 개로 구성한다.

  gov_price_source_rank    가격 소스 위계와 독립성 인정 여부
  gov_pricing_control      통제 5종 정의(판정 주체·허용 판정값·임계·주기)
  gov_pricing_result       기준일 x 데스크 x 통제 실행 결과
  gov_pricing_gap          미흡·미실시·판정불가 건과 조치

판정은 fail-closed다. 관측 기록이 없는 통제는 '미실시'이고, 임계값도 허용
판정값도 없는 통제는 '판정불가'로 남긴다. 임계값을 지어내 채우면 그 순간
대장이 근거를 잃는다.

임계값 칸은 현재 전건 NULL이다. 상품·유동성별 허용오차와 커버리지 하한은
기관 승인 사양이며 이 저장소가 확인한 1차자료에 없다. `risk_lib.ipv`의
기본 허용오차는 구조 시연용이라고 그 모듈이 스스로 적어 두었으므로 규제
근거로 옮기지 않는다. 대신 기존 엔진이 이미 내리는 판정(zone·독립소스 여부)은
`acceptable_verdicts`로 받아 그대로 쓴다.

이 모듈의 TableSpec은 아직 datamodel.catalog에 등재하지 않았다. 등재는 실체화
검증과 문서 수치 일치를 함께 만족해야 하므로 배선 단계에서 `SPECS`를 넘긴다.

참조: RYNTA BRD GOV-006(Market/Pricing 통제) · SEC-PRC-005(IPV),
BCBS Prudent valuation guidance, BCBS d457 MAR32(PLA·백테스트).
"""

from __future__ import annotations

import pandas as pd

from risk_lib import ipv
from risk_lib.alm.params import EVIDENCE_STATUS
from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec

CONTROL_IDS = ("PC-SRC", "PC-REG", "PC-IPV", "PC-PLA", "PC-RBK")
RESULT_STATUSES = ("유효", "미흡", "미실시", "판정불가")
DIRECTIONS = ("min", "max")
FREQUENCIES = ("일별", "월별", "분기별", "변경시")
GAP_SEVERITIES = ("높음", "보통", "낮음")


# ---------------------------------------------------------------- 스펙

SOURCE_RANK = TableSpec(
    name="gov_price_source_rank", korean="가격 소스 위계", product="PRD-MKT",
    grain="가격 소스 1개당 1행",
    columns=(
        C("price_source", "string", "가격 소스", nullable=False),
        C("rank", "int", "위계 순위", nullable=False, unit="count", min_value=1,
          note="낮을수록 독립성이 높다"),
        C("independent", "bool", "독립검증 인정", nullable=False),
        C("rationale", "text", "인정·불인정 사유", nullable=False),
    ),
    primary_key=("price_source",),
    note="Front Office 자체 가격은 위계에 올리되 독립검증으로 인정하지 않는다. "
         "인정 여부를 원장에 두면 커버리지 계산이 어느 소스를 셌는지 되짚힌다.",
)

PRICING_CONTROL = TableSpec(
    name="gov_pricing_control", korean="시장·가격 통제 정의", product="PRD-MKT",
    grain="통제 1개당 1행",
    columns=(
        C("control_id", "string", "통제 식별자", nullable=False,
          allowed=CONTROL_IDS),
        C("control_name", "text", "통제명", nullable=False),
        C("verdict_source", "text", "판정 주체", nullable=False,
          note="판정을 내리는 기존 엔진의 모듈 경로. 대장이 판정을 새로 만들지 않는다"),
        C("acceptable_verdicts", "text", "허용 판정값", nullable=False,
          note="쉼표로 구분. 비어 있으면 임계값 비교로 판정한다"),
        C("threshold_value", "float", "임계값", nullable=True, unit="ratio",
          note="원문 미확인 구간은 NULL이다. 엔진은 NULL을 기본값으로 메우지 않는다"),
        C("threshold_direction", "string", "임계 방향", nullable=True,
          allowed=DIRECTIONS),
        C("frequency", "string", "수행 주기", nullable=False, allowed=FREQUENCIES),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS,
          note="threshold_value에 대한 근거 상태다. acceptable_verdicts는 "
               "기존 엔진이 이미 내리는 판정을 가리키므로 별개다"),
        C("citation", "text", "근거", nullable=False),
        C("owner_role", "text", "통제 소유 역할", nullable=False),
    ),
    primary_key=("control_id",),
)

PRICING_RESULT = TableSpec(
    name="gov_pricing_result", korean="가격 통제 실행결과", product="PRD-MKT",
    grain="기준일 x 데스크 x 통제 1건당 1행",
    columns=(
        C("asof", "date", "기준일자", nullable=False),
        C("desk", "string", "데스크", nullable=False),
        C("control_id", "string", "통제 식별자", nullable=False,
          allowed=CONTROL_IDS),
        C("status", "string", "판정", nullable=False, allowed=RESULT_STATUSES),
        C("verdict", "text", "관측 판정값", nullable=True),
        C("metric_value", "float", "관측 지표", nullable=True, unit="ratio"),
        C("evidence_ref", "text", "증빙 참조", nullable=False),
        C("reason", "text", "판정 사유", nullable=False),
    ),
    primary_key=("asof", "desk", "control_id"),
    foreign_keys=(FK(("control_id",), "gov_pricing_control", ("control_id",)),),
)

PRICING_GAP = TableSpec(
    name="gov_pricing_gap", korean="가격 통제 미비", product="PRD-MKT",
    grain="미비 1건당 1행",
    columns=(
        C("asof", "date", "기준일자", nullable=False),
        C("desk", "string", "데스크", nullable=False),
        C("control_id", "string", "통제 식별자", nullable=False,
          allowed=CONTROL_IDS),
        C("severity", "string", "심각도", nullable=False, allowed=GAP_SEVERITIES),
        C("action", "text", "표준 조치", nullable=False),
        C("owner_role", "text", "조치 담당 역할", nullable=False),
    ),
    primary_key=("asof", "desk", "control_id"),
    foreign_keys=(FK(("asof", "desk", "control_id"), "gov_pricing_result",
                     ("asof", "desk", "control_id")),),
)

SPECS: tuple[TableSpec, ...] = (
    SOURCE_RANK, PRICING_CONTROL, PRICING_RESULT, PRICING_GAP)


# ---------------------------------------------------------------- 정의 적재
#
# 이 두 표가 이 모듈의 유일한 적재 지점이다. 판정 함수는 표를 직접 읽지 않고
# 인자로 받은 DataFrame만 본다.

_SOURCE_RATIONALE = {
    "consensus": "복수 참여자 제출가의 컨센서스. 거래상대와 산출자가 분리된다",
    "broker": "제3자 호가. 체결가가 아니므로 유동성 낮은 종목에서 편차가 크다",
    "exchange": "거래소 종가. 체결 기반이나 상장 상품에 한정된다",
    "model": "FO 모형과 분리된 독립 검증모형. 입력 시장데이터의 독립성이 전제다",
    "front_office": "산출자와 검증자가 같다. 독립검증으로 인정하지 않는다",
}

# (통제ID, 통제명, 판정주체, 허용판정값, 임계, 방향, 주기, 근거상태, 근거, 소유역할)
#
# 임계값을 전건 NULL로 두는 이유. 커버리지 하한·BREAK율 한도·재현 불일치
# 허용건수는 기관이 승인하는 값이고, 이 저장소가 확보한 1차자료에 없다.
# `ipv.py`의 기본 허용오차는 그 모듈이 "구조 시연용"이라고 스스로 적었다.
_CONTROLS = (
    ("PC-SRC", "가격 소스 위계 준수", "risk_lib.ipv.is_independent", "", None, None,
     "일별", "미확인",
     "소스 위계는 risk_lib.ipv.SOURCE_RANK가 정의한다. 커버리지 하한의 승인 근거 미확보",
     "시장리스크관리자"),
    ("PC-REG", "판 간 회귀 재현", "risk_lib.validation.consistency", "", None, None,
     "변경시", "미확인",
     "직전 판 대비 재현 불일치 허용건수의 승인 근거 미확보",
     "리스크데이터관리자"),
    ("PC-IPV", "독립가격검증", "risk_lib.ipv.run_ipv", "", None, None,
     "월별", "미확인",
     "BREAK율 한도·커버리지 하한의 승인 근거 미확보. ipv.py 기본값은 구조 시연용",
     "평가검증담당"),
    ("PC-PLA", "손익귀속·백테스트", "risk_lib.frtb.plat_test", "green,amber",
     None, None, "분기별", "미확인",
     "zone 판정은 risk_lib.frtb가 내린다. BCBS d457 MAR32 원문 미열람",
     "시장리스크관리자"),
    ("PC-RBK", "가격·커브 롤백 가능성", "risk_lib.archive.scan", "가능",
     None, None, "변경시", "미확인",
     "되돌아갈 직전 판의 보관 여부로 판정한다. 보관 세대수의 법적 근거 미확보",
     "리스크데이터관리자"),
)

# 미비 심각도와 표준 조치. 판정 결과에 따라 붙는다.
_GAP_RULES = {
    "미흡": ("높음", "통제 미흡 원인 분석 후 재수행. 해소 전 해당 데스크 산출은 잠정"),
    "미실시": ("높음", "통제 수행 일정 확정 및 미수행 사유 기록"),
    "판정불가": ("보통", "임계값 또는 허용 판정값을 승인 절차로 확정한다"),
}


def build_source_rank() -> pd.DataFrame:
    """가격 소스 위계를 원장으로 만든다.

    순위와 독립성 인정 기준은 `risk_lib.ipv`가 이미 정의했다. 여기서 다시
    적으면 두 곳이 갈라지므로 그 모듈에서 읽어 온다.
    """
    rows = [{
        "price_source": src,
        "rank": int(rank),
        "independent": ipv.is_independent(src),
        "rationale": _SOURCE_RATIONALE.get(src, "사유 미기재"),
    } for src, rank in sorted(ipv.SOURCE_RANK.items(), key=lambda kv: (kv[1], kv[0]))]
    return pd.DataFrame(rows, columns=[c.name for c in SOURCE_RANK.columns]
                        ).astype({"rank": "int64", "independent": "bool"})


def build_pricing_controls() -> pd.DataFrame:
    return pd.DataFrame([{
        "control_id": c[0], "control_name": c[1], "verdict_source": c[2],
        "acceptable_verdicts": c[3], "threshold_value": c[4],
        "threshold_direction": c[5], "frequency": c[6], "evidence_status": c[7],
        "citation": c[8], "owner_role": c[9],
    } for c in _CONTROLS], columns=[c.name for c in PRICING_CONTROL.columns]
    ).astype({"threshold_value": "float64"})


# ---------------------------------------------------------------- 판정

def _judge(control: pd.Series, verdict, metric) -> tuple[str, str]:
    """통제 1건의 관측을 판정한다. (판정, 사유)를 돌려준다."""
    allowed = [v.strip() for v in str(control["acceptable_verdicts"]).split(",")
               if v.strip()]
    if allowed:
        if verdict is None or (isinstance(verdict, float) and pd.isna(verdict)):
            return "판정불가", f"허용 판정값({', '.join(allowed)})이 있으나 관측 판정값이 없다"
        if str(verdict) in allowed:
            return "유효", f"판정값 {verdict} 이 허용집합에 있다"
        return "미흡", f"판정값 {verdict} 이 허용집합({', '.join(allowed)}) 밖이다"
    threshold = control["threshold_value"]
    direction = control["threshold_direction"]
    if pd.isna(threshold) or direction is None or pd.isna(direction):
        return "판정불가", (f"임계값 미확정({control['evidence_status']}). "
                            f"{control['citation']}")
    if metric is None or (isinstance(metric, float) and pd.isna(metric)):
        return "판정불가", "임계값은 있으나 관측 지표가 없다"
    ok = (float(metric) >= float(threshold) if direction == "min"
          else float(metric) <= float(threshold))
    rel = "≥" if direction == "min" else "≤"
    return ("유효" if ok else "미흡",
            f"관측 {metric} {rel} 임계 {threshold} " + ("충족" if ok else "미충족"))


def evaluate_pricing_controls(controls: pd.DataFrame, observations: pd.DataFrame,
                              *, asof: str, desks) -> pd.DataFrame:
    """기준일 x 데스크 x 통제를 판정한다.

    observations는 (desk, control_id, verdict, metric_value, evidence_ref)
    컬럼을 갖는다. 관측이 없는 (데스크, 통제) 조합은 '미실시'로 남는다.
    통제를 돌리지 않은 것과 돌려서 유효한 것을 같게 두면 대장이 무의미해진다.
    """
    obs: dict[tuple[str, str], dict] = {}
    for row in observations.to_dict("records"):
        obs[(row["desk"], row["control_id"])] = row
    rows = []
    # 같은 데스크가 두 번 들어오면 결과 원장의 기본키가 깨진다.
    for desk in sorted(set(desks)):
        for control in controls.to_dict("records"):
            cid = control["control_id"]
            hit = obs.get((desk, cid))
            if hit is None:
                rows.append((asof, desk, cid, "미실시", None, None, "",
                             f"{control['frequency']} 주기 통제의 실행 기록이 없다"))
                continue
            status, reason = _judge(pd.Series(control), hit.get("verdict"),
                                    hit.get("metric_value"))
            rows.append((asof, desk, cid, status, hit.get("verdict"),
                         hit.get("metric_value"), hit.get("evidence_ref", ""),
                         reason))
    return pd.DataFrame(rows, columns=[c.name for c in PRICING_RESULT.columns]
                        ).astype({"metric_value": "float64"})


def build_pricing_gaps(results: pd.DataFrame, controls: pd.DataFrame
                       ) -> pd.DataFrame:
    """유효가 아닌 결과에 심각도와 표준 조치를 붙인다."""
    owner = controls.set_index("control_id")["owner_role"].to_dict()
    rows = []
    for r in results.to_dict("records"):
        rule = _GAP_RULES.get(r["status"])
        if rule is None:
            continue
        rows.append((r["asof"], r["desk"], r["control_id"], rule[0], rule[1],
                     owner.get(r["control_id"], "미지정")))
    return pd.DataFrame(rows, columns=[c.name for c in PRICING_GAP.columns])


# ---------------------------------------------------------------- 관측 어댑터

def observation_from_ipv(result, *, desk: str, evidence_ref: str) -> dict:
    """IPV 실행 결과를 PC-IPV 관측으로 바꾼다.

    명목 기준 커버리지를 쓴다. 건수 기준만 보면 소액 다수를 검증하고 대형
    포지션을 빠뜨려도 커버리지가 높게 나온다.
    """
    return {"desk": desk, "control_id": "PC-IPV", "verdict": None,
            "metric_value": float(result.coverage_by_notional),
            "evidence_ref": evidence_ref}


def observation_from_source_coverage(result, *, desk: str, evidence_ref: str
                                     ) -> dict:
    """IPV 실행 결과를 PC-SRC 관측으로 바꾼다. 독립소스 검증 건수 비율이다."""
    return {"desk": desk, "control_id": "PC-SRC", "verdict": None,
            "metric_value": float(result.coverage), "evidence_ref": evidence_ref}


def observation_from_plat(plat, *, desk: str, evidence_ref: str) -> dict:
    """FRTB PLA 결과를 PC-PLA 관측으로 바꾼다. zone 판정을 그대로 옮긴다."""
    return {"desk": desk, "control_id": "PC-PLA", "verdict": plat.overall_zone,
            "metric_value": float(plat.spearman), "evidence_ref": evidence_ref}


def observation_from_rollback(prior_versions, *, desk: str, evidence_ref: str
                              ) -> dict:
    """직전 판 보관 여부를 PC-RBK 관측으로 바꾼다."""
    return {"desk": desk, "control_id": "PC-RBK",
            "verdict": "가능" if len(prior_versions) else "불가",
            "metric_value": None, "evidence_ref": evidence_ref}


def build_pricing_control(observations, *, asof: str, desks
                          ) -> dict[str, pd.DataFrame]:
    """가격 통제 원장 4장을 만든다.

    observations는 관측 dict의 열거다. 호출자가 실제 통제 실행 결과를 넘기며
    이 함수는 표본을 만들지 않는다.
    """
    controls = build_pricing_controls()
    obs = pd.DataFrame(list(observations),
                       columns=["desk", "control_id", "verdict", "metric_value",
                                "evidence_ref"])
    results = evaluate_pricing_controls(controls, obs, asof=asof, desks=desks)
    return {"gov_price_source_rank": build_source_rank(),
            "gov_pricing_control": controls,
            "gov_pricing_result": results,
            "gov_pricing_gap": build_pricing_gaps(results, controls)}
