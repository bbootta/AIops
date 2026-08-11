"""검증 기억 원장 — 규칙마다 위반 fixture 로 반증한다.

실패할 수 없는 검사는 통제가 아니다 (F-602 · F-E01). verify 의 각 규칙에
대해 (1) 정상 fixture 통과 (2) 위반 fixture 실패를 짝으로 확인하고,
(3) 실제 원장 4종의 상호 정합을 검사한다. 합성 fixture 를 쓰는 이유는
실데이터 분포에 의존한 테스트가 데이터가 좋아지는 순간 죽기 때문이다
(R80 교훈 — StopIteration).
"""

from __future__ import annotations

import copy

from tools.validation_memory import (
    load_carryover, load_patterns, load_rounds, load_self_defects,
    render_carryover, render_patterns, render_rounds, render_self_defects,
    verify,
)

# ------------------------------------------------------------- 합성 fixture

_PROTOCOL = {"challenges": [
    {"challenge_id": "ADV-X-01", "origin": "RUN-X (F-101) 에서 태어났다"},
    {"challenge_id": "ADV-X-02"},
]}


def _rounds():
    return [
        {"seq": 1, "request_id": "IVR-AAA", "run_id": "RUN-X", "verdict": "중부적합",
         "gate": "부적합", "approved": False,
         "severity_counts": {"중부적합": 1, "경부적합": 0, "적합": 0},
         "findings": [{"finding_id": "F-101", "severity": "중부적합", "target": "t"}],
         "recalc_all_match": True, "theme": "x"},
        {"seq": 2, "request_id": "IVR-BBB", "run_id": "RUN-X", "verdict": "경부적합",
         "gate": "조건부", "approved": True,
         "severity_counts": {"중부적합": 0, "경부적합": 1, "적합": 1},
         "findings": [{"finding_id": "F-201", "severity": "경부적합", "target": "t"},
                      {"finding_id": "F-202", "severity": "적합", "target": "t"}],
         "recalc_all_match": True, "theme": "y"},
    ]


def _patterns():
    return {"patterns": [
        {"pattern_id": "P-X", "name": "n", "thesis": "t",
         "members": ["F-101", "F-201"], "status": "live", "open_member": "F-201"},
    ]}


def _defects():
    return [{"defect_id": "SD-X", "round": 1, "kind": "판정", "summary": "s",
             "recorded_in": "F-101", "fix_challenge": "ADV-X-01", "lesson": "l"}]


def _carryover():
    return [{"item_id": "CO-X", "title": "t", "first_seen_round": 1,
             "last_seen_round": 2, "status": "open", "blocker": "b"}]


def _run(**over):
    kw = dict(rounds=_rounds(), patterns=_patterns(), self_defects=_defects(),
              carryover=_carryover(), protocol=_PROTOCOL)
    kw.update(over)
    return verify(**kw)


def test_clean_fixture_passes():
    assert _run() == []


# ------------------------------------------------------- 회차 규칙의 반증

def test_broken_sequence_fails():
    r = _rounds()
    r[1]["seq"] = 3
    assert any("연속이 아니다" in p for p in _run(rounds=r))


def test_duplicate_request_id_fails():
    r = _rounds()
    r[1]["request_id"] = "IVR-AAA"
    assert any("request_id 중복" in p for p in _run(rounds=r))


def test_duplicate_finding_id_across_rounds_fails():
    r = _rounds()
    r[1]["findings"][0]["finding_id"] = "F-101"
    assert any("중복" in p and "F-101" in p for p in _run(rounds=r))


def test_severity_counts_must_match_findings():
    r = _rounds()
    r[0]["severity_counts"] = {"중부적합": 2, "경부적합": 0, "적합": 0}
    assert any("실계" in p for p in _run(rounds=r))


def test_verdict_must_match_worst_severity():
    r = _rounds()
    r[0]["verdict"] = "적합"
    assert any("최고 심각도" in p for p in _run(rounds=r))


def test_gate_deviation_requires_note():
    r = _rounds()
    r[1]["gate"] = "부적합"          # 경부적합인데 부적합 — 사유 없음
    assert any("gate_note" in p for p in _run(rounds=r))
    r[1]["gate_note"] = "조건부 경로 미존재 시기"    # 사유를 남기면 허용
    assert _run(rounds=r) == []


# ------------------------------------------------------- 패턴 규칙의 반증

