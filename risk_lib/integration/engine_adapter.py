"""계산엔진 어댑터 (INT-003).

기존 RWA·ECL·NCR·Pricing·ALM 엔진의 산출값을 받아 쓰려면, 그 엔진이 무엇을
입력으로 받고 무엇을 내놓으며 어느 판본이었는지가 표준 형식으로 남아야 한다.
같은 이름의 산출값이 어느 판 엔진에서 나왔는지 모르면 대사 결과를 해석할 수
없다.

원장 두 장과 판정 한 개로 구성한다.

  int_engine_adapter  엔진 1개당 등록 정보(모듈 경로·판본·주기)
  int_engine_io       엔진 x 방향(입력·출력) x 원장

판정은 fail-closed다. 필수 입력 원장이 실행 결과에 없으면 그 엔진은 '실행불가'다.
선언하지 않은 원장을 내놓아도 남긴다. 선언 밖 산출물은 계보에서 추적되지 않는다.

판본은 엔진 모듈이 스스로 밝히는 값을 쓴다. 이 원장이 판본을 정하지 않는다.
모듈에 판본 표기가 없으면 NULL이며, 그 사실이 화면에 드러나야 한다.

이 모듈의 TableSpec은 아직 datamodel.catalog에 등재하지 않았다. 등재는 실체화
검증과 문서 수치 일치를 함께 만족해야 하므로 배선 단계에서 `SPECS`를 넘긴다.

참조: RYNTA BRD INT-003(계산엔진 Adapter) · PLT-004(Calculation & Validation),
BCBS 239 원칙 3(정확성·무결성).
"""

from __future__ import annotations

import pandas as pd

from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec

DIRECTIONS = ("입력", "출력")
ENGINE_DOMAINS = ("자본", "충당금", "증권", "시장", "ALM")
RUN_STATUSES = ("실행가능", "실행불가", "출력누락")


# ---------------------------------------------------------------- 스펙

ENGINE_ADAPTER = TableSpec(
    name="int_engine_adapter", korean="계산엔진 어댑터", product="PRD-VAL",
    grain="엔진 1개당 1행",
    columns=(
        C("engine_id", "string", "엔진 식별자", nullable=False),
        C("engine_name", "text", "엔진명", nullable=False),
        C("domain", "string", "도메인", nullable=False, allowed=ENGINE_DOMAINS),
        C("module_path", "text", "모듈 경로", nullable=False),
        C("engine_version", "text", "엔진 판본", nullable=True,
          note="모듈이 밝히는 값. 표기가 없으면 NULL이며 지어내지 않는다"),
        C("owner_role", "text", "엔진 소유 역할", nullable=False),
    ),
    primary_key=("engine_id",),
)

ENGINE_IO = TableSpec(
    name="int_engine_io", korean="엔진 입출력 선언", product="PRD-VAL",
    grain="엔진 x 방향 x 원장 1건당 1행",
    columns=(
        C("engine_id", "string", "엔진 식별자", nullable=False),
        C("direction", "string", "방향", nullable=False, allowed=DIRECTIONS),
        C("table_name", "string", "원장명", nullable=False),
        C("required", "bool", "필수 여부", nullable=False),
    ),
    primary_key=("engine_id", "direction", "table_name"),
    foreign_keys=(FK(("engine_id",), "int_engine_adapter", ("engine_id",)),),
)

SPECS: tuple[TableSpec, ...] = (ENGINE_ADAPTER, ENGINE_IO)


# ---------------------------------------------------------------- 등록 적재
#
# 이 표가 이 모듈의 유일한 적재 지점이다. 판정 함수는 표를 직접 읽지 않고
# 인자로 받은 DataFrame만 본다.
#
# 판본을 전건 NULL로 두는 이유. 이 저장소의 엔진 모듈은 판본 상수를 노출하지
# 않는다. 코드 리비전(gov_unified_run.code_revision)이 실행 단위 판본을
# 대신하며, 엔진 단위 판본은 모듈이 그것을 밝히기 전까지 비어 있다.

