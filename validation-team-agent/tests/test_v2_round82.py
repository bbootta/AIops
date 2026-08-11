"""Round 82 — Finding 원장·재발 관리 + 승인 차단 (VAL-013/014/016)."""

from __future__ import annotations

from datetime import date

import pytest

from tools.validation_finding import (
    ROOT_CAUSES,
    SEVERITY_ORDER,
    FindingError,
    append_events,
    approval_blockers,
    close_finding,
    derive,
    detect_recurrence,
    load_events,
    open_finding,
    queue,
    record_remediation,
    record_reverification,
    render_lineage,
    render_queue,
)

AS = date(2026, 7, 25)
SLA = {"critical": 5, "high": 10, "medium": 20}


def _opened(severity="medium", **kw):
    return open_finding(title=kw.pop("title", "PSI 임계 초과"),
                        domain=kw.pop("domain", "credit"), severity=severity,
                        owner_role=kw.pop("owner_role", "credit_model_owner"),
                        as_of=kw.pop("as_of", AS), sla_days=SLA, **kw)


def _full_lifecycle(events, fid, *, root_cause="model", as_of=AS):
    events.append(record_remediation(fid, action="재캘리브레이션",
                                     root_cause=root_cause, as_of=as_of,
                                     events=events))
    events.append(record_reverification(fid, result="pass", evidence="회복",
                                        as_of=as_of, events=events))
    events.append(close_finding(fid, as_of=as_of, events=events))
    return events


# ---------- 개시 ----------

def test_open_creates_event_with_sla_due(tmp_path):
    ev = _opened(severity="critical", events=[])
    f = ev[0]
    assert f["finding_id"] == "VF-20260725-0001"
    assert f["severity"] == "critical"
    assert f["due_at"] == "2026-07-30"      # critical 5일
    assert derive(ev)[f["finding_id"]]["status"] == "open"


def test_ids_increment_within_day():
    ev = _opened(events=[])
    ev += _opened(events=ev)
    assert [e["finding_id"] for e in ev if e["event"] == "opened"] == [
        "VF-20260725-0001", "VF-20260725-0002"]


def test_invalid_severity_and_root_cause_rejected():
    with pytest.raises(FindingError):
        _opened(severity="blocker", events=[])
    with pytest.raises(FindingError):
        _opened(events=[], root_cause="알수없음")


# ---------- 종결 통제 (VAL-013 핵심) ----------

def test_cannot_close_without_reverification():
    ev = _opened(events=[])
    fid = ev[0]["finding_id"]
    with pytest.raises(FindingError, match="재검증 통과 기록 없이"):
        close_finding(fid, as_of=AS, events=ev)


def test_failed_reverification_returns_to_remediating_and_blocks_close():
    ev = _opened(events=[])
    fid = ev[0]["finding_id"]
    ev.append(record_remediation(fid, action="a", root_cause="model",
                                 as_of=AS, events=ev))
    ev.append(record_reverification(fid, result="fail", evidence="미회복",
                                    as_of=AS, events=ev))
    assert derive(ev)[fid]["status"] == "remediating"
    with pytest.raises(FindingError):
        close_finding(fid, as_of=AS, events=ev)


def test_cannot_close_without_root_cause():
    """근본원인 없는 종결은 재발 관리를 무력화하므로 차단."""
    ev = _opened(events=[])
    fid = ev[0]["finding_id"]
    # 보완 기록을 건너뛰고 강제로 재검증 pass 이벤트만 주입
    ev.append({"event": "reverified", "finding_id": fid, "at": AS.isoformat(),
               "result": "pass", "evidence": "x"})
    with pytest.raises(FindingError, match="근본원인"):
        close_finding(fid, as_of=AS, events=ev)


def test_happy_path_closes():
    ev = _opened(events=[])
    fid = ev[0]["finding_id"]
    _full_lifecycle(ev, fid)
    assert derive(ev)[fid]["status"] == "closed"


def test_cannot_close_twice():
    ev = _opened(events=[])
    fid = ev[0]["finding_id"]
    _full_lifecycle(ev, fid)
    with pytest.raises(FindingError, match="이미 종결"):
        close_finding(fid, as_of=AS, events=ev)


def test_invalid_transition_rejected():
    ev = _opened(events=[])
    fid = ev[0]["finding_id"]
    with pytest.raises(FindingError, match="전이 불가"):
        record_reverification(fid, result="pass", evidence="", as_of=AS,
                              events=ev)


def test_unknown_finding_rejected():
    with pytest.raises(FindingError, match="존재하지 않는"):
        record_remediation("VF-X", action="a", root_cause="data", as_of=AS,
                           events=[])


# ---------- 재발 관리 (VAL-014) ----------

def test_recurrence_raises_severity():
    ev = _opened(events=[], target="TRG-CRD-PSI")
    fid = ev[0]["finding_id"]
    _full_lifecycle(ev, fid, root_cause="model")

    new = _opened(events=ev, as_of=date(2026, 10, 1), target="TRG-CRD-PSI",
                  root_cause="model", severity="medium")
    assert new[0]["recurrence_of"] == fid
    assert new[0]["severity"] == "high"
    assert any(e["event"] == "severity_raised" for e in new)


