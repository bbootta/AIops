"""트레이딩 포트폴리오 축 — 설정 마스터 · 포지션 원장 · 유형별 상세 (일원화).

시장 RWA 의 순포지션(엔진 내부 값)과 트레이딩북(`mkt_trade`)이 서로 다른
곳에서 태어나 `rwa_market_component` 는 상류 원장이 없는 표였다. 이 모듈이
그 사이에 포지션 원장을 세운다. 흐름은 한 줄이 된다.

    엔진 순포지션 → mkt_position (포트폴리오 × 위험군)
                  → rwa_market_component  위험군 집계 = 규제 표
                  → mkt_portfolio_capital 포트폴리오 상세 (SSA 동일 산식)
                  → mkt_var_es_portfolio  VaR·ES 자본비중 배분

원장 네 장이다.

  mkt_portfolio          포트폴리오 설정 (구분·전략·배분 가중치·한도 비중)
  mkt_position           포지션 원장. RWA·상세·배분이 전부 여기서 나온다
  mkt_portfolio_capital  포트폴리오 × 위험군 소요자본·RWA
  mkt_var_es_portfolio   전사 VaR·ES 의 포트폴리오 배분

포트폴리오 구분과 배분 가중치는 이 모듈의 적재 표가 유일한 출처다.
가중치는 위험군별로 합이 1.0 이고 전부 양수다. 양수가 아니면 |Σ| ≠ Σ|·| 가
되어 포트폴리오 자본 합이 위험군 자본과 갈라진다. 트레이딩북 배정
(`KIND_TO_PORTFOLIO`)도 여기가 정본이다.

VaR·ES 배분은 자본비중 비례다(내부기준). 포트폴리오 간 분산효과를 0 으로
두므로 합이 전사 값과 정확히 일치하고, 그만큼 각 포트폴리오에는 보수적으로
얹힌다. 독립 재계산이 아니라 배분이라는 사실을 컬럼(`alloc_share`)에 남긴다.
"""

from __future__ import annotations

import pandas as pd

from risk_lib.capital.market_risk import DEFAULT_RISK_WEIGHTS, SSA_SCALING
from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec

RISK_CLASSES = tuple(sorted(SSA_SCALING))
# catalog.RISK_MEASURES 와 같은 값이어야 한다. catalog 가 이 모듈을 import
# 하므로 여기서 catalog 를 읽으면 순환이 된다 — 동치는 테스트가 지킨다.
MEASURES = ("VaR_99", "ES_97_5", "sVaR_99")
EVIDENCE = ("내부기준(합성)", "원문확인", "2차자료", "미확인")

# ---------------------------------------------------------------- 적재 표
#
# 포트폴리오 구분. 이 표가 유일한 데이터 적재 지점이다.
# (id, 이름, 전략, {위험군: 배분 가중치}, VaR 한도 배분 비중)
_PORTFOLIOS: tuple[tuple[str, str, str, dict[str, float], float], ...] = (
    ("PF-RATES", "금리운용", "채권·금리스왑 방향성",
     {"interest_rate": 0.80}, 0.35),
    ("PF-EQTY", "주식운용", "주식 현물·옵션",
     {"equity": 0.85}, 0.25),
    ("PF-FX", "외환운용", "외환 현물·포워드 (금리레그 포함)",
     {"fx": 0.75, "interest_rate": 0.12}, 0.25),
    ("PF-XASST", "혼합·신용", "북 헤지·신용파생·잔여 포지션",
     {"interest_rate": 0.08, "equity": 0.15, "fx": 0.25}, 0.15),
)

# 트레이딩북 상품 유형 → 운용 포트폴리오. materialize_market 이 mkt_trade 에
# portfolio_id 를 붙일 때 쓴다.
KIND_TO_PORTFOLIO = {"swap": "PF-RATES", "option": "PF-EQTY",
                     "cds": "PF-XASST"}


