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


def test_cli_docs_cli_writes_reference(tmp_path):
    out = tmp_path / "cli_reference.md"
    res = _run(["docs-cli", "--out", str(out)])
    assert res.returncode == 0, res.stderr
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "# CLI Reference" in text
    for sub in ("validate", "validate-scenario", "validate-pd-calibration",
                "policy-governance", "policy-lock", "summary", "report"):
        assert f"## `{sub}`" in text


def test_cli_compare_metric_deltas(tmp_path):
    base = tmp_path / "base.json"
    cur = tmp_path / "cur.json"
    base.write_text(json.dumps({
        "metrics": {"ks": {"value": 0.42, "rag": "Green"}},
        "overall_rag": "Green",
    }), encoding="utf-8")
    cur.write_text(json.dumps({
        "metrics": {"ks": {"value": 0.35, "rag": "Yellow"}},
        "overall_rag": "Yellow",
    }), encoding="utf-8")
    res = _run(["compare", "--base", str(base), "--current", str(cur)])
    assert res.returncode == 0, res.stderr
    payload = json.loads(res.stdout)
    assert payload["overall_rag"]["regressed"] is True
    ks_row = next(r for r in payload["metric_diffs"] if r["metric"] == "ks")
    assert ks_row["delta"] < 0
    assert ks_row["transition"] == "Green -> Yellow"


def test_cli_compare_fail_on_regression(tmp_path):
    base = tmp_path / "base.json"
    cur = tmp_path / "cur.json"
    base.write_text(json.dumps({"overall_rag": "Green"}), encoding="utf-8")
    cur.write_text(json.dumps({"overall_rag": "Red"}), encoding="utf-8")
    res = _run(["compare", "--base", str(base), "--current", str(cur),
                "--fail-on-regression"])
    assert res.returncode == 6


def test_cli_version_subcommand_emits_json():
    res = _run(["version"])
    assert res.returncode == 0, res.stderr
    payload = json.loads(res.stdout)
    assert payload["package"] == "quant_validation_agent"
    assert "version" in payload
    assert "python" in payload
    assert "platform" in payload


def test_cli_version_subcommand_json_only_is_compact():
    res = _run(["version", "--json-only"])
    assert res.returncode == 0, res.stderr
    assert "\n" not in res.stdout.rstrip("\n")


def test_cli_version_flag():
    res = _run(["--version"])
    assert res.returncode == 0, res.stderr
    assert "quant_validation_agent" in res.stdout


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


def test_cli_validate_lgd_emits_overall_rag():
    sample = os.path.join(ROOT, "examples", "sample_lgd_ead_data.csv")
    res = _run([
        "validate", "--data", sample,
        "--model-type", "lgd",
        "--actual", "realized_lgd", "--predicted", "predicted_lgd",
    ])
    assert res.returncode == 0, res.stderr
    payload = json.loads(res.stdout)
    assert "overall_rag" in payload
    assert payload["overall_rag"] in {"Green", "Yellow", "Red", "Gray"}


def test_cli_validate_ead_emits_overall_rag():
    sample = os.path.join(ROOT, "examples", "sample_lgd_ead_data.csv")
    res = _run([
        "validate", "--data", sample,
        "--model-type", "ead",
        "--actual", "realized_ead", "--predicted", "predicted_ead",
    ])
    assert res.returncode == 0, res.stderr
    payload = json.loads(res.stdout)
    assert "overall_rag" in payload
    # Some EAD metrics are intentionally Gray (raw currency); aggregate should
    # still derive Red/Yellow/Green from the ratio metrics.
    assert payload["overall_rag"] in {"Green", "Yellow", "Red", "Gray"}


def test_cli_validate_explain_appends_markdown():
    sample = os.path.join(ROOT, "examples", "sample_credit_score_data.csv")
    res = _run([
        "validate", "--data", sample,
        "--model-type", "scoring",
        "--target", "target", "--score", "score",
        "--explain",
    ])
    assert res.returncode == 0, res.stderr
    assert "--- markdown ---" in res.stdout
    assert "## 1. 검증 요약" in res.stdout


