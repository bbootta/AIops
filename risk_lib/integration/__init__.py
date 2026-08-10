"""외부 연계 원장 (INT 계열).

이 저장소는 외부 시스템과 통신하지 않는다. 데이터는 전부 합성이다. 그래서
더욱, **어디서 받아야 하는 데이터인지**와 **지금 받고 있지 않다는 사실**이
원장에 없으면 화면의 수치가 실제 계정계 잔액인 것처럼 읽힌다.

  connector       INT-001 조회 전용 커넥터 등록과 쓰기 시도 차단
  inbound         INT-002 파일·API·배치 수신 표준화(스키마·기준일·체크섬)
  engine_adapter  INT-003 계산엔진 입력·출력·버전 표준 인터페이스
  resilience      INT-008 멱등성·재시도·오류 격리

시장데이터 피드는 `risk_lib.market_feed`(INT-004)가 따로 다룬다.

각 모듈은 자기 TableSpec을 `SPECS`로 들고 있고 `build_*`가 원장을 만든다.
정책값은 build_* 안에만 두고 판정 함수는 원장을 인자로 받는다.
"""

from __future__ import annotations
