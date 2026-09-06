"""PostgreSQL 에서 실행을 되읽는다.

두 경로가 있다.

    load_studio(run_id)      화면용. 원장·기관 축·부문 JSON·독립검증 요청을 읽어
                             Studio 를 만든다. 파이프라인을 돌리지 않는다.
                             render() 결과가 메모리 경로와 바이트 동일하다.
    result_from_db(run_id)   배치용. 입력 포트폴리오와 실행 모수를 읽어 파이프라인을
                             다시 돌린다. 포트폴리오 지문이 등록부와 다르면 멈춘다.
                             결과 객체(PipelineResult)는 DB 에 넣지 않는다. 산출은
                             입력과 코드에서 재현되어야 하고, 재현되지 않는 산출은
                             DB 에 있어도 근거가 못 된다.
"""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from .config import connect, schema_name
from .schema import ROW_COL, RUN_COL, q, qt
from .store import frame_fingerprint


def _rows(conn, sql: str, params=()) -> list[tuple]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def list_runs(conn=None, schema: str | None = None) -> list[dict]:
    schema = schema or schema_name()
    own = conn is None
    conn = conn or connect()
    try:
        rows = _rows(conn, f"SELECT run_id, institution_code, asof, seed, digest, "
                           f"n_tables, n_rows, git_revision, created_at "
                           f"FROM {qt('run_registry', schema)} ORDER BY asof, run_id")
    finally:
        if own:
            conn.close()
    keys = ("run_id", "institution_code", "asof", "seed", "digest", "n_tables",
            "n_rows", "git_revision", "created_at")
    out = []
    for r in rows:
        d = dict(zip(keys, r))
        d["asof"] = d["asof"].isoformat()
        out.append(d)
    return out


def run_record(run_id: str, conn=None, schema: str | None = None) -> dict:
    schema = schema or schema_name()
    own = conn is None
    conn = conn or connect()
    try:
        rows = _rows(conn, f"SELECT run_id, institution_code, asof, seed, digest, "
                           f"headline_digest, portfolio_fingerprint, iv_run_id, "
                           f"iv_request_id, n_tables, n_rows, git_revision, created_at "
                           f"FROM {qt('run_registry', schema)} WHERE run_id = %s",
                     (run_id,))
    finally:
        if own:
            conn.close()
    if not rows:
        raise KeyError(f"등록부에 실행 {run_id} 이 없다 ({schema}.run_registry)")
    keys = ("run_id", "institution_code", "asof", "seed", "digest",
            "headline_digest", "portfolio_fingerprint", "iv_run_id",
            "iv_request_id", "n_tables", "n_rows", "git_revision", "created_at")
    d = dict(zip(keys, rows[0]))
    d["asof"] = d["asof"].isoformat()
    return d


def _restore_value(v):
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, date):
        return v.isoformat()
    return v


def restore_frame(columns: list[str], dtypes: list[str], rows: list[tuple]
                  ) -> pd.DataFrame:
    """명세대로 DataFrame 을 되만든다. 결측은 dtype 이 정하는 결측값으로."""
    data = {c: [_restore_value(r[i]) for r in rows] for i, c in enumerate(columns)}
    df = pd.DataFrame({c: pd.Series(data[c], dtype=object) for c in columns},
                      columns=columns)
    for c, dt in zip(columns, dtypes):
        if dt == "object":
            continue
        try:
            if dt == "str":
                df[c] = df[c].astype("str")
            elif dt in ("float64", "float32"):
                df[c] = df[c].astype("float64").astype(dt)
            elif dt in ("int64", "int32"):
                df[c] = df[c].astype(dt)
            elif dt in ("Int64", "Int32", "Float64", "boolean"):
                df[c] = df[c].astype(dt)
            elif dt == "bool":
                df[c] = df[c].astype(bool)
            else:
                df[c] = df[c].astype(dt)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"{c}: dtype {dt} 로 되돌리지 못했다 ({exc})") from exc
    return df


