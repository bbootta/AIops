import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run(args, stdin_text=None):
    """Invoke the CLI as a subprocess so __main__ wiring is exercised."""
    cmd = [sys.executable, "-m", "quant_validation_agent", *args]
    return subprocess.run(
        cmd,
        cwd=ROOT,
        input=stdin_text,
        capture_output=True,
        text=True,
    )


def test_cli_run_on_sample_request():
    req = os.path.join(ROOT, "examples", "sample_validation_request.md")
    result = _run(["run", "--request", req])
    # `run` always exits 0 — it only prints a plan. Guard findings are
    # surfaced inside the JSON payload for the orchestrator to inspect.
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert "parsed_metadata" in payload
    assert "guards" in payload
    # The sample uses 'prod' as a dataset category, which is flagged for review.
    risky_matches = {m["match"] for m in payload["guards"]["risky_commands"]}
    assert "prod" in risky_matches


def test_cli_thresholds_known_metric():
    result = _run(["thresholds", "--metric", "ks"])
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert "ks" in payload
    assert payload["ks"]["direction"] == "higher_is_better"


def test_cli_thresholds_for_model_type():
    result = _run(["thresholds", "--model-type", "scoring"])
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert "scoring" in payload
    assert "ks" in payload["scoring"]


def test_cli_check_flags_risky_text():
    result = _run(["check", "--text", "DROP TABLE customers"])
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["risky_commands"]


def test_cli_check_flags_pii_text():
    result = _run(["check", "--text", "메일은 user@example.com 입니다"])
    assert result.returncode == 3
    payload = json.loads(result.stdout)
    assert payload["pii_matches"]


def test_cli_check_clean_text_returns_zero():
    result = _run(["check", "--text", "compute KS for sample data"])
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["risky_commands"] == []
    assert payload["pii_matches"] == []


def test_cli_thresholds_segment_override():
    result = _run(["thresholds", "--metric", "ks", "--segment", "ldp_corporate"])
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ks"]["green_threshold"] == 0.25
    assert payload["ks"]["source"] == "segment:ldp_corporate"


