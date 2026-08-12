"""파일·API·배치 수신 표준화 (INT-002).

원천이 파일이든 API이든 배치이든, 받은 것이 무엇이었는지는 같은 방식으로
기록돼야 한다. 스키마가 맞았는지, 기준일이 맞았는지, 내용이 앞 회차와 같은지를
수신 시점에 판정하지 않으면 산출 뒤에 원인을 되짚을 근거가 남지 않는다.

원장 두 장과 판정 한 개로 구성한다.

  int_inbound_contract  피드별 수신 계약(형식·필수 컬럼·기준일 컬럼·주기)
  int_inbound_delivery  피드 x 기준일 x 회차 수신 결과와 체크섬

판정은 fail-closed다. 계약이 없는 피드는 '계약없음'이고 정상으로 넘기지 않는다.
필수 컬럼 결손·기준일 불일치·행수 0은 각각 다른 상태로 남긴다. 하나로 뭉치면
무엇을 고쳐야 하는지가 사라진다.

체크섬은 hashlib.sha256이다. 파이썬 내장 hash()는 프로세스마다 솔트가 달라
같은 파일이 회차마다 다른 값을 낸다. 컬럼 순서를 정렬해 넣는 이유는 원천이
컬럼 순서를 바꿔 보내도 내용이 같으면 같은 값이 나와야 하기 때문이다.

이 모듈의 TableSpec은 아직 datamodel.catalog에 등재하지 않았다. 등재는 실체화
검증과 문서 수치 일치를 함께 만족해야 하므로 배선 단계에서 `SPECS`를 넘긴다.

참조: RYNTA BRD INT-002(파일·API·배치 연계) · DAT-004(원천 스냅샷),
BCBS 239 원칙 3(정확성·무결성) · 원칙 7(정확성).
"""

from __future__ import annotations

import hashlib

import pandas as pd

from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec

FORMATS = ("CSV", "XLSX", "Parquet", "REST API", "DB batch")
FREQUENCIES = ("일별", "월별", "분기별", "수시")
DELIVERY_STATUSES = ("정상", "스키마불일치", "기준일불일치", "행수0", "미수신",
                     "계약없음")


# ---------------------------------------------------------------- 스펙

INBOUND_CONTRACT = TableSpec(
    name="int_inbound_contract", korean="수신 계약", product="PRD-RDM",
    grain="피드 1개당 1행",
    columns=(
        C("feed_id", "string", "피드 식별자", nullable=False),
        C("connector_id", "string", "커넥터 식별자", nullable=False),
        C("feed_name", "text", "피드명", nullable=False),
        C("data_format", "string", "형식", nullable=False, allowed=FORMATS),
        C("required_columns", "text", "필수 컬럼", nullable=False,
          note="쉼표로 구분. 이 목록이 수신 판정의 기준이다"),
        C("asof_column", "string", "기준일 컬럼", nullable=True,
          note="기준일 컬럼이 없는 피드는 NULL이며 기준일 검사를 건너뛴다"),
        C("frequency", "string", "수신 주기", nullable=False,
          allowed=FREQUENCIES),
        C("checksum_algo", "string", "체크섬 방식", nullable=False),
        C("owner_role", "text", "수신 소유 역할", nullable=False),
    ),
    primary_key=("feed_id",),
    foreign_keys=(FK(("connector_id",), "int_connector", ("connector_id",)),),
)

INBOUND_DELIVERY = TableSpec(
    name="int_inbound_delivery", korean="수신 결과", product="PRD-RDM",
    grain="피드 x 기준일 x 회차 1건당 1행",
    columns=(
        C("feed_id", "string", "피드 식별자", nullable=False),
        C("asof", "date", "기준일자", nullable=False),
        C("batch_seq", "int", "회차", nullable=False, unit="count", min_value=1),
        C("received_on", "date", "수신일", nullable=True,
          note="미수신 건은 NULL이다"),
        C("n_rows", "int", "행수", nullable=False, unit="count", min_value=0),
        C("n_columns", "int", "컬럼수", nullable=False, unit="count",
          min_value=0),
        C("checksum", "text", "내용 체크섬", nullable=False),
        C("status", "string", "수신 상태", nullable=False,
          allowed=DELIVERY_STATUSES),
        C("detail", "text", "판정 내용", nullable=False),
    ),
    primary_key=("feed_id", "asof", "batch_seq"),
)

SPECS: tuple[TableSpec, ...] = (INBOUND_CONTRACT, INBOUND_DELIVERY)


# ---------------------------------------------------------------- 계약 적재
#
# 이 표가 이 모듈의 유일한 적재 지점이다. 판정 함수는 표를 직접 읽지 않고
# 인자로 받은 DataFrame만 본다.

_ALGO = "sha256"

# (피드ID, 커넥터ID, 피드명, 형식, 필수컬럼, 기준일컬럼, 주기, 소유역할)
_CONTRACTS = (
    ("FD-EXP", "CN-COR", "익스포저 원장", "DB batch",
     "exposure_id,counterparty_id,ead,asof", "asof", "월별",
     "리스크데이터관리자"),
    ("FD-CPT", "CN-COR", "거래상대 원장", "DB batch",
     "counterparty_id,industry,rating,asof", "asof", "월별",
     "리스크데이터관리자"),
    ("FD-GL", "CN-FIN", "총계정원장 잔액", "CSV",
     "account_code,balance,asof", "asof", "월별", "재무담당"),
    ("FD-RWA", "CN-RSK", "기존엔진 RWA 산출값", "CSV",
     "portfolio,rwa,asof", "asof", "분기별", "리스크관리책임자"),
    ("FD-DOC", "CN-DOC", "규정 원문 발췌", "REST API",
     "document_id,clause,text", None, "수시", "적합성검증담당"),
)


