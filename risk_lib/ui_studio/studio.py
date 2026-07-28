"""에이전틱 UI 스튜디오 — 전 모듈 통제 상태를 하나의 실행 스냅샷으로.

`build_studio(result, portfolio)`가 정규 테이블 71장 · 업무보고서 14서식 ·
UIX 통제 원장을 모두 채우고, 그 위에서 실제로 실행된 조회계획과 레이아웃
제안을 만든다. `app.render(studio)`가 그 스냅샷을 자체 완결 HTML로 그린다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from risk_lib.datamodel.materialize import materialize_all
from risk_lib.datamodel.materialize_detail import materialize_detail
from risk_lib.regulatory.forms import build_forms, form_frames, submission_digest
from risk_lib.ui_studio import governance as gov
from risk_lib.ui_studio import layout as lay
from risk_lib.ui_studio.nl_query import QueryPlan, compile_query, execute

# 데모 조회 — 실제 데이터에 대해 **실행되는** 문장이다. 화면에만 있는 예시가
# 아니라 결과 행 수가 실제 산출에서 나온다.
DEMO_QUERIES: tuple[tuple[str, str, str], ...] = (
    ("V_RDM_ASSET_QUALITY",
     "연체일수 30 이상 그리고 잔액 100억 이상",
     "자산건전성 예외 조회"),
    ("V_RWA_SA_BUCKET",
     "위험가중치 1.0 이상 그리고 EAD 1000억 이상",
     "표준방법 고위험가중 구간 조회"),
    ("V_ECL_RESULT",
     "Stage 2 그리고 커버리지 0.05 초과",
     "SICR 전이 후 커버리지 점검"),
    ("V_MKT_IPV",
     "미해소 일수 5 이상",
     "IPV 미해소 예외 조회"),
    ("V_CRM_EWS_SIGNAL",
     "신호 강도 0.8 이상",
     "조기경보 상위 신호 조회"),
    # 미승인 필드를 짚는 문장 — 차단이 실제로 걸리는지 화면에서 보여준다.
    ("V_RDM_EXPOSURE",
     "차주 식별자 OBL_CORP_00001 그리고 EAD 100억 이상",
     "차주 단위 직접 조회 (차단 예상)"),
)

DEMO_PROMPTS: tuple[tuple[str, str], ...] = (
    ("V_RWA_SA_BUCKET",
     "자산군별 위험가중자산 기여도를 막대차트로 보여주고 아래에 "
     "EAD·위험가중치·소요자기자본 검토 표를 배치해줘. 상위 10건."),
    ("V_ALM_LCR_ITEM",
     "항목별 가중 후 금액을 표로 보여주고 적용률 추이를 함께 배치해줘."),
    # 마스킹 필드를 열로 요구하는 프롬프트 — 집계 최소단위 위반으로 거부된다.
    ("V_CRM_EWS_SIGNAL",
     "차주 식별자와 신호 강도를 행 단위 표로 보여줘."),
)


@dataclass
class Studio:
    asof: str
    run_id: str
    digest: str
    tables: dict[str, pd.DataFrame]
    built_forms: list = field(default_factory=list)
    plans: list[QueryPlan] = field(default_factory=list)
    plan_results: dict[str, pd.DataFrame] = field(default_factory=dict)
    proposals: list[lay.LayoutProposal] = field(default_factory=list)
    result: object = None
    iv_request: object = None      # 독립검증 요청 (3선 위임)
    iv_gate: object = None         # 게이트 상태 — 결재 가능 여부

    def view_fields(self, view_id: str) -> pd.DataFrame:
        p = self.tables["ui_field_policy"]
        return p[p["view_id"] == view_id]

    def view_row(self, view_id: str) -> pd.Series | None:
        v = self.tables["ui_view"]
        hit = v[v["view_id"] == view_id]
        return hit.iloc[0] if len(hit) else None


def build_studio(result, portfolio, *, institution: str = "(기관명)") -> Studio:
    asof = result.meta.get("asof", "1970-01-01")
    run_id = f"RUN-{asof.replace('-', '')}"

    from risk_lib.datamodel.decompose import dq_result_frame, validate_all
    tables = materialize_all(result, portfolio)
    tables.update(materialize_detail(result, portfolio, tables))
    # DQ 결과는 분해 단계의 산물이다 — 없으면 "그때는 통과했다"를 증명 못 한다.
    tables["rdm_dq_result"] = dq_result_frame(validate_all(tables), asof=asof)

    # ---- 업무보고서 (PRD-REG)
    built = build_forms(result, portfolio, tables)
    digest = submission_digest(built)
    tables.update(form_frames(built, asof))

    # ---- UIX 통제 원장
    views, policies = gov.build_views()
    tables["ui_view"], tables["ui_field_policy"] = views, policies
    registry = gov.build_agent_registry()
    tables["agent_registry"] = registry
    tables["agent_activity"] = gov.build_agent_activity(tables, run_id, registry)
    tables["agent_killswitch"] = gov.build_killswitch(run_id)
    tables.update(gov.build_change_factory(tables))
    tables.update(gov.build_evidence_graph(tables, run_id, digest=digest))
    tables["gov_approval"] = gov.build_approvals(tables, run_id)

    # ---- 문서 생성 구간 대조 (자체검증 2선) — 서식이 여기서야 만들어지므로
    # 파이프라인이 아니라 조립 시점에 붙인다. 문서에 손으로 적은 수치가 코드
    # 사실과 어긋나는 결함이 네 번 반복됐고(F-103·F-201·F-401·F-501), 그때마다
    # "다음엔 대조하겠다"로 끝났다. 대조를 사람이 기억해야 하는 한 다섯 번째가
    # 온다 — 6차 조건부 결재 후속조건 2 (이행기한 2026-08-10).
    #
    # `result.validation`에 **덧붙이지 않는다**. 덧붙이면 파이프라인 자체검증
    # 집계가 "스튜디오를 조립했는가"에 따라 달라져 순서 의존이 생긴다 — 같은
    # 파이프라인 결과가 호출 순서에 따라 다른 요약을 내면 그 요약은 근거가
    # 못 된다. 별도로 들고 있다가 요청서에 명시적으로 넘긴다.
    # 서식 간 대사 — 한 서식 안에서만 보는 FormCheck 로는 같은 수치가 서식마다
    # 다른 상태를 잡을 수 없다. 실제로 그 상태로 "검증 1,735건 실패 0"이
    # 나왔다 (지적 F-701).
    from risk_lib.regulatory.cross_form import cross_form_checks
    from risk_lib.validation.doc_figures import check_doc_figures, docs_for_run
    # 문서 파일명의 run_id는 독립검증 규약(RUN-<asof>-<seed>)을 따른다 —
    # 스튜디오의 run_id(seed 없음)와 다르므로 여기서 따로 만든다.
    _iv_run = f"RUN-{asof.replace('-', '')}-{int(result.meta.get('seed', 42))}"
    doc_checks = [c for doc in docs_for_run(_iv_run)
                  for c in check_doc_figures(doc, built, asof)]
    doc_checks += cross_form_checks(built)

    # ---- 상시 독립검증(3선) 위임 — 매 조립마다 요청을 만들고 게이트를 본다.
    # 요청을 "필요할 때만" 만들면 결국 만들지 않게 된다.
    from risk_lib.validation.independent import (
        build_request, check_gate, request_frames,
    )
    iv_request = build_request(result, portfolio, tables,
                               extra_checks=doc_checks, built_forms=built)
    iv_gate = check_gate(iv_request)
    tables.update(request_frames(iv_request, iv_gate))

    studio = Studio(asof=asof, run_id=run_id, digest=digest, tables=tables,
                    built_forms=built, result=result,
                    iv_request=iv_request, iv_gate=iv_gate)

    # ---- 조회계획 컴파일 + 실행
    plans, plan_results = [], {}
    for view_id, utterance, intent in DEMO_QUERIES:
        vrow = studio.view_row(view_id)
        if vrow is None:
            continue
        fields = studio.view_fields(view_id)
        plan = compile_query(utterance, view_id=view_id, asof=asof,
                             fields=fields, intent=intent,
                             population=str(vrow["view_name"]))
        src = tables.get(str(vrow["table_ref"]), pd.DataFrame())
        rows, plan = execute(plan, src, row_limit=int(vrow["row_limit"]))
        plans.append(plan)
        plan_results[plan.plan_id] = rows
    studio.plans, studio.plan_results = plans, plan_results
    tables["ui_query_plan"] = pd.DataFrame([{
        "plan_id": p.plan_id, "view_id": p.view_id, "asof": p.asof,
        "utterance": p.utterance, "intent": p.intent,
        "population": p.population, "condition_ast": p.condition_ast,
        "policy": p.policy, "query_hash": p.query_hash, "n_rows": p.n_rows,
        "status": p.status, "block_reason": p.block_reason,
    } for p in plans], columns=[
        "plan_id", "view_id", "asof", "utterance", "intent", "population",
        "condition_ast", "policy", "query_hash", "n_rows", "status",
        "block_reason"])

    # ---- 레이아웃 제안 + 정책검증 (+ 통과분은 사람 승인)
    proposals = []
    for view_id, prompt in DEMO_PROMPTS:
        vrow = studio.view_row(view_id)
        if vrow is None:
            continue
        p = lay.compose(prompt, view_id=view_id,
                        fields=studio.view_fields(view_id),
                        row_limit=int(vrow["row_limit"]))
        if p.all_pass:
            p = lay.approve(p, approver="리스크관리부장")
        proposals.append(p)
    studio.proposals = proposals
    tables["ui_layout_proposal"] = lay.proposal_frame(proposals)
    return studio
