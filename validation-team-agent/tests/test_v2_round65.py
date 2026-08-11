"""Round 65 — audit log → recurring_findings 매핑 + 후보 추출."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


# ---------- 매핑 함수 ----------

def test_frequency_buckets():
    from tools.findings_mapping import _frequency_bucket

    assert _frequency_bucket(0.50) == "frequent"
    assert _frequency_bucket(0.30) == "frequent"
    assert _frequency_bucket(0.15) == "moderate"
    assert _frequency_bucket(0.05) == "rare"
    assert _frequency_bucket(0.0) == "none"


def test_step_domain_mapping_known_steps():
    from tools.findings_mapping import _STEP_TO_DOMAIN

    for sid in ("3.capital", "3.icaap", "3.market", "3.conc", "3.psi"):
        assert sid in _STEP_TO_DOMAIN


def test_map_audit_to_findings_creates_candidates_for_new_domain():
    from tools.findings_mapping import map_audit_to_findings

    audit = {
        "n_runs": 5,
        "step_fail_rates": [
            {"step_id": "3.capital", "runs_with_step": 5, "n_fails": 4,
             "fail_rate": 0.80},
            {"step_id": "3.disc", "runs_with_step": 5, "n_fails": 0,
             "fail_rate": 0.0},  # 무시됨
        ],
        "dynamic_activations": [],
    }
    mapping = map_audit_to_findings(audit)
    # capital domain RF 가 기존에 없으면 candidate 로
    all_steps = [c["step_id"] for c in mapping["candidates"]] + \
                [c["step_id"] for c in mapping["covered"]]
    assert "3.capital" in all_steps
    # 0% fail step 은 빠짐
    assert "3.disc" not in all_steps


def test_map_audit_uses_existing_finding_when_domain_present(tmp_path):
    """기존 RF 가 있는 domain 은 covered 로 분류."""
    from tools.findings_mapping import map_audit_to_findings

    f_json = tmp_path / "rf.json"
    f_json.write_text(json.dumps({
        "schema_version": "1.0",
        "findings": [
            {"id": "RF-T01", "frequency": "rare", "domain": "data",
             "description": "test PSI"},
        ],
    }), encoding="utf-8")
    audit = {
        "n_runs": 4,
        "step_fail_rates": [
            {"step_id": "3.psi", "runs_with_step": 4, "n_fails": 4,
             "fail_rate": 1.0},
        ],
        "dynamic_activations": [],
    }
    mapping = map_audit_to_findings(audit, findings_path=f_json)
    assert any(c["mapped_finding_id"] == "RF-T01"
               for c in mapping["covered"])
    # rare → frequent 상향 검토 신호
    assert any(c["frequency_upgrade_needed"] for c in mapping["covered"])


def test_dynamic_activations_become_governance_candidate():
    from tools.findings_mapping import map_audit_to_findings

    audit = {
        "n_runs": 3,
        "step_fail_rates": [],
        "dynamic_activations": [
            {"step_id": "9.escalate", "timestamp": "t1"},
            {"step_id": "9.escalate", "timestamp": "t2"},
        ],
    }
    mapping = map_audit_to_findings(audit)
    assert any(c["suggested_domain"] == "governance"
               for c in mapping["candidates"])


def test_emit_add_commands_for_candidates():
    from tools.findings_mapping import emit_add_commands, map_audit_to_findings

    audit = {
        "n_runs": 5,
        "step_fail_rates": [
            {"step_id": "3.alm", "runs_with_step": 5, "n_fails": 5,
             "fail_rate": 1.0},
        ],
        "dynamic_activations": [],
    }
    cmds = emit_add_commands(map_audit_to_findings(audit))
    assert any("tools.findings add" in c for c in cmds)
    # 단일 인용으로 shell 안전
    for c in cmds:
        assert "--frequency frequent" in c or "--frequency moderate" in c \
               or "--frequency rare" in c


# ---------- CLI ----------

ROOT = Path(__file__).resolve().parent.parent


def _seed_log(log_dir: Path):
    from tools.run_workflow_demo import run_demo

    log_dir.mkdir(parents=True, exist_ok=True)
    for seed in (42, 43, 44):
        run_demo(500, True, seed, log_dir)


def test_cli_summary_default(tmp_path):
    log_dir = tmp_path / "logs"
    _seed_log(log_dir)
    res = subprocess.run(
        [sys.executable, "-m", "tools.findings_mapping",
         "--log", str(log_dir / "run.jsonl")],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    assert res.returncode == 0
    assert "Recurring Findings Mapping" in res.stdout
    assert "candidates:" in res.stdout


def test_cli_json_mode(tmp_path):
    log_dir = tmp_path / "logs"
    _seed_log(log_dir)
    res = subprocess.run(
        [sys.executable, "-m", "tools.findings_mapping",
         "--log", str(log_dir / "run.jsonl"), "--json"],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert "candidates" in data
    assert "covered" in data
    assert data["n_runs"] >= 3


def test_cli_emit_add_mode(tmp_path):
    log_dir = tmp_path / "logs"
    _seed_log(log_dir)
    res = subprocess.run(
        [sys.executable, "-m", "tools.findings_mapping",
         "--log", str(log_dir / "run.jsonl"), "--emit-add"],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    assert res.returncode == 0
    # 1 이상의 add 명령
    lines = [ln for ln in res.stdout.splitlines() if ln.strip()]
    assert lines
    for ln in lines:
        assert ln.startswith("python -m tools.findings add ")


# ---------- 카탈로그 sync gate ----------

def test_cli_index_lists_findings_mapping():
    from tools.cli_index import CLI_MODULES

    assert "tools.findings_mapping" in {m for m, _ in CLI_MODULES}


def test_vta_dispatch_has_findings_map():
    from vta.cli.__main__ import _DISPATCH

    assert ("findings", "map") in _DISPATCH


# ---------- 페이지 통합 ----------

@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    from tools.provenance import build_provenance
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import build_request, run_demo

    out = tmp_path_factory.mktemp("r65")
    log_dir = out / "logs"
    for seed in (42, 43, 44):
        run_demo(500, True, seed, log_dir)

    demo = run_demo(500, True, 42, log_dir)
    request = build_request(500, stress=True, seed=42)
    prov = build_provenance(request, n=500, seed=42, stress=True)
    files = build_pack(demo, request, out, provenance=prov, log_dir=log_dir)
    return out, files


def test_findings_mapping_page_generated(pack):
    out, files = pack
    names = {p.name for p in files}
    assert "findings_mapping.html" in names


def test_page_shows_summary_table(pack):
    out, _ = pack
    text = (out / "findings_mapping.html").read_text(encoding="utf-8")
    assert "분석 run 수" in text
    assert "신규 RF 후보" in text or "신규 후보" in text


def test_page_shows_capital_alm_concentration_candidates(pack):
    out, _ = pack
    text = (out / "findings_mapping.html").read_text(encoding="utf-8")
    # stress runs 에서 항상 fail 하는 step 들이 후보로 등장
    for sid in ("3.capital", "3.alm", "3.conc"):
        assert sid in text


def test_page_links_back_to_audit(pack):
    out, _ = pack
    text = (out / "findings_mapping.html").read_text(encoding="utf-8")
    assert 'href="audit_timeseries.html"' in text


def test_index_and_executive_link_to_mapping(pack):
    out, _ = pack
    idx = (out / "index.html").read_text(encoding="utf-8")
    exe = (out / "executive.html").read_text(encoding="utf-8")
    assert 'href="findings_mapping.html"' in idx
    assert 'href="findings_mapping.html"' in exe


def test_page_self_contained(pack):
    out, _ = pack
    text = (out / "findings_mapping.html").read_text(encoding="utf-8")
    assert "https://" not in text
    assert "<script" not in text
    assert "[DRAFT" in text
    assert "Reproducibility" in text


def test_page_warns_against_auto_promote(pack):
    """CLAUDE.md §5 — 임의 완화 금지 / 자동 promote 금지 명시."""
    out, _ = pack
    text = (out / "findings_mapping.html").read_text(encoding="utf-8")
    assert "자동 promote" in text or "promote 는 하지 않" in text \
           or "자동 promote 금지" in text