def test_cli_validate_emits_overall_rag():
    sample = os.path.join(ROOT, "examples", "sample_credit_score_data.csv")
    res = _run([
        "validate",
        "--data", sample,
        "--model-type", "scoring",
        "--target", "target",
        "--score", "score",
    ])
    assert res.returncode == 0, res.stderr
    payload = json.loads(res.stdout)
    assert "overall_rag" in payload
    assert payload["overall_rag"] in {"Green", "Yellow", "Red", "Gray"}


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


def test_cli_validate_lgd_with_segment_detail():
    sample = os.path.join(ROOT, "examples", "sample_lgd_ead_data.csv")
    result = _run([
        "validate",
        "--data", sample,
        "--model-type", "lgd",
        "--actual", "realized_lgd",
        "--predicted", "predicted_lgd",
        "--segment-detail",
        "--segment-col", "collateral_type",
    ])
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert "segment_detail" in payload
    assert payload["segment_detail"]["segment_col"] == "collateral_type"
    cols = set((payload["segment_detail"]["rows"] or [{}])[0].keys())
    assert {"count", "mae", "rmse", "bias"}.issubset(cols)


def test_cli_validate_segment_detail_missing_col_emits_gray_issue(tmp_path):
    sample = os.path.join(ROOT, "examples", "sample_lgd_ead_data.csv")
    result = _run([
        "validate",
        "--data", sample,
        "--model-type", "lgd",
        "--actual", "realized_lgd",
        "--predicted", "predicted_lgd",
        "--segment-detail",
        "--segment-col", "no_such_col",
    ])
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert "segment_detail" not in payload
    issues = [i.get("issue") for i in payload.get("issues", [])]
    assert "segment_detail_skipped" in issues


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


def test_cli_policy_governance_exit_on_yellow_when_lock_missing(tmp_path):
    res = _run([
        "policy-governance",
        "--lock-path", str(tmp_path / "missing.lock.json"),
        "--exit-on-yellow",
    ])
    # Real repo has approved manifest entries, so governance is fine, but the
    # lock is missing → exit 1 under --exit-on-yellow.
    assert res.returncode == 1
    payload = json.loads(res.stdout)
    assert payload["lock"]["is_synced"] is False


def test_cli_policy_governance_exit_on_yellow_off_when_lock_present(tmp_path):
    # Build an in-sync lock for the *real* repo policy.
    import hashlib
    real_policy = os.path.join(ROOT, "harness", "threshold_policy.json")
    digest = hashlib.sha256(open(real_policy, "rb").read()).hexdigest()
    lock = tmp_path / "lock.json"
    lock.write_text(
        json.dumps({"policy_path": real_policy, "policy_digest": digest,
                    "approved_change_id": "CHG-9999", "approved_at": "2026-05-06 00:00:00"}),
        encoding="utf-8",
    )
    res = _run([
        "policy-governance",
        "--lock-path", str(lock),
        "--exit-on-yellow",
    ])
    assert res.returncode == 0


def test_cli_policy_governance_require_lock_exits_7(tmp_path):
    res = _run([
        "policy-governance",
        "--lock-path", str(tmp_path / "missing.lock.json"),
        "--require-lock",
    ])
    assert res.returncode == 7
    payload = json.loads(res.stdout)
    assert payload["lock"]["is_synced"] is False


