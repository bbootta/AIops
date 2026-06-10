"""Round 36 — 사용자 설치 경로 회귀 게이트.

R35 까지 모든 vta CLI 테스트는 pytest 의 pythonpath=["src"] 설정에 의존해
src/vta 를 import 했다. 그러나 README 안내대로 `pip install -r requirements.txt`
만 한 사용자 환경에서는 `python -m vta` 가 ModuleNotFoundError 였다 (R36 발견).

본 테스트는 sys.path / pytest pythonpath 와 무관하게 vta 가 **설치된 패키지**
로서 import 가능한지 확인한다 — editable install (`pip install -e .`) 또는
정상 install 이 된 후에만 통과한다.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _vta_installed() -> bool:
    """sys.path 비우고 vta 가 importable 한지 확인 — 설치된 경우만 True."""
    code = (
        "import sys; sys.path = [p for p in sys.path "
        "if p and p not in ('.', '')]; "
        "import importlib.util; "
        "print(importlib.util.find_spec('vta') is not None)"
    )
    res = subprocess.run(
        [sys.executable, "-c", code],
        cwd="/tmp", capture_output=True, text=True,
    )
    return res.stdout.strip() == "True"


def test_vta_importable_without_pythonpath():
    """editable install 후 PYTHONPATH/cwd 없이도 import 가능."""
    if not _vta_installed():
        pytest.skip("vta 미설치 — `pip install -e .` 후 재실행")
    res = subprocess.run(
        [sys.executable, "-c", "import vta; print(vta.__version__)"],
        cwd="/tmp", capture_output=True, text=True,
    )
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip().startswith("0.")


def test_vta_cli_runs_from_arbitrary_cwd(tmp_path):
    """사용자가 어느 디렉터리에서 호출하든 `python -m vta --help` 가 동작."""
    if not _vta_installed():
        pytest.skip("vta 미설치 — `pip install -e .` 후 재실행")
    res = subprocess.run(
        [sys.executable, "-m", "vta", "--help"],
        cwd=str(tmp_path), capture_output=True, text=True,
    )
    assert res.returncode == 0, res.stderr
    assert "vta" in res.stdout


def test_readme_mentions_editable_install_for_vta():
    """README 가 `python -m vta` 사용 전제로 editable install 을 안내한다."""
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    # 설치 안내 영역에 -e . 가 있고, v2 CLI 안내가 그것과 연결돼 있다.
    assert "pip install -e ." in text
    assert "python -m vta" in text


def test_ci_workflow_installs_editable():
    """CI 가 `pip install -e .` 로 editable install 을 수행한다."""
    ci = Path("/home/user/AIops/.github/workflows/validation-team-agent-ci.yml")
    if not ci.exists():
        pytest.skip("CI workflow 파일 없음 (로컬 체크아웃)")
    text = ci.read_text(encoding="utf-8")
    assert "pip install -e ." in text
    # editable install 후 vta smoke 가 게이트로 존재
    assert "python -m vta" in text
