"""한 실행을 PostgreSQL 에 적재한다.

적재 단위는 스튜디오(build_studio 의 결과)다. 원장 271장이 한 번에 서 있는
유일한 자리가 거기다. 한 트랜잭션 안에서

    1. 같은 run_id 의 이전 행을 전부 지우고
    2. 등록부 행을 쓰고
    3. 원장·기관 축·입력 포트폴리오·한도 프레임을 COPY 로 넣고
    4. 프레임 명세(컬럼 순서·pandas dtype)를 남기고
    5. 화면 부문 JSON 과 독립검증 요청 JSON 을 쓴다.

명세를 남기는 이유는 되돌릴 때 **같은 DataFrame** 을 만들기 위해서다.
int64 와 Int64, bool 과 boolean, str 과 object 는 DB 타입만으로는 구분되지
않는데, 화면은 그 차이로 셀을 다르게 그린다. 렌더가 바이트 동일해야 DB 경로가
메모리 경로와 같은 산출이라고 말할 수 있다.
"""

from __future__ import annotations

import sys
import hashlib
import json
import math
import subprocess
from dataclasses import asdict, is_dataclass
from datetime import date, datetime

import numpy as np
import pandas as pd

from .config import connect, schema_name
from .schema import (EXTRA_FRAMES, ROW_COL, RUN_COL, existing_columns,
                     frame_table_ddl, pg_type_for_dtype, q, qt, spec_by_name)


def pyval(v):
    """DataFrame 셀을 psycopg 가 그대로 보낼 수 있는 값으로. 결측은 NULL."""
    if v is None:
        return None
    if isinstance(v, np.generic):
        v = v.item()
        if v is None:
            return None
    if isinstance(v, float):
        return None if math.isnan(v) else v
    if isinstance(v, (bool, int, str)):
        return v
    if isinstance(v, (pd.Timestamp, datetime)):
        return v.isoformat()
    if isinstance(v, date):
        return v.isoformat()
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return str(v)


def frame_fingerprint(df: pd.DataFrame) -> str:
    """프레임 지문. 컬럼 순서·값·결측을 셀 단위로 정규화해 SHA-256 을 낸다."""
    h = hashlib.sha256()
    h.update("|".join(str(c) for c in df.columns).encode("utf-8"))
    for row in df.itertuples(index=False):
        h.update(json.dumps([pyval(v) for v in row], ensure_ascii=False,
                            separators=(",", ":")).encode("utf-8"))
    return h.hexdigest()


def _git_revision() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                             text=True, check=True).stdout.strip()
    except Exception:                              # noqa: BLE001
        return ""
    return out


def _jsonable(obj):
    """dataclass·numpy·NaN 을 JSON 으로. 부문 JSON 은 화면 페이로드와 같은 규약."""
    if is_dataclass(obj) and not isinstance(obj, type):
        return _jsonable(asdict(obj))
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, pd.DataFrame):
        return {"columns": [str(c) for c in obj.columns],
                "rows": [[pyval(v) for v in r] for r in obj.itertuples(index=False)]}
    return pyval(obj)


def _copy_frame(cur, table: str, df: pd.DataFrame, run_id: str, schema: str,
                columns: list[str]) -> int:
    """프레임을 COPY 로 넣는다. 스펙 컬럼만 넣고 프레임에 없는 컬럼은 NULL."""
    present = [c for c in columns if c in df.columns]
    cols = [RUN_COL, ROW_COL] + present
    sql = (f"COPY {qt(table, schema)} ({', '.join(q(c) for c in cols)}) "
           f"FROM STDIN")
    n = 0
    sub = df[present] if present else df.iloc[:, :0]
    with cur.copy(sql) as cp:
        for i, row in enumerate(sub.itertuples(index=False)):
            cp.write_row((run_id, i, *[pyval(v) for v in row]))
            n += 1
    return n


def _manifest(cur, run_id: str, name: str, kind: str, df: pd.DataFrame,
              schema: str, ordinal: int) -> None:
    """프레임 명세. ordinal 은 스튜디오 안의 순서다. 되읽을 때 같은 순서로 놓아야
    페이로드의 미리보기 순서가 메모리 경로와 같다."""
    cur.execute(f"INSERT INTO {qt('run_frame', schema)} "
                "(run_id, frame, kind, ordinal, n_rows) VALUES (%s, %s, %s, %s, %s)",
                (run_id, name, kind, ordinal, int(len(df))))
    rows = [(run_id, name, i, str(c), str(df[c].dtype))
            for i, c in enumerate(df.columns)]
    if rows:
        cur.executemany(
            f"INSERT INTO {qt('run_frame_column', schema)} "
            "(run_id, frame, ordinal, column_name, dtype) VALUES (%s, %s, %s, %s, %s)",
            rows)