# (엔진ID, 엔진명, 도메인, 모듈경로, 소유역할,
#  ((방향, 원장명, 필수여부), …))
_ENGINES = (
    ("EN-RWA", "위험가중자산 산출", "자본", "risk_lib.capital.rwa_irb",
     "신용리스크관리자",
     (("입력", "exposure", True), ("입력", "counterparty", True),
      ("출력", "rwa_detail", True))),
    ("EN-ECL", "기대신용손실 산출", "충당금", "risk_lib.provisioning.ecl",
     "충당금담당",
     (("입력", "exposure", True), ("입력", "macro_scenario", True),
      ("출력", "ecl_detail", True))),
    ("EN-NCR", "순자본비율 산출", "증권", "risk_lib.ncr", "증권리스크담당",
     (("입력", "ncr_position", True), ("출력", "ncr_result", True))),
    ("EN-ALM", "금리리스크 ΔEVE·ΔNII", "ALM", "risk_lib.alm.kr_irrbb",
     "ALM담당",
     (("입력", "alm_contract", True), ("입력", "irrbb_shock", True),
      ("출력", "irrbb_delta_eve", True), ("출력", "irrbb_delta_nii", True))),
    ("EN-MKT", "시장리스크 민감도·VaR", "시장", "risk_lib.sensitivities",
     "시장리스크관리자",
     (("입력", "market_position", True), ("출력", "market_sensitivity", True))),
)


def build_engine_adapters() -> pd.DataFrame:
    return pd.DataFrame([{
        "engine_id": e[0], "engine_name": e[1], "domain": e[2],
        "module_path": e[3], "engine_version": None, "owner_role": e[4],
    } for e in _ENGINES], columns=[c.name for c in ENGINE_ADAPTER.columns])


def build_engine_io() -> pd.DataFrame:
    rows = []
    for engine in _ENGINES:
        for direction, table_name, required in engine[5]:
            rows.append({"engine_id": engine[0], "direction": direction,
                         "table_name": table_name, "required": bool(required)})
    return pd.DataFrame(rows, columns=[c.name for c in ENGINE_IO.columns]
                        ).astype({"required": "bool"})


# ---------------------------------------------------------------- 판정

def check_engine_io(adapters: pd.DataFrame, io: pd.DataFrame,
                    available_tables) -> pd.DataFrame:
    """선언한 입출력이 실제 원장과 맞는지 본다.

    available_tables는 실행이 실제로 만들어 낸 원장명의 집합이다.
    엔진별로 상태를 하나 돌려준다.

      실행불가   필수 입력 원장이 없다
      출력누락   입력은 있으나 선언한 필수 출력 중 일부가 결과에 없다
      실행가능   필수 입력이 전부 있고 선언한 출력이 전부 나왔다
    """
    have = set(available_tables)
    rows = []
    for engine_id in adapters["engine_id"]:
        decl = io[io["engine_id"] == engine_id]
        need_in = decl[(decl["direction"] == "입력") & decl["required"]]
        need_out = decl[(decl["direction"] == "출력") & decl["required"]]
        missing_in = sorted(set(need_in["table_name"]) - have)
        missing_out = sorted(set(need_out["table_name"]) - have)
        if missing_in:
            status, detail = "실행불가", f"필수 입력 원장 결손: {', '.join(missing_in)}"
        elif missing_out:
            status, detail = "출력누락", f"선언한 출력 미생성: {', '.join(missing_out)}"
        else:
            status, detail = "실행가능", (
                f"입력 {len(need_in)}장 · 출력 {len(need_out)}장 충족")
        rows.append({"engine_id": engine_id, "status": status, "detail": detail,
                     "n_missing_input": len(missing_in),
                     "n_missing_output": len(missing_out)})
    return pd.DataFrame(rows, columns=["engine_id", "status", "detail",
                                       "n_missing_input", "n_missing_output"])


def build_engine_adapter() -> dict[str, pd.DataFrame]:
    """엔진 어댑터 원장 2장을 만든다."""
    return {"int_engine_adapter": build_engine_adapters(),
            "int_engine_io": build_engine_io()}
