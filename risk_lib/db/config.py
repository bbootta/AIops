"""PostgreSQL 연결 설정. 환경변수 둘이 전부다.

    RYNTA_PG_DSN      libpq 연결 문자열. 기본 postgresql://rynta:rynta@localhost:5432/rynta
    RYNTA_PG_SCHEMA   원장을 두는 스키마. 기본 rynta

연결 문자열을 코드에 박지 않는다. 운영·검증·개발이 같은 코드로 다른 DB 를
보게 하는 유일한 방법이 환경변수다. 드라이버(psycopg 3)는 선택 의존성이라
DB 를 쓰지 않는 배치는 설치 없이도 돈다.
"""

from __future__ import annotations

import os

DEFAULT_DSN = "postgresql://rynta:rynta@localhost:5432/rynta"
DEFAULT_SCHEMA = "rynta"


def dsn() -> str:
    return os.environ.get("RYNTA_PG_DSN") or DEFAULT_DSN


def schema_name() -> str:
    return os.environ.get("RYNTA_PG_SCHEMA") or DEFAULT_SCHEMA


def connect(dsn_: str | None = None):
    """psycopg 연결. 드라이버가 없으면 설치 방법을 말하고 멈춘다."""
    try:
        import psycopg
    except ImportError as exc:                     # pragma: no cover
        raise RuntimeError(
            "psycopg 가 설치되어 있지 않다. pip install 'psycopg[binary]' "
            "(또는 pip install -e '.[db]')") from exc
    return psycopg.connect(dsn_ or dsn())


def available(dsn_: str | None = None) -> bool:
    """DB 에 붙을 수 있는가. 테스트가 건너뛸지 정할 때 쓴다."""
    try:
        with connect(dsn_) as conn:
            conn.execute("select 1")
        return True
    except Exception:                              # noqa: BLE001
        return False