def _check_loading_table() -> None:
    """가중치가 위험군별로 정확히 배분되는지 import 시점에 확인한다.

    합이 1.0 에서 벗어나면 포지션이 조용히 새거나 두 번 세어지고, 그 상태로
    화면·서식까지 흘러간다. 틀린 설정은 시작하기 전에 죽는 것이 낫다.
    """
    classes = {c for *_, w, _l in _PORTFOLIOS for c in w}
    for cls in classes:
        if cls not in SSA_SCALING:
            raise ValueError(f"미지의 위험군 배분: {cls}")
        s = sum(w.get(cls, 0.0) for *_, w, _l in _PORTFOLIOS)
        if abs(s - 1.0) > 1e-9:
            raise ValueError(f"{cls} 배분 합이 {s} 다. 1.0 이어야 한다")
        if any(w.get(cls, 0.0) < 0.0 for *_, w, _l in _PORTFOLIOS):
            raise ValueError(f"{cls} 에 음수 배분이 있다")
    if abs(sum(_l for *_, _l in _PORTFOLIOS) - 1.0) > 1e-9:
        raise ValueError("VaR 한도 배분 비중 합이 1.0 이 아니다")


_check_loading_table()


# ---------------------------------------------------------------- TableSpec

PORTFOLIO = TableSpec(
    name="mkt_portfolio", korean="트레이딩 포트폴리오 설정", product="PRD-MKT",
    grain="포트폴리오 1개당 1행",
    columns=(
        C("portfolio_id", "string", "포트폴리오 식별자", nullable=False),
        C("name", "string", "포트폴리오명", nullable=False),
        C("strategy", "text", "운용 전략", nullable=False),
        C("share_interest_rate", "float", "금리 포지션 배분", nullable=False,
          unit="ratio", min_value=0.0, max_value=1.0),
        C("share_equity", "float", "주식 포지션 배분", nullable=False,
          unit="ratio", min_value=0.0, max_value=1.0),
        C("share_fx", "float", "외환 포지션 배분", nullable=False,
          unit="ratio", min_value=0.0, max_value=1.0),
        C("var_limit_share", "float", "VaR 한도 배분 비중", nullable=False,
          unit="ratio", min_value=0.0, max_value=1.0),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE,
          note="구분·가중치는 합성 설정이다. 실기관 적용 시 운용 지침으로 교체된다"),
    ),
    primary_key=("portfolio_id",),
    note="배분 가중치는 위험군별 합 1.0·전부 양수. 이 모듈 적재 표가 정본이다.",
)

POSITION = TableSpec(
    name="mkt_position", korean="시장 포지션 원장", product="PRD-MKT",
    grain="기준일 × 포트폴리오 × 위험군 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("portfolio_id", "string", "포트폴리오 식별자", nullable=False),
        C("risk_class", "string", "위험군", nullable=False,
          allowed=RISK_CLASSES),
        C("net_position", "float", "순포지션", nullable=False, unit="KRW"),
    ),
    primary_key=("asof", "portfolio_id", "risk_class"),
    foreign_keys=(FK(("portfolio_id",), "mkt_portfolio", ("portfolio_id",)),),
    note="시장 RWA·포트폴리오 상세·VaR 배분이 전부 이 원장에서 나온다 (일원화).",
)

PORTFOLIO_CAPITAL = TableSpec(
    name="mkt_portfolio_capital", korean="포트폴리오 시장리스크 자본",
    product="PRD-MKT", grain="기준일 × 포트폴리오 × 위험군 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("portfolio_id", "string", "포트폴리오 식별자", nullable=False),
        C("risk_class", "string", "위험군", nullable=False,
          allowed=RISK_CLASSES),
        C("position", "float", "순포지션", nullable=False, unit="KRW"),
        C("risk_weight", "float", "위험계수", nullable=False, unit="ratio",
          min_value=0.0, citation="MAR40 간편표준방법"),
        C("scaling_factor", "float", "감독조정계수", nullable=False,
          unit="ratio", min_value=0.0, citation="MAR40.2"),
        C("capital", "float", "소요자기자본", nullable=False, unit="KRW",
          min_value=0.0),
        C("rwa", "float", "위험가중자산", nullable=False, unit="KRW",
          min_value=0.0, citation="소요자기자본 × 12.5 (CRE20.1)"),
    ),
    primary_key=("asof", "portfolio_id", "risk_class"),
    foreign_keys=(FK(("portfolio_id",), "mkt_portfolio", ("portfolio_id",)),),
    note="rwa_market_component 와 같은 산식·같은 포지션 원장이다. 위험군으로 "
         "합치면 규제 표와 일치해야 하며, 그 일치는 정합성 체크가 지킨다.",
)

