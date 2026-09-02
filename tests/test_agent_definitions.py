"""에이전트 정의와 코드의 정합 (2026-09 검수 6단계).

정의 파일은 코드가 아니어서 조용히 낡는다. 마감표가 명부에 없는 담당을 가리키고,
검증자 정의가 없는 체크명을 적고, 한 정의 안에서 해라와 하지 마라가 같은 함수를
가리켰다. 여기서는 정의가 가리키는 이름이 코드에 실재하는지를 고정한다.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.risk_agents import (AGENTS_DIR, RISK_DOMAIN_AGENTS,
                               RISK_ROLE_AGENTS)

ROOT = Path(__file__).resolve().parent.parent


def _read(name: str) -> str:
    return (AGENTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def _tools(name: str) -> list[str]:
    m = re.search(r"^tools:\s*(.+)$", _read(name), re.M)
    assert m, f"{name}: tools 줄 없음"
    return [t.strip() for t in m.group(1).split(",")]


# ----- 마감 워크플로 담당 -------------------------------------------------------

def test_close_workflow_agents_exist_in_the_roster():
    """마감표의 agent_ref 는 명부 이름이거나 사람·3선 팀이어야 한다."""
    from risk_lib import close_workflow as cw
    roster = set(RISK_DOMAIN_AGENTS) | set(RISK_ROLE_AGENTS)
    unknown = cw.task_agent_refs() - roster - cw.NON_ROSTER_AGENT_REFS
    assert not unknown, f"명부에 없는 담당: {sorted(unknown)}"


def test_alm_stage_has_an_owner_on_disk():
    from risk_lib import close_workflow as cw
    tk = cw.build_close_tasks({}).set_index("task_id")
    assert tk.loc["CL-07", "agent_ref"] == "alm-analyst"
    assert (AGENTS_DIR / "alm-analyst.md").exists()


def test_alm_product_is_owned_by_the_alm_agent():
    from risk_lib import rynta
    assert rynta.AGENT_OWNER["PRD-ALM"] == "alm-analyst"


# ----- 검증자 정의의 체크명 --------------------------------------------------------

def test_validator_definition_names_checks_that_exist():
    """정의 표의 체크명이 consistency.py 에 실재해야 한다. 와일드카드(`bis_*`)와
    대괄호 표기(`pd_in_[0,1]`)는 제외한다."""
    src = (ROOT / "risk_lib" / "validation" / "consistency.py").read_text(encoding="utf-8")
    # 코드의 문자열 리터럴을 패턴으로 만든다. f"bis_{name}_min" 처럼 자리표시가
    # 있으면 그 자리는 어떤 식별자든 된다.
    patterns = [re.compile("^" + re.sub(r"\{[^}]*\}", "[a-z0-9_]+", lit) + "$")
                for lit in re.findall(r'f?"([A-Za-z0-9_{}]+)"', src)]
    names = re.findall(r"`([a-z0-9_]+)`", _read("risk-validator").split("## 검증 체크리스트")[1]
                       .split("## PD 백테스트")[0])
    columns = {"blocks_approval", "is_identity"}     # val_check 열 이름, 체크명이 아니다
    missing = [n for n in names if n not in columns
               and not any(pt.match(n) for pt in patterns)]
    assert not missing, f"코드에 없는 체크명: {missing}"
    assert "pd_floor_3bp" not in _read("risk-validator")
    assert "`bis_cet1_min`" not in _read("risk-validator")


# ----- 소관 중복 · 자기모순 ----------------------------------------------------------

def test_market_rwa_is_computed_by_exactly_one_agent():
    callers = [n for n in RISK_DOMAIN_AGENTS
               if "compute_market_risk_rwa(" in _read(n)]
    assert callers == ["market-risk-analyst"], callers


def test_orchestrator_routes_every_domain_agent():
    txt = _read("risk-orchestrator")
    missing = [n for n in RISK_DOMAIN_AGENTS if f"`{n}`" not in txt]
    assert not missing, f"오케스트레이터 분류표에 없는 에이전트: {missing}"


def test_macro_monitor_definition_uses_the_live_api():
    txt = _read("macro-indicator-monitor")
    from risk_lib import macro_monitor
    for dep in macro_monitor._DEPRECATED:
        assert not re.search(rf"^\s*{dep},", txt, re.M), f"폐기 API 를 가르친다: {dep}"
    assert "indicator_specs" in txt and "scenario_shock_map" in txt


# ----- 최소 권한 ------------------------------------------------------------------

def test_domain_agents_do_not_carry_edit():
    """산출 저장의 Write 는 정당하지만 risk_lib 소스를 고치는 Edit 는 '조회 전용 →
    제안 전용' 가드레일과 충돌한다."""
    offenders = [n for n in RISK_DOMAIN_AGENTS if "Edit" in _tools(n)]
    assert not offenders, offenders


def test_validator_and_auditor_do_not_write():
    for n in ("risk-validator", "aims-compliance-auditor"):
        assert not ({"Edit", "Write"} & set(_tools(n))), n


# ----- 문서의 개수는 코드가 정본 ---------------------------------------------------------

def test_skill_states_the_recalc_scope_size_the_code_has():
    from risk_lib.validation.independent import RECALC_SCOPE
    txt = (ROOT / ".claude" / "skills" / "independent-validation" / "SKILL.md").read_text(encoding="utf-8")
    m = re.search(r"재계산 대상 (\d+)종", txt)
    assert m and int(m.group(1)) == len(RECALC_SCOPE), (m and m.group(0), len(RECALC_SCOPE))


# ----- 3선 위임 훅 -----------------------------------------------------------------

def test_dispatch_leaves_an_outbox_copy_and_a_record(tmp_path):
    import json
    from types import SimpleNamespace
    from risk_lib.validation import independent as iv
    req = SimpleNamespace(request_id="IVR-x", run_id="RUN-20260630-42", asof="2026-06-30",
                          response_path=lambda d: Path(d) / "RUN-20260630-42.response.json",
                          dispatch_path=lambda d: Path(d) / "RUN-20260630-42.dispatch.json",
                          write=None)
    (tmp_path / "RUN-20260630-42.request.json").write_text('{"request_id": "IVR-x"}', encoding="utf-8")
    p = iv.dispatch_request(req, tmp_path)
    rec = json.loads(p.read_text(encoding="utf-8"))
    assert (tmp_path / "outbox" / "RUN-20260630-42.request.json").exists()
    assert rec["branch"] == iv.VALIDATION_TEAM_BRANCH and rec["status"] == "발신"
    assert any("git checkout" in c for c in rec["handover"])
    assert iv.dispatched(req, tmp_path)
    # 같은 요청을 다시 발신해도 기록은 같다 (벽시계 없음)
    assert p.read_text(encoding="utf-8") == iv.dispatch_request(req, tmp_path).read_text(encoding="utf-8")


def test_dispatch_record_for_another_request_id_does_not_count(tmp_path):
    import json
    from types import SimpleNamespace
    from risk_lib.validation import independent as iv
    req = SimpleNamespace(request_id="IVR-new", run_id="R", asof="2026-06-30",
                          dispatch_path=lambda d: Path(d) / "R.dispatch.json")
    (tmp_path / "R.dispatch.json").write_text(json.dumps({"request_id": "IVR-old"}), encoding="utf-8")
    assert not iv.dispatched(req, tmp_path)


def test_no_long_dashes_in_the_new_agent_definition():
    txt = _read("alm-analyst")
    assert "—" not in txt and "–" not in txt