def test_cli_validate_scoring(tmp_path):
    # Use the example credit-score CSV; higher score == lower risk in the sample.
    sample = os.path.join(ROOT, "examples", "sample_credit_score_data.csv")
    out_path = tmp_path / "report.json"
    result = _run(
        [
            "validate",
            "--data", sample,
            "--model-type", "scoring",
            "--target", "target",
            "--score", "score",
            "--dataset-col", "dataset",
            "--baseline-value", "dev",
            "--segment", "retail",
            "--out", str(out_path),
        ]
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert {"ks", "auroc", "ar"}.issubset(payload["metrics"].keys())
    # PSI is included because dataset_col + baseline are provided.
    assert "psi" in payload["metrics"]
    assert out_path.exists()


def test_cli_validate_with_decile_rag():
    sample = os.path.join(ROOT, "examples", "sample_credit_score_data.csv")
    result = _run([
        "validate",
        "--data", sample,
        "--model-type", "scoring",
        "--target", "target",
        "--score", "score",
        "--decile-rag",
    ])
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert "lift_top_decile" in payload["metrics"]
    assert payload["metrics"]["lift_top_decile"]["rag"] in {"Green", "Yellow", "Red", "Gray"}


def test_cli_validate_lgd(tmp_path):
    sample = os.path.join(ROOT, "examples", "sample_lgd_ead_data.csv")
    result = _run(
        [
            "validate",
            "--data", sample,
            "--model-type", "lgd",
            "--actual", "realized_lgd",
            "--predicted", "predicted_lgd",
        ]
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert {"mae", "rmse", "bias"}.issubset(payload["metrics"].keys())
    # LGD now has thresholds — should produce a real RAG, not Gray.
    assert payload["metrics"]["mae"]["rag"] in {"Green", "Yellow", "Red"}
    assert payload["metrics"]["bias"]["rag"] in {"Green", "Yellow", "Red"}


def test_cli_validate_ead_ratio_metrics():
    sample = os.path.join(ROOT, "examples", "sample_lgd_ead_data.csv")
    result = _run(
        [
            "validate",
            "--data", sample,
            "--model-type", "ead",
            "--actual", "realized_ead",
            "--predicted", "predicted_ead",
        ]
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert {"mae_ratio", "rmse_ratio", "bias_ratio"}.issubset(payload["metrics"].keys())
    assert payload["metrics"]["mae_ratio"]["rag"] in {"Green", "Yellow", "Red"}
    # Default normalizer should come from policy.
    assert payload["ead_normalizer"] == "mean_realized"


def test_cli_validate_ead_with_total_exposure_normalizer():
    sample = os.path.join(ROOT, "examples", "sample_lgd_ead_data.csv")
    result = _run(
        [
            "validate",
            "--data", sample,
            "--model-type", "ead",
            "--actual", "realized_ead",
            "--predicted", "predicted_ead",
            "--ead-normalizer", "total_exposure",
        ]
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ead_normalizer"] == "total_exposure"


def test_cli_validate_missing_columns(tmp_path):
    csv = tmp_path / "tiny.csv"
    csv.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
    result = _run(
        [
            "validate",
            "--data", str(csv),
            "--model-type", "scoring",
            "--target", "target",
            "--score", "score",
        ]
    )
    assert result.returncode == 4
    payload = json.loads(result.stdout)
    assert payload["schema"]["required_columns"]["pass"] is False


def test_cli_note_add(tmp_path):
    target = tmp_path / "notes.md"
    result = _run(
        [
            "note",
            "add",
            "--text", "표본 부족 사례 1건",
            "--model", "PD-corp",
            "--path", str(target),
        ]
    )
    assert result.returncode == 0, result.stderr
    assert target.exists()
    text = target.read_text(encoding="utf-8")
    assert "PD-corp" in text
    assert "표본 부족 사례 1건" in text


def test_cli_policy_governance_real_repo_exits_zero():
    res = _run(["policy-governance"])
    assert res.returncode == 0, res.stdout + res.stderr
    payload = json.loads(res.stdout)
    assert payload["manifest_governance"]["all_require_human_approval"] is True


def test_cli_policy_governance_violation_exits_6(tmp_path):
    bad_manifest = tmp_path / "manifest.json"
    bad_manifest.write_text(json.dumps({
        "entries": [
            {
                "change_id": "CHG-9090",
                "component": "harness/threshold_policy.json",
                "human_approval_required": False,
            }
        ]
    }), encoding="utf-8")
    res = _run([
        "policy-governance",
        "--manifest-path", str(bad_manifest),
    ])
    assert res.returncode == 6


def test_cli_policy_governance_json_only_is_compact():
    res = _run(["policy-governance", "--json-only"])
    assert res.returncode == 0, res.stderr
    # Compact JSON is exactly one line and parses cleanly.
    stdout = res.stdout.rstrip("\n")
    assert "\n" not in stdout, "expected compact single-line JSON"
    payload = json.loads(stdout)
    assert payload["manifest_governance"]["all_require_human_approval"] is True


def test_cli_policy_governance_require_lock_exits_7(tmp_path):
    res = _run([
        "policy-governance",
        "--lock-path", str(tmp_path / "missing.lock.json"),
        "--require-lock",
    ])
    assert res.returncode == 7
    payload = json.loads(res.stdout)
    assert payload["lock"]["is_synced"] is False


def test_cli_policy_lock_dry_run_does_not_write(tmp_path):
    fake_policy = tmp_path / "policy.json"
    fake_policy.write_text("{}", encoding="utf-8")
    lock_path = tmp_path / "policy.lock.json"
    res = _run([
        "policy-lock",
        "--change-id", "CHG-9999",
        "--policy-path", str(fake_policy),
        "--lock-path", str(lock_path),
    ])
    assert res.returncode == 0, res.stderr
    payload = json.loads(res.stdout)
    assert payload["would_write"] is True
    assert not lock_path.exists()


def test_cli_policy_lock_confirm_writes_lock(tmp_path):
    fake_policy = tmp_path / "policy.json"
    fake_policy.write_text("{}", encoding="utf-8")
    lock_path = tmp_path / "policy.lock.json"
    res = _run([
        "policy-lock",
        "--change-id", "CHG-9998",
        "--confirm",
        "--policy-path", str(fake_policy),
        "--lock-path", str(lock_path),
    ])
    assert res.returncode == 0, res.stderr
    payload = json.loads(res.stdout)
    assert payload["would_write"] is False
    assert lock_path.exists()
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    assert lock["approved_change_id"] == "CHG-9998"


def test_cli_policy_lock_rejects_bad_change_id(tmp_path):
    fake_policy = tmp_path / "policy.json"
    fake_policy.write_text("{}", encoding="utf-8")
    res = _run([
        "policy-lock",
        "--change-id", "not-valid",
        "--policy-path", str(fake_policy),
    ])
    assert res.returncode == 4


def test_cli_note_blocks_pii(tmp_path):
    target = tmp_path / "notes.md"
    result = _run(
        [
            "note",
            "add",
            "--text", "메일 user@example.com 확인 필요",
            "--model", "PD-corp",
            "--path", str(target),
        ]
    )
    assert result.returncode == 5
    assert not target.exists()


def test_cli_report_renders_nine_sections(tmp_path):
    sample = os.path.join(ROOT, "examples", "sample_credit_score_data.csv")
    json_out = tmp_path / "report.json"
    md_out = tmp_path / "report.md"
    res1 = _run(
        [
            "validate",
            "--data", sample,
            "--model-type", "scoring",
            "--target", "target",
            "--score", "score",
            "--out", str(json_out),
        ]
    )
    assert res1.returncode == 0, res1.stderr
    res2 = _run(["report", "--input", str(json_out), "--out", str(md_out)])
    assert res2.returncode == 0, res2.stderr
    text = md_out.read_text(encoding="utf-8")
    for header in [
        "## 1. 검증 요약",
        "## 2. 입력 데이터 점검",
        "## 3. 주요 지표",
        "## 4. 세부 분석",
        "## 5. 이상 징후",
        "## 6. 한계",
        "## 7. 검증 의견 초안",
        "## 8. 추가 확인사항",
        "## 9. 감사추적",
    ]:
        assert header in text


def test_cli_report_missing_input(tmp_path):
    res = _run(["report", "--input", str(tmp_path / "nope.json")])
    assert res.returncode == 4


def test_cli_report_no_input_returns_error(tmp_path):
    res = _run(["report"])
    assert res.returncode == 4


def test_cli_report_scenario_includes_fit_rag(tmp_path):
    """Scenario report attaches RAG for R²/VIF/condition_index from policy."""
    hist = os.path.join(ROOT, "examples", "sample_macro_history.csv")
    sc = os.path.join(ROOT, "examples", "sample_macro_scenario.csv")
    json_out = tmp_path / "scenario.json"
    md_out = tmp_path / "scenario.md"
    res1 = _run([
        "validate-scenario",
        "--hist-data", hist,
        "--scenario-data", sc,
        "--target", "pd_multiplier",
        "--features", "gdp_growth,unemployment,bond_spread",
        "--scenario-col", "scenario",
        "--period-col", "period",
        "--pred-col-in-scenario", "pd_multiplier",
        "--multiplier-floors", "base=1.0,adverse=1.0,severe=1.0",
        "--out", str(json_out),
    ])
    assert res1.returncode == 0, res1.stderr
    res2 = _run(["report", "--scenario-input", str(json_out), "--out", str(md_out)])
    assert res2.returncode == 0, res2.stderr
    text = md_out.read_text(encoding="utf-8")
    assert "적합도 RAG" in text
    # The synthetic data is well-fit, so r_squared should be Green (>=0.7).
    assert "r_squared" in text and "Green" in text
    # VIF max should appear in the fit-RAG block.
    assert "vif_max" in text
    assert "condition_index_max" in text


def test_cli_report_include_stationarity_rag(tmp_path):
    hist = os.path.join(ROOT, "examples", "sample_macro_history.csv")
    sc = os.path.join(ROOT, "examples", "sample_macro_scenario.csv")
    json_out = tmp_path / "scenario.json"
    md_out = tmp_path / "scenario.md"
    res1 = _run([
        "validate-scenario",
        "--hist-data", hist,
        "--scenario-data", sc,
        "--target", "pd_multiplier",
        "--features", "gdp_growth,unemployment,bond_spread",
        "--scenario-col", "scenario",
        "--period-col", "period",
        "--pred-col-in-scenario", "pd_multiplier",
        "--multiplier-floors", "base=1.0,adverse=1.0,severe=1.0",
        "--out", str(json_out),
    ])
    assert res1.returncode == 0, res1.stderr
    res2 = _run([
        "report", "--scenario-input", str(json_out),
        "--include-stationarity-rag",
        "--out", str(md_out),
    ])
    assert res2.returncode == 0, res2.stderr
    text = md_out.read_text(encoding="utf-8")
    assert "Stationarity RAG" in text
    # Real synthetic dataset has gdp_growth marginal; expect Yellow or Green.
    assert any(s in text for s in ("RAG: **Green**", "RAG: **Yellow**", "RAG: **Red**"))


def test_cli_report_threshold_overrides_invalid_returns_6(tmp_path):
    json_out = tmp_path / "scenario.json"
    json_out.write_text(json.dumps({"fit": {}, "severity": {"order": {}}, "multiplier_floors": []}),
                        encoding="utf-8")
    bad_policy = tmp_path / "bad.json"
    bad_policy.write_text('{"metrics": {"x": {"direction": "diagonal", "green_threshold": 0, "yellow_threshold": 0}}}',
                          encoding="utf-8")
    res = _run([
        "report", "--scenario-input", str(json_out),
        "--threshold-overrides", str(bad_policy),
    ])
    assert res.returncode == 6


def test_cli_report_renders_scenario_input(tmp_path):
    hist = os.path.join(ROOT, "examples", "sample_macro_history.csv")
    sc = os.path.join(ROOT, "examples", "sample_macro_scenario.csv")
    json_out = tmp_path / "scenario.json"
    md_out = tmp_path / "scenario.md"
    res1 = _run(
        [
            "validate-scenario",
            "--hist-data", hist,
            "--scenario-data", sc,
            "--target", "pd_multiplier",
            "--features", "gdp_growth,unemployment,bond_spread",
            "--scenario-col", "scenario",
            "--period-col", "period",
            "--pred-col-in-scenario", "pd_multiplier",
            "--multiplier-floors", "base=1.0,adverse=1.0,severe=1.0",
            "--out", str(json_out),
        ]
    )
    assert res1.returncode == 0, res1.stderr
    res2 = _run(["report", "--scenario-input", str(json_out), "--out", str(md_out)])
    assert res2.returncode == 0, res2.stderr
    text = md_out.read_text(encoding="utf-8")
    assert "## 1. 검증 요약" in text
    assert "PD multiplier" in text or "시나리오 회귀" in text
    assert "ADF" in text or "stationarity" in text.lower()
    assert "시나리오 결과" in text
    assert "Multiplier floor" in text
    assert "Durbin–Watson" in text


def test_cli_validate_rejects_malformed_policy(tmp_path, monkeypatch):
    """When the loaded policy fails schema validation, validate exits 6."""
    bad_policy = tmp_path / "bad_policy.json"
    bad_policy.write_text(
        json.dumps(
            {
                "metrics": {
                    "ks": {"direction": "diagonal", "green_threshold": 0.4, "yellow_threshold": 0.3}
                }
            }
        ),
        encoding="utf-8",
    )
    # Point the loader at the bad policy via env-injected module path.
    sample = os.path.join(ROOT, "examples", "sample_credit_score_data.csv")
    env = os.environ.copy()
    env["QVA_TEST_BAD_POLICY"] = str(bad_policy)
    # Run validate but inject the bad policy via monkey-patching the loader
    # by exporting a shim module path. Simplest path: set DEFAULT_POLICY_PATH
    # via PYTHONPATH-loaded sitecustomize is overkill; instead exercise the
    # `thresholds --path` flag which reuses _load_validated_policy.
    result = subprocess.run(
        [sys.executable, "-m", "quant_validation_agent",
         "thresholds", "--path", str(bad_policy), "--metric", "ks"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 6, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["error"] == "policy_invalid"


def test_cli_validate_writes_run_log(tmp_path):
    sample = os.path.join(ROOT, "examples", "sample_credit_score_data.csv")
    log_dir = tmp_path / "runlogs"
    result = _run(
        [
            "validate",
            "--data", sample,
            "--model-type", "scoring",
            "--target", "target",
            "--score", "score",
            "--log-dir", str(log_dir),
        ]
    )
    assert result.returncode == 0, result.stderr
    files = list(log_dir.glob("run_*.json")) if log_dir.exists() else []
    assert len(files) == 1
    payload = json.loads(files[0].read_text(encoding="utf-8"))
    assert payload["request_summary"].startswith("validate ")
    assert "main_results" in payload


def test_cli_validate_pd_calibration_aggregated(tmp_path):
    sample = os.path.join(ROOT, "examples", "sample_pd_timeseries.csv")
    out = tmp_path / "pdcal.json"
    result = _run(
        [
            "validate-pd-calibration",
            "--data", sample,
            "--pred-col", "predicted_pd",
            "--default-col", "defaults",
            "--count-col", "count",
            "--bucket-col", "grade",
            "--hl-bins", "5",
            "--out", str(out),
        ]
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert "metrics" in payload
    assert "brier" in payload["metrics"] and "pd_bias" in payload["metrics"]
    assert "hosmer_lemeshow" in payload
    assert "spiegelhalter_z" in payload
    assert payload["binomial_per_bucket"] is not None
    assert out.exists()


def test_cli_validate_pd_calibration_with_hl_rag(tmp_path):
    sample = os.path.join(ROOT, "examples", "sample_pd_timeseries.csv")
    result = _run(
        [
            "validate-pd-calibration",
            "--data", sample,
            "--pred-col", "predicted_pd",
            "--default-col", "defaults",
            "--count-col", "count",
            "--bucket-col", "grade",
            "--hl-bins", "5",
            "--hl-rag",
        ]
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["hl_rag_enabled"] is True
    assert "hl_pvalue" in payload["metrics"]
    assert "spiegel_pvalue" in payload["metrics"]
    assert payload["metrics"]["hl_pvalue"]["rag"] in {"Green", "Yellow", "Red", "Gray"}


def test_cli_validate_pd_calibration_missing_columns(tmp_path):
    csv = tmp_path / "tiny.csv"
    csv.write_text("a,b\n1,2\n", encoding="utf-8")
    result = _run(
        [
            "validate-pd-calibration",
            "--data", str(csv),
            "--pred-col", "predicted_pd",
            "--default-col", "default_flag",
        ]
    )
    assert result.returncode == 4


def test_cli_validate_scenario_with_supplied_multipliers(tmp_path):
    hist = os.path.join(ROOT, "examples", "sample_macro_history.csv")
    sc = os.path.join(ROOT, "examples", "sample_macro_scenario.csv")
    out = tmp_path / "scenario_report.json"
    result = _run(
        [
            "validate-scenario",
            "--hist-data", hist,
            "--scenario-data", sc,
            "--target", "pd_multiplier",
            "--features", "gdp_growth,unemployment,bond_spread",
            "--scenario-col", "scenario",
            "--period-col", "period",
            "--pred-col-in-scenario", "pd_multiplier",
            "--multiplier-floors", "base=1.0,adverse=1.0,severe=1.0",
            "--expected-signs", "gdp_growth=-,unemployment=+,bond_spread=+",
            "--out", str(out),
        ]
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert "fit" in payload and "severity" in payload
    assert payload["severity"]["order"]["n_violation_total"] == 0
    assert out.exists()