def test_recurrence_capped_at_critical():
    ev = _opened(events=[], severity="critical", target="T")
    fid = ev[0]["finding_id"]
    _full_lifecycle(ev, fid, root_cause="data")
    new = _opened(events=ev, severity="critical", target="T",
                  root_cause="data")
    assert new[0]["severity"] == "critical"


def test_no_recurrence_when_root_cause_differs():
    ev = _opened(events=[], target="T")
    fid = ev[0]["finding_id"]
    _full_lifecycle(ev, fid, root_cause="model")
    new = _opened(events=ev, target="T", root_cause="data")
    assert new[0]["recurrence_of"] is None
    assert new[0]["severity"] == "medium"


def test_open_finding_is_not_recurrence_source():
    """미종결 건은 재발 판정 기준이 아니다 (아직 해소된 적 없음)."""
    ev = _opened(events=[], target="T", root_cause="model")
    new = _opened(events=ev, target="T", root_cause="model")
    assert new[0]["recurrence_of"] is None


def test_detect_recurrence_requires_root_cause():
    assert detect_recurrence("credit", None, "T", {}) is None


# ---------- 큐 / 계보 ----------

def test_queue_orders_by_due_and_flags_overdue():
    ev = _opened(events=[], severity="critical")
    ev += _opened(events=ev, severity="medium")
    rows = queue(derive(ev), as_of=AS)
    assert [r["due_at"] for r in rows] == sorted(r["due_at"] for r in rows)
    assert all(not r["overdue"] for r in rows)
    later = queue(derive(ev), as_of=date(2026, 8, 20))
    assert all(r["overdue"] for r in later)


def test_queue_excludes_closed_and_filters():
    ev = _opened(events=[], severity="critical")
    fid = ev[0]["finding_id"]
    ev += _opened(events=ev, severity="medium")
    _full_lifecycle(ev, fid, root_cause="data")
    rows = queue(derive(ev), as_of=AS)
    assert [r["finding_id"] for r in rows] == ["VF-20260725-0002"]
    assert queue(derive(ev), as_of=AS, severity="critical") == []


def test_lineage_shows_full_chain():
    ev = _opened(events=[])
    fid = ev[0]["finding_id"]
    _full_lifecycle(ev, fid)
    text = render_lineage(derive(ev)[fid])
    for token in ("opened", "remediation_recorded", "reverified", "closed"):
        assert token in text


def test_render_queue_empty():
    assert "없음" in render_queue([])


def test_derive_rejects_orphan_event():
    with pytest.raises(FindingError, match="opened 이벤트 없이"):
        derive([{"event": "closed", "finding_id": "VF-X", "at": "2026-07-25"}])


# ---------- 승인 차단 (VAL-016) ----------

def test_critical_open_finding_blocks_approval():
    ev = _opened(events=[], severity="critical")
    blockers = approval_blockers(derive(ev))
    assert len(blockers) == 1
    assert blockers[0]["finding_id"] == ev[0]["finding_id"]


def test_closed_critical_does_not_block():
    ev = _opened(events=[], severity="critical")
    _full_lifecycle(ev, ev[0]["finding_id"], root_cause="data")
    assert approval_blockers(derive(ev)) == []


def test_non_critical_does_not_block():
    ev = _opened(events=[], severity="high")
    assert approval_blockers(derive(ev)) == []


def test_manifest_promote_blocked_by_critical_finding(monkeypatch):
    from tools import manifest as manifest_mod
    from tools.validation_finding import approval_blockers as real

    ev = _opened(events=[], severity="critical")
    states = derive(ev)
    monkeypatch.setattr("tools.validation_finding.approval_blockers",
                        lambda *a, **k: real(states))
    with pytest.raises(manifest_mod.ManifestError, match="VAL-016"):
        manifest_mod.promote("CHG-0001", "applied")


def test_manifest_promote_gate_can_be_bypassed_explicitly(monkeypatch):
    """차단은 기본값이며 우회는 명시적 인자로만 가능하다 (조용한 우회 금지)."""
    from tools import manifest as manifest_mod

    called = {"n": 0}

    def _spy(*a, **k):
        called["n"] += 1
        return []

    monkeypatch.setattr("tools.validation_finding.approval_blockers", _spy)
    with pytest.raises(manifest_mod.ManifestError):
        # 전이 규칙 자체는 여전히 적용되므로 ManifestError 가 나되,
        # Finding 게이트는 호출되지 않아야 한다.
        manifest_mod.promote("CHG-0001", "applied", check_findings=False)
    assert called["n"] == 0


# ---------- 저장소 / 카탈로그 ----------

def test_events_are_append_only(tmp_path):
    path = tmp_path / "f.jsonl"
    ev = _opened(events=[])
    append_events(ev, path)
    append_events(_opened(events=load_events(path)), path)
    rows = load_events(path)
    assert [r["finding_id"] for r in rows if r["event"] == "opened"] == [
        "VF-20260725-0001", "VF-20260725-0002"]


def test_taxonomy_constants():
    assert set(ROOT_CAUSES) == {"data", "model", "formula", "implementation",
                                "process"}
    assert SEVERITY_ORDER == ("medium", "high", "critical")


def test_catalog_sync():
    from tools.cli_index import CLI_MODULES
    from vta.cli.__main__ import _DISPATCH

    assert "tools.validation_finding" in {m for m, _ in CLI_MODULES}
    assert ("finding",) in _DISPATCH
