from pathlib import Path

from tools import policy_lint as pl


def test_extract_picks_up_canonical_thresholds():
    text = "KS ≥ 0.30, AUROC >= 0.70, PSI < 0.10, Gini ≥ 0.40"
    out = pl._extract(text)
    metrics = {(m, op, v) for m, op, v in out}
    assert ("KS", "≥", 0.30) in metrics
    assert ("AUROC", "≥", 0.70) in metrics
    assert ("PSI", "<", 0.10) in metrics
    assert ("GINI", "≥", 0.40) in metrics


def test_lint_passes_on_consistent_files(tmp_path: Path):
    metric = tmp_path / "metric.md"
    pol_dir = tmp_path / "policies"
    pol_dir.mkdir()
    metric.write_text("KS ≥ 0.30\nAUROC ≥ 0.70", encoding="utf-8")
    (pol_dir / "credit.md").write_text("KS ≥ 0.30\nAUROC ≥ 0.70", encoding="utf-8")
    out = pl.lint_policies(metric, pol_dir)
    assert out["passed"] is True
    assert out["conflicts"] == []


def test_lint_detects_cross_file_conflict(tmp_path: Path):
    metric = tmp_path / "metric.md"
    pol_dir = tmp_path / "policies"
    pol_dir.mkdir()
    metric.write_text("KS ≥ 0.30", encoding="utf-8")
    (pol_dir / "credit.md").write_text("KS ≥ 0.25", encoding="utf-8")
    out = pl.lint_policies(metric, pol_dir)
    assert out["passed"] is False
    assert any(c["metric"] == "KS" for c in out["conflicts"])


def test_lint_detects_intra_file_conflict(tmp_path: Path):
    metric = tmp_path / "metric.md"
    pol_dir = tmp_path / "policies"
    pol_dir.mkdir()
    metric.write_text("KS ≥ 0.30\n... 다른 단락 ...\nKS ≥ 0.40", encoding="utf-8")
    out = pl.lint_policies(metric, pol_dir)
    assert out["passed"] is False


def test_repository_policies_are_consistent():
    out = pl.lint_policies()
    assert out["passed"] is True, pl.format_report(out)