VAR_ES_PORTFOLIO = TableSpec(
    name="mkt_var_es_portfolio", korean="포트폴리오 VaR·ES 배분",
    product="PRD-MKT", grain="기준일 × 포트폴리오 × 측정치 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("portfolio_id", "string", "포트폴리오 식별자", nullable=False),
        C("measure", "string", "측정치", nullable=False, allowed=MEASURES),
        C("horizon_days", "int", "보유기간", nullable=False, unit="days",
          min_value=1),
        C("confidence", "float", "신뢰수준", nullable=False, unit="ratio",
          min_value=0.5, max_value=1.0),
        C("value", "float", "배분값", nullable=False, unit="KRW",
          min_value=0.0),
        C("alloc_share", "float", "배분 비중", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0,
          note="자본비중 비례배분(내부기준). 독립 재계산이 아니라 배분이다"),
    ),
    primary_key=("asof", "portfolio_id", "measure"),
    foreign_keys=(FK(("portfolio_id",), "mkt_portfolio", ("portfolio_id",)),),
    note="전사 mkt_var_es 를 자본비중으로 나눈 값. 측정치별 합 = 전사 값.",
)

SPECS: tuple[TableSpec, ...] = (PORTFOLIO, POSITION, PORTFOLIO_CAPITAL,
                                VAR_ES_PORTFOLIO)


# ---------------------------------------------------------------- 빌더

def portfolio_frame() -> pd.DataFrame:
    """포트폴리오 설정 원장. 적재 표를 그대로 편다."""
    return pd.DataFrame([{
        "portfolio_id": pid, "name": name, "strategy": strat,
        "share_interest_rate": float(w.get("interest_rate", 0.0)),
        "share_equity": float(w.get("equity", 0.0)),
        "share_fx": float(w.get("fx", 0.0)),
        "var_limit_share": float(lim),
        "evidence_status": "내부기준(합성)",
    } for pid, name, strat, w, lim in _PORTFOLIOS],
        columns=[c.name for c in PORTFOLIO.columns])


def split_positions(class_positions: pd.DataFrame, *, asof: str
                    ) -> pd.DataFrame:
    """엔진의 위험군 순포지션을 포트폴리오로 가른다.

    가중치가 위험군별 합 1.0·전부 양수이므로 포트폴리오 합은 위험군 값을
    보존한다(부동소수 오차 이내). RWA 총액은 이 분해와 무관하게 위험군
    총계에서 나오므로 headline 은 변하지 않는다.
    """
    rows = []
    for _, r in class_positions.iterrows():
        cls, net = str(r["risk_class"]), float(r["net_position"])
        for pid, _name, _strat, w, _lim in _PORTFOLIOS:
            share = float(w.get(cls, 0.0))
            if share > 0.0:
                rows.append({"asof": asof, "portfolio_id": pid,
                             "risk_class": cls, "net_position": net * share})
    return pd.DataFrame(rows, columns=[c.name for c in POSITION.columns])


def capital_frame(positions: pd.DataFrame) -> pd.DataFrame:
    """포지션 원장 → 포트폴리오 × 위험군 소요자본·RWA.

    산식은 `compute_market_risk_rwa` 와 같다: |순포지션| × 위험계수 × SF,
    RWA = 자본 × 12.5. 상수도 같은 모듈에서 가져온다. 산식이 두 벌이 되면
    포트폴리오 합과 규제 표가 조용히 갈라진다.
    """
    rows = []
    for _, r in positions.iterrows():
        cls = str(r["risk_class"])
        rw = float(DEFAULT_RISK_WEIGHTS[cls])
        sf = float(SSA_SCALING[cls])
        cap = abs(float(r["net_position"])) * rw * sf
        rows.append({"asof": r["asof"], "portfolio_id": r["portfolio_id"],
                     "risk_class": cls, "position": float(r["net_position"]),
                     "risk_weight": rw, "scaling_factor": sf,
                     "capital": cap, "rwa": cap * 12.5})
    return pd.DataFrame(rows,
                        columns=[c.name for c in PORTFOLIO_CAPITAL.columns])