def test_pattern_member_must_exist_in_rounds():
    p = _patterns()
    p["patterns"][0]["members"].append("F-999")
    assert any("F-999" in x and "회차 원장에 없다" in x for x in _run(patterns=p))


def test_pattern_members_must_be_in_round_order():
    p = _patterns()
    p["patterns"][0]["members"] = ["F-201", "F-101"]
    assert any("회차 순이 아니다" in x for x in _run(patterns=p))


def test_live_pattern_requires_open_member():
    p = _patterns()
    del p["patterns"][0]["open_member"]
    assert any("open_member" in x for x in _run(patterns=p))


def test_closed_pattern_requires_note():
    p = _patterns()
    p["patterns"][0]["status"] = "closed"
    p["patterns"][0].pop("open_member")
    assert any("closed_note" in x for x in _run(patterns=p))


# --------------------------------------------------- 자기결함 규칙의 반증

def test_self_defect_evidence_must_exist():
    d = _defects()
    d[0]["recorded_in"] = "F-777"
    assert any("F-777" in x for x in _run(self_defects=d))


def test_self_defect_fix_challenge_must_be_in_protocol():
    d = _defects()
    d[0]["fix_challenge"] = "ADV-NOPE-99"
    assert any("ADV-NOPE-99" in x for x in _run(self_defects=d))


def test_self_defect_without_any_fix_fails():
    d = _defects()
    d[0]["fix_challenge"] = None
    assert any("시정 없이 닫히지 않는다" in x for x in _run(self_defects=d))


# ---------------------------------------------- 프로토콜 origin 역참조 반증

def test_protocol_origin_must_point_at_recorded_finding():
    proto = copy.deepcopy(_PROTOCOL)
    proto["challenges"][0]["origin"] = "어디서도 기록되지 않은 F-666 에서 태어났다"
    assert any("F-666" in x and "출처가 끊겼다" in x for x in _run(protocol=proto))


# ------------------------------------------------------- 이월 규칙의 반증

def test_carryover_round_range_is_checked():
    c = _carryover()
    c[0]["last_seen_round"] = 9
    assert any("회차 범위 오류" in x for x in _run(carryover=c))


def test_closed_carryover_requires_resolution():
    c = _carryover()
    c[0]["status"] = "closed"
    assert any("resolution" in x for x in _run(carryover=c))


# --------------------------------------------------------- 실제 원장 정합

def test_real_ledgers_are_consistent():
    """실제 원장 4종 + 실제 프로토콜의 상호 정합 — 배치가 되돌아가면 잡힌다."""
    assert verify() == []


def test_real_rounds_derive_from_exchange_history():
    rounds = load_rounds()
    assert [r["seq"] for r in rounds] == list(range(1, len(rounds) + 1))
    assert rounds[0]["request_id"].startswith("IVR-")
    # 결재 회차는 실제 결재 원장이 있는 4·6차뿐이어야 한다
    assert [r["seq"] for r in rounds if r.get("approved")] == [4, 6]


def test_real_pattern_counts_are_derived_not_typed():
    """반복 횟수를 손으로 센 수치(125종·9건 오기)의 재발 방지 — 원본에서 파생."""
    idx = {f["finding_id"] for r in load_rounds() for f in r["findings"]}
    for p in load_patterns()["patterns"]:
        assert set(p["members"]) <= idx


def test_renders_do_not_crash_and_carry_key_facts():
    rounds = load_rounds()
    out = render_rounds(rounds)
    assert f"{len(rounds)}회" in out
    md = render_rounds(rounds, md=True)
    assert md.startswith("| 회차 |")
    assert render_patterns(load_patterns(), rounds).count("반복") >= 4
    assert "검증자도 검증 대상" in render_self_defects(load_self_defects())
    co = render_carryover(load_carryover(), n_rounds=len(rounds))
    assert "연속 미해소" in co and "미확인은 통과가 아니다" in co


def test_cli_verify_exit_codes(tmp_path, monkeypatch):
    from tools import validation_memory as vm
    assert vm.main(["verify"]) == 0
    broken = tmp_path / "rounds.jsonl"
    rows = _rounds()
    rows[1]["seq"] = 5
    broken.write_text("\n".join(__import__("json").dumps(r, ensure_ascii=False)
                                for r in rows), encoding="utf-8")
    monkeypatch.setattr(vm, "ROUNDS_PATH", broken)
    assert vm.main(["verify"]) == 1
