"""Round 79 — 팩 재현성 자체검증 (pack_verify): "재현 가능"을 실증한다."""

from __future__ import annotations

import json

import pytest

from tools.pack_verify import (
    LOG_DERIVED_PAGES,
    normalize_page,
    render_report,
    verify_pack,
)


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    from tools.report_pack import main

    out = tmp_path_factory.mktemp("pack")
    rc = main(["--n", "2000", "--seed", "42", "--out", str(out),
               "--log-dir", str(out / "logs")])
    assert rc == 0
    return out


# ---------- provenance.json ----------

def test_pack_writes_machine_readable_provenance(pack):
    p = pack / "provenance.json"
    assert p.exists()
    prov = json.loads(p.read_text(encoding="utf-8"))
    assert prov["inputs"]["n"] == 2000
    assert prov["inputs"]["seed"] == 42
    assert prov["inputs"]["fingerprint"]["df"]["sha256"]
    assert prov["policy_versions"]


def test_page_count_excludes_provenance_json(pack):
    """provenance.json 은 페이지가 아니므로 47 페이지 규격을 깨지 않는다."""
    assert len(list(pack.glob("*.html"))) == 47


# ---------- 정규화 ----------

def test_normalize_strips_volatile_values():
    a = normalize_page("생성 2026-01-01T00:00:00Z · dirty=yes · <td>13.178초</td>")
    b = normalize_page("생성 2026-07-24T11:22:33Z · dirty=no · <td>1.74초</td>")
    assert a == b


def test_normalize_keeps_result_numbers():
    """수치 결과는 정규화 대상이 아니다 — 그러면 검증이 무의미해진다."""
    a = normalize_page("<td>KS=0.6001</td>")
    b = normalize_page("<td>KS=0.5000</td>")
    assert a != b


# ---------- fast 검증 ----------

def test_verify_passes_on_fresh_pack(pack):
    res = verify_pack(pack)
    assert res["passed"], res["checks"]
    names = {c["check"] for c in res["checks"]}
    assert {"입력 df SHA-256", "입력 스칼라 SHA-256", "정책 SSoT 버전",
            "git rev"} <= names


def test_verify_detects_tampered_provenance(pack, tmp_path):
    """기록된 입력 해시를 바꾸면 검증이 실패해야 한다 (탐지력 확인)."""
    import shutil

    clone = tmp_path / "tampered"
    shutil.copytree(pack, clone)
    prov = json.loads((clone / "provenance.json").read_text(encoding="utf-8"))
    prov["inputs"]["fingerprint"]["df"]["sha256"] = "0" * 64
    (clone / "provenance.json").write_text(
        json.dumps(prov, ensure_ascii=False), encoding="utf-8")

    res = verify_pack(clone)
    assert not res["passed"]
    fails = [c["check"] for c in res["checks"] if c["status"] == "fail"]
    assert "입력 df SHA-256" in fails


def test_verify_detects_wrong_seed(pack, tmp_path):
    """seed 를 바꾸면 df 지문이 달라져 검증이 실패한다."""
    import shutil

    clone = tmp_path / "wrongseed"
    shutil.copytree(pack, clone)
    prov = json.loads((clone / "provenance.json").read_text(encoding="utf-8"))
    prov["inputs"]["seed"] = 999
    (clone / "provenance.json").write_text(
        json.dumps(prov, ensure_ascii=False), encoding="utf-8")
    assert not verify_pack(clone)["passed"]


def test_verify_fails_without_provenance(tmp_path):
    empty = tmp_path / "nopack"
    empty.mkdir()
    res = verify_pack(empty)
    assert not res["passed"]
    assert "provenance.json" in res["checks"][0]["check"]


# ---------- deep 검증 ----------

def test_deep_verify_matches_all_deterministic_pages(pack):
    res = verify_pack(pack, deep=True)
    page_check = next(c for c in res["checks"]
                      if c["check"] == "페이지 재빌드 대조")
    assert page_check["status"] == "ok", page_check["detail"]
    assert "44" in page_check["detail"]
    assert res["passed"]


def test_deep_verify_reports_log_derived_pages_as_skip(pack):
    """로그 파생 페이지는 조용히 통과시키지 않고 사유와 함께 SKIP 보고."""
    res = verify_pack(pack, deep=True)
    log_check = next(c for c in res["checks"] if c["check"] == "로그 파생 페이지")
    assert log_check["status"] == "skipped"
    for name in LOG_DERIVED_PAGES:
        assert name in log_check["detail"]
    assert res["n_skipped"] >= 1


def test_deep_verify_detects_edited_page(pack, tmp_path):
    """페이지 내용을 고치면 deep 대조가 잡아낸다."""
    import shutil

    clone = tmp_path / "edited"
    shutil.copytree(pack, clone)
    p = clone / "credit.html"
    p.write_text(p.read_text(encoding="utf-8").replace(
        "변별력", "변별력(임의수정)", 1), encoding="utf-8")

    res = verify_pack(clone, deep=True)
    page_check = next(c for c in res["checks"]
                      if c["check"] == "페이지 재빌드 대조")
    assert page_check["status"] == "fail"
    assert "credit.html" in page_check["detail"]
    assert not res["passed"]


# ---------- 보고 / CLI ----------

def test_render_report_marks_skip_in_summary(pack):
    text = render_report(verify_pack(pack, deep=True))
    assert "[PASS]" in text and "[SKIP]" in text
    assert "검증 범위 밖" in text


def test_cli_exit_codes(pack, tmp_path):
    from tools.pack_verify import main

    assert main(["--pack", str(pack)]) == 0
    empty = tmp_path / "none"
    empty.mkdir()
    assert main(["--pack", str(empty)]) == 1


def test_catalog_sync():
    from tools.cli_index import CLI_MODULES
    from vta.cli.__main__ import _DISPATCH

    assert "tools.pack_verify" in {m for m, _ in CLI_MODULES}
    assert ("pack", "verify") in _DISPATCH
