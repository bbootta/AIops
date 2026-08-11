"""Round 38 — 재현가능성 인프라.

CRO 보고 기준: 모든 산출값은 *재현 가능*하고 *설명 가능* 해야 한다.
본 테스트는 provenance 모듈의 결정성과, report_pack 의 모든 페이지에
재현가능성 카드가 강제 삽입되는지를 게이트한다.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


# ---------- provenance 결정성 ----------

def test_request_fingerprint_deterministic_same_seed():
    from tools.provenance import request_fingerprint
    from tools.run_workflow_demo import build_request

    f1 = request_fingerprint(build_request(2_000, stress=False, seed=42))
    f2 = request_fingerprint(build_request(2_000, stress=False, seed=42))
    assert f1 == f2


def test_request_fingerprint_changes_with_seed():
    from tools.provenance import request_fingerprint
    from tools.run_workflow_demo import build_request

    f_a = request_fingerprint(build_request(2_000, stress=False, seed=42))
    f_b = request_fingerprint(build_request(2_000, stress=False, seed=43))
    assert f_a["df"]["sha256"] != f_b["df"]["sha256"]


def test_request_fingerprint_changes_with_stress_flag():
    from tools.provenance import request_fingerprint
    from tools.run_workflow_demo import build_request

    fn = request_fingerprint(build_request(2_000, stress=False, seed=42))
    fs = request_fingerprint(build_request(2_000, stress=True, seed=42))
    # scalar 부분이 달라진다 (capital_*, market_*, liquidity_* 등)
    assert fn["scalar_sha256"] != fs["scalar_sha256"]


def test_request_fingerprint_changes_with_column_addition():
    """columns/dtype 가 df 지문에 반영된다 — 컬럼 추가만으로 sha 변경."""
    import pandas as pd

    from tools.provenance import _df_fingerprint

    df = pd.DataFrame({"a": [1, 2, 3]})
    sha_a = _df_fingerprint(df)["sha256"]
    df2 = df.copy()
    df2["b"] = [0, 0, 0]
    sha_b = _df_fingerprint(df2)["sha256"]
    assert sha_a != sha_b


def test_policy_versions_lists_known_policies():
    from tools.provenance import policy_versions

    pv = policy_versions()
    assert "orchestration_matrix" in pv
    assert "icaap_thresholds" in pv
    assert "alm_thresholds" in pv
    # 매트릭스 버전이 1.0 이상
    assert re.match(r"^\d+\.\d+", pv["orchestration_matrix"])


def test_git_info_returns_short_rev():
    from tools.provenance import git_info

    info = git_info()
    assert "rev" in info and "branch" in info and "dirty" in info
    # repo 안에서 호출되므로 'unknown' 이 아니어야 한다
    assert info["rev"] != "unknown"


def test_build_provenance_has_reproduce_command():
    from tools.provenance import build_provenance
    from tools.run_workflow_demo import build_request

    req = build_request(500, stress=True, seed=99)
    prov = build_provenance(req, n=500, seed=99, stress=True)
    assert prov["reproduce"] == (
        "python -m tools.report_pack --n 500 --seed 99 --stress --out <dir>")
    assert prov["inputs"]["n"] == 500
    assert prov["inputs"]["stress"] is True
    assert "fingerprint" in prov["inputs"]


# ---------- report_pack provenance 강제 ----------

@pytest.fixture(scope="module")
def pack_with_prov(tmp_path_factory):
    from tools.provenance import build_provenance
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import build_request, run_demo

    out = tmp_path_factory.mktemp("pack_prov")
    demo = run_demo(800, False, 42, out / "logs")
    request = build_request(800, stress=False, seed=42)
    prov = build_provenance(request, n=800, seed=42, stress=False)
    files = build_pack(demo, request, out, provenance=prov)
    return out, files, prov


def test_every_page_contains_provenance_card(pack_with_prov):
    out, files, _ = pack_with_prov
    for p in files:
        text = p.read_text(encoding="utf-8")
        assert "Reproducibility" in text, f"{p.name}: 재현가능성 카드 누락"
        assert "재실행 명령" in text


def test_provenance_card_contains_input_hashes(pack_with_prov):
    out, _, prov = pack_with_prov
    idx = (out / "index.html").read_text(encoding="utf-8")
    df_sha = prov["inputs"]["fingerprint"]["df"]["sha256"][:16]
    scalar_sha = prov["inputs"]["fingerprint"]["scalar_sha256"][:16]
    assert df_sha in idx
    assert scalar_sha in idx


def test_provenance_card_lists_policy_versions(pack_with_prov):
    out, _, _ = pack_with_prov
    idx = (out / "index.html").read_text(encoding="utf-8")
    # 매트릭스/ICAAP/ALM 정책 버전이 카드에 등장
    for policy in ("orchestration_matrix", "icaap_thresholds", "alm_thresholds"):
        assert policy in idx


def test_provenance_card_shows_git_rev(pack_with_prov):
    out, _, prov = pack_with_prov
    page = (out / "credit.html").read_text(encoding="utf-8")
    assert prov["git"]["rev"] in page
    assert prov["git"]["branch"] in page


def test_provenance_card_appears_before_footer(pack_with_prov):
    """카드가 항상 footer 직전이어야 함 (CRO 시야의 마지막 정보)."""
    out, files, _ = pack_with_prov
    for p in files:
        text = p.read_text(encoding="utf-8")
        i_card = text.find("Reproducibility")
        i_footer = text.find("<footer>")
        assert 0 < i_card < i_footer, f"{p.name}: 카드 위치 비정상"


def test_pack_cli_emits_provenance(tmp_path):
    from tools.report_pack import main

    rc = main(["--n", "400", "--out", str(tmp_path / "p"),
               "--log-dir", str(tmp_path / "logs")])
    assert rc == 0
    idx = (tmp_path / "p" / "index.html").read_text(encoding="utf-8")
    assert "Reproducibility" in idx
    assert "python -m tools.report_pack --n 400" in idx


def test_pack_without_provenance_still_builds(tmp_path):
    """provenance=None 호환 모드 — R37 호출 시 동작 불변."""
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import build_request, run_demo

    demo = run_demo(300, False, 42, tmp_path / "logs")
    req = build_request(300, stress=False, seed=42)
    files = build_pack(demo, req, tmp_path / "p", provenance=None)
    assert all(p.exists() for p in files)
    idx = (tmp_path / "p" / "index.html").read_text(encoding="utf-8")
    # provenance 카드는 없지만 DRAFT 워터마크는 강제
    assert "[DRAFT" in idx
    assert "Reproducibility" not in idx
