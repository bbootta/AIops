"""Round 68 — 보고서 팩 archive (분기 누적 + auto-prev)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent


# ---------- archive 함수 단위 ----------

def test_load_index_empty_archive(tmp_path):
    from tools.pack_archive import load_index

    d = load_index(tmp_path / "noarc")
    assert d == {"schema_version": "1.0", "entries": []}


def test_add_copies_pack_and_indexes(tmp_path):
    from tools.pack_archive import add, list_entries, load_index

    pack = tmp_path / "p"
    pack.mkdir()
    (pack / "index.html").write_text("<html>x</html>", encoding="utf-8")
    (pack / "pack_manifest.json").write_text(
        json.dumps({"n_pages": 1, "all_have_watermark": True,
                    "all_have_provenance": True, "by_domain": {}}),
        encoding="utf-8")

    arc = tmp_path / "arc"
    e = add(arc, pack, label="Q1", stress=False, notes="test")
    assert e["label"] == "Q1"
    assert (arc / "Q1" / "index.html").exists()
    # 원본은 그대로 (copy)
    assert pack.exists()

    idx = load_index(arc)
    assert len(idx["entries"]) == 1
    assert idx["entries"][0]["meta"]["n_pages"] == 1

    entries = list_entries(arc)
    assert entries[0]["stress"] is False


def test_add_move_mode_removes_source(tmp_path):
    from tools.pack_archive import add

    pack = tmp_path / "p"
    pack.mkdir()
    (pack / "index.html").write_text("x", encoding="utf-8")
    arc = tmp_path / "arc"
    add(arc, pack, label="Q1", move=True)
    assert not pack.exists()
    assert (arc / "Q1").exists()


def test_add_duplicate_label_raises(tmp_path):
    from tools.pack_archive import add

    pack = tmp_path / "p"
    pack.mkdir()
    (pack / "index.html").write_text("x", encoding="utf-8")
    arc = tmp_path / "arc"
    add(arc, pack, label="Q1")
    pack2 = tmp_path / "p2"
    pack2.mkdir()
    (pack2 / "index.html").write_text("y", encoding="utf-8")
    with pytest.raises(FileExistsError):
        add(arc, pack2, label="Q1")


def test_keep_prunes_oldest(tmp_path):
    from tools.pack_archive import add, list_entries

    arc = tmp_path / "arc"
    for label in ("Q1", "Q2", "Q3", "Q4", "Q5"):
        p = tmp_path / f"p_{label}"
        p.mkdir()
        (p / "index.html").write_text("x", encoding="utf-8")
        add(arc, p, label=label)
    # keep=3 — 가장 오래된 2개 prune
    p_last = tmp_path / "p_Q6"
    p_last.mkdir()
    (p_last / "index.html").write_text("x", encoding="utf-8")
    add(arc, p_last, label="Q6", keep=3)
    entries = list_entries(arc)
    labels = [e["label"] for e in entries]
    assert len(labels) == 3
    # Q6 가 가장 새로운 것 (latest first)
    assert labels[0] == "Q6"
    # Q1/Q2 디렉터리는 삭제됨
    assert not (arc / "Q1").exists()
    assert not (arc / "Q2").exists()


def test_latest_returns_most_recent(tmp_path):
    from tools.pack_archive import add, latest, latest_pack_dir

    arc = tmp_path / "arc"
    for label, stress in (("Q1", False), ("Q2", True), ("Q3", False)):
        p = tmp_path / f"p_{label}"
        p.mkdir()
        (p / "index.html").write_text("x", encoding="utf-8")
        add(arc, p, label=label, stress=stress)
    e = latest(arc)
    assert e["label"] == "Q3"
    # stress 필터
    s = latest(arc, stress=True)
    assert s["label"] == "Q2"
    assert latest_pack_dir(arc) == arc / "Q3"


def test_latest_empty_returns_none(tmp_path):
    from tools.pack_archive import latest, latest_pack_dir

    assert latest(tmp_path / "noarc") is None
    assert latest_pack_dir(tmp_path / "noarc") is None


# ---------- CLI ----------

def _make_pack(tmp_path: Path) -> Path:
    p = tmp_path / "pack"
    p.mkdir()
    (p / "index.html").write_text("x", encoding="utf-8")
    return p


def test_cli_add_list_latest(tmp_path):
    pack = _make_pack(tmp_path)
    arc = tmp_path / "arc"

    res = subprocess.run(
        [sys.executable, "-m", "tools.pack_archive", "add",
         "--archive", str(arc), "--pack", str(pack), "--label", "Q1"],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    assert res.returncode == 0
    assert "Q1" in res.stdout

    res = subprocess.run(
        [sys.executable, "-m", "tools.pack_archive", "list",
         "--archive", str(arc)],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    assert res.returncode == 0
    assert "Q1" in res.stdout

    res = subprocess.run(
        [sys.executable, "-m", "tools.pack_archive", "latest",
         "--archive", str(arc)],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    assert res.returncode == 0
    assert "Q1" in res.stdout


def test_cli_list_json_mode(tmp_path):
    pack = _make_pack(tmp_path)
    arc = tmp_path / "arc"
    subprocess.run(
        [sys.executable, "-m", "tools.pack_archive", "add",
         "--archive", str(arc), "--pack", str(pack), "--label", "Q1"],
        cwd=str(ROOT), check=True, capture_output=True, text=True,
    )
    res = subprocess.run(
        [sys.executable, "-m", "tools.pack_archive", "list",
         "--archive", str(arc), "--json"],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert isinstance(data, list)
    assert data[0]["label"] == "Q1"


# ---------- 카탈로그 sync ----------

def test_cli_index_lists_pack_archive():
    from tools.cli_index import CLI_MODULES

    assert "tools.pack_archive" in {m for m, _ in CLI_MODULES}


def test_vta_dispatch_has_archive():
    from vta.cli.__main__ import _DISPATCH

    assert ("archive",) in _DISPATCH


# ---------- report_pack 통합 ----------

@pytest.fixture(scope="module")
def pack_with_archive(tmp_path_factory):
    from tools.provenance import build_provenance
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import build_request, run_demo

    work = tmp_path_factory.mktemp("r68")
    archive = work / "archive"

    # 1st build → archive 등록
    a = work / "A"
    demo_a = run_demo(500, False, 42, work / "logsA")
    req_a = build_request(500, stress=False, seed=42)
    prov_a = build_provenance(req_a, n=500, seed=42, stress=False)
    build_pack(demo_a, req_a, a, provenance=prov_a, archive_root=archive)

    # 가짜 archive 등록 (외부 add 호출로)
    from tools.pack_archive import add
    add(archive, a, label="Q1", stress=False)

    # 2nd build with archive
    b = work / "B"
    demo_b = run_demo(500, True, 42, work / "logsB")
    req_b = build_request(500, stress=True, seed=42)
    prov_b = build_provenance(req_b, n=500, seed=42, stress=True)
    files = build_pack(demo_b, req_b, b, provenance=prov_b,
                       archive_root=archive)
    return b, files, archive


def test_archive_index_page_generated(pack_with_archive):
    out, files, _ = pack_with_archive
    names = {p.name for p in files}
    assert "archive_index.html" in names


def test_archive_index_page_lists_entry(pack_with_archive):
    out, _, _ = pack_with_archive
    text = (out / "archive_index.html").read_text(encoding="utf-8")
    assert "Q1" in text
    assert "분기별 보고서 팩" in text


def test_archive_index_shows_guidance(pack_with_archive):
    out, _, _ = pack_with_archive
    text = (out / "archive_index.html").read_text(encoding="utf-8")
    assert "auto-prev" in text or "auto_prev" in text or "최신순" in text
    assert "운영 가이드" in text


def test_archive_index_without_archive(tmp_path):
    from tools.provenance import build_provenance
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import build_request, run_demo

    out = tmp_path / "noarc"
    demo = run_demo(500, False, 42, tmp_path / "logs")
    req = build_request(500, stress=False, seed=42)
    prov = build_provenance(req, n=500, seed=42, stress=False)
    build_pack(demo, req, out, provenance=prov)
    text = (out / "archive_index.html").read_text(encoding="utf-8")
    assert "미지정" in text or "비어" in text


def test_index_and_executive_link_to_archive(pack_with_archive):
    out, _, _ = pack_with_archive
    idx = (out / "index.html").read_text(encoding="utf-8")
    exe = (out / "executive.html").read_text(encoding="utf-8")
    assert 'href="archive_index.html"' in idx
    assert 'href="archive_index.html"' in exe


def test_archive_self_contained(pack_with_archive):
    out, _, _ = pack_with_archive
    text = (out / "archive_index.html").read_text(encoding="utf-8")
    assert "https://" not in text
    assert "<script" not in text
    assert "[DRAFT" in text
    assert "Reproducibility" in text