def allocate_var_es(var_es: pd.DataFrame, capital: pd.DataFrame
                    ) -> pd.DataFrame:
    """전사 VaR·ES 를 포트폴리오 자본비중으로 배분한다 (내부기준).

    측정치별 합이 전사 값과 정확히 일치하도록 비중을 곱해서만 나눈다.
    분산효과를 0 으로 두는 배분이므로 각 포트폴리오에는 보수적이다.
    """
    by_pf = capital.groupby("portfolio_id")["capital"].sum()
    total = float(by_pf.sum())
    rows = []
    for _, m in var_es.iterrows():
        for pid, cap in by_pf.items():
            share = float(cap) / total if total > 0 else 0.0
            rows.append({"asof": m["asof"], "portfolio_id": str(pid),
                         "measure": str(m["measure"]),
                         "horizon_days": int(m["horizon_days"]),
                         "confidence": float(m["confidence"]),
                         "value": float(m["value"]) * share,
                         "alloc_share": share})
    return pd.DataFrame(rows,
                        columns=[c.name for c in VAR_ES_PORTFOLIO.columns])


# ---------------------------------------------------------------- 원장 빌더
#
# 이 두 함수는 materialize_* 래퍼가 아니라 여기 있어야 한다. 계보 스캐너가
# materialize* 이름을 오케스트레이터로 보고 feeds 를 만들지 않으므로, 원장을
# 읽고 쓰는 몸통이 여기 있어야 mkt_position → rwa_market_component 의존이
# 계보에 나타난다. 일원화는 그 선이 보여야 완성이다.

def build_component_tables(by_class: dict[str, float], base,
                           *, asof: str) -> dict[str, pd.DataFrame]:
    """포지션 원장 → 규제 표(위험군)와 포트폴리오 × 위험군 자본.

    소요자본은 엔진 산출(`by_class`)을 그대로 쓰고, 포지션 열은
    `mkt_position` 집계다. 예전에는 capital/0.08 역산을 적었는데 그 수는
    어떤 포지션도 아니다 (금리는 실제의 4배쯤 작게 보였다). 원장이 없으면
    지어내지 않고 NaN 을 남긴다.
    """
    pos = base.get("mkt_position")
    have = isinstance(pos, pd.DataFrame) and not pos.empty
    agg = pos.groupby("risk_class")["net_position"].sum() if have else {}

    out: dict[str, pd.DataFrame] = {}
    out["rwa_market_component"] = pd.DataFrame([{
        "asof": asof, "risk_class": cls,
        "position": float(agg.get(cls, float("nan"))),
        "capital": float(capital), "rwa": float(capital) * 12.5,
    } for cls, capital in by_class.items() if cls in RISK_CLASSES],
        columns=["asof", "risk_class", "position", "capital", "rwa"])
    out["mkt_portfolio_capital"] = (
        capital_frame(pos) if have
        else pd.DataFrame(columns=[c.name for c in PORTFOLIO_CAPITAL.columns]))
    return out


def build_var_es_allocation(base) -> dict[str, pd.DataFrame]:
    """전사 VaR·ES 를 포트폴리오 자본비중으로 배분한 원장."""
    var_es = base.get("mkt_var_es")
    capital = base.get("mkt_portfolio_capital")
    ok = (isinstance(var_es, pd.DataFrame) and not var_es.empty
          and isinstance(capital, pd.DataFrame) and not capital.empty)
    out: dict[str, pd.DataFrame] = {}
    out["mkt_var_es_portfolio"] = (
        allocate_var_es(var_es, capital) if ok
        else pd.DataFrame(columns=[c.name for c in VAR_ES_PORTFOLIO.columns]))
    return out
