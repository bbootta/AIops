"""조회 전용 보안 커넥터 (INT-001).

리스크 산출 플랫폼이 계정계·정보계에 쓰기 권한을 들고 붙으면, 산출 오류가
원장 오류가 된다. 조회 전용이라는 약속은 등록된 오퍼레이션 목록으로 확인돼야
한다. `agent_registry`가 에이전트의 write_allowed를 전건 false로 두고 검사하는
것과 같은 구조를, 시스템 연계 계층에도 둔다.

원장 세 장과 판정 한 개로 구성한다.

  int_connector            연결 대상 시스템과 접근 모드
  int_connector_operation  커넥터 x 오퍼레이션과 동사(read·write·delete)
  int_connector_violation  조회 전용 위반 판정 결과

판정은 fail-closed다. 등록되지 않은 커넥터를 참조하는 오퍼레이션은 위반이며,
접근 모드가 '조회전용'인데 read가 아닌 동사가 붙으면 위반이다. 위반이 없다는
것은 위반 원장이 비어 있는 것으로 표현되고, 검사하지 않은 것과 구분된다.

현재 연결 상태는 전건 '미연결'이다. 이 저장소는 외부 시스템과 통신하지 않는다.
연결하지 않았다는 사실을 원장에 남기지 않으면 합성 데이터가 원천 데이터로
읽힌다.

이 모듈의 TableSpec은 아직 datamodel.catalog에 등재하지 않았다. 등재는 실체화
검증과 문서 수치 일치를 함께 만족해야 하므로 배선 단계에서 `SPECS`를 넘긴다.

참조: RYNTA BRD INT-001(Read-only Secure Connector) · PLT-001(Secure Connectors),
전자금융감독규정 제13조(전산자료 접근통제).
"""

from __future__ import annotations

import pandas as pd

from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec

SOURCE_DOMAINS = ("계정계", "정보계", "리스크", "재무", "문서", "시장데이터")
PROTOCOLS = ("DB 조회", "REST", "SFTP 파일", "메시지큐", "수기 입력")
ACCESS_MODES = ("조회전용", "쓰기포함")
CONNECTION_STATUSES = ("연결", "미연결", "중단")
VERBS = ("read", "write", "delete")
VIOLATION_KINDS = ("미등록 커넥터", "조회전용 위반", "접근모드 미승인")


# ---------------------------------------------------------------- 스펙

CONNECTOR = TableSpec(
    name="int_connector", korean="보안 커넥터", product="PRD-RDM",
    grain="커넥터 1개당 1행",
    columns=(
        C("connector_id", "string", "커넥터 식별자", nullable=False),
        C("system_name", "text", "연결 대상 시스템", nullable=False),
        C("source_domain", "string", "원천 구분", nullable=False,
          allowed=SOURCE_DOMAINS),
        C("protocol", "string", "연계 방식", nullable=False, allowed=PROTOCOLS),
        C("access_mode", "string", "접근 모드", nullable=False,
          allowed=ACCESS_MODES),
        C("connection_status", "string", "연결 상태", nullable=False,
          allowed=CONNECTION_STATUSES),
        C("fallback", "text", "미연결 시 대체 경로", nullable=False),
        C("owner_role", "text", "연계 소유 역할", nullable=False),
        C("citation", "text", "근거", nullable=False),
    ),
    primary_key=("connector_id",),
    note="접근 모드를 원장에 두는 이유는, 쓰기 권한을 요구한 커넥터가 있었는지 "
         "그리고 그것이 승인됐는지를 감사에서 되짚기 위해서다.",
)

CONNECTOR_OPERATION = TableSpec(
    name="int_connector_operation", korean="커넥터 오퍼레이션", product="PRD-RDM",
    grain="커넥터 x 오퍼레이션 1건당 1행",
    columns=(
        C("connector_id", "string", "커넥터 식별자", nullable=False),
        C("operation", "string", "오퍼레이션", nullable=False),
        C("verb", "string", "동사", nullable=False, allowed=VERBS),
        C("target_object", "text", "대상 객체", nullable=False),
        C("purpose", "text", "사용 목적", nullable=False),
    ),
    primary_key=("connector_id", "operation"),
    foreign_keys=(FK(("connector_id",), "int_connector", ("connector_id",)),),
)

CONNECTOR_VIOLATION = TableSpec(
    name="int_connector_violation", korean="커넥터 접근통제 위반",
    product="PRD-RDM",
    grain="위반 1건당 1행",
    columns=(
        C("connector_id", "string", "커넥터 식별자", nullable=False),
        C("operation", "string", "오퍼레이션", nullable=False),
        C("violation_kind", "string", "위반 구분", nullable=False,
          allowed=VIOLATION_KINDS),
        C("detail", "text", "위반 내용", nullable=False),
    ),
    primary_key=("connector_id", "operation", "violation_kind"),
)

SPECS: tuple[TableSpec, ...] = (CONNECTOR, CONNECTOR_OPERATION,
                                CONNECTOR_VIOLATION)


# ---------------------------------------------------------------- 등록 적재
#
# 이 표가 이 모듈의 유일한 적재 지점이다. 판정 함수는 표를 직접 읽지 않고
# 인자로 받은 DataFrame만 본다.

_FALLBACK_SYNTH = "risk_lib.data_gen 합성 데이터. 출처가 '합성'으로 찍힌다"

