"""Round 63 — 보고서 팩 CSV/JSON/manifest export."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    from tools.provenance import build_provenance
    from tools.report_export import export_pack
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import build_request, run_demo

    out = tmp_path_factory.mktemp("r63")
    demo = run_demo(2_000, True, 42, out / "logs")
    request = build_request(2_000, stress=True, seed=42)
    prov = build_provenance(request, n=2_000, seed=42, stress=True)
    build_pack(demo, request, out, provenance=prov)
    written = export_pack(out, stress=True)
    return out, written


# ---------- 파일 ----------

def test_exports_all_expected_files(exported):
    out, _ = exported
    for name in ("kpi.csv", "heatmap.csv", "qoq.csv", "risk_watch.csv",
                 "change_manifest_summary.csv", "export.json",
                 "pack_manifest.json"):
        assert (out / name).exists(), name


def test_kpi_csv_well_formed(exported):
    out, _ = exported
    with (out / "kpi.csv").open() as f:
        rows = list(csv.DictReader(f))
    assert rows
    for r in rows:
        assert {"label", "value", "status"} <= set(r)


def test_heatmap_csv_15_domains(exported):
    out, _ = exported
    with (out / "heatmap.csv").open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) >= 13
    for r in rows:
        assert {"domain", "status", "detail", "link"} <= set(r)
        assert r["status"] in ("ok", "warning", "fail", "skipped", "simulated")


def test_qoq_csv_covers_required_metrics(exported):
    out, _ = exported
    with (out / "qoq.csv").open() as f:
        rows = list(csv.DictReader(f))
    metrics = {r["metric"] for r in rows}
    for m in ("cet1", "lcr", "nsfr", "icaap", "delta_eve", "psi", "hhi"):
        assert m in metrics


def test_qoq_delta_arithmetic(exported):
    out, _ = exported
    with (out / "qoq.csv").open() as f:
        for row in csv.DictReader(f):
            prev_v = float(row["previous_value"])
            curr_v = float(row["current_value"])
            delta = float(row["delta"])
            assert abs((curr_v - prev_v) - delta) < 1e-9


def test_risk_watch_csv_stress(exported):
    out, _ = exported
    with (out / "risk_watch.csv").open() as f:
        rows = list(csv.DictReader(f))
    # stress 모드이므로 적어도 1건 fail/warning 존재
    assert any(r["status"] in ("fail", "warning") for r in rows)
    # 표준 액션 attached
    for r in rows:
        assert r["standard_action"]


def test_change_manifest_summary_has_proposed(exported):
    out, _ = exported
    with (out / "change_manifest_summary.csv").open() as f:
        rows = list(csv.DictReader(f))
    statuses = {r["status"] for r in rows}
    assert "proposed" in statuses


# ---------- 통합 JSON ----------

def test_export_json_consolidates_all_sections(exported):
    out, _ = exported
    data = json.loads((out / "export.json").read_text(encoding="utf-8"))
    for key in ("kpi", "heatmap", "qoq", "risk_watch",
                "change_manifest_summary", "generated_at_utc"):
        assert key in data
    assert data["stress"] is True


# ---------- 팩 manifest ----------

def test_pack_manifest_lists_all_pages(exported):
    out, _ = exported
    m = json.loads((out / "pack_manifest.json").read_text(encoding="utf-8"))
    n_html = sum(1 for _ in out.glob("*.html"))
    assert m["n_pages"] == n_html
    # 41 페이지 시점 기준 최소 30 페이지 보장
    assert n_html >= 30


def test_pack_manifest_all_pages_have_watermark_and_provenance(exported):
    out, _ = exported
    m = json.loads((out / "pack_manifest.json").read_text(encoding="utf-8"))
    assert m["all_have_watermark"] is True
    assert m["all_have_provenance"] is True


def test_pack_manifest_sha256_matches_file(exported):
    import hashlib

    out, _ = exported
    m = json.loads((out / "pack_manifest.json").read_text(encoding="utf-8"))
    for entry in m["pages"][:5]:
        actual = hashlib.sha256((out / entry["file"]).read_bytes()).hexdigest()
        assert actual == entry["sha256"]


def test_pack_manifest_classifies_known_domains(exported):
    out, _ = exported
    m = json.loads((out / "pack_manifest.json").read_text(encoding="utf-8"))
    domains = m["by_domain"]
    for required in ("신용", "자본", "ALM", "시장", "IFRS9", "ESG"):
        assert required in domains, f"{required} 누락"


# ---------- CLI / 카탈로그 ----------

def test_cli_index_lists_export_module():
    from tools.cli_index import CLI_MODULES

    assert "tools.report_export" in {m for m, _ in CLI_MODULES}


def test_vta_dispatch_has_report_export():
    from vta.cli.__main__ import _DISPATCH

    assert ("report", "export") in _DISPATCH


def test_export_cli_works(tmp_path):
    """python -m tools.report_export --pack <dir> 가 동작."""
    import subprocess
    import sys

    from tools.provenance import build_provenance
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import build_request, run_demo

    out = tmp_path / "p"
    demo = run_demo(800, False, 42, tmp_path / "logs")
    req = build_request(800, stress=False, seed=42)
    prov = build_provenance(req, n=800, seed=42, stress=False)
    build_pack(demo, req, out, provenance=prov)

    res = subprocess.run(
        [sys.executable, "-m", "tools.report_export", "--pack", str(out)],
        cwd=str(Path(__file__).resolve().parent.parent),
        capture_output=True, text=True,
    )
    assert res.returncode == 0, res.stderr
    assert (out / "kpi.csv").exists()
    assert (out / "pack_manifest.json").exists()
