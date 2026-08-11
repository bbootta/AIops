"""Round 34 — CLI 카탈로그 정합성 sync gate.

cli_index / vta dispatch / README 가 실제 CLI 모듈 집합과 어긋나는 것을
재발 방지한다 (R34 리뷰에서 7개 CLI 누락 발견).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _modules_with_cli() -> set[str]:
    """tools/ 에서 `if __name__ == "__main__"` 을 가진 모듈명 집합."""
    out: set[str] = set()
    for p in sorted((ROOT / "tools").glob("*.py")):
        if p.name == "__init__.py":
            continue
        if '__name__ == "__main__"' in p.read_text(encoding="utf-8"):
            out.add(f"tools.{p.stem}")
    return out


def test_cli_index_covers_all_cli_modules():
    """__main__ 을 가진 모든 tools 모듈은 cli_index 에 등재돼야 한다."""
    from tools.cli_index import CLI_MODULES

    indexed = {m for m, _ in CLI_MODULES}
    actual = _modules_with_cli()
    missing = actual - indexed
    assert not missing, f"cli_index 누락: {sorted(missing)}"
    stale = indexed - actual
    assert not stale, f"cli_index 에 있으나 CLI 아님: {sorted(stale)}"


def test_vta_dispatch_targets_exist():
    """vta dispatch 의 모든 대상 모듈이 실제 CLI 모듈이어야 한다."""
    from vta.cli.__main__ import _DISPATCH

    actual = _modules_with_cli()
    bad = {m for m in _DISPATCH.values() if m not in actual}
    assert not bad, f"vta dispatch 대상이 CLI 아님: {sorted(bad)}"


def test_vta_dispatch_covers_new_tools():
    from vta.cli.__main__ import _DISPATCH

    assert ("workflow", "viz") in _DISPATCH
    assert ("benchmark",) in _DISPATCH
    assert ("kpi",) in _DISPATCH
    assert ("dashboard",) in _DISPATCH
    assert ("report", "pdf") in _DISPATCH


def test_readme_mentions_each_cli_module():
    """cli_index 의 모든 모듈이 README 에 언급돼야 한다 (cli_index 자신 제외)."""
    from tools.cli_index import CLI_MODULES

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    missing = [
        m for m, _ in CLI_MODULES
        if m != "tools.cli_index" and m not in readme
    ]
    assert not missing, f"README 미기재 CLI: {missing}"


def test_cli_index_renders_all_rows():
    from tools.cli_index import CLI_MODULES, build_index, render_markdown

    md = render_markdown(build_index())
    for m, _ in CLI_MODULES:
        assert f"`{m}`" in md


def test_readme_mentions_each_policy_file():
    """harness/ 의 모든 정책 SSoT (schema 제외) 가 README 정책 표에 언급돼야 한다."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    missing = []
    for p in sorted((ROOT / "harness").glob("*.json")):
        if p.name.endswith(".schema.json"):
            continue
        stem = p.stem  # 예: capital_adequacy_thresholds
        base = stem.removesuffix("_thresholds")
        if stem not in readme and base not in readme:
            missing.append(p.name)
    assert not missing, f"README 정책 표 미기재: {missing}"


def test_vta_cli_dispatches_benchmark(tmp_path):
    """python -m vta benchmark 가 v1 tools.benchmark 로 dispatch 된다."""
    out = tmp_path / "bench.json"
    env_root = str(ROOT)
    res = subprocess.run(
        [sys.executable, "-m", "vta", "benchmark",
         "--n", "200", "--runs", "1", "--json", "--out", str(out)],
        cwd=env_root, capture_output=True, text=True,
        env={"PYTHONPATH": f"{env_root}/src:{env_root}", "PATH": "/usr/bin:/bin:/usr/local/bin"},
    )
    assert res.returncode == 0, res.stderr
    assert out.exists()
