"""시장데이터 외부 피드 어댑터 (INT-004).

이 저장소의 시장데이터는 전부 합성이다(risk_lib.market_data.demo_market_data).
합성이라는 사실 자체는 문제가 아니지만, **어디서 받아야 할 데이터인지**와
**지금 받고 있지 않다는 상태**가 원장에 없으면 화면의 커브가 실제 시세인 것처럼
읽힌다.

어댑터 인터페이스와 상태 원장 세 장을 만든다.

  int_market_feed     받아야 할 외부 피드와 현재 연결 상태
  int_feed_field_map  피드 필드 x 표준 리스크팩터 매핑
  int_feed_health     기준일별 수신 상태와 대체 경로

연결이 없으면 `UnconnectedFeedAdapter`가 빈 결과와 사유를 돌려준다. 산출은
멈추지 않고 합성 대체 경로로 넘어가되, 그때 만들어진 값에는 출처가 '합성'으로
찍힌다. 조용히 대체하면 화면이 사실을 잃는다.

이 모듈은 외부 통신을 하지 않는다. 실제 연결 계층은 이 저장소 밖이며, 여기서
정의하는 것은 인터페이스와 상태 기록이다.

이 모듈의 TableSpec은 아직 datamodel.catalog에 등재하지 않았다. 등재는 실체화
검증과 문서 수치 일치를 함께 만족해야 하므로 배선 단계에서 `SPECS`를 넘긴다.
스펙 품질 기준(입도·기본키·float 단위·FK 대상 존재)은 지금부터 지킨다.

참조: RYNTA BRD INT-004(시장데이터 Adapter) · SEC-PRC-001(시장데이터),
BCBS 239 원칙 3(정확성) · 원칙 7(정확성·보고).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import pandas as pd

from risk_lib.alm.params import EVIDENCE_STATUS
from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec

FEED_KINDS = ("거래소 시세", "채권평가사", "브로커 호가", "중앙은행 공시",
              "내부 산출")
PROTOCOLS = ("REST", "FIX", "SFTP 파일", "수기 입력")
CONNECTION_STATUSES = ("연결", "미연결", "중단")
DATA_SOURCES = ("외부피드", "합성", "미수신")
HEALTH_STATUSES = ("정상", "미연결", "지연", "부분수신")


MARKET_FEED = TableSpec(
    name="int_market_feed", korean="시장데이터 피드", product="PRD-MKT",
    grain="외부 피드 1개당 1행",
    columns=(
        C("feed_id", "string", "피드 식별자", nullable=False),
        C("feed_name", "text", "피드 명칭", nullable=False),
        C("feed_kind", "string", "피드 구분", nullable=False, allowed=FEED_KINDS),
        C("protocol", "string", "연계 방식", nullable=False, allowed=PROTOCOLS),
        C("factor_scope", "text", "대상 리스크팩터", nullable=False),
        C("expected_factors", "int", "기대 팩터 수", nullable=False, unit="count",
          min_value=1),
        C("publish_time", "text", "공표 시각", nullable=False),
        C("connection_status", "string", "연결 상태", nullable=False,
          allowed=CONNECTION_STATUSES),
        C("last_sync", "date", "최종 수신일", nullable=True,
          note="연결된 적이 없으면 NULL이다"),
        C("fallback_source", "string", "대체 경로", nullable=False,
          allowed=DATA_SOURCES),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("feed_id",),
    note="연결 상태가 '미연결'이면 이 피드로 산출된 값은 전부 대체 경로 산물이다.",
)

FEED_FIELD_MAP = TableSpec(
    name="int_feed_field_map", korean="피드 필드 매핑", product="PRD-MKT",
    grain="피드 x 외부 필드 1건당 1행",
    columns=(
        C("feed_id", "string", "피드 식별자", nullable=False),
        C("external_field", "text", "외부 필드명", nullable=False),
        C("canonical_factor", "string", "표준 리스크팩터", nullable=False),
        C("unit", "string", "단위", nullable=False),
        C("transform", "text", "변환 규칙", nullable=False),
    ),
    primary_key=("feed_id", "external_field"),
    foreign_keys=(FK(("feed_id",), "int_market_feed", ("feed_id",)),),
    note="매핑이 없으면 외부 필드가 들어와도 표준 팩터로 옮길 수 없다.",
)

FEED_HEALTH = TableSpec(
    name="int_feed_health", korean="피드 수신 상태", product="PRD-MKT",
    grain="피드 x 기준일 1건당 1행",
    columns=(
        C("feed_id", "string", "피드 식별자", nullable=False),
        C("asof", "date", "기준일", nullable=False),
        C("expected_factors", "int", "기대 팩터 수", nullable=False, unit="count",
          min_value=0),
        C("received_factors", "int", "수신 팩터 수", nullable=False, unit="count",
          min_value=0),
        C("staleness_days", "float", "최종 수신 후 경과", nullable=True,
          unit="days", min_value=0.0,
          note="수신 이력이 없으면 NULL이다. 0으로 적으면 방금 받은 것으로 읽힌다"),
        C("data_source", "string", "실제 사용 출처", nullable=False,
          allowed=DATA_SOURCES),
        C("status", "string", "수신 상태", nullable=False, allowed=HEALTH_STATUSES),
        C("reason", "text", "사유", nullable=False),
    ),
    primary_key=("feed_id", "asof"),
    foreign_keys=(FK(("feed_id",), "int_market_feed", ("feed_id",)),),
)

SPECS: tuple[TableSpec, ...] = (MARKET_FEED, FEED_FIELD_MAP, FEED_HEALTH)


# ---------------------------------------------------------------- 어댑터

@runtime_checkable
class MarketFeedAdapter(Protocol):
    """외부 시장데이터 피드 어댑터.

    fetch는 (데이터, 사유)를 돌려준다. 데이터가 비어 있어도 예외를 던지지
    않는다. 예외로 끊으면 호출부가 사유를 원장에 남길 기회를 잃는다.
    """

    feed_id: str
    source_label: str

    def fetch(self, *, asof: str, factors: tuple[str, ...]
              ) -> tuple[pd.DataFrame, str]: ...


_QUOTE_COLUMNS = ("feed_id", "asof", "canonical_factor", "value", "unit",
                  "data_source")


class UnconnectedFeedAdapter:
    """연결이 없는 피드. 빈 결과와 사유를 돌려준다."""

    source_label = "미수신"

    def __init__(self, feed_id: str, reason: str):
        self.feed_id = feed_id
        self._reason = reason

    def fetch(self, *, asof: str, factors: tuple[str, ...]
              ) -> tuple[pd.DataFrame, str]:
        return pd.DataFrame(columns=list(_QUOTE_COLUMNS)), self._reason


class SyntheticFeedAdapter:
    """합성 대체 경로. 값의 출처를 '합성'으로 찍는다.

    값 자체는 인자로 받은 제공 함수에서 온다. 이 어댑터가 숫자를 만들지 않는다.
    """

    source_label = "합성"

    def __init__(self, feed_id: str, provider):
        self.feed_id = feed_id
        self._provider = provider

    def fetch(self, *, asof: str, factors: tuple[str, ...]
              ) -> tuple[pd.DataFrame, str]:
        values = self._provider(asof=asof, factors=factors)
        rows = [{"feed_id": self.feed_id, "asof": asof,
                 "canonical_factor": k, "value": float(v),
                 "unit": "ratio", "data_source": "합성"}
                for k, v in values.items()]
        return (pd.DataFrame(rows, columns=list(_QUOTE_COLUMNS)),
                "외부 피드 미연결로 합성 대체 경로를 사용했다")


def resolve_adapter(feed_row: pd.Series, *, synthetic_provider=None
                    ) -> MarketFeedAdapter:
    """피드 상태에 맞는 어댑터를 고른다.

    연결된 피드의 실제 어댑터는 이 저장소 밖이다. 여기서는 미연결과 합성
    대체만 고를 수 있으며, 연결 상태가 '연결'인데 실제 구현이 없으면 그 사실을
    사유로 돌려준다.
    """
    fid = str(feed_row["feed_id"])
    status = str(feed_row["connection_status"])
    if status == "연결":
        return UnconnectedFeedAdapter(
            fid, "연결 상태로 등록됐으나 실제 연계 계층이 이 저장소에 없다")
    if str(feed_row["fallback_source"]) == "합성" and synthetic_provider is not None:
        return SyntheticFeedAdapter(fid, synthetic_provider)
    return UnconnectedFeedAdapter(fid, f"연결 상태 {status}, 대체 경로 없음")


# ---------------------------------------------------------------- 적재 표
#
# (피드ID, 명칭, 구분, 방식, 대상 팩터, 기대 팩터수, 공표시각)
_FEEDS = (
    ("FD-KTB", "국고채 지표금리", "채권평가사", "SFTP 파일",
     "원화 무이표커브 만기별 금리", 12, "영업일 16:30"),
    ("FD-IRS", "이자율스왑 호가", "브로커 호가", "REST",
     "원화 IRS 커브", 10, "영업일 15:45"),
    ("FD-FX", "환율 고시", "중앙은행 공시", "REST",
     "USD·EUR·JPY·CNY 대원화 환율", 4, "영업일 15:30"),
    ("FD-EQ", "주가지수 종가", "거래소 시세", "REST",
     "KOSPI200·KOSDAQ150 종가", 2, "영업일 15:40"),
    ("FD-VOL", "옵션 내재변동성", "거래소 시세", "REST",
     "지수옵션 만기·행사가별 내재변동성", 25, "영업일 15:45"),
    ("FD-CRS", "신용스프레드", "채권평가사", "SFTP 파일",
     "등급별 회사채 스프레드", 7, "영업일 17:00"),
)

# (피드ID, 외부 필드명, 표준 팩터, 단위, 변환)
_FIELD_MAP = (
    ("FD-KTB", "GOVT_KR_3M", "ZERO_KRW_0.25Y", "ratio", "퍼센트를 100으로 나눈다"),
    ("FD-KTB", "GOVT_KR_1Y", "ZERO_KRW_1Y", "ratio", "퍼센트를 100으로 나눈다"),
    ("FD-KTB", "GOVT_KR_3Y", "ZERO_KRW_3Y", "ratio", "퍼센트를 100으로 나눈다"),
    ("FD-KTB", "GOVT_KR_10Y", "ZERO_KRW_10Y", "ratio", "퍼센트를 100으로 나눈다"),
    ("FD-IRS", "IRS_KRW_1Y", "SWAP_KRW_1Y", "ratio", "퍼센트를 100으로 나눈다"),
    ("FD-IRS", "IRS_KRW_5Y", "SWAP_KRW_5Y", "ratio", "퍼센트를 100으로 나눈다"),
    ("FD-FX", "USDKRW_CLOSE", "FX_USDKRW", "KRW", "그대로 사용한다"),
    ("FD-FX", "EURKRW_CLOSE", "FX_EURKRW", "KRW", "그대로 사용한다"),
    ("FD-EQ", "KOSPI200_CLOSE", "EQ_KOSPI200", "index", "그대로 사용한다"),
    ("FD-VOL", "K200_IV_ATM_3M", "VOL_KOSPI200_3M_ATM", "ratio",
     "퍼센트를 100으로 나눈다"),
    ("FD-CRS", "CORP_AA_3Y_SPRD", "CS_AA_3Y", "bp", "bp를 10000으로 나눈다"),
)


def build_market_feeds() -> pd.DataFrame:
    """피드 원장. 전건 '미연결'이다. 이 저장소에 외부 연계 계층이 없다."""
    return pd.DataFrame([{
        "feed_id": f[0], "feed_name": f[1], "feed_kind": f[2], "protocol": f[3],
        "factor_scope": f[4], "expected_factors": f[5], "publish_time": f[6],
        "connection_status": "미연결", "last_sync": None,
        "fallback_source": "합성", "evidence_status": "미확인",
    } for f in _FEEDS], columns=[c.name for c in MARKET_FEED.columns])


def build_field_map() -> pd.DataFrame:
    return pd.DataFrame([{
        "feed_id": m[0], "external_field": m[1], "canonical_factor": m[2],
        "unit": m[3], "transform": m[4],
    } for m in _FIELD_MAP], columns=[c.name for c in FEED_FIELD_MAP.columns])


def probe(feeds: pd.DataFrame, field_map: pd.DataFrame, *, asof: str,
          synthetic_provider=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """피드마다 어댑터를 붙여 수신을 시도하고 상태를 원장에 남긴다.

    (수신 상태 원장, 실제로 받은 시세)를 돌려준다. 미연결 피드도 행을 남긴다.
    행이 없으면 시도하지 않은 것과 받지 못한 것이 같아진다.
    """
    rows, quotes = [], []
    for _, f in feeds.iterrows():
        fid = str(f["feed_id"])
        factors = tuple(field_map[field_map["feed_id"] == fid]["canonical_factor"])
        adapter = resolve_adapter(f, synthetic_provider=synthetic_provider)
        data, reason = adapter.fetch(asof=asof, factors=factors)
        received = int(len(data))
        expected = int(f["expected_factors"])
        if received == 0:
            status, source = "미연결", "미수신"
        elif received < expected:
            status, source = "부분수신", adapter.source_label
        else:
            status, source = "정상", adapter.source_label
        rows.append({
            "feed_id": fid, "asof": asof, "expected_factors": expected,
            "received_factors": received,
            "staleness_days": None if pd.isna(f["last_sync"]) else 0.0,
            "data_source": source, "status": status, "reason": reason,
        })
        if received:
            quotes.append(data)
    health = pd.DataFrame(rows, columns=[c.name for c in FEED_HEALTH.columns]
                          ).astype({"staleness_days": "float64"})
    quote_frame = (pd.concat(quotes, ignore_index=True) if quotes
                   else pd.DataFrame(columns=list(_QUOTE_COLUMNS)))
    return health, quote_frame


def build_market_feed(*, asof: str, synthetic_provider=None
                      ) -> tuple[dict[str, pd.DataFrame], list[str]]:
    """피드 원장 3장을 만든다. (원장, 미연결 사유)를 돌려준다."""
    feeds = build_market_feeds()
    field_map = build_field_map()
    health, _quotes = probe(feeds, field_map, asof=asof,
                            synthetic_provider=synthetic_provider)
    unconnected = [f"{r['feed_id']}: {r['status']} ({r['reason']})"
                   for _, r in health.iterrows() if r["status"] != "정상"]
    return ({"int_market_feed": feeds,
             "int_feed_field_map": field_map,
             "int_feed_health": health}, unconnected)
