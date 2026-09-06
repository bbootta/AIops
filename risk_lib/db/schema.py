"""물리 스키마. 카탈로그 TableSpec 이 곧 PostgreSQL 테이블이다.

카탈로그 271장과 기관 축 원장 5장이 각각 한 테이블이 된다. 모든 원장 테이블은
앞머리에 `_run_id` 와 `_row` 를 갖는다 (원장 자체의 run_id 컬럼과 겹치지 않게 밑줄을 앞에 둔다).

    _run_id  실행 식별자 (RUN-<기준일>-<기관코드>). 여러 실행이 한 테이블에 쌓인다.
    _row     실행 안의 행 순서. 원장은 순서가 뜻을 갖는 곳이 있어(경로·사다리)
             적재 순서를 그대로 되돌릴 수 있어야 한다.

기본키는 (_run_id, _row) 이고, 카탈로그의 자연키는 (_run_id, 자연키) 유일 인덱스로
건다. 자연키 중복은 적재 시점에 실패로 드러난다 (조용히 덮어쓰지 않는다).

타입은 스펙 논리 타입에서 나온다. 문자열은 길이 제한 없는 TEXT 다. 스펙의
VARCHAR(64)·(256) 을 그대로 쓰면 실제 원장 11개 컬럼이 잘린다. 허용값·범위
CHECK 는 물리 스키마에 걸지 않는다. 그 판정은 rdm_dq_result 원장이 이미
기록하며, 위반 행을 DB 가 거부하면 "위반이 있었다"는 사실 자체가 사라진다.

외래키도 걸지 않는다. 참조무결성 판정은 spec.check_refs 와 DQ 원장의 몫이고,
고아 레코드는 기록되어야 할 사실이다.
"""

from __future__ import annotations

import pandas as pd

from risk_lib import data_gen_intl as _intl
from risk_lib.datamodel import catalog as cat
from risk_lib.datamodel.spec import ColumnSpec, TableSpec

from .config import schema_name

RUN_COL = "_run_id"
ROW_COL = "_row"

PG_TYPE = {
    "string": "TEXT",
    "text": "TEXT",
    "int": "BIGINT",
    "float": "DOUBLE PRECISION",
    "bool": "BOOLEAN",
    "date": "DATE",
}

# 기관 축 원장 5장. 카탈로그 밖이지만 화면·배치가 읽는 원장이라 같이 싣는다.
INST_SPECS: tuple[TableSpec, ...] = (
    _intl.INST_MASTER_INTL, _intl.INST_PROFILE, _intl.INST_PORTFOLIO_MIX,
    _intl.INST_COUNTRY_MIX, _intl.INTL_LABEL_LEXICON)

# 카탈로그 밖 프레임. 스펙이 없어 pandas dtype 에서 타입을 정한다.
EXTRA_FRAMES = ("x_portfolio", "x_limits", "x_limits_full")


def all_specs() -> tuple[TableSpec, ...]:
    return tuple(cat.ALL_TABLES) + INST_SPECS


def spec_by_name() -> dict[str, TableSpec]:
    return {sp.name: sp for sp in all_specs()}


def q(ident: str) -> str:
    """식별자 인용. 원장 이름은 소문자 스네이크지만 규칙에 기대지 않는다."""
    return '"' + ident.replace('"', '""') + '"'


def qt(table: str, schema: str | None = None) -> str:
    return f"{q(schema or schema_name())}.{q(table)}"


