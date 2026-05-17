from pathlib import Path

from tools import policy_lint as pl


def test_no_policy_files_returns_passed(tmp_path):
    out = pl.check_sample_size_alignment(
        code_defaults={"min_total": 1000, "min_defaults": 50, "min_per_grade": 30},
        policies_dir=tmp_path,
    )
    assert out["passed"] is True
    assert out["conflicts"] == []


def test_detects_conflict_with_code(tmp_path):
    (tmp_path / "credit.md").write_text(
        "표본 적정성: min_total = 500\n",
        encoding="utf-8",
    )
    out = pl.check_sample_size_alignment(
        code_defaults={"min_total": 1000, "min_defaults": 50, "min_per_grade": 30},
        policies_dir=tmp_path,
    )
    assert out["passed"] is False
    assert any(c["key"] == "min_total" and c["policy"] == 500 for c in out["conflicts"])


def test_passes_when_code_and_policy_agree(tmp_path):
    (tmp_path / "credit.md").write_text(
        "min_per_grade = 30\nmin_defaults = 50\n",
        encoding="utf-8",
    )
    out = pl.check_sample_size_alignment(
        code_defaults={"min_total": 1000, "min_defaults": 50, "min_per_grade": 30},
        policies_dir=tmp_path,
    )
    assert out["passed"] is True


def test_main_include_sample_size_flag(tmp_path, capsys):
    """기존 lint_policies는 통과, sample_size 점검만 추가 실행."""
    metric = tmp_path / "metric.md"
    pol = tmp_path / "policies"
    pol.mkdir()
    metric.write_text("", encoding="utf-8")
    rc = pl.main([
        "--metric-policy", str(metric),
        "--policies-dir", str(pol),
        "--include-sample-size",
    ])
    captured = capsys.readouterr().out
    assert rc == 0
    assert "sample_size_alignment" in captured
