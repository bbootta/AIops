"""Round 73 — 운영 데이터 어댑터 (PII 차단 boundary + 매핑 + pseudonymize)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def clean_csv(tmp_path):
    df = pd.DataFrame({
        "cust_id": [f"C{i:05d}" for i in range(150)],
        "obs_dt": pd.date_range("2025-01-01", periods=150).strftime("%Y-%m-%d"),
        "model_score": [0.1 * (i % 10) for i in range(150)],
        "bad_flag": [(i % 7 == 0) * 1 for i in range(150)],
    })
    p = tmp_path / "clean.csv"
    df.to_csv(p, index=False)
    return p


@pytest.fixture
def pii_csv(tmp_path, clean_csv):
    df = pd.read_csv(clean_csv)
    df["memo"] = "901231-1234567"  # 주민번호 패턴
    p = tmp_path / "dirty.csv"
    df.to_csv(p, index=False)
    return p


@pytest.fixture
def mapping(tmp_path):
    p = tmp_path / "map.json"
    p.write_text(json.dumps({
        "id_col": "cust_id", "date_col": "obs_dt",
        "score_col": "model_score", "target_col": "bad_flag"}),
        encoding="utf-8")
    return p


# ---------- 매핑 ----------

def test_load_mapping_rejects_unknown_keys(tmp_path):
    from tools.data_adapter import MappingError, load_mapping

    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"score_col": "s", "target_col": "t",
                             "wrong_key": "x"}), encoding="utf-8")
    with pytest.raises(MappingError):
        load_mapping(p)


def test_load_mapping_requires_score_and_target(tmp_path):
    from tools.data_adapter import MappingError, load_mapping

    p = tmp_path / "missing.json"
    p.write_text(json.dumps({"score_col": "s"}), encoding="utf-8")
    with pytest.raises(MappingError):
        load_mapping(p)


def test_missing_column_in_file_raises(clean_csv, tmp_path):
    from tools.data_adapter import MappingError, load_validation_input

    with pytest.raises(MappingError):
        load_validation_input(clean_csv, {"score_col": "no_such",
                                          "target_col": "bad_flag"})


# ---------- PII boundary ----------

def test_clean_file_passes(clean_csv, mapping):
    from tools.data_adapter import load_mapping, load_validation_input

    req = load_validation_input(clean_csv, load_mapping(mapping))
    meta = req["_adapter_meta"]
    assert meta["schema_passed"] is True
    assert meta["pii_findings"] == 0
    assert req["score_col"] == "model_score"


def test_pii_blocks_by_default(pii_csv, mapping):
    from tools.data_adapter import (
        PIIDetectedError,
        load_mapping,
        load_validation_input,
    )

    with pytest.raises(PIIDetectedError) as e:
        load_validation_input(pii_csv, load_mapping(mapping))
    # 원문 미노출 — 주민번호가 예외 메시지에 없어야
    assert "901231" not in str(e.value)


def test_pii_drop_removes_offending_column(pii_csv, mapping):
    from tools.data_adapter import load_mapping, load_validation_input

    req = load_validation_input(pii_csv, load_mapping(mapping),
                                pii_action="drop")
    assert "memo" not in req["df"].columns
    assert "memo" in req["_adapter_meta"]["dropped_columns"]


def test_pii_in_mapped_column_cannot_drop(tmp_path, mapping):
    """매핑 대상 컬럼 자체가 PII 면 drop 불가 — 원천 정제 요구."""
    from tools.data_adapter import (
        PIIDetectedError,
        load_mapping,
        load_validation_input,
    )

    df = pd.DataFrame({
        "cust_id": ["901231-1234567"] * 150,  # id 자체가 주민번호
        "obs_dt": pd.date_range("2025-01-01", periods=150).strftime("%Y-%m-%d"),
        "model_score": [0.5] * 150,
        "bad_flag": [0, 1] * 75,
    })
    p = tmp_path / "bad_id.csv"
    df.to_csv(p, index=False)
    with pytest.raises(PIIDetectedError):
        load_validation_input(p, load_mapping(mapping), pii_action="drop")


def test_date_string_not_false_positive(clean_csv, mapping):
    """YYYY-MM-DD 문자열 날짜가 계좌번호 패턴 오탐되지 않음 (R19 재발 방지)."""
    from tools.data_adapter import load_mapping, load_validation_input

    req = load_validation_input(clean_csv, load_mapping(mapping))
    assert req["_adapter_meta"]["pii_findings"] == 0
    # date_col 이 datetime dtype 으로 정규화
    assert pd.api.types.is_datetime64_any_dtype(req["df"]["obs_dt"])


# ---------- pseudonymize ----------

def test_id_column_pseudonymized(clean_csv, mapping):
    from tools.data_adapter import load_mapping, load_validation_input

    req = load_validation_input(clean_csv, load_mapping(mapping))
    ids = req["df"]["cust_id"]
    # 원본 형식 (C00001) 이 남지 않고 16 hex
    assert not ids.str.startswith("C").any()
    assert ids.str.len().eq(16).all()
    assert req["_adapter_meta"]["pseudonymized"] is True


def test_pseudonymize_deterministic_with_salt(clean_csv, mapping):
    from tools.data_adapter import load_mapping, load_validation_input

    m = load_mapping(mapping)
    r1 = load_validation_input(clean_csv, m, salt=b"fixed")
    r2 = load_validation_input(clean_csv, m, salt=b"fixed")
    assert (r1["df"]["cust_id"] == r2["df"]["cust_id"]).all()
    r3 = load_validation_input(clean_csv, m, salt=b"other")
    assert not (r1["df"]["cust_id"] == r3["df"]["cust_id"]).all()


def test_pseudonymize_can_be_disabled(clean_csv, mapping):
    from tools.data_adapter import load_mapping, load_validation_input

    req = load_validation_input(clean_csv, load_mapping(mapping),
                                pseudonymize=False)
    assert req["df"]["cust_id"].str.startswith("C").all()
    assert req["_adapter_meta"]["pseudonymized"] is False


# ---------- 스키마 ----------

def test_non_numeric_score_rejected(tmp_path, mapping):
    from tools.data_adapter import MappingError, load_mapping, load_validation_input

    df = pd.DataFrame({
        "cust_id": [f"C{i}" for i in range(150)],
        "obs_dt": pd.date_range("2025-01-01", periods=150).strftime("%Y-%m-%d"),
        "model_score": ["high"] * 150,  # 문자열 score
        "bad_flag": [0, 1] * 75,
    })
    p = tmp_path / "bad_score.csv"
    df.to_csv(p, index=False)
    with pytest.raises(MappingError):
        load_validation_input(p, load_mapping(mapping))


# ---------- 워크플로우 통합 ----------

def test_adapter_request_runs_through_engine(clean_csv, mapping, tmp_path):
    """어댑터 산출 request 가 실제 워크플로우를 통과한다."""
    from tools.data_adapter import load_mapping, load_validation_input
    from tools.handlers import register_default_handlers
    from tools.workflow import WorkflowEngine

    req = load_validation_input(clean_csv, load_mapping(mapping))
    req.pop("_adapter_meta")
    eng = WorkflowEngine()
    register_default_handlers(eng)
    run = eng.run(req, log_dir=tmp_path)
    assert "3.disc" in run.executed_order
    # 안전 점검 통과 (PII 없음)
    assert run.context.results["2.safety"].status == "ok"


# ---------- CLI + 카탈로그 ----------

def test_cli_validate_clean(clean_csv, mapping):
    res = subprocess.run(
        [sys.executable, "-m", "tools.data_adapter", "validate",
         "--input", str(clean_csv), "--mapping", str(mapping)],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    assert res.returncode == 0
    assert "boundary 3중 통과" in res.stdout


def test_cli_blocks_pii(pii_csv, mapping):
    res = subprocess.run(
        [sys.executable, "-m", "tools.data_adapter", "validate",
         "--input", str(pii_csv), "--mapping", str(mapping)],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    assert res.returncode == 1
    assert "차단" in res.stderr
    assert "901231" not in res.stderr  # 원문 미노출


def test_catalog_sync():
    from tools.cli_index import CLI_MODULES
    from vta.cli.__main__ import _DISPATCH

    assert "tools.data_adapter" in {m for m, _ in CLI_MODULES}
    assert ("data", "load") in _DISPATCH