def _lit(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def column_sql(col: ColumnSpec) -> str:
    return f"{q(col.name)} {PG_TYPE[col.dtype]}"


def table_ddl(spec: TableSpec, schema: str | None = None) -> list[str]:
    """원장 한 장의 DDL. CREATE 는 멱등이고 인덱스·주석도 그렇다."""
    t = qt(spec.name, schema)
    cols = [f"{q(RUN_COL)} TEXT NOT NULL", f"{q(ROW_COL)} BIGINT NOT NULL"]
    cols += [column_sql(c) for c in spec.columns]
    cols.append(f"PRIMARY KEY ({q(RUN_COL)}, {q(ROW_COL)})")
    out = [f"CREATE TABLE IF NOT EXISTS {t} (\n  " + ",\n  ".join(cols) + "\n)"]
    if spec.primary_key:
        keys = ", ".join([q(RUN_COL)] + [q(k) for k in spec.primary_key])
        out.append(f"CREATE UNIQUE INDEX IF NOT EXISTS {q('ux_' + spec.name)} "
                   f"ON {t} ({keys})")
    out.append(f"COMMENT ON TABLE {t} IS "
               + _lit(f"{spec.korean} · 입도: {spec.grain} · {spec.product}"))
    for c in spec.columns:
        label = " · ".join(x for x in (c.korean, c.unit, c.citation) if x)
        if label:
            out.append(f"COMMENT ON COLUMN {t}.{q(c.name)} IS {_lit(label)}")
    return out


def control_ddl(schema: str | None = None) -> list[str]:
    """실행 등록부·부문 JSON·프레임 명세. 원장 테이블과 같은 스키마에 둔다.

    부문 본문은 JSONB 가 아니라 JSON 이다. JSONB 는 키 순서를 버리는데, 화면
    페이로드는 키 순서까지 포함해 메모리 경로와 바이트 동일해야 한다.
    """
    s = schema or schema_name()
    return [
        f"CREATE SCHEMA IF NOT EXISTS {q(s)}",
        f"""CREATE TABLE IF NOT EXISTS {qt('run_registry', s)} (
  run_id TEXT PRIMARY KEY,
  institution_code TEXT NOT NULL,
  asof DATE NOT NULL,
  seed BIGINT NOT NULL,
  digest TEXT NOT NULL,
  headline_digest TEXT,
  portfolio_fingerprint TEXT,
  iv_run_id TEXT,
  iv_request_id TEXT,
  n_tables BIGINT NOT NULL,
  n_rows BIGINT NOT NULL,
  git_revision TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)""",
        f"""CREATE TABLE IF NOT EXISTS {qt('run_section', s)} (
  run_id TEXT NOT NULL,
  section TEXT NOT NULL,
  body JSON NOT NULL,
  PRIMARY KEY (run_id, section)
)""",
        f"""CREATE TABLE IF NOT EXISTS {qt('run_frame', s)} (
  run_id TEXT NOT NULL,
  frame TEXT NOT NULL,
  kind TEXT NOT NULL,
  ordinal BIGINT NOT NULL,
  n_rows BIGINT NOT NULL,
  PRIMARY KEY (run_id, frame)
)""",
        f"""CREATE TABLE IF NOT EXISTS {qt('run_frame_column', s)} (
  run_id TEXT NOT NULL,
  frame TEXT NOT NULL,
  ordinal BIGINT NOT NULL,
  column_name TEXT NOT NULL,
  dtype TEXT NOT NULL,
  PRIMARY KEY (run_id, frame, ordinal)
)""",
    ]


def all_ddl(schema: str | None = None) -> list[str]:
    out = control_ddl(schema)
    for sp in all_specs():
        out += table_ddl(sp, schema)
    return out


def init_schema(conn, schema: str | None = None) -> int:
    """스키마·등록부·원장 테이블 전부를 만든다. 돌려주는 값은 실행한 문장 수."""
    stmts = all_ddl(schema)
    with conn.cursor() as cur:
        for stmt in stmts:
            cur.execute(stmt)
    conn.commit()
    return len(stmts)


def pg_type_for_dtype(dtype: str) -> str:
    """스펙 없는 프레임의 컬럼 타입. pandas dtype 에서 정한다."""
    d = str(dtype)
    if d in ("int64", "Int64", "int32", "Int32"):
        return "BIGINT"
    if d in ("float64", "float32", "Float64"):
        return "DOUBLE PRECISION"
    if d in ("bool", "boolean"):
        return "BOOLEAN"
    return "TEXT"


def frame_table_ddl(name: str, df: pd.DataFrame, schema: str | None = None) -> str:
    t = qt(name, schema)
    cols = [f"{q(RUN_COL)} TEXT NOT NULL", f"{q(ROW_COL)} BIGINT NOT NULL"]
    cols += [f"{q(str(c))} {pg_type_for_dtype(df[c].dtype)}" for c in df.columns]
    cols.append(f"PRIMARY KEY ({q(RUN_COL)}, {q(ROW_COL)})")
    return f"CREATE TABLE IF NOT EXISTS {t} (\n  " + ",\n  ".join(cols) + "\n)"


def existing_columns(conn, table: str, schema: str | None = None) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position",
            (schema or schema_name(), table))
        return [r[0] for r in cur.fetchall()]
