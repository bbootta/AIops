"""상시 독립검증(3선) 위임 — 요청·응답·게이트.

핵심 명제:
  1) 게이트는 fail-closed다. 응답이 없으면 '적합'이 아니라 '응답대기'이며
     결재 상신이 막힌다.
  2) 다른 실행의 응답을 이 실행의 승인으로 쓸 수 없다.
  3) 요청은 3선이 **다시 계산할 수 있는** 최소 집합을 담는다 — 자체검증 실패
     항목과 우리가 아는 가정을 숨기지 않는다.
  4) 자체검증(2선)이 독립검증(3선)을 대체하지 않는다.
"""

from __future__ import annotations

import json
from dataclasses import asdict, replace

import pytest

from risk_lib.datamodel import catalog as cat
from risk_lib.validation.independent import (
    KNOWN_ASSUMPTIONS, RECALC_SCOPE, VALIDATION_TEAM, VALIDATION_TEAM_BRANCH,
    Finding, IndependentValidationPending, ValidationResponse,
    build_request, check_gate, request_frames,
)


@pytest.fixture(scope="module")
def studio(result, portfolio):
    from risk_lib.ui_studio.studio import build_studio
    return build_studio(result, portfolio)


@pytest.fixture
def request_obj(result, portfolio, studio):
    return build_request(result, portfolio, studio.tables)


def _response(req, *, verdict="적합", findings=None, matches=None,
              run_id=None, request_id=None):
    return {
        "request_id": request_id or req.request_id,
        "run_id": run_id or req.run_id,
        "verdict": verdict,
        "validated_by": VALIDATION_TEAM,
        "validated_at": "2026-06-30T09:00:00+00:00",
        "findings": findings or [],
        "recalc_matches": (matches if matches is not None
                           else {k: True for k, *_ in RECALC_SCOPE}),
    }