def build_inbound_contracts() -> pd.DataFrame:
    return pd.DataFrame([{
        "feed_id": c[0], "connector_id": c[1], "feed_name": c[2],
        "data_format": c[3], "required_columns": c[4], "asof_column": c[5],
        "frequency": c[6], "checksum_algo": _ALGO, "owner_role": c[7],
    } for c in _CONTRACTS],
        columns=[c.name for c in INBOUND_CONTRACT.columns])


# ---------------------------------------------------------------- 체크섬

def payload_checksum(payload: pd.DataFrame) -> str:
    """수신분의 내용 지문. 같은 내용이면 같은 값이 나와야 한다.

    컬럼을 정렬해 넣으므로 원천이 컬럼 순서만 바꿔 보내도 값이 흔들리지 않는다.
    행 순서는 정렬하지 않는다. 행 순서가 바뀐 것은 내용이 바뀐 것으로 보고
    수신자가 확인해야 할 사건이다.
    """
    h = hashlib.sha256()
    h.update(_ALGO.encode("utf-8"))
    cols = sorted(map(str, payload.columns))
    h.update(",".join(cols).encode("utf-8"))
    h.update(str(payload.shape).encode("utf-8"))
    if len(payload):
        h.update(payload[cols].to_csv(index=False).encode("utf-8"))
    return h.hexdigest()


# ---------------------------------------------------------------- 판정

def verify_delivery(contracts: pd.DataFrame, feed_id: str,
                    payload: pd.DataFrame | None, *, asof: str,
                    batch_seq: int = 1, received_on: str | None = None) -> dict:
    """수신 1건을 계약과 대조해 판정한다.

    payload가 None이면 '미수신'이다. 미수신도 수신 결과이므로 행을 남긴다.
    기록하지 않으면 '안 왔다'와 '아직 안 봤다'가 같아진다.

    상태 우선순위는 계약없음 > 미수신 > 스키마불일치 > 기준일불일치 > 행수0 >
    정상이다. 스키마가 틀린 수신분의 기준일을 따지는 것은 의미가 없다.
    """
    hit = contracts[contracts["feed_id"] == feed_id]
    if hit.empty:
        return {"feed_id": feed_id, "asof": asof, "batch_seq": int(batch_seq),
                "received_on": received_on, "n_rows": 0, "n_columns": 0,
                "checksum": "", "status": "계약없음",
                "detail": f"수신 계약에 피드 {feed_id} 가 없다"}
    contract = hit.iloc[0]
    if payload is None:
        return {"feed_id": feed_id, "asof": asof, "batch_seq": int(batch_seq),
                "received_on": None, "n_rows": 0, "n_columns": 0,
                "checksum": "", "status": "미수신",
                "detail": f"{contract['frequency']} 주기 피드의 수신분이 없다"}

    base = {"feed_id": feed_id, "asof": asof, "batch_seq": int(batch_seq),
            "received_on": received_on, "n_rows": int(len(payload)),
            "n_columns": int(payload.shape[1]),
            "checksum": payload_checksum(payload)}

    required = [c.strip() for c in str(contract["required_columns"]).split(",")
                if c.strip()]
    missing = [c for c in required if c not in payload.columns]
    if missing:
        return {**base, "status": "스키마불일치",
                "detail": f"필수 컬럼 결손: {', '.join(missing)}"}

    asof_col = contract["asof_column"]
    if asof_col is not None and not pd.isna(asof_col):
        values = sorted({str(v) for v in payload[asof_col].tolist()})
        off = [v for v in values if v != asof]
        if off:
            return {**base, "status": "기준일불일치",
                    "detail": f"기준일 {asof} 아닌 값 {len(off)}종: "
                              f"{', '.join(off[:3])}"}

    if len(payload) == 0:
        return {**base, "status": "행수0",
                "detail": "스키마·기준일은 맞으나 행이 없다"}
    return {**base, "status": "정상",
            "detail": f"필수 컬럼 {len(required)}개 충족, 기준일 일치"}


def build_inbound_deliveries(contracts: pd.DataFrame, payloads: dict, *,
                             asof: str, received_on: str | None = None
                             ) -> pd.DataFrame:
    """계약에 등록된 전 피드의 수신 결과를 만든다.

    payloads는 feed_id → DataFrame 이며 없는 피드는 '미수신'으로 남는다.
    계약에 없는 피드가 payloads에 있으면 '계약없음'으로 함께 남긴다.
    """
    rows = []
    for feed_id in contracts["feed_id"]:
        rows.append(verify_delivery(contracts, feed_id, payloads.get(feed_id),
                                    asof=asof, received_on=received_on))
    extra = sorted(set(payloads) - set(contracts["feed_id"]))
    for feed_id in extra:
        rows.append(verify_delivery(contracts, feed_id, payloads[feed_id],
                                    asof=asof, received_on=received_on))
    return pd.DataFrame(rows, columns=[c.name for c in INBOUND_DELIVERY.columns]
                        ).astype({"n_rows": "int64", "n_columns": "int64",
                                  "batch_seq": "int64"})


def build_inbound(payloads: dict, *, asof: str, received_on: str | None = None
                  ) -> dict[str, pd.DataFrame]:
    """수신 원장 2장을 만든다."""
    contracts = build_inbound_contracts()
    return {"int_inbound_contract": contracts,
            "int_inbound_delivery": build_inbound_deliveries(
                contracts, payloads, asof=asof, received_on=received_on)}
