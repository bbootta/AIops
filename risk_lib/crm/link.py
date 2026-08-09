"""담보-익스포저 관계 원장과 합성 관계 그래프 생성기.

**왜 관계 원장이 필요한가.** 현행 `rdm_collateral`은 담보 1건에 `exposure_id`
컬럼 하나를 붙여 담보와 익스포저를 1:1로 묶는다. 실제 여신은 그렇지 않다.
포괄근담보 1건이 여러 여신을 덮고(1:N), 부동산·예금·보증이 여신 1건에 겹쳐
걸리며(M:1), 그룹 여신은 교차담보 풀로 얽힌다(M:N). 1:1 컬럼으로는 이 셋을
표현할 수 없고, 표현되지 않으면 배분 초과·중복이 검증에 잡히지 않는다.

**relation_type은 라벨이 아니라 유도값이다.** 합성기가 "이건 M:N"이라고 적고
실제 링크 차수가 다르면 검증이 그 불일치를 못 잡는다. 그래서 `relation_type`과
`pool_id`는 링크 집합에서만 계산한다(`derive_graph`). 합성기도 같은 함수를
쓰고, 정합성 검사는 원장에 적힌 값을 다시 유도해 대조한다.

**담보·익스포저 계약조건 원장이 따로 있는 이유.** [별표 3] 65.나(통화불일치)와
99.~101.(만기불일치)를 적용하려면 담보의 통화·원만기·잔존만기, 익스포저의
통화·잔존만기가 있어야 한다. `rdm_collateral`에는 통화도 만기도 없고,
`rdm_exposure`에도 통화가 없다. 없는 칸을 엔진이 지어내지 않도록 계약조건을
원장으로 분리하고, 합성한 칸은 `source='synthetic'`으로 표시한다.

**시드 오프셋 3300은 신규 전용이다.** 기존 스트림과 겹치면 무관한 산출이
바뀐다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec

__all__ = [
    "RELATION_TYPES", "COLLATERAL_TERMS", "EXPOSURE_TERMS", "COLLATERAL_LINK",
    "derive_graph", "build_baseline_links", "build_crm_link_universe",
]

_RNG_OFFSET = 3300          # 신규 전용. 기존 난수 스트림을 밀지 않는다

RELATION_TYPES: tuple[str, ...] = ("1:1", "1:N", "M:1", "M:N")

# 합성 관계 그래프의 블록 모양 (케이스, 담보 수, 익스포저 수).
# 규제값이 아니라 합성 데이터의 형태다. 네 케이스를 순환하며 채우므로 담보·
# 익스포저 공급량이 늘면 네 케이스가 함께 늘어난다.
_CASE_SHAPE: tuple[tuple[str, int, int], ...] = (
    ("1:1", 1, 1),
    ("1:N", 1, 3),
    ("M:1", 3, 1),
    ("M:N", 4, 3),
)

_CCY_POOL: tuple[str, ...] = ("KRW", "USD", "JPY", "EUR")
_FX_SHARE = 0.12            # 합성 비중. 통화불일치 경로가 실제로 타지도록 둔다


COLLATERAL_TERMS = TableSpec(
    name="crm_collateral_terms", korean="담보 계약조건", product="PRD-RWA",
    grain="기준일 × 담보 1건당 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("collateral_id", "string", "담보 식별자", nullable=False),
        C("collateral_type", "string", "담보 종류", nullable=False),
        C("ccy", "string", "담보 통화", nullable=False,
          citation="[별표 3] 65.나. 익스포저와 통화가 다르면 Hfx 적용"),
        C("market_value", "float", "시가", nullable=False, unit="KRW",
          min_value=0.0),
        C("haircut", "float", "담보차감률(Hc)", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0,
          citation="[별표 3] 65.가 담보차감률 표. rdm_collateral에서 그대로 가져온다"),
        C("original_maturity_years", "float", "원만기", nullable=True,
          unit="years", min_value=0.0,
          citation="[별표 3] 100.(1). 원만기 1년 미만이면 경감효과 불인정"),
        C("residual_maturity_years", "float", "잔존만기", nullable=True,
          unit="years", min_value=0.0,
          citation="[별표 3] 100.(2) · 101. 잔존만기 3개월 이하 불인정, "
                   "그 위는 (t-0.25)/(T-0.25)로 조정"),
        C("source", "string", "원천", nullable=False,
          allowed=("synthetic", "collateral_mgmt")),
    ),
    primary_key=("asof", "collateral_id"),
    foreign_keys=(FK(("collateral_id",), "rdm_collateral", ("collateral_id",)),),
    note="통화·만기는 rdm_collateral에 없어 합성한다. 시가·차감률은 rdm_collateral "
         "실측값을 그대로 옮긴다. 합성 칸과 실측 칸이 한 표에 섞이므로 source로 "
         "구분한다.",
)

EXPOSURE_TERMS = TableSpec(
    name="crm_exposure_terms", korean="CRM 산출 익스포저 조건", product="PRD-RWA",
    grain="기준일 × 익스포저 1건당 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("exposure_id", "string", "익스포저 식별자", nullable=False),
        C("ccy", "string", "익스포저 통화", nullable=False),
        C("ead", "float", "조정전 익스포저(E)", nullable=False, unit="KRW",
          min_value=0.0, citation="[별표 3] 62.의 E, 조정전 익스포저의 현재가치"),
        C("exposure_haircut", "float", "익스포저 차감률(He)", nullable=False,
          unit="ratio", min_value=0.0, max_value=1.0,
          citation="[별표 3] 65.다. He는 적격 금융자산담보요건 미충족 유가증권 "
                   "대여에만 30%가 붙는다. 은행계정 대출은 대상이 아니므로 0이다"),
        C("maturity_years", "float", "잔존만기", nullable=False, unit="years",
          min_value=0.0,
          citation="[별표 3] 99.나. 채무 변제 전까지 남은 최장기간"),
        C("risk_weight", "float", "위험가중치", nullable=False, unit="ratio",
          min_value=0.0, max_value=15.0,
          note="배분규칙 risk_weight_desc의 정렬 키이자 RWA 대사의 가중치"),
        C("source", "string", "원천", nullable=False,
          allowed=("synthetic", "core_banking")),
    ),
    primary_key=("asof", "exposure_id"),
    foreign_keys=(FK(("exposure_id",), "rdm_exposure", ("exposure_id",)),),
    note="통화만 합성이고 EAD·잔존만기·위험가중치는 기존 원장(rdm_exposure · "
         "rwa_result)에서 옮긴다.",
)

COLLATERAL_LINK = TableSpec(
    name="crm_collateral_link", korean="담보-익스포저 관계", product="PRD-RWA",
    grain="기준일 × 담보 × 익스포저 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("collateral_id", "string", "담보 식별자", nullable=False),
        C("exposure_id", "string", "익스포저 식별자", nullable=False),
        C("relation_type", "string", "관계 유형", nullable=False,
          allowed=RELATION_TYPES,
          note="링크 차수에서 유도한다. 담보 차수>1이면 1:N, 익스포저 차수>1이면 "
               "M:1, 둘 다 >1이면 M:N. 합성기가 붙인 라벨이 아니다"),
        C("pool_id", "string", "교차담보 풀", nullable=False,
          note="링크 그래프의 연결 성분. 배분은 성분 단위로 푼다"),
        C("priority", "int", "담보권 순위", nullable=False, min_value=1,
          note="링크별 선순위·후순위. 1이 선순위다. 배분 엔진은 익스포저 1건에 "
               "여러 담보가 걸린 경우 이 순위로 실행 순서를 정하고, 동순위는 "
               "collateral_id로 깨서 결정론을 지킨다"),
        C("coverage_ratio", "float", "설정 비율", nullable=False, unit="ratio",
          min_value=0.0, max_value=1.0,
          note="이 링크로 배분 가능한 담보 조정가치의 상한 비율. 포괄근담보는 "
               "여러 익스포저에 각각 전액(1.0) 설정되므로 담보별 합이 1을 "
               "넘을 수 있다. 실제 초과배분은 배분 엔진이 막는다"),
        C("source", "string", "원천", nullable=False,
          allowed=("synthetic", "collateral_mgmt")),
    ),
    primary_key=("asof", "collateral_id", "exposure_id"),
    foreign_keys=(FK(("collateral_id",), "rdm_collateral", ("collateral_id",)),
                  FK(("exposure_id",), "rdm_exposure", ("exposure_id",))),
    note="[별표 3] 102.가는 익스포저 1건에 여러 경감기법이 걸린 경우 각 경감기법이 "
         "적용되는 부분으로 구분해 개별 산출하라고 정한다. 그 '부분'을 만들려면 "
         "관계가 먼저 표로 있어야 한다.",
)


# ---------------------------------------------------------------- 그래프 유도

def _components(pairs: list[tuple[str, str]]) -> dict[str, str]:
    """이분 그래프의 연결 성분. 반환은 노드키('C:'/'E:' 접두) → pool_id.

    union-find를 직접 쓴다. 외부 그래프 라이브러리를 끌어오면 의존성이 늘고,
    성분 번호가 라이브러리 순회 순서에 따라 달라져 결정론이 깨진다.
    """
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for cid, eid in pairs:
        a, b = find(f"C:{cid}"), find(f"E:{eid}")
        if a != b:
            parent[a] = b

    # 성분 번호는 성분에 속한 최소 노드키 순으로 매긴다. 입력 행 순서가
    # 바뀌어도 같은 이름이 나온다.
    roots: dict[str, list[str]] = {}
    for node in parent:
        roots.setdefault(find(node), []).append(node)
    order = sorted(roots.items(), key=lambda kv: min(kv[1]))
    label = {root: f"POOL{i + 1:05d}" for i, (root, _) in enumerate(order)}
    return {node: label[find(node)] for node in parent}


def derive_graph(links: pd.DataFrame) -> pd.DataFrame:
    """링크 집합에서 `relation_type`·`pool_id`를 유도해 채운 사본을 돌려준다.

    입력에 두 컬럼이 이미 있어도 덮어쓴다. 원장에 적힌 라벨을 믿고 계산하면
    라벨이 틀렸을 때 배분도 함께 틀린다.
    """
    if links.empty:
        out = links.copy()
        out["relation_type"] = pd.Series(dtype="object")
        out["pool_id"] = pd.Series(dtype="object")
        return out

    df = links.copy()
    cid = df["collateral_id"].astype(str)
    eid = df["exposure_id"].astype(str)
    deg_c = cid.map(cid.value_counts())
    deg_e = eid.map(eid.value_counts())

    rel = np.where(
        (deg_c > 1) & (deg_e > 1), "M:N",
        np.where(deg_c > 1, "1:N",
                 np.where(deg_e > 1, "M:1", "1:1")))
    df["relation_type"] = rel

    comp = _components(list(zip(cid, eid)))
    df["pool_id"] = [comp[f"C:{c}"] for c in cid]
    return df


# ---------------------------------------------------------------- 빌더

def build_baseline_links(collateral: pd.DataFrame, *, asof: str) -> pd.DataFrame:
    """`rdm_collateral`의 1:1 매핑을 그대로 관계 원장으로 옮긴다.

    현행 산출(1:1만 다루던 상태)의 기준선이다. 확장 그래프로 갈아탄 뒤에도 이
    기준선으로 돌리면 같은 배분이 나와야 회귀가 없다고 말할 수 있다.
    """
    df = pd.DataFrame({
        "asof": asof,
        "collateral_id": collateral["collateral_id"].astype(str),
        "exposure_id": collateral["exposure_id"].astype(str),
        "priority": 1,
        "coverage_ratio": 1.0,
        "source": "collateral_mgmt",
    }).reset_index(drop=True)
    return derive_graph(df)[list(COLLATERAL_LINK.column_names)]


def build_crm_link_universe(
    exposure: pd.DataFrame,
    collateral: pd.DataFrame,
    rwa_result: pd.DataFrame,
    *,
    asof: str,
    seed: int,
) -> dict[str, pd.DataFrame]:
    """1:1 · 1:N · M:1 · M:N 네 케이스를 모두 포함한 합성 관계 그래프와
    담보·익스포저 계약조건 원장을 만든다.

    `seed`는 필수 인자다. 기본값을 주면 호출자가 시드를 넘기지 않아도 통과하고,
    파이프라인 시드와 다른 스트림이 조용히 섞인다.

    `rwa_result`가 필요한 이유: 배분규칙 `risk_weight_desc`의 정렬 키와 RWA
    대사의 가중치가 위험가중치다. 합성기가 위험가중치를 지어내면 대사가
    자기 자신과의 대사가 된다.
    """
    rng = np.random.default_rng(seed + _RNG_OFFSET)

    exp = exposure.drop_duplicates(subset=["exposure_id"]).copy()
    exp["exposure_id"] = exp["exposure_id"].astype(str)
    rwa = rwa_result.drop_duplicates(subset=["exposure_id"]).copy()
    rwa["exposure_id"] = rwa["exposure_id"].astype(str)
    rw = rwa.set_index("exposure_id")["risk_weight"].astype(float)
    exp = exp[exp["exposure_id"].isin(rw.index)].sort_values("exposure_id")
    exp = exp.reset_index(drop=True)

    col = (collateral.drop_duplicates(subset=["collateral_id"])
           .sort_values("collateral_id").reset_index(drop=True).copy())
    col["collateral_id"] = col["collateral_id"].astype(str)

    # ---- 계약조건: 없는 칸(통화·만기)만 합성한다 -------------------------
    n_e = len(exp)
    exp_ccy = np.where(rng.random(n_e) < _FX_SHARE,
                       rng.choice(_CCY_POOL[1:], n_e), _CCY_POOL[0])
    exposure_terms = pd.DataFrame({
        "asof": asof,
        "exposure_id": exp["exposure_id"],
        "ccy": exp_ccy,
        "ead": exp["ead"].to_numpy(dtype=float),
        # He는 은행계정 대출에 붙지 않는다(65.다). 0을 원장 칸으로 두는 이유는
        # 엔진이 기본값을 갖지 않게 하기 위해서다.
        "exposure_haircut": 0.0,
        "maturity_years": exp["maturity"].to_numpy(dtype=float),
        "risk_weight": exp["exposure_id"].map(rw).to_numpy(dtype=float),
        "source": "synthetic",
    })

    n_c = len(col)
    col_ccy = np.where(rng.random(n_c) < _FX_SHARE,
                       rng.choice(_CCY_POOL[1:], n_c), _CCY_POOL[0])
    # 원만기 하한 1년(100.(1))에 걸리는 담보가 실제로 섞이도록 0.5년부터 뽑는다.
    orig = rng.uniform(0.5, 8.0, n_c)
    resid = orig * rng.uniform(0.10, 1.00, n_c)
    collateral_terms = pd.DataFrame({
        "asof": asof,
        "collateral_id": col["collateral_id"],
        "collateral_type": col["collateral_type"].astype(str),
        "ccy": col_ccy,
        "market_value": col["market_value"].to_numpy(dtype=float),
        "haircut": col["haircut"].to_numpy(dtype=float),
        "original_maturity_years": orig,
        "residual_maturity_years": resid,
        "source": "synthetic",
    })

    # ---- 관계 그래프: 네 케이스를 순환하며 블록으로 채운다 -----------------
    cids = col["collateral_id"].tolist()
    eids = exp["exposure_id"].tolist()
    rows: list[dict] = []
    ci = ei = 0
    while True:
        progressed = False
        for _case, need_c, need_e in _CASE_SHAPE:
            if ci + need_c > len(cids) or ei + need_e > len(eids):
                continue
            block_c = cids[ci:ci + need_c]
            block_e = eids[ei:ei + need_e]
            ci += need_c
            ei += need_e
            progressed = True
            if need_c == 1 or need_e == 1:
                # 1:1 · 1:N · M:1. 블록 안의 담보와 익스포저를 전부 잇는다
                pairs = [(c, e) for c in block_c for e in block_e]
            else:
                # M:N. 사다리로 이어 붙여 연결 성분 하나가 되게 한다.
                # 담보 i를 익스포저 i와 i+1에 걸면 담보 차수·익스포저 차수가
                # 모두 2 이상이 되어 블록 전체가 M:N으로 유도된다.
                q = len(block_e)
                pairs = []
                for k, c in enumerate(block_c):
                    pairs.append((c, block_e[k % q]))
                    pairs.append((c, block_e[(k + 1) % q]))
                pairs = sorted(set(pairs))
            for c in block_c:
                own = [p for p in pairs if p[0] == c]
                # 담보권 순위는 같은 담보 안에서 유일해야 한다. 난수 순열로
                # 정하되 시드가 같으면 같은 순열이 나온다.
                order = rng.permutation(len(own))
                for rank, (_c, e) in zip(order, own):
                    rows.append({
                        "asof": asof, "collateral_id": c, "exposure_id": e,
                        "priority": int(rank) + 1,
                        "coverage_ratio": float(round(
                            0.5 + 0.5 * rng.random(), 4)),
                        "source": "synthetic",
                    })
        if not progressed:
            break

    links = pd.DataFrame(rows, columns=["asof", "collateral_id", "exposure_id",
                                        "priority", "coverage_ratio", "source"])
    links = links.sort_values(["collateral_id", "exposure_id"]).reset_index(drop=True)
    links = derive_graph(links)[list(COLLATERAL_LINK.column_names)]

    # 링크에 걸리지 않은 담보·익스포저는 계약조건 원장에서도 뺀다. 참조되지
    # 않는 행을 남기면 총량 검사에서 분모가 어긋난다.
    used_c = set(links["collateral_id"])
    used_e = set(links["exposure_id"])
    return {
        "crm_collateral_terms": collateral_terms[
            collateral_terms["collateral_id"].isin(used_c)].reset_index(drop=True),
        "crm_exposure_terms": exposure_terms[
            exposure_terms["exposure_id"].isin(used_e)].reset_index(drop=True),
        "crm_collateral_link": links,
    }
