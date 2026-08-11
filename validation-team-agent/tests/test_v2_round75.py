"""Round 75 — CRO digest 이메일 초안 (HITL) + ICAAP post-stress KPI 오표기 수정."""

from __future__ import annotations

import re
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    from tools.run_workflow_demo import run_demo

    return run_demo(2_000, False, 42, tmp_path_factory.mktemp("logs"))


@pytest.fixture(scope="module")
def digest(demo):
    from tools.cro_digest import build_digest

    return build_digest(demo, stress=False, seed=42, n=2_000,
                        generated_at="2026-01-01T00:00:00Z")


def test_digest_has_draft_and_hitl(digest):
    assert "[DRAFT]" in digest["subject"]
    for body in (digest["html"], digest["text"]):
        assert "DRAFT" in body
        assert "HITL" in body
        assert "승인" in body


def test_digest_is_self_contained(digest):
    """이메일 안전성 — 외부 리소스/스크립트 없음."""
    h = digest["html"]
    assert "<script" not in h.lower()
    assert not re.search(r'(src|href)\s*=\s*"https?://', h)


def test_digest_contains_kpi_and_domains(digest):
    for token in ("경영진 KPI", "부문 신호등", "LCR", "NSFR",
                  "내부자본비율 (ICAAP)"):
        assert token in digest["html"]
    assert "== 경영진 KPI ==" in digest["text"]


def test_digest_deterministic(demo):
    from tools.cro_digest import build_digest

    a = build_digest(demo, stress=False, seed=42, n=2_000,
                     generated_at="2026-01-01T00:00:00Z")
    b = build_digest(demo, stress=False, seed=42, n=2_000,
                     generated_at="2026-01-01T00:00:00Z")
    assert a == b


def test_icaap_post_stress_level_exposed(demo):
    """R75 수정: handler 출력에 post_stress_level 포함 — KPI fail 오표기 방지."""
    out = demo["results"]["3.icaap"]["outputs"]
    assert out["post_stress_level"] == "ok"  # 1.1875 ≥ warning 1.05


def test_post_stress_kpi_not_fail_in_normal_mode(demo):
    from tools.executive_insights import kpi_cards

    cards = {label: status for label, _, status in kpi_cards(demo)}
    assert cards["스트레스 후 ICAAP"] == "ok"


def test_digest_stress_mode_shows_failures(tmp_path):
    from tools.cro_digest import build_digest
    from tools.run_workflow_demo import run_demo

    demo_s = run_demo(2_000, True, 42, tmp_path / "logs")
    d = build_digest(demo_s, stress=True, seed=42, n=2_000,
                     generated_at="2026-01-01T00:00:00Z")
    assert "스트레스" in d["subject"]
    assert "미달" in d["text"]
    assert "== Top 리스크 / 표준 조치 ==" in d["text"]


def test_cli_writes_drafts_only(tmp_path, capsys):
    from tools.cro_digest import main

    out = tmp_path / "digest.html"
    txt = tmp_path / "digest.txt"
    rc = main(["--n", "2000", "--out", str(out), "--text-out", str(txt),
               "--log-dir", str(tmp_path / "logs")])
    assert rc == 0
    assert out.exists() and txt.exists()
    assert "발송은 인간 승인 필요" in capsys.readouterr().out
    # 발송 기능이 모듈에 존재하지 않는다 (초안 전용)
    src = Path("tools/cro_digest.py").read_text(encoding="utf-8")
    assert "smtplib" not in src
    assert "sendmail" not in src


def test_catalog_sync():
    from tools.cli_index import CLI_MODULES
    from vta.cli.__main__ import _DISPATCH

    assert "tools.cro_digest" in {m for m, _ in CLI_MODULES}
    assert ("report", "digest") in _DISPATCH