def _ensure_extra_table(cur, name: str, df: pd.DataFrame, schema: str) -> None:
    """스펙 없는 프레임의 테이블. 없으면 만들고, 있으면 모자란 컬럼을 더한다.

    스펙 없는 프레임(입력 포트폴리오 등)은 기관 생성기마다 모양이 다르다. 국내
    표본에는 없는 라벨 컬럼이 해외 합성 기관에는 있다. 그래서 테이블은 실린
    프레임들의 합집합이고, 없는 컬럼은 NULL 이다. 더한 컬럼은 로그로 남긴다.
    스펙 있는 원장은 이 길을 타지 않는다. 그쪽 컬럼은 카탈로그가 정한다.
    """
    have = existing_columns(cur.connection, name, schema)
    if not have:
        cur.execute(frame_table_ddl(name, df, schema))
        return
    added = [str(c) for c in df.columns if str(c) not in have]
    for c in added:
        cur.execute(f"ALTER TABLE {qt(name, schema)} ADD COLUMN {q(c)} "
                    f"{pg_type_for_dtype(df[c].dtype)}")
    if added:
        print(f"  {schema}.{name} 컬럼 추가 {added}", file=sys.stderr)


def _delete_run(cur, run_id: str, schema: str, tables: list[str]) -> None:
    for t in ("run_registry", "run_section", "run_frame", "run_frame_column"):
        cur.execute(f"DELETE FROM {qt(t, schema)} WHERE run_id = %s", (run_id,))
    for t in tables:
        if existing_columns(cur.connection, t, schema):
            cur.execute(f"DELETE FROM {qt(t, schema)} WHERE {q(RUN_COL)} = %s", (run_id,))


def store_run(studio, portfolio: pd.DataFrame | None = None, *,
              conn=None, schema: str | None = None) -> dict:
    """스튜디오 한 벌을 적재한다. 같은 run_id 가 있으면 통째로 바꾼다."""
    from risk_lib.ui_studio.app import sections_for

    schema = schema or schema_name()
    specs = spec_by_name()
    own = conn is None
    conn = conn or connect()
    run_id = studio.run_id
    sections = studio.sections if studio.sections is not None else sections_for(studio)
    iv = studio.iv_request
    iv_json = _jsonable(iv) if iv is not None else None

    frames: list[tuple[str, str, pd.DataFrame]] = []
    skipped: list[str] = []
    for name, df in studio.tables.items():
        if not isinstance(df, pd.DataFrame):
            continue
        if name in specs:
            frames.append((name, "ledger", df))
        else:
            skipped.append(name)
    for name, df in (studio.inst_tables or {}).items():
        if isinstance(df, pd.DataFrame) and name in specs:
            frames.append((name, "inst", df))
    extra: list[tuple[str, pd.DataFrame]] = []
    if portfolio is not None:
        extra.append(("x_portfolio", portfolio))
    res = getattr(studio, "result", None)
    if res is not None:
        if isinstance(getattr(res, "limits", None), pd.DataFrame):
            extra.append(("x_limits", res.limits))
        if isinstance(getattr(res, "limits_full", None), pd.DataFrame):
            extra.append(("x_limits_full", res.limits_full))

    n_rows = 0
    try:
        with conn.cursor() as cur:
            _delete_run(cur, run_id, schema,
                        [n for n, _, _ in frames] + list(EXTRA_FRAMES))
            for name, df in extra:
                _ensure_extra_table(cur, name, df, schema)
            for k, (name, kind, df) in enumerate(frames):
                n_rows += _copy_frame(cur, name, df, run_id, schema,
                                      [c.name for c in specs[name].columns])
                _manifest(cur, run_id, name, kind, df, schema, k)
            for k, (name, df) in enumerate(extra):
                _copy_frame(cur, name, df, run_id, schema,
                            [str(c) for c in df.columns])
                _manifest(cur, run_id, name, "extra", df, schema, len(frames) + k)
            from psycopg.types.json import Json
            for key, body in sections.items():
                cur.execute(
                    f"INSERT INTO {qt('run_section', schema)} (run_id, section, body) "
                    "VALUES (%s, %s, %s)", (run_id, key, Json(_jsonable(body))))
            if iv_json is not None:
                cur.execute(
                    f"INSERT INTO {qt('run_section', schema)} (run_id, section, body) "
                    "VALUES (%s, %s, %s)", (run_id, "iv_request", Json(iv_json)))
            cur.execute(
                f"INSERT INTO {qt('run_registry', schema)} "
                "(run_id, institution_code, asof, seed, digest, headline_digest, "
                " portfolio_fingerprint, iv_run_id, iv_request_id, n_tables, n_rows, "
                " git_revision) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (run_id, studio.institution_code, studio.asof, int(studio.seed),
                 studio.digest,
                 getattr(iv, "headline_digest", None),
                 frame_fingerprint(portfolio) if portfolio is not None else None,
                 getattr(iv, "run_id", None), getattr(iv, "request_id", None),
                 len([f for f in frames if f[1] == "ledger"]), n_rows,
                 _git_revision()))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if own:
            conn.close()
    return {"run_id": run_id, "schema": schema, "n_tables": len(frames),
            "n_rows": n_rows, "n_sections": len(sections) + (1 if iv_json else 0),
            "extra": [n for n, _ in extra], "skipped": skipped}
