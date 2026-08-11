"""에이전틱 UI 스튜디오 — 전 모듈 통제 상태를 하나의 실행 스냅샷으로.

`build_studio(result, portfolio)`가 정규 테이블 71장 · 업무보고서 14서식 ·
UIX 통제 원장을 모두 채우고, 그 위에서 실제로 실행된 조회계획과 레이아웃
제안을 만든다. `app.render(studio)`가 그 스냅샷을 자체 완결 HTML로 그린다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from risk_lib import institutions as _inst
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
    # 이 스냅샷이 어느 기관의 산출인가. 화면의 기관 선택기는 이 값으로
    # 실행을 가른다. 산출에 쓰이는 값이 아니라 실행의 소속 표시다.
    institution_code: str = _inst.PRIMARY_INSTITUTION
    # 기관 축 원장. `tables` 에 넣지 않는 이유는 이것이 이 실행의 산출물이
    # 아니기 때문이다. 전 기관을 담은 축 마스터를 실행 원장에 섞으면 기관
    # 귀속·DQ·마감 판정이 이 원장까지 세게 되고, 실제로 기관코드 도장을
    # 찍는 검사가 전 기관이 든 프로파일 원장에서 걸렸다.
    inst_tables: dict[str, pd.DataFrame] = field(default_factory=dict)

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

    from risk_lib.datamodel.code_master import build_code_master
    from risk_lib.datamodel.decompose import dq_result_frame, validate_all
    tables = materialize_all(result, portfolio)
    # 코드 마스터 — 정렬·표시의 정본. 카탈로그 스펙에서 생성한다.
    tables["rdm_code_master"] = build_code_master()
    tables.update(materialize_detail(result, portfolio, tables))
    # 계정·상품 코드 스코프 — 반드시 detail **이후**다. LCR 적용률·거래
    # 건수를 산출 원장에서 실측 조인하는데, 그 원장들(alm_lcr_item·mkt_trade)
    # 이 detail 단계에서 생긴다. 앞에 두면 조인이 조용히 NaN이 된다 —
    # 실제로 그랬고 엔진-일치 검사가 잡았다.
    from risk_lib.datamodel import code_scope as _cs
    tables["rdm_account_master"] = _cs.account_master()
    tables["rdm_product_master"] = _cs.product_master()
    tables["crm_code_scope"] = _cs.credit_scope(tables)
    tables["mkt_code_scope"] = _cs.market_scope(tables)
    tables["alm_code_scope"] = _cs.alm_scope(tables)
    tables["opr_code_scope"] = _cs.op_scope(tables)
    # 선행 원장 — 집합투자증권(CRE60)·파생(CRE52)·유동화(CRE40~45).
    # 신용 익스포저 한 줄로 뭉뚱그리면 LTA/MBA·SA-CCR·SEC 계층을 산출할 수
    # 없다. 각 프레임워크의 입력이 원장 수준에서 다르기 때문이다.
    from risk_lib.datamodel.derivatives import build_derivatives
    _seed = int(result.meta.get("seed", 42))
    # 집합투자증권·유동화는 **파이프라인이 이미 세운 원장**을 그대로 받는다.
    # 이 원장의 RWA 가 자본비율 분모에 들어가 있으므로, 화면이 같은 인자로
    # 다시 만들면 두 번째 실행이 되고, 분모와 화면이 각각 다른 산출을 설명할
    # 여지가 생긴다. 같은 값이 나올 것이라는 기대는 통제가 아니다.
    _structured = getattr(result, "structured", None)
    if _structured is None:                       # 구형 result 로 부를 때만
        from risk_lib.datamodel.funds import build_funds
        from risk_lib.datamodel.securitisation import build_securitisation
        tables.update(build_funds(asof=asof, seed=_seed))
        tables.update(build_securitisation(asof=asof, seed=_seed))
    else:
        tables.update(_structured.tables)
    tables.update(build_derivatives(asof=asof, seed=_seed))

    # 도메인별 집계 원장 — 반드시 선행 원장·detail 이후다(mkt_trade·
    # opr_loss_event·st_capital_path 를 읽는다).
    from risk_lib.datamodel.exposure_agg import build_exposure_aggregates
    tables.update(build_exposure_aggregates(tables, asof=asof))

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
    # 예외·조치 워크플로(RDM-007)와 경보·조치 정책(PLT-015) — 예외는 세
    # 원장에서 파생되고, 정책은 정적 바인딩이다.
    tables["gov_alert_policy"] = gov.build_alert_policy()
    tables["gov_exception_action"] = gov.build_exception_actions(tables)

    # ---- 실행 통제 원장 (마감·감사체인·보존·통합 실행·AI 추적)
    # "이 실행이 무엇을 실었는가"를 입력으로 쓰므로 조립이 끝난 뒤에 만든다.
    # 앞에 두면 아직 서지 않은 원장이 빠진 채로 마감·통합 판정이 나간다.
    from risk_lib.datamodel.materialize_ledgers import materialize_run_control
    tables.update(materialize_run_control(result, tables, run_id=run_id))

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

    # ---- 기관 축 원장. 기관 선택기와 기관 설정 화면의 연결 원장이다.
    # `tables` 와 섞지 않는다. 이 원장은 이 실행의 산출물이 아니라 전 기관을
    # 담은 축 마스터라, 실행 원장에 섞으면 DQ·마감·기관귀속 판정이 그것까지
    # 세게 된다.
    from risk_lib import data_gen_intl as _intl
    inst_code = str(result.meta.get("institution_code")
                    or _intl.BASE_INSTITUTION)

    studio = Studio(asof=asof, run_id=run_id, digest=digest, tables=tables,
                    built_forms=built, result=result,
                    iv_request=iv_request, iv_gate=iv_gate,
                    institution_code=inst_code,
                    inst_tables=_intl.build_all())

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
