"""PostgreSQL 저장소 왕복 검사.

DB 가 없으면 건너뛴다 (RYNTA_PG_DSN 로 붙을 수 있어야 돈다). 검사 스키마는
RYNTA_PG_TEST_SCHEMA (기본 rynta_test) 이고 운영 스키마와 섞이지 않는다.

가장 센 검사는 렌더 바이트 동일이다. DB 에서 되읽은 스튜디오로 만든 화면이
메모리 스튜디오로 만든 화면과 한 바이트도 다르지 않아야 "화면이 DB 를 읽는다"
고 말할 수 있다.
"""

from __future__ import annotations

import os

import pandas as pd
import pytest

from risk_lib.db import config as _cfg

pytestmark = pytest.mark.skipif(
    not _cfg.available(), reason="PostgreSQL 에 붙을 수 없다 (RYNTA_PG_DSN)")

SCHEMA = os.environ.get("RYNTA_PG_TEST_SCHEMA", "rynta_test")


@pytest.fixture(scope="module")
def studio(result, portfolio):
    from risk_lib.ui_studio.studio import build_studio
    return build_studio(result, portfolio)


@pytest.fixture(scope="module")
def stored(studio, portfolio):
    from risk_lib.db import connect, init_schema, store_run
    with connect() as conn:
        init_schema(conn, SCHEMA)
    return store_run(studio, portfolio, schema=SCHEMA)


@pytest.fixture(scope="module")
def loaded(stored, studio):
    from risk_lib.db import load_studio
    return load_studio(studio.run_id, schema=SCHEMA)


def test_schema_has_every_catalog_table():
    from risk_lib.db import connect
    from risk_lib.db.schema import all_specs, init_schema
    with connect() as conn:
        init_schema(conn, SCHEMA)
        with conn.cursor() as cur:
            cur.execute("SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = %s", (SCHEMA,))
            have = {r[0] for r in cur.fetchall()}
    missing = [sp.name for sp in all_specs() if sp.name not in have]
    assert not missing, f"DB 에 없는 원장 테이블 {missing[:5]}"
    assert {"run_registry", "run_section", "run_frame", "run_frame_column"} <= have


def test_store_registers_run_and_every_ledger(stored, studio):
    from risk_lib.db import run_record
    assert stored["skipped"] == []
    rec = run_record(studio.run_id, schema=SCHEMA)
    assert rec["digest"] == studio.digest
    assert rec["seed"] == studio.seed
    assert rec["n_tables"] == len(studio.tables)
    assert rec["portfolio_fingerprint"]


def test_ledgers_round_trip_exactly(loaded, studio):
    assert list(loaded.tables) == list(studio.tables)      # 순서까지
    for name, df in studio.tables.items():
        got = loaded.tables[name]
        assert list(got.columns) == list(df.columns), name
        assert [str(x) for x in got.dtypes] == [str(x) for x in df.dtypes], name
        pd.testing.assert_frame_equal(got, df, check_exact=True, obj=name)
    for name, df in studio.inst_tables.items():
        pd.testing.assert_frame_equal(loaded.inst_tables[name], df, check_exact=True,
                                      obj=name)


def test_render_from_db_is_byte_identical(loaded, studio):
    from risk_lib.ui_studio.app import render
    assert loaded.result is None                          # 재계산 없이
    assert render([loaded]) == render([studio])


def test_independent_request_survives(loaded, studio):
    assert loaded.iv_request is not None
    assert loaded.iv_request.request_id == studio.iv_request.request_id
    assert loaded.iv_request.self_validation == studio.iv_request.self_validation
    assert loaded.iv_gate.status == studio.iv_gate.status


def test_portfolio_round_trip(stored, studio, portfolio):
    from risk_lib.db import load_portfolio
    pf = load_portfolio(studio.run_id, schema=SCHEMA)
    assert list(pf.columns) == list(portfolio.columns)
    assert len(pf) == len(portfolio)


def test_tampered_portfolio_is_refused(stored, studio):
    """DB 의 입력이 적재 시점과 다르면 재산출을 시작하지 않는다 (fail-closed)."""
    from risk_lib.db import connect, load_portfolio
    from risk_lib.db.schema import qt
    sql = f"UPDATE {qt('run_registry', SCHEMA)} SET portfolio_fingerprint = %s WHERE run_id = %s"
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT portfolio_fingerprint FROM {qt('run_registry', SCHEMA)} "
                        f"WHERE run_id = %s", (studio.run_id,))
            original = cur.fetchone()[0]
            cur.execute(sql, ("tampered", studio.run_id))
        conn.commit()
    try:
        with pytest.raises(RuntimeError, match="지문 불일치"):
            load_portfolio(studio.run_id, schema=SCHEMA)
    finally:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (original, studio.run_id))
            conn.commit()


def test_reload_replaces_same_run(studio, portfolio):
    from risk_lib.db import connect, store_run
    from risk_lib.db.schema import qt
    store_run(studio, portfolio, schema=SCHEMA)
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT count(*) FROM {qt('run_registry', SCHEMA)} "
                        f"WHERE run_id = %s", (studio.run_id,))
            assert cur.fetchone()[0] == 1
            cur.execute(f"SELECT count(*) FROM {qt('val_check', SCHEMA)} "
                        f"WHERE \"_run_id\" = %s", (studio.run_id,))
            assert cur.fetchone()[0] == len(studio.tables["val_check"])