def _write(tmp_path, req, payload):
    p = req.response_path(tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return p


# ----- 요청 패키지 ------------------------------------------------------------

def test_request_names_the_validation_team_branch(request_obj):
    assert request_obj.requested_to == VALIDATION_TEAM
    assert request_obj.branch == VALIDATION_TEAM_BRANCH == \
        "claude/validation-team-agent-Pw9F5"


def test_request_carries_every_recalc_target(request_obj):
    keys = {t["key"] for t in request_obj.recalc_targets}
    assert keys == {k for k, *_ in RECALC_SCOPE}
    assert len(keys) >= 10
    for t in request_obj.recalc_targets:
        assert t["citation"] and t["korean"]
        assert t["value"] is not None, t["key"]


def test_request_is_reproducible_by_the_other_team(request_obj):
    """재현 명령이 없으면 3선은 다시 계산할 수 없다."""
    joined = " ".join(request_obj.reproduce)
    assert "generate_portfolio" in joined and "run_pipeline" in joined
    assert str(request_obj.seed) in joined
    assert request_obj.asof in joined
    assert request_obj.headline_digest and request_obj.portfolio_fingerprint


def test_request_does_not_hide_self_validation_failures(result, portfolio,
                                                        studio):
    """자체검증 FAIL을 숨기고 넘기면 독립검증이 출발점을 잃는다."""
    req = build_request(result, portfolio, studio.tables)
    checks = studio.tables["val_check"]
    assert req.self_validation == {
        k: int(v) for k, v in checks["status"].value_counts().items()}
    assert set(req.self_validation_failures) == set(
        checks.loc[checks["status"] == "FAIL", "check_name"])


def test_request_hands_over_the_known_assumptions(request_obj):
    """우리가 아는 약한 고리를 넘기지 않으면 3선이 도전할 대상을 못 찾는다."""
    assert request_obj.known_assumptions == list(KNOWN_ASSUMPTIONS)
    assert len(KNOWN_ASSUMPTIONS) >= 6
    joined = " ".join(KNOWN_ASSUMPTIONS)
    for topic in ("자산건전성", "CRM", "서식번호", "충격 축"):
        assert topic in joined, topic


def test_request_round_trips_through_json(request_obj, tmp_path):
    p = request_obj.write(tmp_path)
    raw = json.loads(p.read_text(encoding="utf-8"))
    assert raw == json.loads(json.dumps(asdict(request_obj), ensure_ascii=False))


# ----- 게이트: fail-closed ----------------------------------------------------

def test_gate_is_pending_without_a_response(request_obj, tmp_path):
    gate = check_gate(request_obj, tmp_path)
    assert gate.status == "응답대기"
    assert not gate.approved
    with pytest.raises(IndependentValidationPending, match="독립검증 미완료"):
        gate.require()


def test_gate_approves_on_a_clean_response(request_obj, tmp_path):
    _write(tmp_path, request_obj, _response(request_obj))
    gate = check_gate(request_obj, tmp_path)
    assert gate.status == "적합" and gate.approved
    gate.require()                      # 예외 없음


def test_gate_rejects_a_response_from_another_run(request_obj, tmp_path):
    """다른 실행의 승인을 이 실행에 쓰면 게이트가 무의미해진다."""
    _write(tmp_path, request_obj,
           _response(request_obj, run_id="RUN-19990101-1"))
    gate = check_gate(request_obj, tmp_path)
    assert gate.status == "부적합" and "run_id 불일치" in gate.reason


def test_gate_rejects_a_response_with_a_stale_request_id(request_obj, tmp_path):
    _write(tmp_path, request_obj, _response(request_obj, request_id="IVR-OLD"))
    gate = check_gate(request_obj, tmp_path)
    assert gate.status == "부적합" and "request_id 불일치" in gate.reason


def test_gate_rejects_a_material_finding(request_obj, tmp_path):
    _write(tmp_path, request_obj, _response(
        request_obj, findings=[asdict(Finding(
            "F-001", "중부적합", "cet1_ratio", "독립 재계산 불일치"))]))
    gate = check_gate(request_obj, tmp_path)
    assert gate.status == "부적합" and "중부적합" in gate.reason


def test_gate_allows_a_minor_finding(request_obj, tmp_path):
    _write(tmp_path, request_obj, _response(
        request_obj, findings=[asdict(Finding(
            "F-002", "경부적합", "ecl_total", "가정 문서화 미흡"))]))
    assert check_gate(request_obj, tmp_path).status == "적합"


def test_gate_rejects_a_recalculation_mismatch(request_obj, tmp_path):
    matches = {k: True for k, *_ in RECALC_SCOPE}
    matches["rwa_final_total"] = False
    _write(tmp_path, request_obj, _response(request_obj, matches=matches))
    gate = check_gate(request_obj, tmp_path)
    assert gate.status == "부적합" and "rwa_final_total" in gate.reason


def test_gate_rejects_a_non_compliant_verdict(request_obj, tmp_path):
    _write(tmp_path, request_obj, _response(request_obj, verdict="중부적합"))
    assert check_gate(request_obj, tmp_path).status == "부적합"


# ----- 조건부 승인 (독립검증 지적 F-207) --------------------------------------
#
# 3선이 게이트 코드 자체를 검증해 docstring–구현 모순을 찾았다. docstring은
# "경부적합까지는 조건부 통과"라고 했으나 구현은 verdict == "적합"만 통과시켜,
# 약속한 조건부 경로가 존재하지 않았다. 판정 도구가 스스로 모순되면 그 위의
# 모든 판정이 흔들린다.

def test_a_minor_verdict_is_neither_pass_nor_fail(request_obj, tmp_path):
    _write(tmp_path, request_obj, _response(
        request_obj, verdict="경부적합", findings=[asdict(Finding(
            "F-201", "경부적합", "cet1_ratio", "문서 주장과 코드 불일치"))]))
    gate = check_gate(request_obj, tmp_path)
    assert gate.status == "조건부"
    assert not gate.approved              # 기계 판정만으로는 결재 불가
    assert "F-201" in gate.reason and "이행기한" in gate.reason


def test_conditional_status_still_blocks_without_a_record(request_obj, tmp_path):
    """조건부는 통과가 아니다 — 기록 없이 require()하면 여전히 막힌다."""
    _write(tmp_path, request_obj, _response(request_obj, verdict="경부적합"))
    with pytest.raises(IndependentValidationPending):
        check_gate(request_obj, tmp_path).require()


def test_conditional_approval_record_unblocks_the_gate(request_obj, tmp_path):
    from risk_lib.validation.independent import ConditionalApproval
    _write(tmp_path, request_obj, _response(request_obj, verdict="경부적합"))
    gate = check_gate(request_obj, tmp_path)
    gate.require(ConditionalApproval(
        approver="리스크관리책임자",
        residual_risk="합성 자본의 규모 비례분 54.3%",
        conditions=("실 자본 원장 확보 후 재산출",),
        due_date="2026-09-30",
        scope="내부 검토용 제한 배포",
        findings_accepted=("F-201", "F-202")))


def test_an_incomplete_conditional_record_does_not_unblock(request_obj, tmp_path):
    """빈 기록으로 조건부를 통과시키면 조건부가 무조건이 된다."""
    from risk_lib.validation.independent import ConditionalApproval
    _write(tmp_path, request_obj, _response(request_obj, verdict="경부적합"))
    gate = check_gate(request_obj, tmp_path)
    with pytest.raises(IndependentValidationPending, match="누락 항목"):
        gate.require(ConditionalApproval(
            approver="", residual_risk="", conditions=(),
            due_date="", scope=""))


def test_conditional_never_applies_when_a_material_finding_exists(
        request_obj, tmp_path):
    """중부적합이 하나라도 있으면 조건부 경로 자체가 열리지 않는다."""
    from risk_lib.validation.independent import ConditionalApproval
    _write(tmp_path, request_obj, _response(
        request_obj, verdict="경부적합", findings=[asdict(Finding(
            "F-900", "중부적합", "cet1_ratio", "재계산 불일치"))]))
    gate = check_gate(request_obj, tmp_path)
    assert gate.status == "부적합"
    with pytest.raises(IndependentValidationPending):
        gate.require(ConditionalApproval(
            approver="리스크관리책임자", residual_risk="—",
            conditions=("—",), due_date="2026-09-30", scope="—"))


def test_conditional_does_not_survive_a_recalculation_mismatch(
        request_obj, tmp_path):
    """재계산이 어긋나면 판정과 무관하게 부적합이다."""
    matches = {k: True for k, *_ in RECALC_SCOPE}
    matches["rwa_final_total"] = False
    _write(tmp_path, request_obj,
           _response(request_obj, verdict="경부적합", matches=matches))
    assert check_gate(request_obj, tmp_path).status == "부적합"


def test_request_id_changes_when_the_disclosed_content_changes(
        result, portfolio, studio, monkeypatch):
    """산출값이 그대로여도 3선에게 넘기는 내용이 바뀌면 재검증 대상이다.

    request_id가 headline 수치만 지문화하면, 가정 공시나 자체검증 WARN이 바뀌어도
    식별자가 그대로여서 그 변경을 본 적 없는 이전 응답이 계속 승인으로 통한다.
    산출값이 안 바뀌는 시정(문서·통제·가정 공시)일수록 재검증이 필요한데 그때
    정확히 뚫리므로, 넘기는 것 전부를 지문에 넣는다.
    """
    import risk_lib.validation.independent as iv
    before = build_request(result, portfolio, studio.tables).request_id
    monkeypatch.setattr(
        iv, "KNOWN_ASSUMPTIONS", KNOWN_ASSUMPTIONS + ("새로 공시한 가정",))
    after = build_request(result, portfolio, studio.tables)
    assert after.request_id != before
    assert after.headline_digest == studio.iv_request.headline_digest  # 수치는 그대로


def _mutate(value):
    """어떤 타입이든 '내용이 달라진' 값을 만든다."""
    if isinstance(value, str):
        return value + "-변경"
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        return value + 1
    if isinstance(value, float):
        return value + 1.0
    if isinstance(value, list):
        return value + [{"변경": True}] if all(
            isinstance(v, dict) for v in value) and value else value + ["변경"]
    if isinstance(value, dict):
        return {**value, "변경": 1}
    raise AssertionError(f"변형 규칙 없는 타입: {type(value)}")


def test_any_field_change_moves_the_request_id(request_obj):
    """**어떤 필드를 바꿔도** 식별자가 변해야 한다 (지적 F-301 · 후속조건 2).

    "특정 필드를 바꾸면 변한다"로 테스트를 쓰면 열거에서 빠진 필드가 그대로
    남는다 — 실제로 두 번 뚫렸다. headline 수치만 지문화했을 때 가정·WARN이,
    여섯 항목을 열거했을 때 recalc_targets의 citation이 뚫렸다. 그래서 명제를
    "전수"로 세운다. 새 필드가 늘어도 이 테스트가 자동으로 덮는다.
    """
    from dataclasses import fields, replace
    from risk_lib.validation.independent import (
        request_identifier, _ID_EXCLUDED_FIELDS)

    base = request_identifier(request_obj)
    checked = []
    for f in fields(request_obj):
        if f.name in _ID_EXCLUDED_FIELDS:
            continue
        mutated = replace(request_obj,
                          **{f.name: _mutate(getattr(request_obj, f.name))})
        assert request_identifier(mutated) != base, f"{f.name} 변경이 지문에 안 잡힌다"
        checked.append(f.name)
    assert len(checked) == len(fields(request_obj)) - len(_ID_EXCLUDED_FIELDS)
    assert "recalc_targets" in checked      # F-301이 뚫었던 바로 그 필드


def test_the_id_ignores_only_itself_and_the_wall_clock(request_obj):
    """제외 목록이 넓어지면 그만큼 stale 방어에 구멍이 난다."""
    from dataclasses import replace
    from risk_lib.validation.independent import (
        request_identifier, _ID_EXCLUDED_FIELDS)

    assert _ID_EXCLUDED_FIELDS == {"request_id", "created_at"}
    same = replace(request_obj, request_id="IVR-엉뚱한값",
                   created_at="1999-01-01T00:00:00+00:00")
    assert request_identifier(same) == request_identifier(request_obj)


def test_the_id_is_stable_for_identical_content(request_obj):
    """같은 내용이면 같은 식별자여야 한다 — 아니면 매번 재검증을 요구하게 된다."""
    from risk_lib.validation.independent import request_identifier
    assert request_identifier(request_obj) == request_identifier(request_obj)
    assert request_obj.request_id == request_identifier(request_obj)


def test_passes_docstring_matches_the_implementation():
    """F-207의 재발 방지 — docstring이 약속한 경로가 코드에 있어야 한다."""
    resp = ValidationResponse(
        request_id="IVR-X", run_id="RUN-X", verdict="경부적합",
        validated_by=VALIDATION_TEAM, validated_at="2026-07-26T00:00:00+00:00")
    assert resp.passes is False          # 무조건 통과는 아니고
    assert resp.conditional is True      # 조건부 경로는 열린다


def test_gate_rejects_an_unreadable_response(request_obj, tmp_path):
    p = request_obj.response_path(tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{ not json", encoding="utf-8")
    gate = check_gate(request_obj, tmp_path)
    assert gate.status == "부적합" and "읽을 수 없음" in gate.reason


# ----- 정규 테이블 ------------------------------------------------------------

def test_frames_satisfy_the_catalog_spec(request_obj, tmp_path):
    from risk_lib.datamodel.spec import validate
    gate = check_gate(request_obj, tmp_path)
    frames = request_frames(request_obj, gate)
    specs = {s.name: s for s in cat.ALL_TABLES}
    for name, df in frames.items():
        bad = [v for v in validate(df, specs[name]) if v.severity == "FAIL"]
        assert bad == [], (name, bad)


def test_recomputed_stays_null_before_a_response(request_obj, tmp_path):
    """응답 전에 0으로 채우면 '일치한 것'처럼 보인다."""
    frames = request_frames(request_obj, check_gate(request_obj, tmp_path))
    t = frames["val_independent_target"]
    assert t["recomputed"].isna().all()
    assert t["matched"].isna().all()


def test_recomputed_is_filled_from_the_response(request_obj, tmp_path):
    _write(tmp_path, request_obj, _response(
        request_obj, findings=[asdict(Finding(
            "F-003", "경부적합", "ecl_total", "재계산 일치", 1234.0, 1234.0))]))
    gate = check_gate(request_obj, tmp_path)
    t = request_frames(request_obj, gate)["val_independent_target"]
    row = t[t["target"] == "ecl_total"].iloc[0]
    assert float(row["recomputed"]) == 1234.0
    assert bool(row["matched"]) is True


# ----- 스튜디오 통합 ----------------------------------------------------------

def test_studio_always_builds_a_request(studio):
    """'필요할 때만' 만들면 결국 만들지 않게 된다."""
    assert studio.iv_request is not None
    assert studio.iv_gate is not None
    assert "val_independent_request" in studio.tables
    assert "val_independent_target" in studio.tables


def test_studio_gate_is_pending_by_default(studio, tmp_path, monkeypatch):
    from risk_lib.validation import independent as iv
    monkeypatch.setattr(iv, "DEFAULT_DIR", tmp_path)
    gate = iv.check_gate(studio.iv_request, tmp_path)
    assert gate.status == "응답대기"


def test_self_validation_pass_does_not_approve_the_gate(studio, tmp_path):
    """2선 PASS만으로 3선 게이트가 열리면 위임이 형식이 된다."""
    assert studio.iv_request.self_validation.get("FAIL", 0) == 0
    assert check_gate(studio.iv_request, tmp_path).status != "적합"


def test_every_recalc_target_has_a_value_in_the_ledger(studio):
    t = studio.tables["val_independent_target"]
    assert len(t) == len(RECALC_SCOPE)
    assert t["reported"].notna().all()


# ----- 지침·스킬 반영 ---------------------------------------------------------

def _read(path: str) -> str:
    from pathlib import Path
    return Path(path).read_text(encoding="utf-8")


def test_skill_exists_and_names_the_branch():
    txt = _read(".claude/skills/independent-validation/SKILL.md")
    assert VALIDATION_TEAM_BRANCH in txt
    assert "fail-closed" in txt
    assert "매 작업" in txt


def test_project_instructions_separate_the_two_layers():
    txt = _read("CLAUDE.md")
    assert VALIDATION_TEAM_BRANCH in txt
    assert "자체검증" in txt and "상시 독립검증" in txt


def test_aims_policy_records_the_third_line():
    txt = _read("AIMS_POLICY.md")
    assert VALIDATION_TEAM_BRANCH in txt
    assert "3선" in txt


def test_orchestrator_mandates_the_delegation():
    txt = _read(".claude/agents/risk-orchestrator.md")
    assert VALIDATION_TEAM_BRANCH in txt
    assert "check_gate" in txt


def test_validator_declares_it_is_not_independent():
    txt = _read(".claude/agents/risk-validator.md")
    assert "독립검증이 아니다" in txt
    assert VALIDATION_TEAM_BRANCH in txt


def test_every_domain_agent_states_the_delegation():
    from pathlib import Path
    for f in sorted(Path(".claude/agents").glob("*.md")):
        if f.stem == "aims-compliance-auditor":
            continue           # 내부심사자는 별도 역할 (조항 9.2)
        txt = f.read_text(encoding="utf-8")
        assert VALIDATION_TEAM_BRANCH in txt, f.name
