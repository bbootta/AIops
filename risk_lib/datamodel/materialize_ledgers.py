"""신규 원장(R15) 실체화 엔진.

R15 원장은 세 갈래로 들어온다.

1. **파이프라인이 이미 만든 것** — 거시 마스터·한도 정의·[별표 9-1] 국내 고유
   요건·공시서식·LGD/CCF 실측검증·내부등급법 추정·거액익스포져·행동모형·
   조달·증거금·상품·RCSA·피드·PMA·경영조치·변경·연계 통제. `_stage_ledgers`가
   산출하고 `result.ledger_tables`로 나온다. 여기서는 그대로 싣는다. 다시
   만들면 화면과 산출이 두 벌이 된다.
2. **부문 원장을 입력으로 쓰는 것** — 신용평가시스템(`crm_model`)과 CRM 담보
   배분(`rwa_result`). 그 입력이 실체화 단계에서 서므로 여기서 만든다.
3. **실행 전체를 입력으로 쓰는 것** — 마감 워크플로·감사체인·보존·통합 실행·
   AI 추적·가격 통제. 조립이 끝나야 원장 목록이 확정되므로 스튜디오가 마지막에
   `materialize_run_control`을 부른다.

값을 여기서 만들지 않는다. 이 모듈이 하는 일은 이미 있는 산출을 원장 계약에
맞춰 넘기는 것뿐이다.
"""

from __future__ import annotations

import warnings as warnings_mod

import pandas as pd


def _asof(result) -> str:
    return result.meta.get("asof", "1970-01-01")


def _seed(result) -> int:
    return int(result.meta.get("seed", 42))


# ---------------------------------------------------------------- 부문 의존 원장

def materialize_ledgers(result, portfolio, base: dict[str, pd.DataFrame]
                        ) -> dict[str, pd.DataFrame]:
    """파이프라인 원장 전달 + 부문 원장을 입력으로 쓰는 두 갈래 산출."""
    asof, seed = _asof(result), _seed(result)
    out: dict[str, pd.DataFrame] = dict(getattr(result, "ledger_tables", {}) or {})

    # ---- 신용평가시스템 (BNK-CRM-002~009)
    # 요건 적용 대상은 `crm_model`의 신용 도메인 모형이다. 모형 원장을 넘기지
    # 않으면 시장·ALM 모형에까지 신용평가 최소요건이 걸린다.
    models = base.get("crm_model")
    if models is not None and not models.empty:
        from risk_lib.credit_rating.build import build_credit_rating
        rating = build_credit_rating(portfolio, models, asof=asof, seed=seed)
        out.update(rating.tables)

    # ---- CRM 담보-익스포저 다대다 배분
    # 배분규칙 `risk_weight_desc`의 정렬 키가 위험가중치이므로 RWA 산출 원장이
    # 있어야 한다. 합성기가 위험가중치를 지어내면 대사가 자기 자신과의 대사다.
    rwa_result = base.get("rwa_result")
    if rwa_result is not None and not rwa_result.empty:
        from risk_lib import crm as crm_mod
        with warnings_mod.catch_warnings():
            warnings_mod.simplefilter("ignore")
            link = crm_mod.build_crm_link_universe(
                base["rdm_exposure"], base["rdm_collateral"], rwa_result,
                asof=asof, seed=seed)
            param = crm_mod.build_crm_mitigation_param()
            alloc, _w = crm_mod.allocate_crm(
                link["crm_collateral_link"], link["crm_collateral_terms"],
                link["crm_exposure_terms"], param, asof=asof,
                alloc_rule=crm_mod.ALLOC_RULES[0])
        out.update(link)
        out["crm_mitigation_param"] = param
        out["crm_allocation"] = alloc

    # ---- 가격·평가 통제 (GOV-006)
    # 관측은 공표 원장에서 직접 뽑는다. IPV 엔진을 여기서 다시 돌리면 통제가
    # 설명하는 IPV와 화면이 싣는 IPV가 다른 실행이 될 수 있다.
    out.update(_pricing_control(base, asof=asof))
    return out


