"""Detect drift between the committed docs/cli_reference.md and what
`python -m quant_validation_agent docs-cli` would currently produce.

Run `make docs-cli` (or `python -m quant_validation_agent docs-cli`) and
commit the result whenever the CLI surface changes.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(ROOT, "docs", "cli_reference.md")


def _generate(tmp_path) -> str:
    out = tmp_path / "cli_reference.md"
    res = subprocess.run(
        [sys.executable, "-m", "quant_validation_agent", "docs-cli", "--out", str(out)],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert res.returncode == 0, res.stderr
    return out.read_text(encoding="utf-8")


def test_cli_reference_exists():
    assert os.path.exists(REF), (
        "docs/cli_reference.md missing — run `python -m quant_validation_agent docs-cli`"
    )


def test_cli_reference_matches_current(tmp_path):
    committed = open(REF, "r", encoding="utf-8").read()
    generated = _generate(tmp_path)
    assert committed == generated, (
        "docs/cli_reference.md is stale. Regenerate with "
        "`python -m quant_validation_agent docs-cli --out docs/cli_reference.md`."
    )
