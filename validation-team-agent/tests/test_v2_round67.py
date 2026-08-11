"""Round 67 — 보고서 팩 변화 detection (pack_diff)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent


# ---------- diff 함수 단위 ----------

def test_diff_kpi_detects_changed_and_unchanged():
    from tools.pack_diff import diff_kpi

    prev = [
        {"label": "CET1", "value": "13.0%", "status": "ok"},
        {"label": "LCR", "value": "1.30", "status": "ok"},
    ]
    curr = [
        {"label": "CET1", "value": "5.0%", "status": "fail"},
        {"label": "LCR", "value": "1.30", "status": "ok"},  # 동일
        {"label": "NSFR", "value": "0.90", "status": "fail"},  # 새 KPI
    ]
    d = diff_kpi(prev, curr)
    assert d["unchanged_count"] == 1
    assert len(d["changed"]) == 1
    assert d["changed"][0]["label"] == "CET1"
    assert d["changed"][0]["transition"] == "degraded"
    assert len(d["added"]) == 1
    assert d["added"][0]["label"] == "NSFR"


def test_diff_kpi_detects_improvement():
    from tools.pack_diff import diff_kpi

    prev = [{"label": "LCR", "value": "0.80", "status": "fail"}]
    curr = [{"label": "LCR", "value": "1.10", "status": "ok"}]
    d = diff_kpi(prev, curr)
    assert d["changed"][0]["transition"] == "improved"


def test_diff_heatmap_status_transitions():
    from tools.pack_diff import diff_heatmap

    prev = [
        {"domain": "신용", "status": "ok", "detail": "x"},
        {"domain": "자본", "status": "ok", "detail": "y"},
    ]
    curr = [
        {"domain": "신용", "status": "fail", "detail": "PSI 상승"},
        {"domain": "자본", "status": "ok", "detail": "y"},
    ]
    d = diff_heatmap(prev, curr)
    assert len(d["transitions"]) == 1
    assert d["transitions"][0]["domain"] == "신용"
    assert d["transitions"][0]["severity"] == "degraded"


def test_diff_qoq_numerical_changes():
    from tools.pack_diff import diff_qoq

    prev = [{"metric": "cet1", "current_value": 0.13}]
    curr = [{"metric": "cet1", "current_value": 0.10}]
    d = diff_qoq(prev, curr)
    assert len(d) == 1
    assert abs(d[0]["abs_change"] - (-0.03)) < 1e-9
    assert d[0]["rel_change"] is not None


def test_diff_qoq_zero_prev_handled_safely():
    from tools.pack_diff import diff_qoq

    d = diff_qoq([{"metric": "x", "current_value": 0}],
                 [{"metric": "x", "current_value": 1.0}])
    assert d[0]["rel_change"] is None  # 분모 0


def test_diff_pages_uses_sha256():
    from tools.pack_diff import diff_pages

    prev = [
        {"file": "a.html", "sha256": "aaa", "size_bytes": 100},
        {"file": "b.html", "sha256": "bbb", "size_bytes": 200},
    ]
    curr = [
        {"file": "a.html", "sha256": "aaa", "size_bytes": 100},  # 동일
        {"file": "b.html", "sha256": "ccc", "size_bytes": 250},  # 변경
        {"file": "c.html", "sha256": "ddd", "size_bytes": 300},  # 추가
    ]
    d = diff_pages(prev, curr)
    assert d["unchanged_count"] == 1
    assert len(d["changed_pages"]) == 1
    assert d["changed_pages"][0]["file"] == "b.html"
    assert d["added_pages"] == ["c.html"]


# ---------- 통합 (export.json + pack_manifest.json) ----------

@pytest.fixture
def two_packs(tmp_path):
    from tools.provenance import build_provenance
    from tools.report_export import export_pack
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import build_request, run_demo

    # Pack A — normal
    out_a = tmp_path / "A"
    demo_a = run_demo(500, False, 42, tmp_path / "logsA")
    req_a = build_request(500, stress=False, seed=42)
    prov_a = build_provenance(req_a, n=500, seed=42, stress=False)
    build_pack(demo_a, req_a, out_a, provenance=prov_a)
    export_pack(out_a, stress=False)

    # Pack B — stress
    out_b = tmp_path / "B"
    demo_b = run_demo(500, True, 42, tmp_path / "logsB")
    req_b = build_request(500, stress=True, seed=42)
    prov_b = build_provenance(req_b, n=500, seed=42, stress=True)
    build_pack(demo_b, req_b, out_b, provenance=prov_b)
    export_pack(out_b, stress=True)

    return out_a, out_b


def test_diff_export_files_full(two_packs):
    from tools.pack_diff import diff_export_files

    a, b = two_packs
    d = diff_export_files(a, b)
    # normal → stress 전환: KPI 상당수 변경
    assert d["kpi"]["changed"]
    # 부문 status 전이 다수 (자본/유동성/ALM 등 모두 degraded)
    assert d["heatmap"]["transitions"]
    assert any(t["severity"] == "degraded"
               for t in d["heatmap"]["transitions"])


def test_diff_missing_export_raises(tmp_path):
    from tools.pack_diff import diff_export_files

    (tmp_path / "A").mkdir()
    (tmp_path / "B").mkdir()
    with pytest.raises(FileNotFoundError):
        diff_export_files(tmp_path / "A", tmp_path / "B")


# ---------- CLI ----------

def test_cli_summary_mode(two_packs):
    a, b = two_packs
    res = subprocess.run(
        [sys.executable, "-m", "tools.pack_diff",
         "--prev", str(a), "--curr", str(b)],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    assert res.returncode == 0
    assert "Pack diff" in res.stdout
    assert "KPI" in res.stdout
    assert "Heatmap" in res.stdout


def test_cli_json_mode(two_packs):
    a, b = two_packs
    res = subprocess.run(
        [sys.executable, "-m", "tools.pack_diff",
         "--prev", str(a), "--curr", str(b), "--json"],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert {"kpi", "heatmap", "qoq", "pages"} <= set(data)


def test_cli_index_lists_pack_diff():
    from tools.cli_index import CLI_MODULES

    assert "tools.pack_diff" in {m for m, _ in CLI_MODULES}


def test_vta_dispatch_has_pack_diff():
    from vta.cli.__main__ import _DISPATCH

    assert ("pack", "diff") in _DISPATCH


# ---------- 보고서 페이지 ----------

@pytest.fixture(scope="module")
def pack_with_diff(tmp_path_factory):
    from tools.provenance import build_provenance
    from tools.report_export import export_pack
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import build_request, run_demo

    work = tmp_path_factory.mktemp("r67")

    # Pack A (prev)
    a = work / "A"
    demo_a = run_demo(500, False, 42, work / "logsA")
    req_a = build_request(500, stress=False, seed=42)
    prov_a = build_provenance(req_a, n=500, seed=42, stress=False)
    build_pack(demo_a, req_a, a, provenance=prov_a)
    export_pack(a, stress=False)

    # Pack B (curr, with prev pointer)
    b = work / "B"
    demo_b = run_demo(500, True, 42, work / "logsB")
    req_b = build_request(500, stress=True, seed=42)
    prov_b = build_provenance(req_b, n=500, seed=42, stress=True)
    files = build_pack(demo_b, req_b, b, provenance=prov_b, prev_pack_dir=a)
    return b, files


def test_pack_diff_page_generated(pack_with_diff):
    out, files = pack_with_diff
    names = {p.name for p in files}
    assert "pack_diff.html" in names


def test_page_shows_summary_box(pack_with_diff):
    out, _ = pack_with_diff
    text = (out / "pack_diff.html").read_text(encoding="utf-8")
    assert "부문 status 전이" in text
    assert "악화" in text or "degraded" in text
    assert "비교 대상" in text


def test_page_shows_kpi_table(pack_with_diff):
    out, _ = pack_with_diff
    text = (out / "pack_diff.html").read_text(encoding="utf-8")
    assert "KPI 변경" in text


def test_page_shows_page_sha_changes(pack_with_diff):
    out, _ = pack_with_diff
    text = (out / "pack_diff.html").read_text(encoding="utf-8")
    assert "SHA-256" in text or "SHA" in text


def test_page_links_to_governance_and_change(pack_with_diff):
    out, _ = pack_with_diff
    text = (out / "pack_diff.html").read_text(encoding="utf-8")
    assert 'href="governance_trend.html"' in text
    assert 'href="change_audit.html"' in text


def test_index_and_executive_links(pack_with_diff):
    out, _ = pack_with_diff
    idx = (out / "index.html").read_text(encoding="utf-8")
    exe = (out / "executive.html").read_text(encoding="utf-8")
    assert 'href="pack_diff.html"' in idx
    assert 'href="pack_diff.html"' in exe


def test_page_without_prev_shows_guidance(tmp_path):
    """prev_pack_dir 미제공 시 안내 메시지."""
    from tools.provenance import build_provenance
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import build_request, run_demo

    out = tmp_path / "noprev"
    demo = run_demo(500, False, 42, tmp_path / "logs")
    req = build_request(500, stress=False, seed=42)
    prov = build_provenance(req, n=500, seed=42, stress=False)
    build_pack(demo, req, out, provenance=prov)  # prev_pack_dir 없음
    text = (out / "pack_diff.html").read_text(encoding="utf-8")
    assert "비교 대상 팩 미지정" in text or "prev-pack" in text


def test_page_self_contained(pack_with_diff):
    out, _ = pack_with_diff
    text = (out / "pack_diff.html").read_text(encoding="utf-8")
    assert "https://" not in text
    assert "<script" not in text
    assert "[DRAFT" in text
    assert "Reproducibility" in text
