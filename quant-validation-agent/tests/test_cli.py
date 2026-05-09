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
