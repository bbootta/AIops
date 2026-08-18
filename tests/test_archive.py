"""산출물 이력 보관 — 판이 덮이지 않고 이력이 스스로 만들어지는가.

핵심 명제:
  1) 같은 기준일자에 두 번 만들면 **v01·v02로 나란히** 쌓인다. 덮어쓰면
     "어느 판을 제출했는가"에 답할 수 없다.
  2) 이력은 각 판의 `버전정보.json`을 **스캔해서** 만든다 — 손으로 적은 목록은
     낡는다(독립검증 F-501 유형).
  3) 판을 지우면 이력에서도 사라진다. 이력이 없는 판, 판이 없는 이력이 없다.
  4) 보관 위치는 **리스크관리 팀에이전트 경로 아래**다. 저장소 루트에 두면
     경로에 소유가 남지 않아 2선 산출물과 3선 산출물이 구분되지 않는다.
"""

from __future__ import annotations

import json
from pathlib import Path

from risk_lib.archive import (
    ARCHIVE_ROOT, TEAM_HOME, VERSION_INFO, ledger, next_version, scan,
    version_path, write_ledger,
)


def _fake_version(root, asof, run_date, version, **over):
    d = version_path(asof, run_date, version, root)
    d.mkdir(parents=True, exist_ok=True)
    info = {
        "asof": asof, "run_date": run_date, "version": version, "seed": 42,
        "request_id": f"IVR-{asof}-{version}", "headline_digest": "h" * 32,
        "submission_digest": "s" * 64, "gate_status": "응답대기",
        "n_forms": 290, "n_form_lines": 5896, "n_form_checks_failed": 0,
        "n_tables": 81, "self_validation": {"PASS": 60, "WARN": 5},
        "git_revision": "abc123", "created_at": "2026-07-29T00:00:00+00:00",
    }
    info.update(over)
    (d / VERSION_INFO).write_text(json.dumps(info, ensure_ascii=False),
                                  encoding="utf-8")
    return d


def test_versions_accumulate_within_an_asof(tmp_path):
    """같은 기준일자의 두 번째 실행은 v02로 간다 — 덮어쓰지 않는다."""
    assert next_version("2026-06-30", tmp_path) == 1
    _fake_version(tmp_path, "2026-06-30", "2026-07-29", 1)
    assert next_version("2026-06-30", tmp_path) == 2
    _fake_version(tmp_path, "2026-06-30", "2026-07-30", 2)
    assert next_version("2026-06-30", tmp_path) == 3


def test_version_numbering_is_per_asof(tmp_path):
    """기준일자가 다르면 판 번호가 섞이지 않는다 — 보고 단위가 기준일자다."""
    _fake_version(tmp_path, "2026-06-30", "2026-07-29", 1)
    _fake_version(tmp_path, "2026-06-30", "2026-07-29", 2)
    assert next_version("2026-03-31", tmp_path) == 1


def test_run_date_survives_in_the_path(tmp_path):
    """수행일자를 폴더명에 남긴다 — 같은 판 번호라도 언제 만들었는지 잃지 않는다."""
    d = _fake_version(tmp_path, "2026-06-30", "2026-08-15", 3)
    assert d.name == "20260815_v03"


def test_ledger_is_scanned_not_written(tmp_path):
    """이력은 판을 스캔한 결과다 — 판을 지우면 이력에서도 사라진다."""
    _fake_version(tmp_path, "2026-06-30", "2026-07-29", 1)
    _fake_version(tmp_path, "2026-03-31", "2026-07-29", 1,
                  gate_status="조건부")
    write_ledger(tmp_path)
    df = ledger(tmp_path)
    assert len(df) == 2
    assert set(df["기준일자"]) == {"2026-06-30", "2026-03-31"}
    assert "조건부" in set(df["게이트"])

    import shutil
    shutil.rmtree(version_path("2026-03-31", "2026-07-29", 1, tmp_path))
    assert len(ledger(tmp_path)) == 1


def test_ledger_carries_the_gate_state(tmp_path):
    """게이트 상태가 이력에 남아야 한다 — 어느 판이 결재 가능했는지가 감사 대상이다."""
    _fake_version(tmp_path, "2026-06-30", "2026-07-29", 1, gate_status="부적합")
    _fake_version(tmp_path, "2026-06-30", "2026-07-30", 2, gate_status="적합")
    df = ledger(tmp_path)
    assert list(df["게이트"]) == ["부적합", "적합"]


def test_ledger_records_the_code_revision(tmp_path):
    """판을 만든 코드 리비전이 없으면 재생성이 불가능하다."""
    _fake_version(tmp_path, "2026-06-30", "2026-07-29", 1, git_revision="deadbeef123")
    assert scan(tmp_path)[0].git_revision == "deadbeef123"
    assert "deadbeef123"[:12] in set(ledger(tmp_path)["코드리비전"])


def test_archive_root_lives_under_the_team_home():
    """산출물은 리스크관리 팀에이전트 경로 아래에만 쌓인다.

    저장소 루트(`deliverables/`)에 두면 누가 만든 판인지가 경로에 남지 않고,
    3선(적합성검증 팀에이전트)의 산출물과 섞인다. 그러면 "독립"이라는 말이
    경로 수준에서 무너진다.
    """
    assert TEAM_HOME == Path("teams/risk-management")
    assert ARCHIVE_ROOT.parent == TEAM_HOME
    assert version_path("2026-06-30", "2026-07-29", 1).is_relative_to(TEAM_HOME)


def test_empty_archive_does_not_crash(tmp_path):
    assert scan(tmp_path) == []
    assert ledger(tmp_path).empty
    paths = write_ledger(tmp_path / "새경로")
    assert "보관된 판이 없다" in paths["md"].read_text(encoding="utf-8")