# (커넥터ID, 시스템, 원천구분, 방식, 접근모드, 대체경로, 소유역할, 근거)
_CONNECTORS = (
    ("CN-COR", "계정계 여수신 원장", "계정계", "DB 조회", "조회전용",
     _FALLBACK_SYNTH, "리스크데이터관리자",
     "익스포저·잔액·계약조건의 원천. 연계 사양 미확정"),
    ("CN-DWH", "정보계 데이터웨어하우스", "정보계", "DB 조회", "조회전용",
     _FALLBACK_SYNTH, "리스크데이터관리자",
     "이력·집계의 원천. 연계 사양 미확정"),
    ("CN-RSK", "기존 리스크엔진 산출결과", "리스크", "SFTP 파일", "조회전용",
     _FALLBACK_SYNTH, "리스크관리책임자",
     "RWA·ECL 기존 산출값 대사용. 연계 사양 미확정"),
    ("CN-FIN", "재무회계 총계정원장", "재무", "DB 조회", "조회전용",
     _FALLBACK_SYNTH, "재무담당",
     "충당금·자본의 회계 대사 대상. 연계 사양 미확정"),
    ("CN-DOC", "규정·모형 문서 저장소", "문서", "REST", "조회전용",
     "docs/primary_sources 수기 발췌", "적합성검증담당",
     "규정 원문·모형 문서의 원천. 연계 사양 미확정"),
)

# (커넥터ID, 오퍼레이션, 동사, 대상객체, 목적)
_OPERATIONS = (
    ("CN-COR", "list_accounts", "read", "여수신 계좌", "익스포저 적재"),
    ("CN-COR", "get_contract_terms", "read", "계약조건", "현금흐름 산출"),
    ("CN-DWH", "query_snapshot", "read", "기준일 스냅샷", "판별 적재"),
    ("CN-RSK", "fetch_result_file", "read", "산출결과 파일", "대사"),
    ("CN-FIN", "query_gl_balance", "read", "총계정원장 잔액", "회계 대사"),
    ("CN-DOC", "get_document", "read", "규정·모형 문서", "근거 인용"),
)


def build_connectors() -> pd.DataFrame:
    """커넥터 등록부. 연결 상태는 전건 '미연결'이다.

    이 저장소는 외부 시스템과 통신하지 않는다. 상태를 '연결'로 적으면
    원장이 사실과 달라진다.
    """
    return pd.DataFrame([{
        "connector_id": c[0], "system_name": c[1], "source_domain": c[2],
        "protocol": c[3], "access_mode": c[4], "connection_status": "미연결",
        "fallback": c[5], "owner_role": c[6], "citation": c[7],
    } for c in _CONNECTORS], columns=[c.name for c in CONNECTOR.columns])


def build_connector_operations() -> pd.DataFrame:
    return pd.DataFrame([{
        "connector_id": o[0], "operation": o[1], "verb": o[2],
        "target_object": o[3], "purpose": o[4],
    } for o in _OPERATIONS],
        columns=[c.name for c in CONNECTOR_OPERATION.columns])


# ---------------------------------------------------------------- 판정

def check_read_only(connectors: pd.DataFrame, operations: pd.DataFrame,
                    approved_write: tuple[str, ...] = ()) -> pd.DataFrame:
    """조회 전용 약속이 지켜지는지 검사한다.

    위반 세 가지를 본다.
      미등록 커넥터   오퍼레이션이 등록되지 않은 커넥터를 참조한다
      조회전용 위반   접근 모드가 '조회전용'인데 read가 아닌 동사가 붙었다
      접근모드 미승인 접근 모드가 '쓰기포함'인데 승인 목록에 없다

    approved_write는 쓰기 권한을 승인받은 커넥터 식별자다. 비워 두면 쓰기포함
    커넥터가 전부 위반이 된다. 기본을 '승인 없음'으로 두는 이유는, 승인
    목록을 빠뜨린 상태가 통과로 읽히면 안 되기 때문이다.
    """
    mode = connectors.set_index("connector_id")["access_mode"].to_dict()
    rows = []
    for op in operations.to_dict("records"):
        cid, name, verb = op["connector_id"], op["operation"], op["verb"]
        if cid not in mode:
            rows.append((cid, name, "미등록 커넥터",
                         f"오퍼레이션 {name} 이 등록되지 않은 커넥터를 참조한다"))
            continue
        if mode[cid] == "조회전용" and verb != "read":
            rows.append((cid, name, "조회전용 위반",
                         f"접근 모드 조회전용인데 동사가 {verb} 다"))
    for cid, access_mode in sorted(mode.items()):
        if access_mode == "쓰기포함" and cid not in approved_write:
            rows.append((cid, "*", "접근모드 미승인",
                         "쓰기포함 커넥터가 승인 목록에 없다"))
    return pd.DataFrame(rows,
                        columns=[c.name for c in CONNECTOR_VIOLATION.columns])


def build_connector_control(approved_write: tuple[str, ...] = ()
                            ) -> dict[str, pd.DataFrame]:
    """커넥터 원장 3장을 만든다."""
    connectors = build_connectors()
    operations = build_connector_operations()
    return {"int_connector": connectors,
            "int_connector_operation": operations,
            "int_connector_violation": check_read_only(
                connectors, operations, approved_write)}