def load_frames(run_id: str, conn, schema: str, kinds: tuple[str, ...] | None = None
                ) -> dict[str, tuple[str, pd.DataFrame]]:
    """실행의 프레임 전부를 (종류, DataFrame) 로. 명세의 컬럼 순서·dtype 을 따른다."""
    meta = _rows(conn, f"SELECT frame, kind FROM {qt('run_frame', schema)} "
                       f"WHERE run_id = %s ORDER BY ordinal", (run_id,))
    cols = _rows(conn, f"SELECT frame, ordinal, column_name, dtype "
                       f"FROM {qt('run_frame_column', schema)} WHERE run_id = %s "
                       f"ORDER BY frame, ordinal", (run_id,))
    by_frame: dict[str, list[tuple[str, str]]] = {}
    for frame, _, name, dt in cols:
        by_frame.setdefault(frame, []).append((name, dt))
    out: dict[str, tuple[str, pd.DataFrame]] = {}
    for frame, kind in meta:
        if kinds and kind not in kinds:
            continue
        spec = by_frame.get(frame, [])
        names = [n for n, _ in spec]
        dts = [d for _, d in spec]
        if names:
            sql = (f"SELECT {', '.join(q(n) for n in names)} FROM {qt(frame, schema)} "
                   f"WHERE {q(RUN_COL)} = %s ORDER BY {q(ROW_COL)}")
            rows = _rows(conn, sql, (run_id,))
        else:
            rows = []
        out[frame] = (kind, restore_frame(names, dts, rows))
    return out


def load_sections(run_id: str, conn, schema: str) -> dict:
    rows = _rows(conn, f"SELECT section, body FROM {qt('run_section', schema)} "
                       f"WHERE run_id = %s", (run_id,))
    return {k: v for k, v in rows}


def load_studio(run_id: str, *, conn=None, schema: str | None = None):
    """DB 원장으로 Studio 를 만든다. render()/write_app() 이 그대로 받는다."""
    from risk_lib.ui_studio.studio import Studio
    from risk_lib.validation.independent import ValidationRequest, check_gate

    schema = schema or schema_name()
    own = conn is None
    conn = conn or connect()
    try:
        rec = run_record(run_id, conn, schema)
        frames = load_frames(run_id, conn, schema)
        sections = load_sections(run_id, conn, schema)
    finally:
        if own:
            conn.close()
    tables = {n: df for n, (k, df) in frames.items() if k == "ledger"}
    inst = {n: df for n, (k, df) in frames.items() if k == "inst"}
    iv_body = sections.pop("iv_request", None)
    iv_request = ValidationRequest(**iv_body) if iv_body else None
    iv_gate = check_gate(iv_request) if iv_request is not None else None
    return Studio(asof=rec["asof"], run_id=run_id, digest=rec["digest"],
                  tables=tables, inst_tables=inst,
                  institution_code=rec["institution_code"],
                  institution_source="db", seed=int(rec["seed"]),
                  sections=sections, iv_request=iv_request, iv_gate=iv_gate,
                  result=None)


def load_portfolio(run_id: str, *, conn=None, schema: str | None = None
                   ) -> pd.DataFrame:
    schema = schema or schema_name()
    own = conn is None
    conn = conn or connect()
    try:
        rec = run_record(run_id, conn, schema)
        frames = load_frames(run_id, conn, schema, kinds=("extra",))
    finally:
        if own:
            conn.close()
    if "x_portfolio" not in frames:
        raise KeyError(f"실행 {run_id} 에 입력 포트폴리오(x_portfolio)가 없다. "
                       f"db-load 가 포트폴리오를 함께 적재해야 재산출할 수 있다.")
    pf = frames["x_portfolio"][1]
    want = rec.get("portfolio_fingerprint")
    got = frame_fingerprint(pf)
    if want and got != want:
        raise RuntimeError(
            f"실행 {run_id} 의 포트폴리오 지문 불일치: 등록부 {want[:16]} ≠ 복원 {got[:16]}. "
            f"DB 의 입력이 적재 시점과 다르다. 재산출을 진행하지 않는다.")
    return pf


def result_from_db(run_id: str, *, conn=None, schema: str | None = None):
    """DB 의 입력으로 파이프라인을 다시 돌린다. (result, portfolio, record) 를 준다."""
    from risk_lib.pipeline import run_pipeline

    schema = schema or schema_name()
    own = conn is None
    conn = conn or connect()
    try:
        rec = run_record(run_id, conn, schema)
        pf = load_portfolio(run_id, conn=conn, schema=schema)
    finally:
        if own:
            conn.close()
    result = run_pipeline(pf, seed=int(rec["seed"]), asof=rec["asof"],
                          institution_code=rec["institution_code"])
    return result, pf, rec
