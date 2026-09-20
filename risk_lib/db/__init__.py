"""PostgreSQL 저장소. 배치와 에이전틱 UI 가 원장을 여기서 읽는다.

    schema   카탈로그 스펙 → 물리 테이블 (실행별 run_id 접두)
    store    한 실행(스튜디오)을 적재한다. 원장 전량·기관 축·입력 포트폴리오·
             화면 부문 JSON·독립검증 요청.
    load     실행 목록, 스튜디오 복원(화면), 입력 복원 후 재산출(배치).

읽기 경로는 둘이다. 화면은 원장과 부문 JSON 을 그대로 읽어 그린다 (재계산
없음, 메모리 경로와 바이트 동일). 결과 객체가 필요한 배치(보고서·서식)는
DB 의 입력 포트폴리오와 실행 모수로 파이프라인을 다시 돌리고, 입력 지문이
등록부와 다르면 멈춘다.
"""

from .config import DEFAULT_DSN, DEFAULT_SCHEMA, available, connect, dsn, schema_name
from .load import list_runs, load_portfolio, load_studio, result_from_db, run_record
from .schema import all_specs, init_schema
from .store import store_run

__all__ = [
    "DEFAULT_DSN", "DEFAULT_SCHEMA", "available", "connect", "dsn", "schema_name",
    "all_specs", "init_schema", "store_run",
    "list_runs", "load_portfolio", "load_studio", "result_from_db", "run_record",
]
