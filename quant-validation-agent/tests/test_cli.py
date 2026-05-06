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
