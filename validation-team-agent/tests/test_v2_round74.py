"""Round 74 — report_pack --input-csv 통합 (어댑터 → 팩 빌드 직접 연결)."""

from __future__ import annotations

import hashlib
import json

import pandas as pd
import pytest


@pytest.fixture
def ops_csv(tmp_path):
    n = 2000
    df = pd.DataFrame({
        "cust_id": [f"C{i:06d}" for i in range(n)],
        "obs_dt": pd.date_range("2025-01-01", periods=n, freq="h")
                    .strftime("%Y-%m-%d"),
        "model_score": [round(0.05 + 0.9 * ((i * 37) % 100) / 100, 4)
                        for i in range(n)],
        "bad_flag": [(i % 11 == 0) * 1 for i in range(n)],
    })
    p = tmp_path / "ops_extract.csv"
    df.to_csv(p, index=False)
    return p


@pytest.fixture
def mapping_json(tmp_path):
    p = tmp_path / "map.json"
    p.write_text(json.dumps({
        "id_col": "cust_id", "date_col": "obs_dt",
        "score_col": "model_score", "target_col": "bad_flag"}),
        encoding="utf-8")
    return p


# ---------- build_request_from_file ----------

def test_merges_domain_scalars(ops_csv, mapping_json):
    from tools.run_workflow_demo import build_request_from_file

    request, meta = build_request_from_file(ops_csv, mapping_json)
    # 신용 부문 = 파일, 기타 부문 = 합성 스칼라 병합
    assert request["score_col"] == "model_score"
    for key in ("liquidity_hqla", "irrbb_tier1", "scenario_weight_panel",
                "op_business_indicator_eur_bn"):
        assert key in request
    # adapter_meta 는 request 에서 분리
    assert "_adapter_meta" not in request
    assert meta["n_rows"] == 2000


def test_build_request_regression_after_refactor():
    """_domain_inputs 분리 후에도 기존 합성 request 구성이 동일하다."""
    from tools.run_workflow_demo import build_request

    req = build_request(1000, stress=False, seed=1)
    for key in ("df", "liquidity_hqla", "irrbb_delta_eve_by_scenario",
                "macro_series", "scenario_weight_panel"):
        assert key in req
    stress_req = build_request(1000, stress=True, seed=1)
    assert stress_req["market_var_exceptions"] == 12
    assert req["market_var_exceptions"] == 3


def test_run_demo_accepts_prebuilt_request(ops_csv, mapping_json, tmp_path):
    from tools.run_workflow_demo import build_request_from_file, run_demo

    request, _ = build_request_from_file(ops_csv, mapping_json)
    demo = run_demo(0, False, 42, tmp_path, request=request)
    assert demo["n_rows"] == 2000
    assert "3.disc" in demo["executed_order"]
    assert demo["results"]["2.safety"]["status"] == "ok"


def test_pseudonym_never_all_digits(ops_csv, mapping_json):
    """접두사 'p' 로 전부-숫자 pseudonym 이 계좌번호 패턴에 오탐되지 않는다."""
    from tools.run_workflow_demo import build_request_from_file

    request, _ = build_request_from_file(ops_csv, mapping_json)
    ids = request["df"]["cust_id"]
    assert ids.str.startswith("p").all()
    assert ids.str.len().eq(16).all()


# ---------- provenance ----------

def test_file_sha256(tmp_path):
    from tools.provenance import file_sha256

    p = tmp_path / "x.bin"
    p.write_bytes(b"hello")
    assert file_sha256(p) == hashlib.sha256(b"hello").hexdigest()


def test_provenance_source_changes_reproduce_command(ops_csv, mapping_json):
    from tools.provenance import build_provenance
    from tools.run_workflow_demo import build_request, build_request_from_file

    request, meta = build_request_from_file(ops_csv, mapping_json)
    prov = build_provenance(
        request, n=meta["n_rows"], seed=42, stress=False,
        source={"input_file": str(ops_csv), "file_sha256": "ab" * 32,
                "mapping_file": str(mapping_json), "pii_action": "block",
                "dropped_columns": [], "pseudonymized": True})
    assert "--input-csv" in prov["reproduce"]
    assert prov["inputs"]["source"]["input_file"] == str(ops_csv)
    assert any("합성 예시" in n for n in prov["notes"])

    # 기존 합성 모드는 불변 (backward compat)
    prov_syn = build_provenance(build_request(500, stress=False, seed=1),
                                n=500, seed=1, stress=False)
    assert "--input-csv" not in prov_syn["reproduce"]
    assert "source" not in prov_syn["inputs"]


# ---------- report_pack main --input-csv ----------

def test_pack_build_from_csv(ops_csv, mapping_json, tmp_path):
    from tools.report_pack import main

    out = tmp_path / "pack"
    rc = main(["--input-csv", str(ops_csv), "--mapping", str(mapping_json),
               "--seed", "42", "--out", str(out),
               "--log-dir", str(tmp_path / "logs")])
    assert rc == 0
    pages = sorted(out.glob("*.html"))
    assert len(pages) == 47
    execu = (out / "executive.html").read_text(encoding="utf-8")
    assert "운영 추출 파일" in execu
    assert "기타 부문 스칼라 입력은 합성 예시" in execu
    assert "--input-csv" in execu.replace("&#x2d;", "-")
    # 원본 식별자 (C000000) 는 어떤 페이지에도 실리지 않는다 (pseudonymize)
    for p in pages:
        assert "C000000" not in p.read_text(encoding="utf-8"), p.name


def test_pack_build_blocks_pii_csv(ops_csv, mapping_json, tmp_path, capsys):
    from tools.report_pack import main

    df = pd.read_csv(ops_csv)
    df["memo"] = "901231-1234567"
    dirty = tmp_path / "dirty.csv"
    df.to_csv(dirty, index=False)
    rc = main(["--input-csv", str(dirty), "--mapping", str(mapping_json),
               "--out", str(tmp_path / "pack_blocked"),
               "--log-dir", str(tmp_path / "logs")])
    assert rc == 1
    err = capsys.readouterr().err
    assert "차단" in err
    assert "901231" not in err  # 원문 미노출


def test_input_csv_requires_mapping(ops_csv, tmp_path):
    from tools.report_pack import main

    with pytest.raises(SystemExit):
        main(["--input-csv", str(ops_csv), "--out", str(tmp_path / "p")])