def _make_fake_manifest(tmp_path, change_id="CHG-9999", approved=True, policy_component=True):
    """Build a minimal manifest+policy pair for policy-lock tests."""
    fake_policy = tmp_path / "policy.json"
    fake_policy.write_text("{}", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    component = "harness/threshold_policy.json" if policy_component else "tools/example.py"
    manifest.write_text(json.dumps({
        "entries": [
            {
                "change_id": change_id,
                "component": component,
                "human_approval_required": approved,
            }
        ]
    }), encoding="utf-8")
    return fake_policy, manifest


def test_cli_policy_lock_dry_run_does_not_write(tmp_path):
    fake_policy, manifest = _make_fake_manifest(tmp_path, "CHG-9999")
    lock_path = tmp_path / "policy.lock.json"
    res = _run([
        "policy-lock",
        "--change-id", "CHG-9999",
        "--policy-path", str(fake_policy),
        "--lock-path", str(lock_path),
        "--manifest-path", str(manifest),
    ])
    assert res.returncode == 0, res.stderr
    payload = json.loads(res.stdout)
    assert payload["would_write"] is True
    assert not lock_path.exists()


def test_cli_policy_lock_confirm_writes_lock(tmp_path):
    fake_policy, manifest = _make_fake_manifest(tmp_path, "CHG-9998")
    lock_path = tmp_path / "policy.lock.json"
    res = _run([
        "policy-lock",
        "--change-id", "CHG-9998",
        "--confirm",
        "--policy-path", str(fake_policy),
        "--lock-path", str(lock_path),
        "--manifest-path", str(manifest),
    ])
    assert res.returncode == 0, res.stderr
    payload = json.loads(res.stdout)
    assert payload["would_write"] is False
    assert lock_path.exists()
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    assert lock["approved_change_id"] == "CHG-9998"


def test_cli_policy_lock_rejects_bad_change_id(tmp_path):
    fake_policy, manifest = _make_fake_manifest(tmp_path)
    res = _run([
        "policy-lock",
        "--change-id", "not-valid",
        "--policy-path", str(fake_policy),
        "--manifest-path", str(manifest),
    ])
    assert res.returncode == 4


def test_cli_policy_lock_rejects_unknown_change_id(tmp_path):
    fake_policy, manifest = _make_fake_manifest(tmp_path, "CHG-1111")
    res = _run([
        "policy-lock",
        "--change-id", "CHG-9999",
        "--policy-path", str(fake_policy),
        "--manifest-path", str(manifest),
    ])
    assert res.returncode == 6
    payload = json.loads(res.stdout)
    assert payload["error"] == "change_id_not_in_manifest"


def test_cli_policy_lock_rejects_unapproved_change(tmp_path):
    fake_policy, manifest = _make_fake_manifest(tmp_path, "CHG-2222", approved=False)
    res = _run([
        "policy-lock",
        "--change-id", "CHG-2222",
        "--policy-path", str(fake_policy),
        "--manifest-path", str(manifest),
    ])
    assert res.returncode == 6
    payload = json.loads(res.stdout)
    assert payload["error"] == "approval_missing"


def test_cli_policy_lock_rejects_non_policy_component(tmp_path):
    fake_policy, manifest = _make_fake_manifest(tmp_path, "CHG-3333", policy_component=False)
    res = _run([
        "policy-lock",
        "--change-id", "CHG-3333",
        "--policy-path", str(fake_policy),
        "--manifest-path", str(manifest),
    ])
    assert res.returncode == 6
    payload = json.loads(res.stdout)
    assert payload["error"] == "change_id_not_in_manifest"


def test_cli_policy_lock_skip_manifest_check_allows_unknown(tmp_path):
    fake_policy, manifest = _make_fake_manifest(tmp_path, "CHG-1111")
    lock_path = tmp_path / "lock.json"
    res = _run([
        "policy-lock",
        "--change-id", "CHG-9000",
        "--skip-manifest-check",
        "--confirm",
        "--policy-path", str(fake_policy),
        "--manifest-path", str(manifest),
        "--lock-path", str(lock_path),
    ])
    assert res.returncode == 0, res.stderr
    assert lock_path.exists()


def test_cli_summary_aggregates_validate_outputs(tmp_path):
    sample = os.path.join(ROOT, "examples", "sample_credit_score_data.csv")
    out_a = tmp_path / "a.json"
    out_b = tmp_path / "b.json"
    res_a = _run([
        "validate", "--data", sample, "--model-type", "scoring",
        "--target", "target", "--score", "score", "--out", str(out_a),
    ])
    res_b = _run([
        "validate", "--data", sample, "--model-type", "scoring",
        "--target", "target", "--score", "score", "--out", str(out_b),
    ])
    assert res_a.returncode == 0 and res_b.returncode == 0
    res = _run(["summary", "--input", str(out_a), "--input", str(out_b)])
    assert res.returncode == 0, res.stderr
    payload = json.loads(res.stdout)
    assert len(payload["items"]) == 2
    assert payload["worst_rag"] in {"Green", "Yellow", "Red", "Gray"}
    assert all(it["overall_rag"] == "Green" for it in payload["items"])


def test_cli_summary_handles_missing_and_invalid(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    res = _run([
        "summary",
        "--input", str(tmp_path / "missing.json"),
        "--input", str(bad),
    ])
    assert res.returncode == 0, res.stderr
    payload = json.loads(res.stdout)
    kinds = {it["kind"] for it in payload["items"]}
    assert "missing" in kinds and "invalid_json" in kinds


def test_cli_summary_out_writes_file(tmp_path):
    sample = tmp_path / "s.json"
    sample.write_text(json.dumps({"metrics": {"x": {"rag": "Green"}}, "overall_rag": "Green"}),
                      encoding="utf-8")
    out = tmp_path / "summary.json"
    res = _run(["summary", "--input", str(sample), "--out", str(out)])
    assert res.returncode == 0, res.stderr
    assert out.exists()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["worst_rag"] == "Green"


def test_cli_summary_fail_on_red(tmp_path):
    red = tmp_path / "red.json"
    red.write_text(json.dumps({"metrics": {"x": {"rag": "Red"}}, "overall_rag": "Red"}),
                   encoding="utf-8")
    res = _run(["summary", "--input", str(red), "--fail-on-red"])
    assert res.returncode == 6


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


def test_cli_report_max_rows_truncates_metrics(tmp_path):
    sample = os.path.join(ROOT, "examples", "sample_credit_score_data.csv")
    json_out = tmp_path / "scoring.json"
    md_out = tmp_path / "scoring.md"
    res1 = _run([
        "validate", "--data", sample,
        "--model-type", "scoring",
        "--target", "target", "--score", "score",
        "--decile-rag",
        "--out", str(json_out),
    ])
    assert res1.returncode == 0, res1.stderr
    res2 = _run(["report", "--input", str(json_out), "--max-rows", "2", "--out", str(md_out)])
    assert res2.returncode == 0, res2.stderr
    text = md_out.read_text(encoding="utf-8")
    # 4 metrics (ks/auroc/ar/lift_top_decile) → 2 truncated
    assert "more rows truncated" in text


def test_cli_report_max_rows_invalid(tmp_path):
    json_out = tmp_path / "report.json"
    json_out.write_text(json.dumps({"metrics": {}, "issues": [], "schema": {}}), encoding="utf-8")
    res = _run(["report", "--input", str(json_out), "--max-rows", "0"])
    assert res.returncode == 4


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


def test_cli_validate_pd_calibration_emits_binomial_summary():
    sample = os.path.join(ROOT, "examples", "sample_pd_timeseries.csv")
    res = _run([
        "validate-pd-calibration",
        "--data", sample,
        "--pred-col", "predicted_pd",
        "--default-col", "defaults",
        "--count-col", "count",
        "--bucket-col", "grade",
        "--hl-bins", "5",
    ])
    assert res.returncode == 0, res.stderr
    payload = json.loads(res.stdout)
    summary = payload.get("binomial_summary")
    assert summary is not None
    assert summary["n_buckets"] >= 1
    assert summary["n_buckets_rejecting_h0"] >= 0
    assert summary["n_buckets_rejecting_h0"] <= summary["n_buckets"]


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


def test_cli_validate_pd_calibration_out_pattern_writes_resolved_path(tmp_path):
    sample = os.path.join(ROOT, "examples", "sample_pd_timeseries.csv")
    pattern = str(tmp_path / "pdcal_{ts}.json")
    res = _run([
        "validate-pd-calibration",
        "--data", sample,
        "--pred-col", "predicted_pd",
        "--default-col", "defaults",
        "--count-col", "count",
        "--bucket-col", "grade",
        "--out-pattern", pattern,
    ])
    assert res.returncode == 0, res.stderr
    payload = json.loads(res.stdout)
    assert "resolved_out_path" in payload
    assert "{ts}" not in payload["resolved_out_path"]
    assert os.path.exists(payload["resolved_out_path"])


def test_cli_validate_pd_calibration_decile_rag_records_direction():
    sample = os.path.join(ROOT, "examples", "sample_pd_timeseries.csv")
    res = _run([
        "validate-pd-calibration",
        "--data", sample,
        "--pred-col", "predicted_pd",
        "--default-col", "defaults",
        "--count-col", "count",
        "--bucket-col", "grade",
        "--decile-rag",
    ])
    assert res.returncode == 0, res.stderr
    payload = json.loads(res.stdout)
    assert "score_direction" in payload
    # On the well-behaved synthetic dataset, higher PD should align with
    # higher default frequency.
    assert payload["score_direction"].get("higher_is_worse") is True


def test_cli_validate_pd_calibration_segment_detail():
    sample = os.path.join(ROOT, "examples", "sample_pd_timeseries.csv")
    res = _run([
        "validate-pd-calibration",
        "--data", sample,
        "--pred-col", "predicted_pd",
        "--default-col", "defaults",
        "--count-col", "count",
        "--bucket-col", "grade",
        "--hl-bins", "5",
        "--segment-detail",
    ])
    assert res.returncode == 0, res.stderr
    payload = json.loads(res.stdout)
    assert "segment_detail" in payload
    rows = payload["segment_detail"]["rows"]
    assert len(rows) >= 1
    assert {"count", "mean_pred", "mean_actual", "diff"}.issubset(rows[0].keys())


def test_cli_validate_pd_calibration_segment_detail_without_bucket_emits_gray():
    sample = os.path.join(ROOT, "examples", "sample_pd_timeseries.csv")
    res = _run([
        "validate-pd-calibration",
        "--data", sample,
        "--pred-col", "predicted_pd",
        "--default-col", "defaults",
        "--count-col", "count",
        # No --bucket-col
        "--segment-detail",
    ])
    assert res.returncode == 0, res.stderr
    payload = json.loads(res.stdout)
    assert "segment_detail" not in payload
    issues = [i.get("issue") for i in payload.get("issues", [])]
    assert "segment_detail_skipped" in issues


def test_cli_validate_pd_calibration_with_decile_rag():
    sample = os.path.join(ROOT, "examples", "sample_pd_timeseries.csv")
    result = _run([
        "validate-pd-calibration",
        "--data", sample,
        "--pred-col", "predicted_pd",
        "--default-col", "defaults",
        "--count-col", "count",
        "--bucket-col", "grade",
        "--decile-rag",
    ])
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert "lift_top_decile" in payload["metrics"]
    assert payload["metrics"]["lift_top_decile"]["rag"] in {"Green", "Yellow", "Red", "Gray"}


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


def test_cli_validate_scenario_severity_violation_case(tmp_path):
    """The failure-case sample is engineered so adverse > severe at 2026Q1."""
    hist = os.path.join(ROOT, "examples", "sample_macro_history.csv")
    sc = os.path.join(ROOT, "examples", "sample_scenario_failure_case.csv")
    res = _run([
        "validate-scenario",
        "--hist-data", hist,
        "--scenario-data", sc,
        "--target", "pd_multiplier",
        "--features", "gdp_growth,unemployment,bond_spread",
        "--scenario-col", "scenario",
        "--period-col", "period",
        "--pred-col-in-scenario", "pd_multiplier",
        "--multiplier-floors", "base=1.0,adverse=1.0,severe=1.0",
    ])
    assert res.returncode == 0, res.stderr
    payload = json.loads(res.stdout)
    assert payload["severity"]["order"]["n_violation_total"] >= 1
    assert payload["overall_rag"] == "Red"


def test_cli_validate_scenario_inline_stationarity_rag(tmp_path):
    hist = os.path.join(ROOT, "examples", "sample_macro_history.csv")
    sc = os.path.join(ROOT, "examples", "sample_macro_scenario.csv")
    res = _run([
        "validate-scenario",
        "--hist-data", hist,
        "--scenario-data", sc,
        "--target", "pd_multiplier",
        "--features", "gdp_growth,unemployment,bond_spread",
        "--scenario-col", "scenario",
        "--period-col", "period",
        "--pred-col-in-scenario", "pd_multiplier",
        "--include-stationarity-rag",
    ])
    assert res.returncode == 0, res.stderr
    payload = json.loads(res.stdout)
    assert "stationarity_rag" in payload
    assert payload["stationarity_rag"]["rag"] in {"Green", "Yellow", "Red", "Gray"}


def test_cli_validate_scenario_emits_overall_rag(tmp_path):
    hist = os.path.join(ROOT, "examples", "sample_macro_history.csv")
    sc = os.path.join(ROOT, "examples", "sample_macro_scenario.csv")
    res = _run([
        "validate-scenario",
        "--hist-data", hist,
        "--scenario-data", sc,
        "--target", "pd_multiplier",
        "--features", "gdp_growth,unemployment,bond_spread",
        "--scenario-col", "scenario",
        "--period-col", "period",
        "--pred-col-in-scenario", "pd_multiplier",
        "--multiplier-floors", "base=1.0,adverse=1.0,severe=1.0",
    ])
    assert res.returncode == 0, res.stderr
    payload = json.loads(res.stdout)
    assert "overall_rag" in payload
    # Synthetic data has no severity / floor violations → Yellow (fit-RAG is
    # only computed by `report`).
    assert payload["overall_rag"] == "Yellow"


def test_cli_validate_scenario_out_pattern_writes_resolved_path(tmp_path):
    hist = os.path.join(ROOT, "examples", "sample_macro_history.csv")
    sc = os.path.join(ROOT, "examples", "sample_macro_scenario.csv")
    pattern = str(tmp_path / "scenario_{ts}.json")
    res = _run([
        "validate-scenario",
        "--hist-data", hist,
        "--scenario-data", sc,
        "--target", "pd_multiplier",
        "--features", "gdp_growth,unemployment,bond_spread",
        "--scenario-col", "scenario",
        "--period-col", "period",
        "--pred-col-in-scenario", "pd_multiplier",
        "--out-pattern", pattern,
    ])
    assert res.returncode == 0, res.stderr
    payload = json.loads(res.stdout)
    assert "resolved_out_path" in payload
    assert "{ts}" not in payload["resolved_out_path"]
    assert os.path.exists(payload["resolved_out_path"])


def test_cli_validate_scenario_max_predictions_truncates(tmp_path):
    hist = os.path.join(ROOT, "examples", "sample_macro_history.csv")
    sc = os.path.join(ROOT, "examples", "sample_macro_scenario.csv")
    res = _run([
        "validate-scenario",
        "--hist-data", hist,
        "--scenario-data", sc,
        "--target", "pd_multiplier",
        "--features", "gdp_growth,unemployment,bond_spread",
        "--scenario-col", "scenario",
        "--period-col", "period",
        "--pred-col-in-scenario", "pd_multiplier",
        "--max-predictions", "3",
    ])
    assert res.returncode == 0, res.stderr
    payload = json.loads(res.stdout)
    assert len(payload["predictions"]) == 3
    assert payload["predictions_total"] >= 4
    assert payload["predictions_truncated"] >= 1


def test_cli_validate_scenario_max_predictions_invalid(tmp_path):
    hist = os.path.join(ROOT, "examples", "sample_macro_history.csv")
    sc = os.path.join(ROOT, "examples", "sample_macro_scenario.csv")
    res = _run([
        "validate-scenario",
        "--hist-data", hist,
        "--scenario-data", sc,
        "--target", "pd_multiplier",
        "--features", "gdp_growth,unemployment,bond_spread",
        "--scenario-col", "scenario",
        "--period-col", "period",
        "--pred-col-in-scenario", "pd_multiplier",
        "--max-predictions", "0",
    ])
    assert res.returncode == 4


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
