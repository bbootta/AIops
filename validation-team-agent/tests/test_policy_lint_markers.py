from pathlib import Path

from tools import policy_lint as pl


def test_marker_extracts_threshold():
    text = "Some prose. <!-- threshold: KS>=0.30 --> more prose."
    items = pl._extract(text)
    assert ("KS", "≥", 0.30) in items


def test_marker_with_spaces_and_lt():
    text = "<!-- threshold:  PSI < 0.10  -->"
    items = pl._extract(text)
    assert ("PSI", "<", 0.10) in items


def test_marker_normalizes_auc_to_auroc():
    text = "<!-- threshold: AUC>=0.70 -->"
    items = pl._extract(text)
    assert ("AUROC", "≥", 0.70) in items


def test_lint_uses_markers_for_conflict_detection(tmp_path: Path):
    metric = tmp_path / "metric.md"
    pol_dir = tmp_path / "policies"
    pol_dir.mkdir()
    metric.write_text("KS ≥ 0.30", encoding="utf-8")
    (pol_dir / "credit.md").write_text(
        "산문에는 임계 표기가 없지만 마커로만 명시:\n"
        "<!-- threshold: KS>=0.40 -->\n",
        encoding="utf-8",
    )
    out = pl.lint_policies(metric, pol_dir)
    assert out["passed"] is False
    assert any(c["metric"] == "KS" for c in out["conflicts"])