def _pricing_control(tables: dict[str, pd.DataFrame], *, asof: str
                     ) -> dict[str, pd.DataFrame]:
    """IPV 원장에서 커버리지 관측을 만들고 가격 통제를 판정한다.

    PC-IPV는 명목 기준 커버리지, PC-SRC는 건수 기준 커버리지다. 두 정의는
    `ipv.run_ipv`가 쓰는 것과 같고, 여기서는 그 결과가 실린 원장
    (`mkt_ipv`·`mkt_trade`)에서 같은 값을 다시 뽑는다.

    관측이 없는 통제는 행을 만들지 않는다. 그러면 판정 엔진이 '미실시'로
    남긴다. 기록 없는 통제를 통과로 적으면 통제가 아니다.
    """
    from risk_lib.governance import pricing_control as pc

    ipv, trade = tables.get("mkt_ipv"), tables.get("mkt_trade")
    obs: list[dict] = []
    if ipv is not None and len(ipv) and trade is not None and len(trade):
        merged = ipv.merge(trade[["trade_id", "notional"]], on="trade_id",
                           how="left")
        notional = merged["notional"].astype(float)
        verified = merged["verified"].astype(bool)
        total = float(notional.sum())
        if total > 0:
            obs.append({"desk": "금리", "control_id": "PC-IPV", "verdict": None,
                        "metric_value": float(notional[verified].sum()) / total,
                        "evidence_ref": "mkt_ipv · mkt_trade"})
        obs.append({"desk": "금리", "control_id": "PC-SRC", "verdict": None,
                    "metric_value": float(verified.mean()),
                    "evidence_ref": "mkt_ipv.verified"})
    from risk_lib import archive
    obs.append(pc.observation_from_rollback(
        archive.scan(), desk="금리", evidence_ref="archive.scan()"))
    return pc.build_pricing_control(obs, asof=asof, desks=["금리"])


# ---------------------------------------------------------------- 실행 통제 원장

def materialize_run_control(result, tables: dict[str, pd.DataFrame], *,
                            run_id: str) -> dict[str, pd.DataFrame]:
    """조립이 끝난 뒤의 실행 통제 원장.

    마감·감사체인·보존·통합 실행·AI 추적은 "이 실행이 무엇을 실었는가"를
    입력으로 쓴다. 조립 중간에 부르면 아직 서지 않은 원장이 빠진 채로 판정이
    나가고, 그 판정은 실행이 끝난 뒤의 사실과 다르다.
    """
    asof, seed = _asof(result), _seed(result)
    out: dict[str, pd.DataFrame] = {}

    from risk_lib.aig.trace import build_redaction_rules, build_trace_from_activity
    from risk_lib.close_workflow import build_close_workflow
    from risk_lib.governance.audit_chain import build_audit_chain
    from risk_lib.governance.rbac import build_rbac
    from risk_lib.governance.retention import build_retention
    from risk_lib.governance.unified_run import build_unified_run

    # RBAC은 감사체인보다 먼저다. 체인이 접근판정(`gov_access_decision`)을
    # 사건으로 모으므로 뒤에 두면 그 사건이 빠진 체인이 나간다.
    out.update(build_rbac(asof=asof))

    close_t, _issues = build_close_workflow(tables, asof=asof)
    out.update(close_t)

    chain, _notes = build_audit_chain({**tables, **out}, asof=asof)
    out["gov_audit_chain"] = chain

    ret_t, _skipped = build_retention({**tables, **out}, run_id=run_id,
                                      asof=asof)
    out.update(ret_t)

    # 코드 판은 저장소의 사실이다. 읽지 못하면 지어내지 않고 '미확인'을 적는다.
    from risk_lib.repro import _git_commit
    run_t, _problems = build_unified_run(
        {**tables, **out}, run_id=run_id, asof=asof, seed=seed,
        code_revision=_git_commit() or "미확인")
    out.update(run_t)

    rules = build_redaction_rules()
    out["aig_redaction_rule"] = rules
    activity = tables.get("agent_activity")
    if activity is not None and len(activity):
        out["aig_agent_trace"] = build_trace_from_activity(
            activity, rules, asof=asof, run_id=run_id)
    return out
