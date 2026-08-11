"""에이전틱 UI 스튜디오 렌더러. 자체 완결 단일 HTML.

외부 CDN·폰트·스크립트를 쓰지 않는다(폐쇄망 전제). 데이터는 Studio 스냅샷을
JSON으로 인라인하고, 화면은 그 JSON만 읽는다. 화면과 원장이 갈라질 여지를
없애기 위해서다. 미리보기 행 수는 상한을 두되 **모집단 건수는 그대로 표시**한다.
"""

from __future__ import annotations

import html
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from risk_lib.datamodel import catalog as cat
from risk_lib import commercial as _com
from risk_lib.ui_studio import i18n as _i18n
from risk_lib.ui_studio.req_trace import build_trace as _req_rows
from risk_lib.ui_studio.req_trace import coverage as _req_coverage
from risk_lib.ui_studio.studio import DEMO_PROMPTS, DEMO_QUERIES, Studio

PREVIEW_ROWS = 12

# 화면 안에서 조회·필터를 실제로 돌리기 위한 행 예산. 시연 대상 테이블은
# 넉넉히, 나머지는 미리보기 수준으로만 싣는다.
INTERACTIVE_ROWS = 200
INTERACTIVE_ROWS_DEMO = 3000
DEMO_TABLES = (
    "rdm_asset_quality", "rdm_exposure", "rdm_exposure_balance",
    "rwa_sa_bucket", "rwa_irb_pool", "ecl_result", "crm_ews_signal",
    "alm_lcr_item", "alm_nsfr_item", "mkt_ipv", "opr_loss_event",
    "reg_form_line", "st_capital_path", "st_calc_trace",
    "pru_balance_sheet", "pru_income_statement", "pru_liquidity_ratio",
    "pru_ownership_limit", "pru_camel", "pru_prompt_action",
    # 백테스트 예외 달력은 250 영업일 전체가 있어야 그림이 된다. 200행에서
    # 자르면 달력의 마지막 두 달이 비는데, 그 공백을 예외가 없는 구간으로 오독할 수 있다.
    "mkt_backtest_exception",
    # 코드 마스터는 정렬 기준 원장이다. 잘리면 그 코드셋의 정렬 순서가 어긋나,
    # 어떤 화면은 맞고 어떤 화면은 틀리는 최악의 상태가 된다.
    "rdm_code_master",
)

# ALM 화면이 **집계해서 그리는** 원장. 사다리·워터폴·소진경로는 버킷/일자
# 전체가 있어야 성립한다. 표본으로 그리면 빠진 구간이 "잔액 없음"으로 읽히고,
# 시나리오 축이 잘리면 최악 시나리오가 아예 화면에서 사라진다.
# (tests/test_ui_alm.py 가 이 목록이 전량 실렸는지 고정한다)
ALM_FULL_TABLES = (
    "alm_time_bucket", "alm_product_terms", "alm_behaviour_param",
    "alm_prepay_scurve_param", "alm_behaviour_scenario_mult", "alm_nmd_param",
    "alm_cashflow_bucket", "alm_rate_shock_param", "alm_scenario_def",
    "alm_post_shock_floor", "alm_irrbb_result", "alm_irrbb_bucket_pv",
    "alm_nii_result", "alm_lcr_factor", "alm_lcr_flow", "alm_nsfr_factor",
    "alm_nsfr_item", "alm_maturity_ladder", "alm_liquidity_stress_param",
    "alm_survival_path", "alm_result",
)

# 신규 화면(국내 금리리스크·내부등급법 추정·행동모형·거액익스포져·실측검증)이
# **집계해서 그리는** 원장. 200행 상한에 걸리면 등급·범주 축이 잘려 없는 등급이
# 생기고, 잘렸다는 사실은 집계 결과에 남지 않는다. 여기 적힌 것만 전량 싣는다.
NEW_SCREEN_FULL_TABLES = (
    # 별표 9-1 국내 금리리스크
    "alm_repricing_gap", "kr_nmd_category", "kr_retail_criteria",
    "kr_retail_behavioural_scope", "kr_irrbb_governance", "kr_auto_option_param",
    "disc_irrbb_table6", "disc_irrbb_table7_qualitative",
    "disc_irrbb_table7_quantitative",
    # 고객행동모형 추정
    "alm_behaviour_model", "alm_behaviour_backtest", "alm_prepay_observation",
    "alm_early_redemption_observation", "alm_nmd_balance_history",
    "alm_nmd_core_method_compare",
    # 내부등급법 추정
    "crm_pd_estimate", "crm_pd_yearly_dr", "crm_lgd_estimate",
    "crm_ccf_estimate", "crm_defaulted_lgd", "crm_moc_component",
    "crm_input_floor", "crm_estimation_run", "crm_estimation_param",
    "crm_model_governance", "crm_backtest_result", "crm_backtest_criteria",
    "crm_lgd_backtest", "crm_ccf_backtest", "crm_representativeness",
    "crm_dev_sample", "crm_lgd_discount_rate", "crm_irb_scope",
    "crm_default_observation", "crm_sample_representativeness",
    # 회수 할인율(CAPM)·부도자산 LGD(BEEL 곡선·PLGD). 관측 산점과 경과월 곡선은
    # 축 전체가 있어야 그림이 된다. 뒤쪽 관측월이 잘리면 그 공백이 관측이 없는
    # 구간으로 읽힌다.
    "crm_capm_observation", "crm_capm_estimate",
    "crm_beel_curve", "crm_plgd", "crm_plgd_sensitivity",
    # 거액익스포져 (position·measure·group 은 만 행대라 _lex_dict 가 집계한다)
    "lex_setting", "lex_aggregate", "lex_exemption", "lex_lookthrough",
    "lex_substitution",
    # 한도 정의
    "lim_limit_definition",
)

_ENGINE_JS = (Path(__file__).with_name("engine.js")).read_text(encoding="utf-8")


# ---------------------------------------------------------------- 직렬화

def _cell(v):
    if v is None:
        return None
    # numpy 스칼라(np.bool_ · np.int64 · np.float64)는 파이썬 bool·int·float가
    # 아니다. 그대로 두면 아래 isinstance 검사를 빠져나가 str(v)가 되고,
    # 불리언 컬럼이 'False' **문자열**로 실린다. 자바스크립트에서 비어 있지 않은
    # 문자열은 참이므로 화면의 판정이 통째로 뒤집힌다(아웃라이어 판정 6건이
    # 전부 통과로 나오고 있었다). 파이썬 값으로 먼저 되돌린다.
    if isinstance(v, np.generic):
        v = v.item()
        if v is None:
            return None
    if isinstance(v, float):
        return None if math.isnan(v) else v
    if isinstance(v, (int, bool, str)):
        return v
    if v is pd.NA or (hasattr(pd, "isna") and not isinstance(v, (list, tuple))
                      and pd.isna(v)):
        return None
    return str(v)


# 컬럼 표시명은 **카탈로그(ColumnSpec.korean)가 정본**이다. 화면에서 따로
# 지으면 두 벌이 갈라진다. 같은 물리명이 테이블마다 다른 업무 명칭을 갖는
# 컬럼이 50종 있으므로(예: ead → EAD/익스포저, status → 게이트 상태/매핑 상태)
# 전역 사전이 아니라 테이블별로 푼다.
_SPEC_BY_NAME = {sp.name: sp for sp in cat.ALL_TABLES}


def _labels(table: str | None, columns: list[str]) -> list[str | None]:
    sp = _SPEC_BY_NAME.get(table or "")
    m = {c.name: (c.korean or None) for c in sp.columns} if sp else {}
    return [m.get(c) for c in columns]


def _frame(df: pd.DataFrame, limit: int = PREVIEW_ROWS,
           table: str | None = None,
           labels: dict[str, str] | None = None) -> dict:
    head = df.head(limit)
    cols = [str(c) for c in df.columns]
    return {
        "table": table,
        "columns": cols,
        "labels": ([labels.get(c) for c in cols] if labels
                   else _labels(table, cols)),
        "rows": [[_cell(v) for v in row] for row in head.itertuples(index=False)],
        "total": int(len(df)),
        "shown": int(len(head)),
    }


def _adj_frame(s: Studio) -> pd.DataFrame:
    from risk_lib.adjustments import demo_ledger
    led = demo_ledger(s.result, asof=s.asof)
    return pd.DataFrame([{
        "adjustment_id": a.adjustment_id, "figure_id": a.figure_id,
        "label": a.label, "base_value": a.base_value,
        "adjusted_value": a.adjusted_value, "delta": a.delta,
        "reason": a.reason, "evidence_ref": a.evidence_ref,
        "requester": a.requester, "approver": a.approver,
        "expires_on": a.expires_on, "status": a.status,
    } for a in led.adjustments])


def _reverse_dict(s: Studio) -> dict:
    r = s.result.reverse_stress
    return {
        "metric": r.metric, "target_ratio": r.target_ratio,
        "base_ratio": r.base_ratio, "critical_severity": r.critical_severity,
        "resilient": bool(r.resilient), "converged": bool(r.converged),
        "ratio_at_break": r.ratio_at_break,
        "rwa_at_break": r.rwa_total_at_break, "ecl_at_break": r.ecl_at_break,
        "implied_gdp_shock": r.implied_gdp_shock,
        "implied_lgd_addon": r.implied_lgd_addon,
    }


def _executive_dict(s: Studio) -> dict:
    """경영진 요약 화면의 데이터. `02_reports/executive.html`과 **같은 엔진**.

    `html_exec`의 사실·브리핑·KRI·액션 생성기를 그대로 호출한다. 화면이 자기
    나름대로 다시 계산하면 같은 원장을 두 화면이 각자 그리는 상태가 되고,
    어느 쪽이 맞는지 확인해야 하는 상태가 된다.

    HTML 리포트는 이 dict에 서식을 입힌 것이고, 이 화면은 같은 dict를 브라우저에서
    그린다. 두 산출물의 수치가 갈라질 자리가 없다.
    """
    from risk_lib.html_exec import (
        _cro_briefing, _kri_card_data, _top_actions, briefing_facts,
    )

    r = s.result
    seed = int(r.meta.get("seed", 42))
    facts = briefing_facts(r)
    return {
        "facts": facts,
        "briefing": list(_cro_briefing(r)),
        "kris": _kri_card_data(r.raf, seed=seed),
        # RWA 귀속. 리포트 ops/23 이 그리는 것과 같은 산출이다.
        "attribution": [
            {"component": str(x["component"]), "rwa": float(x["rwa"]),
             "share": float(x["share"])}
            for _, x in r.attribution["rwa_components"].iterrows()],
        "actions": list(_top_actions(r, max_actions=5)),
        "source": "risk_lib.html_exec (02_reports/executive.html 과 동일 산출)",
    }


# 이탈 경보 임계. 계열 자기 표준편차의 배수. 산출과 화면 문구가 같은 값을
# 봐야 하므로 여기서 정하고 엔진에 넘긴다.
MACRO_Z = 1.5


def _macro_dict(s: Studio) -> dict:
    """거시·금융지표 모니터링 화면 데이터. 전량 `risk_lib.macro_monitor` 산출.

    최근값·경보·충격 배수를 화면에서 다시 구하지 않도록 여기서 엔진 함수로
    풀어 싣는다. 같은 원장을 화면이 따로 집계하면 어느 쪽이 그 지표의 현재값인지
    사후에 물어야 한다.
    """
    from risk_lib import macro_monitor as mm

    obs, link = s.tables["macro_indicator"], s.tables["macro_scenario_link"]
    # 지표 정의와 시나리오 충격 배수는 **마스터 원장**에서 읽는다. 모듈 상수
    # (INDICATORS · SCENARIO_SHOCK)는 원장으로 옮겨졌고 파생 뷰로만 남아 있어,
    # 그쪽을 읽으면 원장을 고쳐도 화면이 옛 값을 그린다.
    master = s.tables["rdm_macro_indicator_master"]
    shock = s.tables["st_macro_scenario_shock"]
    specs = mm.indicator_specs(master)
    spec = {sp.indicator_id: sp for sp in specs}
    smap = mm.scenario_shock_map(shock)
    lat = mm.latest_observations(obs).set_index("indicator_id")
    keys = ("name", "category", "source", "source_code", "period", "freq",
            "value", "unit", "yoy", "basis")
    return {
        "observations": _frame(obs, 10_000, table="macro_indicator"),
        # 지표 순서는 마스터 원장의 행 순서다. 부문이 이어져 나오도록 원장이
        # 정렬돼 있으므로 화면에서 다시 정렬하지 않는다.
        "latest": [
            {"indicator_id": sp.indicator_id, "drives": sp.drives,
             **{k: _cell(lat.loc[sp.indicator_id, k]) for k in keys}}
            for sp in specs if sp.indicator_id in lat.index],
        "alerts": mm.alerts(obs, z_threshold=MACRO_Z),
        "z_threshold": MACRO_Z,
        # 마스터 원장의 승인·근거 상태. 지표 정의가 수기입력 원장이므로
        # 승인란이 비어 있는지가 화면에 보여야 한다.
        "master": _frame(master, 100, table="rdm_macro_indicator_master"),
        # 충격폭은 지표마다 단위가 다르다. 비교하려면 엔진이 쓴 표준편차 배수가
        # 있어야 하므로 충격 원장 값을 그대로 붙인다. 배수가 원장에 없으면
        # 0으로 채우지 않고 비운다.
        "links": [
            {**{k: _cell(v) for k, v in r.items()},
             "unit": spec[r["indicator_id"]].unit if r["indicator_id"] in spec else "",
             "sigma": smap.get(str(r["scenario"]), {}).get(
                 str(r["indicator_id"]))}
            for _, r in link.iterrows()],
        "basis_mix": {str(k): int(v)
                      for k, v in obs["basis"].value_counts().items()},
    }


def _alm_dict(s: Studio) -> dict:
    """ALM 화면 보조 집계. 화면에 전량을 실을 수 없는 원장 하나뿐이다.

    행동조정 현금흐름은 계약 단위라 1만 행을 넘는다. 화면에 표본 200행만 싣고
    거기서 행동모형별 기여도를 집계하면 기여도가 표본 크기의 함수가 되는데,
    그 사실은 화면에 드러나지 않는다. 그래서 여기서 **원장 전량**을 시나리오 ×
    모형 축으로 합치고 모집단 행수·계약수를 함께 남긴다. 새 수치를 만드는
    것이 아니라 `adjustment_cf`(= 행동 − 계약)를 그대로 더한다.
    """
    b = s.tables.get("alm_cashflow_behavioural")
    if not isinstance(b, pd.DataFrame) or b.empty:
        return {}
    g = (b.groupby(["scenario", "behaviour_model"], as_index=False)
         .agg(adjustment_cf=("adjustment_cf", "sum"),
              principal_cf=("principal_cf", "sum"),
              n_contracts=("contract_id", "nunique"),
              n_rows=("contract_id", "size")))
    return {
        "behaviour_contrib": _frame(g, 10_000, labels={
            "scenario": "시나리오", "behaviour_model": "행동모형",
            "adjustment_cf": "행동조정액 (행동 − 계약)",
            "principal_cf": "행동조정 후 원금흐름",
            "n_contracts": "대상 계약수", "n_rows": "원장 행수"}),
        "behaviour_source": "alm_cashflow_behavioural",
        "behaviour_rows": int(len(b)),
        "behaviour_contracts": int(b["contract_id"].nunique()),
    }


def _sim_dict(s: Studio) -> dict:
    """자본비율 시뮬레이션의 기준값. 전부 파이프라인 산출을 그대로 옮긴다.

    화면이 항등식으로 RWA 총액을 역산하면 구성요소를 나눌 수 없고, 역산값과
    엔진의 `rwa` 산출이 갈라져도 화면에서는 보이지 않는다. 구성요소·자본계층·
    버퍼·레버리지·연동 한도를 여기서 한 벌로 싣고, 화면은 그 값에 사용자가 준
    증감을 더해 비율을 다시 계산할 뿐이다.
    """
    from risk_lib.capital.bis import BIS_MINIMUMS

    r = s.result
    rw = r.rwa
    cap = r.meta["capital"]
    fl = rw["output_floor"]
    ic = r.icaap
    lev = r.leverage
    # 구성요소 라벨은 여기서 정하되 값은 전부 엔진 산출이다. 합계가
    # internal_total 과 맞는지는 tests/test_ui_interactive.py 가 고정한다.
    comps = [
        ("sa", "신용 표준방법"), ("irb", "신용 내부등급법"),
        ("ccr", "거래상대방(CCR)"), ("fund", "집합투자증권"),
        ("securitisation", "유동화"), ("market", "시장리스크"),
        ("op", "운영리스크"),
    ]
    lim = s.tables.get("lim_limit_definition")
    obligor = None
    if isinstance(lim, pd.DataFrame) and len(lim):
        sub = lim[lim["threshold_unit"] == "ratio_tier1"]
        if len(sub):
            row = sub.iloc[0]
            obligor = {
                "limit_id": str(row["limit_id"]),
                "threshold_value": _cell(row["threshold_value"]),
                "threshold_formula": str(row["threshold_formula"]),
                "citation": str(row["citation"]),
                "evidence_status": str(row["evidence_status"]),
            }
    irrbb = None
    ir = s.tables.get("alm_irrbb_result")
    if isinstance(ir, pd.DataFrame) and len(ir):
        w = ir[ir["is_worst"]]
        w = w.iloc[0] if len(w) else ir.iloc[0]
        irrbb = {
            "basis": str(w["basis"]), "scenario": str(w["scenario"]),
            "delta_eve": _cell(w["delta_eve"]), "tier1": _cell(w["tier1"]),
            "ratio": _cell(w["delta_eve_to_tier1"]),
            "outlier_test_pass": bool(w["outlier_test_pass"]),
            "framework_version": str(w["framework_version"]),
        }
    return {
        # 산출에 없는 구성요소는 0으로 채우지 않고 뺀다. 0으로 채우면 그
        # 구성요소가 없다는 뜻과 값이 0이라는 뜻이 한 줄에서 섞인다.
        "components": [{"key": k, "label": lab, "value": float(rw[k])}
                       for k, lab in comps if k in rw],
        "internal_total": float(rw["internal_total"]),
        "standardised_total": float(rw["standardised_total"]),
        "floor_pct": float(fl.floor),
        "floor_amount": float(fl.floor_amount),
        "add_on": float(fl.add_on),
        "binding": bool(fl.is_binding),
        "final_total": float(rw["final_total"]),
        "capital": {"cet1": float(cap.cet1), "at1": float(cap.additional_t1),
                    "t2": float(cap.tier2)},
        "minimums": {k: float(v) for k, v in BIS_MINIMUMS.items()},
        "buffers": {k: float(v) for k, v in r.meta["buffers"].items()},
        "required": {k: float(v) for k, v in r.bis.required.items()},
        "leverage": {"exposure_measure": float(lev.exposure_measure),
                     "required": float(lev.required),
                     "ratio": float(lev.leverage_ratio)},
        "icaap": {"available_capital": float(ic.available_capital),
                  "ec": float(ic.ec_diversified),
                  "buffer": float(ic.buffer),
                  "utilisation": float(ic.utilisation)},
        "single_obligor": obligor,
        "irrbb": irrbb,
    }


def _lex_dict(s: Studio) -> dict:
    """거액익스포져 화면의 집계. 포지션 원장이 8천 행대라 화면에 전량을 실을 수 없다.

    상위 순위·보고대상·소진 분포를 표본 200행에서 집계하면 순위가 표본의
    함수가 된다. 여기서 **원장 전량**을 체계별로 집계하고 모집단 행수를 함께
    남긴다. 새 값을 만들지 않으며 원장 컬럼을 고르고 더할 뿐이다.
    """
    pos = s.tables.get("lex_position")
    if not isinstance(pos, pd.DataFrame) or pos.empty:
        return {}
    keep = ["framework", "group_id", "aggregation_unit", "n_members",
            "denominator_basis", "denominator_amount", "exposure_pre_crm",
            "exposure_measured", "exposure_exempt", "exposure_included",
            "ratio", "counterparty_class", "limit_pct", "limit_amount",
            "utilisation", "headroom", "reportable", "reportable_pre_crm",
            "breach", "limit_citation", "measure_evidence_status"]
    frameworks: list[dict] = []
    tops: dict[str, dict] = {}
    for fw, g in pos.groupby("framework", sort=True):
        g = g.sort_values("utilisation", ascending=False)
        # 소진율 분포는 10%p 폭으로 센다. 경계는 [lo, hi) 이고 마지막 칸만
        # 상한이 열려 있다. 위반은 100% 이상 칸에 들어간다.
        edges = [0.0, 0.25, 0.5, 0.75, 0.9, 1.0]
        hist = []
        for k, lo in enumerate(edges):
            hi = edges[k + 1] if k + 1 < len(edges) else None
            n = int(((g["utilisation"] >= lo) & (
                (g["utilisation"] < hi) if hi is not None else True)).sum())
            hist.append({"lower": lo, "upper": hi, "n": n})
        frameworks.append({
            "framework": str(fw),
            "aggregation_unit": str(g["aggregation_unit"].iloc[0]),
            "denominator_basis": str(g["denominator_basis"].iloc[0]),
            "denominator_amount": _cell(g["denominator_amount"].iloc[0]),
            "limit_pct": _cell(g["limit_pct"].iloc[0]),
            "limit_amount": _cell(g["limit_amount"].iloc[0]),
            "limit_citation": str(g["limit_citation"].iloc[0]),
            "n_positions": int(len(g)),
            "n_reportable": int(g["reportable"].sum()),
            "n_reportable_pre_crm": int(g["reportable_pre_crm"].sum()),
            "n_breach": int(g["breach"].sum()),
            "sum_included": float(g["exposure_included"].sum()),
            "sum_exempt": float(g["exposure_exempt"].sum()),
            "histogram": hist,
        })
        tops[str(fw)] = _frame(g.head(15)[keep], 15, table="lex_position")
    # 대체(substitution)로 보장제공자에게 옮겨 붙은 금액. 그 제공자의 포지션이
    # 한도를 넘었는지는 포지션 원장의 breach 컬럼에서 읽는다.
    prov = []
    sub = s.tables.get("lex_substitution")
    if isinstance(sub, pd.DataFrame) and len(sub):
        agg = (sub.groupby("protection_provider_id", as_index=False)
               .agg(substituted_in=("provider_recognised_amount", "sum"),
                    n_links=("original_counterparty_id", "size")))
        agg = agg[agg["substituted_in"] > 0].sort_values(
            "substituted_in", ascending=False).head(15)
        bygrp = pos.set_index(["framework", "group_id"])
        for _, x in agg.iterrows():
            cid = str(x["protection_provider_id"])
            hit = pos[pos["group_id"].astype(str).str.contains(cid, regex=False)]
            prov.append({
                "provider": cid,
                "substituted_in": float(x["substituted_in"]),
                "n_links": int(x["n_links"]),
                "breach": bool(hit["breach"].any()) if len(hit) else None,
                "max_utilisation": (float(hit["utilisation"].max())
                                    if len(hit) else None),
            })
        del bygrp
    grp = s.tables.get("lex_connected_group")
    groups = {}
    if isinstance(grp, pd.DataFrame) and len(grp):
        basis = (grp.groupby("connection_basis", as_index=False)
                 .agg(n=("counterparty_id", "size")))
        top = (grp[grp["n_members"] > 1]
               .drop_duplicates("group_id")
               .sort_values("n_members", ascending=False).head(12))
        groups = {
            "basis": [{"basis": str(b), "n": int(n)}
                      for b, n in basis.itertuples(index=False)],
            "n_groups": int(grp["group_id"].nunique()),
            "n_multi": int((grp.drop_duplicates("group_id")["n_members"] > 1).sum()),
            "n_review": int(grp["interdep_review_required"].sum()),
            "top": _frame(top[["group_id", "n_members", "connection_basis",
                               "basis_detail", "basis_metric", "linked_to"]],
                          12, table="lex_connected_group"),
        }
    meas = s.tables.get("lex_exposure_measure")
    measure = []
    if isinstance(meas, pd.DataFrame) and len(meas):
        m = (meas.groupby("exposure_type", as_index=False)
             .agg(measured=("measured_amount", "sum"),
                  gross=("gross_amount", "sum"),
                  n=("counterparty_id", "size"))
             .sort_values("measured", ascending=False))
        measure = [{"exposure_type": str(x["exposure_type"]),
                    "measured": float(x["measured"]),
                    "gross": float(x["gross"]), "n": int(x["n"])}
                   for _, x in m.iterrows()]
    return {
        "frameworks": frameworks, "top": tops, "providers": prov,
        "groups": groups, "measure": measure,
        "n_positions": int(len(pos)),
    }


def _irb_dict(s: Studio) -> dict:
    """내부등급법 추정 화면의 집계. 회수이력이 6천 행대라 화면에 전량을 실을 수 없다.

    회수곡선은 부도 후 경과월별 누적회수율이므로 관측 전량이 있어야 곡선이
    된다. 표본으로 그리면 뒤쪽 경과월이 통째로 빠지고, 그 공백은 회수가 끝난
    것으로 읽힌다. 여기서 원장 전량을 경과월 축으로 합친다.
    """
    out: dict = {}
    rec = s.tables.get("crm_recovery_history")
    if isinstance(rec, pd.DataFrame) and len(rec):
        ead = (rec.drop_duplicates("default_id")
               .groupby("segment", as_index=False)
               .agg(ead=("ead_at_default", "sum")))
        base = dict(ead.itertuples(index=False))
        rows = []
        for seg, g in rec.groupby("segment", sort=True):
            tot = float(base.get(seg, 0.0)) or 1.0
            cum = 0.0
            for m, gm in g.groupby("months_since_default", sort=True):
                net = float((gm["recovery_amount"] - gm["direct_cost"]
                             - gm["indirect_cost"]).sum())
                cum += net
                rows.append({"segment": str(seg), "month": int(m),
                             "cum_recovery_rate": cum / tot,
                             "net_amount": net})
        out["recovery_curve"] = rows
        out["recovery_rows"] = int(len(rec))
        out["recovery_defaults"] = int(rec["default_id"].nunique())
    obs = s.tables.get("crm_default_observation")
    if isinstance(obs, pd.DataFrame) and len(obs):
        cens = (obs.groupby(["segment", "censoring_status"], as_index=False)
                .agg(n=("exposure_id", "size"),
                     ead=("ead_at_default", "sum")))
        out["censoring"] = [{"segment": str(x["segment"]),
                             "status": str(x["censoring_status"]),
                             "n": int(x["n"]), "ead": float(x["ead"])}
                            for _, x in cens.iterrows()]
    return out


def _kpis(s: Studio) -> list[dict]:
    r = s.result
    t = s.tables
    aq = t["rdm_asset_quality"]
    npl = float(aq[aq["classification"].isin(("고정", "회수의문", "추정손실"))]
                ["balance"].sum())
    bal = float(aq["balance"].sum()) or 1.0
    checks = t["val_check"]
    n_fail = int((checks["status"] == "FAIL").sum())
    n_warn = int((checks["status"] == "WARN").sum())
    reg_checks = t["reg_form_check"]
    trough = r.stress_path_trough
    sev = trough[trough["scenario"] == "severely_adverse"]
    # 콕핏의 자본 신호는 **제약이 되는 계층**을 따른다. CET1만 보고 판정하면
    # CET1이 요구를 넘는 동안 기본자본·총자본이 완충자본을 밑돌아도 화면이
    # 초록으로 남는다. 배당·성과급이 제한되는 상태를 "양호"라고 읽게 된다.
    _KO_TIER = {"cet1": "보통주자본", "tier1": "기본자본", "total": "총자본"}
    _short = {k: v for k, v in r.bis.surplus_shortfall.items() if v < 0}
    _bind = min(r.bis.surplus_shortfall, key=r.bis.surplus_shortfall.get)
    return [
        {"label": "보통주자본비율 (CET1)", "value": f"{r.bis.cet1_ratio:.2%}",
         "sub": (f"요구 {r.bis.required['cet1']:.2%} · 여유 "
                 f"{r.bis.surplus_shortfall['cet1']*100:+.2f}%p"
                 + (f" · 제약 {_KO_TIER[_bind]} "
                    f"{r.bis.surplus_shortfall[_bind]*100:+.2f}%p "
                    f"(완충자본 미달 {len(_short)}종, 배당·성과급 제한)"
                    if _short else " · 전 계층 요구 충족")),
         "tone": "bad" if _short else "good",
         "lineage": "BR-01 / 3100"},
        {"label": "위기상황 CET1 저점",
         "value": f"{float(sev['trough_cet1'].iloc[0]):.2%}" if len(sev) else "-",
         "sub": f"심각 시나리오 · {sev['trough_quarter'].iloc[0]}" if len(sev) else "",
         "tone": "warn" if len(sev) and not bool(sev["passes_all"].iloc[0]) else "good",
         "lineage": "BR-14 / 2300"},
        {"label": "기대신용손실 (ECL)",
         "value": f"{float(r.ecl['total'])/1e8:,.0f}억원",
         "sub": f"고정이하여신비율 {npl/bal:.2%}",
         "tone": "neutral", "lineage": "BR-11 / 2000"},
        {"label": "유동성커버리지비율 (LCR)",
         "value": f"{float(r.alm['lcr'].lcr):.1%}",
         "sub": f"NSFR {float(r.alm['nsfr'].nsfr):.1%} · 최저 100%",
         "tone": "good" if r.alm["lcr"].lcr >= 1.0 else "bad",
         "lineage": "BR-08 / 5000"},
        {"label": "자체검증", "value": f"FAIL {n_fail} · WARN {n_warn}",
         "sub": f"총 {len(checks)}건", "tone": "good" if n_fail == 0 else "bad",
         "lineage": "val_check"},
        {"label": "업무보고서 대사",
         "value": f"{int((reg_checks['status']=='PASS').sum())}/{len(reg_checks)}",
         "sub": f"서식 {len(t['reg_form'])}장 · 라인 {len(t['reg_form_line'])}행",
         "tone": "good" if not int((reg_checks["status"] == "FAIL").sum()) else "bad",
         "lineage": "reg_form_check"},
    ]


def _payload(s: Studio) -> dict:
    t = s.tables
    spec_by_name = {sp.name: sp for sp in cat.ALL_TABLES}

    catalog_rows = []
    for sp in cat.ALL_TABLES:
        df = t.get(sp.name)
        catalog_rows.append({
            "name": sp.name, "korean": sp.korean, "product": sp.product,
            "grain": sp.grain, "columns": len(sp.columns),
            "pk": ", ".join(sp.primary_key) or "-",
            "fk": len(sp.foreign_keys),
            "rows": int(len(df)) if isinstance(df, pd.DataFrame) else 0,
            "materialised": isinstance(df, pd.DataFrame),
        })

    previews = {name: _frame(df, table=name) for name, df in t.items()
                if isinstance(df, pd.DataFrame) and name in spec_by_name}

    # ---- 브라우저에서 실제로 조회·필터가 돌아가려면 데이터가 화면 안에
    # 있어야 한다. 전량을 실으면 파일이 감당이 안 되므로 상한을 두되,
    # **모집단 건수를 함께 남겨** 잘린 사실이 화면에 드러나게 한다.
    views_meta, data = {}, {}
    fp = t["ui_field_policy"]
    policy_by_view: dict[str, list[dict]] = {}
    for _, r in fp.iterrows():
        policy_by_view.setdefault(str(r["view_id"]), []).append({
            "field_name": str(r["field_name"]), "korean": str(r["korean"]),
            "permitted": bool(r["permitted"]), "masking": str(r["masking"]),
            "min_aggregation": int(r["min_aggregation"]),
        })
    for _, v in t["ui_view"].iterrows():
        vid = str(v["view_id"])
        tref = v["table_ref"]
        if not isinstance(tref, str) or tref not in t:
            continue
        df = t[tref]
        budget = (INTERACTIVE_ROWS_DEMO
                  if tref in DEMO_TABLES or tref in ALM_FULL_TABLES
                  or tref in NEW_SCREEN_FULL_TABLES
                  else INTERACTIVE_ROWS)
        views_meta[vid] = {
            "view_id": vid, "view_name": str(v["view_name"]),
            "domain": str(v["domain"]), "table_ref": tref,
            "row_limit": int(v["row_limit"]),
            "fields": policy_by_view.get(vid, []),
            "total_rows": int(len(df)), "embedded_rows": int(min(len(df), budget)),
        }
        if tref not in data:
            data[tref] = _frame(df, budget, table=tref)

    plans = []
    for p in s.plans:
        res = s.plan_results.get(p.plan_id, pd.DataFrame())
        _vrow = s.view_row(p.view_id)
        _tref = str(_vrow["table_ref"]) if _vrow is not None else None
        plans.append({
            "plan_id": p.plan_id, "view_id": p.view_id, "intent": p.intent,
            "utterance": p.utterance, "population": p.population,
            "ast": p.condition_ast, "policy": p.policy, "hash": p.query_hash,
            "status": p.status, "block_reason": p.block_reason,
            "n_rows": p.n_rows, "result": _frame(res, 8, table=_tref),
            "steps": [
                ("01 의도", p.intent), ("02 기준일", p.asof),
                ("03 모집단", p.population),
                ("04 조건", " ∧ ".join(c.describe() for c in p.conditions) or "-"),
                ("05 정책", p.policy),
            ],
        })

    proposals = []
    for pr in s.proposals:
        # 승인된 제안만 실제 데이터로 미리보기를 만든다. 거부된 제안이
        # 화면에 그려지면 "거부됐다"는 통제가 무의미해진다.
        preview = {"columns": [], "rows": [], "total": 0, "shown": 0}
        if pr.status == "approved":
            vrow = s.view_row(pr.view_id)
            src = t.get(str(vrow["table_ref"])) if vrow is not None else None
            if isinstance(src, pd.DataFrame) and pr.columns:
                cols = [c for c in pr.columns if c in src.columns]
                sub = src[cols]
                num = next((c for c in cols
                            if pd.api.types.is_numeric_dtype(sub[c])), None)
                if num:
                    sub = sub.sort_values(num, ascending=False)
                preview = _frame(sub, min(pr.row_limit, 10),
                                 table=str(vrow["table_ref"]))
                preview["bar_column"] = num
                # 막대 라벨은 **범주형** 열이어야 한다. 숫자 열을 라벨로 쓰면
                # 축과 값이 같은 종류가 되어 차트가 읽히지 않는다.
                preview["label_column"] = next(
                    (c for c in cols
                     if not pd.api.types.is_numeric_dtype(sub[c])), None)
        proposals.append({
            "proposal_id": pr.proposal_id, "view_id": pr.view_id,
            "prompt": pr.prompt, "layout": pr.layout_text(),
            "blocks": list(pr.blocks), "columns": list(pr.columns),
            "row_limit": pr.row_limit, "status": pr.status,
            "preview": preview,
            "checks": [
                ("필드 권한", pr.field_policy_pass),
                ("스키마·단위", pr.schema_pass),
                ("집계 최소단위", pr.aggregation_pass),
                ("사람 적용승인", pr.status == "approved"),
            ],
            "rejected": list(pr.rejected_fields),
        })

    forms = [{
        "form_id": b.spec.form_id, "form_no": b.spec.form_no_display,
        "official": b.spec.form_no.is_official,
        "form_name": b.spec.form_name,
        "frequency": b.spec.frequency, "citation": b.spec.citation,
        "section": b.spec.section,
        "n_lines": len(b.lines), "n_checks": len(b.checks),
        "n_failed": b.n_failed,
        "lines": [{
            "code": ln.line_code, "name": ln.line_name, "level": ln.level,
            "unit": ln.unit,
            "value": _cell(ln.value) if ln.unit != "text" else ln.text_value,
            "formula": ln.formula or "", "citation": ln.citation or "",
            "module": ln.source_module or "", "subtotal": ln.is_subtotal,
        } for ln in b.lines],
    } for b in s.built_forms]

    return {
        "meta": {
            "asof": s.asof, "run_id": s.run_id, "digest": s.digest,
            "seed": s.result.meta.get("seed", 42),
            "n_tables": len(cat.ALL_TABLES),
            "n_columns": sum(len(sp.columns) for sp in cat.ALL_TABLES),
            "n_rows": int(sum(len(df) for df in t.values()
                              if isinstance(df, pd.DataFrame))),
        },
        "kpis": _kpis(s),
        # 경영진 요약. html_exec와 같은 생성기에서 나온다 (02_reports/executive.html).
        "executive": _executive_dict(s),
        "catalog": catalog_rows,
        "previews": previews,
        "views": _frame(t["ui_view"], 10_000, table="ui_view"),
        "field_policy": _frame(t["ui_field_policy"], 10_000, table="ui_field_policy"),
        "view_meta": views_meta,
        "data": data,
        "demo_queries": [
            {"view_id": v, "utterance": u, "intent": i}
            for v, u, i in DEMO_QUERIES if v in views_meta
        ],
        "demo_prompts": [
            {"view_id": v, "prompt": q}
            for v, q in DEMO_PROMPTS if v in views_meta
        ],
        "plans": plans,
        "proposals": proposals,
        "forms": forms,
        "form_checks": _frame(t["reg_form_check"], 200, table="reg_form_check"),
        "agents": _frame(t["agent_registry"], 100, table="agent_registry"),
        "activity": _frame(t["agent_activity"], 100, table="agent_activity"),
        "killswitch": _frame(t["agent_killswitch"], 50, table="agent_killswitch"),
        "evidence_nodes": _frame(t["gov_evidence_node"], 50, table="gov_evidence_node"),
        "evidence_edges": _frame(t["gov_evidence_edge"], 50, table="gov_evidence_edge"),
        "approvals": _frame(t["gov_approval"], 100, table="gov_approval"),
        "changes": _frame(t["chg_change_request"], 50, table="chg_change_request"),
        "change_impacts": _frame(t["chg_impact_map"], 200, table="chg_impact_map"),
        "change_tests": _frame(t["chg_regression_test"], 100, table="chg_regression_test"),
        "reconciliation": _frame(t["rdm_reconciliation"], 50, table="rdm_reconciliation"),
        "contracts": _frame(t["rdm_source_contract"], 50, table="rdm_source_contract"),
        "canonical_map": _frame(t["rdm_canonical_map"], 200, table="rdm_canonical_map"),
        "validation": _frame(t["val_check"], 400, table="val_check"),
        "independent": {
            "status": str(t["val_independent_request"]["status"].iloc[0]),
            "reason": str(t["val_independent_request"]["reason"].iloc[0]),
            "request_id": str(t["val_independent_request"]["request_id"].iloc[0]),
            "requested_to": str(t["val_independent_request"]["requested_to"].iloc[0]),
            "branch": str(t["val_independent_request"]["branch"].iloc[0]),
            "n_targets": int(t["val_independent_request"]["n_recalc_targets"].iloc[0]),
            "self_validation": " · ".join(
                f"{k} {v}" for k, v in sorted(
                    (s.iv_request.self_validation if s.iv_request else {}).items())),
            "assumptions": list(s.iv_request.known_assumptions) if s.iv_request else [],
        },
        "independent_targets": _frame(t["val_independent_target"], 50, table="val_independent_target"),
        # v9.6.0 업무요건 추적. 증빙 참조는 tests/test_req_trace.py 가 실재를
        # 검증한다. 여기 실리는 것은 주장 목록이 아니라 검사를 통과한 목록이다.
        "req_trace": {"coverage": _req_coverage(), "rows": _req_rows()},
        # 오버레이(수동조정) 원장. DAT-006. 엔진 산출값을 사람이 덮어쓴
        # 기록이다. 기록 없는 조정은 재현 불가의 시작이므로 전 건이 사유·증빙·
        # 승인·만료를 갖는다.
        "adjustments": _frame(_adj_frame(s), 100, labels={
            "adjustment_id": "조정 식별자", "figure_id": "대상 수치",
            "label": "항목", "base_value": "엔진 산출값",
            "adjusted_value": "조정 후 값", "delta": "조정폭",
            "reason": "사유", "evidence_ref": "증빙 참조",
            "requester": "요청자", "approver": "승인자",
            "expires_on": "만료일", "status": "상태"}),
        # 한도·소진. 다차원 한도 엔진 산출.
        "limits": _frame(s.result.limits, 200, labels={
            "limit": "한도명", "dimension": "차원", "bucket": "구간",
            "exposure": "익스포저", "threshold": "한도액",
            "utilisation": "소진율", "severity": "심각도"}),
        # 한도 소진율 전량. 위반 아닌 버킷까지. 화면이 분포를 보여야 한다.
        "limits_full": _frame(
            s.result.limits_full if s.result.limits_full is not None
            else s.result.limits, 60, labels={
                "limit": "한도명", "dimension": "차원", "bucket": "구간",
                "exposure": "익스포저", "threshold": "한도액",
                "utilisation": "소진율", "severity": "심각도"}),
        # 역스트레스. 자본 임계를 뚫는 심도를 푼다 (BNK-ST-006).
        "reverse_stress": _reverse_dict(s),
        # 거시·금융지표. 시나리오 심도의 입력 원장.
        "macro": _macro_dict(s),
        # ALM. 화면에 전량을 실을 수 없는 행동조정 현금흐름의 축소 집계.
        "alm": _alm_dict(s),
        # 자본비율 시뮬레이션 기준값. RWA 구성·자본계층·버퍼·레버리지·연동 한도.
        "sim": _sim_dict(s),
        # 거액익스포져. 포지션 원장 전량 집계 (화면 탑재분은 표본이다).
        "lex": _lex_dict(s),
        # 내부등급법 추정. 회수이력 전량에서 낸 회수곡선과 관측중단 집계.
        "irb": _irb_dict(s),
        # 사업성(COM). 규제 산출물이 아니다. 제출 지문·독립검증 대상에 넣지
        # 않으며, 전 수치가 가정 원장에서 계산으로만 나온다.
        "commercial": {
            "assumptions": _frame(_com.assumption_frame(), 50, labels={
                "assumption_id": "가정 ID", "description": "설명",
                "value": "값", "unit": "단위"}),
            "quotes": _frame(_com.quote_frame(), 10, labels={
                "package": "패키지", "name": "이름", "scope": "포함 범위",
                "build_cost": "순구축대가", "lifecycle_annual": "Lifecycle(연)",
                "arr": "ARR", "year1_total": "1년차 합계", "tco_3y": "3년 TCO",
                "payback_years": "회수기간(년)"}),
            "roi": _frame(_com.roi_frame(), 10, labels={
                "benefit_id": "편익 ID", "description": "설명",
                "assumption_ref": "출처 가정", "annual_value": "연 편익"}),
            "funnel": _frame(_com.funnel_frame(), 10, labels={
                "stage_id": "단계 ID", "stage": "단계", "exit_criteria": "전환 기준"}),
            "double_counting": _com.check_no_double_counting(),
        },
        "domains": sorted({r["product"] for r in catalog_rows}),
    }


# ---------------------------------------------------------------- HTML

# 팔레트는 두 벌뿐이고, 세 자리(기본·OS 선호·명시 토글)에 같은 값을 쓴다.
# 손으로 세 번 적으면 한 자리만 고치는 날이 온다. 값은 여기 한 번만 둔다.
#
# 색 체계는 RYNTA 브로셔 UI(v9.5.0)의 것을 그대로 쓴다. 딥네이비 바탕에
# **역할 기반** 색: 엔진(결정론적 산출)=파랑, 에이전트(제안)=보라,
# 사람(승인)=앰버, 증빙(계보)=틸. 상태색(ok/watch/danger)과 역할색을
# 상태색과 역할색은 분리한다. 경보색을 장식에 쓰면 경보의 식별력이 떨어진다.
_DARK = {
    "--bg": "#06111d", "--panel": "#0a1928", "--panel2": "#0d2134",
    "--panel3": "#102941", "--line": "rgba(146,188,220,.17)",
    "--text": "#eef7ff", "--muted": "#8ea4b8",
    "--accent": "#42a9ff",            # 엔진 (결정론적 산출)
    "--agent": "#a78bfa",             # 에이전트 (제안 전용)
    "--human": "#f6bb56",             # 사람 (승인 권한)
    "--lineage": "#2dd4bf",           # 증빙 (계보·검증)
    "--good": "#44d19d", "--warn": "#f6bb56", "--bad": "#fb6472",
    "--chip": "rgba(255,255,255,.045)",
    "--on-accent": "#04111b",         # 파랑 위 잉크 (어두운 판은 검정이 선다)
    "--card-grad": "linear-gradient(150deg,#0d2134,rgba(7,20,33,.95))",
    "--shadow": "0 10px 34px rgba(0,0,0,.12)",
}
# 밝은 판은 같은 역할 체계를 종이 위로 옮긴 것이다. 의미색은 채도를 내려야
# 흰 바탕에서 읽히고, 파랑 위 잉크는 흰색이어야 선다.
_LIGHT = {
    **_DARK,
    "--bg": "#f3f7fb", "--panel": "#fff", "--panel2": "#ecf2f8",
    "--panel3": "#e1eaf3", "--line": "#d3dee8",
    "--text": "#14212e", "--muted": "#5c6f81",
    "--accent": "#1264c4", "--agent": "#6d4fd0", "--human": "#8a5a00",
    "--lineage": "#0d7d70",
    "--good": "#177a52", "--warn": "#935f00", "--bad": "#cc2f45",
    "--chip": "#ecf2f8", "--on-accent": "#fff",
    "--card-grad": "linear-gradient(150deg,#fff,#f7fafd)",
    "--shadow": "0 10px 30px rgba(20,45,70,.08)",
}


def _tokens(d: dict[str, str]) -> str:
    return "".join(f"{k}:{v};" for k, v in d.items())


# 뷰어가 테마를 직접 고르는 환경(아티팩트 등)에서는 루트에 data-theme이 찍히고,
# 그 지정이 OS 선호보다 뒤에 와야 두 방향 모두 적용된다.
_PALETTE = f"""
:root{{{_tokens(_DARK)}}}
@media (prefers-color-scheme:light){{:root{{{_tokens(_LIGHT)}}}}}
:root[data-theme="light"]{{{_tokens(_LIGHT)}}}
:root[data-theme="dark"]{{{_tokens(_DARK)}}}
"""

_CSS = _PALETTE + """
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
font:13px/1.5 Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",
"Apple SD Gothic Neo","Noto Sans KR","Malgun Gothic",sans-serif}
a{color:var(--accent)}
.topbar{position:sticky;top:0;z-index:20}
header{background:var(--panel);
border-bottom:1px solid var(--line);padding:11px 20px;min-height:50px;
display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.brand{font-weight:800;font-size:15px;letter-spacing:-.01em}
.brand span{color:var(--accent)}
.hchip{background:var(--chip);border:1px solid var(--line);border-radius:8px;
padding:4px 9px;font-size:10.5px;font-weight:650;letter-spacing:.03em;
color:var(--muted)}
label.hchip{display:inline-flex;align-items:center;gap:5px}
.asofsel{padding:1px 5px;font-size:11px;border-radius:5px}
/* 화면 밝기 토글은 비상정지 버튼 왼쪽에 붙는다. 오른쪽 끝 여백을 이 버튼이
   먼저 차지하고 비상정지가 그 뒤에 온다. */
/* 언어 전환이 밝기 토글 왼쪽에 붙는다. 오른쪽 끝 여백은 둘 중 앞선 것이
   차지한다. */
#langbtn{margin-left:auto}
.theme{background:var(--chip);border:1px solid var(--line);
color:var(--muted);border-radius:8px;padding:5px 11px;font-size:11px;
font-weight:700;letter-spacing:.03em;cursor:pointer;display:inline-flex;
gap:6px;align-items:center}
.theme:hover{border-color:var(--accent);color:var(--text)}
.kill{background:transparent;border:1px solid var(--bad);
color:var(--bad);border-radius:8px;padding:5px 13px;font-size:11px;
font-weight:750;letter-spacing:.03em;cursor:pointer}
.kill.on{background:var(--bad);color:#fff}
.killbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;
padding:10px 20px;background:var(--panel);border-bottom:1px solid var(--bad);
box-shadow:inset 3px 0 0 var(--bad);font-size:11px}
.killbar[hidden]{display:none}
.killbar label{color:var(--bad);font-weight:750}
.killbar input{flex:1 1 320px;min-width:0;background:var(--bg);
color:var(--text);border:1px solid var(--line);border-radius:8px;
padding:6px 10px;font:inherit}
.killbar button{border-radius:8px;padding:6px 12px;font:inherit;cursor:pointer;
border:1px solid var(--line);background:var(--chip);color:var(--text)}
.killbar .killgo{border-color:var(--bad);background:var(--bad);color:#fff}
.killnote{color:var(--muted);flex:1 1 100%}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.layout{display:grid;grid-template-columns:224px minmax(0,1fr);
align-items:start}
nav{position:sticky;top:96px;max-height:calc(100vh - 96px);overflow-y:auto;
display:flex;flex-direction:column;gap:1px;padding:12px 10px 24px;
background:var(--bg);border-right:1px solid var(--line)}
.navgroup{color:var(--text);font-size:10.5px;font-weight:800;
letter-spacing:.08em;padding:7px 8px;margin-top:10px;cursor:pointer;
user-select:none;background:var(--panel2);border:1px solid var(--line);
border-radius:8px}
.navgroup:first-child{margin-top:0}
.navgroup::before{content:'▾ ';color:var(--accent)}
.navgroup.closed::before{content:'▸ ';color:var(--muted)}
nav button{background:transparent;border:none;color:var(--muted);
margin-left:9px;padding:6px 10px 6px 13px;cursor:pointer;font-size:12px;
text-align:left;font-weight:650;font-family:inherit;
border-left:2px solid var(--line);border-radius:0 8px 8px 0}
nav button:hover{color:var(--text);background:var(--chip);
border-left-color:var(--muted)}
nav button.on{background:var(--accent);color:var(--on-accent);
border-left-color:var(--accent);font-weight:750}
nav button[hidden]{display:none}
.navgroup.sub{margin-left:11px;margin-top:4px;font-size:10px;
background:transparent;border:none;border-left:2px solid var(--line);
border-radius:0;color:var(--muted);padding:5px 8px}
nav button.lvl2{margin-left:22px}
nav button.lvl3{margin-left:34px}
main{padding:20px;min-width:0}
@media(max-width:900px){
  .layout{grid-template-columns:1fr}
  nav{position:static;max-height:none;flex-direction:row;flex-wrap:wrap;
  border-right:none;border-bottom:1px solid var(--line)}
  .navgroup{flex:1 1 100%}
}
section{display:none}section.on{display:block}
h2{font-size:24px;line-height:1.15;letter-spacing:-.03em;margin:2px 0 6px}
.lead{color:var(--muted);font-size:12px;margin:0 0 16px;max-width:96ch}
.grid{display:grid;gap:10px;grid-template-columns:repeat(auto-fit,minmax(230px,1fr))}
.card{background:var(--card-grad);border:1px solid var(--line);
border-radius:16px;padding:15px;min-width:0;box-shadow:var(--shadow);
margin:10px 0}
.card .card{box-shadow:none;margin:0}
.card h3{margin:0 0 9px;font-size:13px;font-weight:800;letter-spacing:-.01em}
.kpi .lab{font-size:10.5px;font-weight:700;letter-spacing:.05em;
color:var(--muted)}
.kpi .val{font-size:25px;font-weight:800;letter-spacing:-.02em;margin:6px 0 3px;
font-variant-numeric:tabular-nums}
.kpi .sub{font-size:11px;color:var(--muted)}
.kpi .ln{font-size:10px;color:var(--lineage);font-weight:650;margin-top:7px}
.good{color:var(--good)}.warn{color:var(--warn)}.bad{color:var(--bad)}
.tw{overflow:auto;border:1px solid var(--line);border-radius:11px;margin:10px 0;
max-height:912px}   /* ≈ 30행 + 머리글 (넘치면 그리드 안에서 스크롤) */
table{border-collapse:collapse;width:100%;font-size:11.5px;min-width:520px}
th{background:var(--panel2);color:var(--muted);text-align:left;padding:7px 9px;
font-weight:750;letter-spacing:.02em;border-bottom:1px solid var(--line);
white-space:nowrap;position:sticky;top:0}
td{padding:6px 9px;border-bottom:1px solid var(--line);vertical-align:top}
tr:last-child td{border-bottom:none}
tbody tr:hover td{background:rgba(66,169,255,.06)}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
tr.sub td{background:var(--panel2);font-weight:650}
.pill{display:inline-block;padding:2px 9px;border-radius:7px;font-size:10px;
font-weight:750;letter-spacing:.04em;border:1px solid var(--line);
background:var(--chip)}
.pill.good{border-color:var(--good);color:var(--good)}
.pill.warn{border-color:var(--warn);color:var(--warn)}
.pill.bad{border-color:var(--bad);color:var(--bad)}
.meta{font-size:11px;color:var(--muted);margin:6px 0}
.steps{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}
.step{background:var(--chip);border:1px solid var(--line);border-radius:10px;
padding:8px 11px;min-width:130px}
.step b{display:block;font-size:9.5px;color:var(--muted);font-weight:750;
letter-spacing:.06em}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
font-size:11px}
.bar{height:9px;background:var(--chip);border-radius:5px;overflow:hidden}
.bar i{display:block;height:100%;
background:linear-gradient(90deg,var(--accent),var(--lineage))}
.sel{background:var(--panel2);color:var(--text);border:1px solid var(--line);
border-radius:8px;padding:6px 9px;font-family:inherit;font-size:12px}
.split{display:grid;gap:12px;grid-template-columns:minmax(260px,1fr) 2.2fr}
@media(max-width:900px){.split{grid-template-columns:1fr}}
.list{max-height:520px;overflow:auto;border:1px solid var(--line);
border-radius:11px}
.list button{display:block;width:100%;text-align:left;background:transparent;
border:none;border-bottom:1px solid var(--line);color:var(--text);
padding:8px 11px;cursor:pointer;font-family:inherit;font-size:12px}
.list button:hover{background:var(--chip)}
.list button.on{background:var(--accent);color:var(--on-accent)}
.list button small{display:block;color:var(--muted);font-size:10px}
.list button.on small{color:var(--on-accent);opacity:.75}
.listsec{background:var(--panel2);border-bottom:1px solid var(--line);
padding:6px 11px;font-size:10.5px;font-weight:750;letter-spacing:.05em;
color:var(--muted)}
.flow{display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin:10px 0}
.node{background:var(--chip);border:1px solid var(--line);border-radius:10px;
padding:8px 11px;min-width:120px}
.node b{display:block;font-size:9.5px;color:var(--muted);font-weight:750;
letter-spacing:.05em}
.arrow{color:var(--muted)}
.note{border:1px solid rgba(66,169,255,.27);border-left:3px solid var(--accent);
background:rgba(66,169,255,.055);padding:9px 12px;border-radius:0 10px 10px 0;
font-size:11.5px;color:var(--muted);margin:12px 0}
.note.bad{border-color:rgba(251,100,114,.35);border-left-color:var(--bad);
background:rgba(251,100,114,.06);color:var(--bad)}
.note[hidden]{display:none}
footer{padding:20px;color:var(--muted);font-size:11px;
border-top:1px solid var(--line);margin-top:24px}
.toolbar{display:flex;gap:8px;flex-wrap:wrap;align-items:flex-start;margin:10px 0}
.input{flex:1;min-width:280px;background:var(--panel);color:var(--text);
border:1px solid var(--line);border-radius:9px;padding:8px 11px;
font-family:inherit;font-size:12.5px}
.input:focus{outline:none;border-color:var(--accent)}
textarea.input{resize:vertical;line-height:1.5}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin:2px 0 10px}
.chip{background:var(--chip);border:1px solid var(--line);color:var(--muted);
border-radius:8px;padding:4px 11px;font-size:11px;font-weight:600;
cursor:pointer;font-family:inherit;max-width:100%;overflow:hidden;
text-overflow:ellipsis;white-space:nowrap}
.chip:hover{color:var(--text);border-color:var(--accent)}
.chip.on{background:var(--accent);color:var(--on-accent);
border-color:var(--accent)}
.btn{background:var(--chip);border:1px solid var(--line);color:var(--text);
border-radius:8px;padding:6px 13px;font-size:12px;font-weight:650;
cursor:pointer;font-family:inherit}
.btn:hover:not(:disabled){border-color:var(--accent)}
.btn:disabled{opacity:.4;cursor:not-allowed}
.btn.primary{background:var(--accent);border-color:var(--accent);
color:var(--on-accent);font-weight:750}
.spark{width:100%;height:120px;display:block}
.blocks{display:grid;gap:12px;grid-template-columns:repeat(2,minmax(0,1fr));
margin:10px 0;align-items:start}
.blocks .blk{min-width:0;background:var(--chip);border:1px solid var(--line);
border-radius:12px;padding:12px;overflow:hidden}
.blocks .blk.viz-table,.blocks .blk.viz-kpi{grid-column:1/-1}
@media(max-width:1100px){.blocks{grid-template-columns:1fr}}
.blkhead{display:flex;gap:8px;align-items:center;font-size:12px;
font-weight:750;margin:2px 0 8px}
.aisum{display:flex;gap:9px;align-items:baseline;margin:2px 0 12px;
padding:9px 13px;border-radius:10px;font-size:12.5px;
background:var(--chip);border:1px solid var(--line)}
.aisum.good{border-left:3px solid var(--good)}
.aisum.warn{border-left:3px solid var(--warn)}
.aisum.bad{border-left:3px solid var(--bad)}
.aisum-tag{flex:none;font-size:9.5px;font-weight:800;letter-spacing:.08em;
color:var(--lineage)}
.blockhead{display:flex;align-items:center;gap:10px;width:100%;
background:transparent;border:none;color:var(--text);cursor:pointer;
font-family:inherit;font-size:13px;font-weight:750;padding:2px 0;text-align:left}
.blockhead small{margin-left:auto;color:var(--muted);font-weight:400;font-size:11px}
.bnum{background:var(--accent);color:var(--on-accent);border-radius:6px;
padding:2px 7px;font-size:11px;font-weight:750;
font-variant-numeric:tabular-nums}
/* 3선 도전 가정. 항목이 2~6줄 문단이라 그대로 나열하면 읽기 어려운 덩어리가 된다.
   접힌 줄은 한 줄로 잘라 고정하고(nowrap+말줄임) 전문은 펼쳤을 때만 흐른다. */
.asmp-sec{margin:14px 0 0}
.asmp-sec[hidden],.asmp-row[hidden]{display:none}
.asmp-hd{display:flex;gap:8px;align-items:center;padding:0 0 5px;
border-bottom:1px solid var(--line);font-size:10.5px;font-weight:800;
letter-spacing:.06em;color:var(--muted)}
.asmp-row{border-bottom:1px solid var(--line)}
.asmp-row>summary{display:flex;gap:7px;align-items:center;cursor:pointer;
padding:7px 4px;font-size:12px;list-style:none}
.asmp-row>summary::-webkit-details-marker{display:none}
.asmp-row>summary::before{content:'▸';flex:none;color:var(--muted);font-size:10px}
.asmp-row[open]>summary::before{content:'▾';color:var(--accent)}
.asmp-row>summary:hover{background:var(--chip)}
.asmp-row[open]>summary{font-weight:700}
.asmp-sum{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;
white-space:nowrap}
.asmp-fid{flex:none;font-size:9.5px;font-weight:750;letter-spacing:.03em;
color:var(--lineage);border:1px solid var(--line);background:var(--chip);
border-radius:6px;padding:1px 6px;font-variant-numeric:tabular-nums}
.asmp-body{padding:0 6px 13px 21px;font-size:12px;line-height:1.7;
color:var(--muted);max-width:92ch}
"""

_JS = r"""
const RUNS = window.__RYNTA_RUNS__;
let D = window.__RYNTA__;               /* 활성 실행 (기준일 전환 시 재지정) */
const $ = (s,r=document)=>r.querySelector(s);

/* ---- 화면 언어 -----------------------------------------------------------
   기본은 영어다. 사용자가 고르면 그 선택이 이기고 localStorage 에 남는다.
   조회는 한국어 원문 → 영문이다. 화면 소스에 이미 한국어가 적혀 있고 그
   문자열이 그대로 키 노릇을 하므로, 문자열마다 키를 새로 다는 대신 원문으로
   찾는다. 등록되지 않은 문자열은 한국어로 떨어진다. 조용히 떨어지면 누락을
   못 보므로 개발 모드(주소에 ?i18n=debug)에서는 표시를 감싼다. */
const I18N = window.__RYNTA_I18N__ || {map:{},default:'en',langs:['en','ko'],
                                       storage_key:'rynta-lang',debug:false};
const I18N_DEBUG = I18N.debug ||
  (typeof location!=='undefined' && /[?&]i18n=debug/.test(location.search));
/* 누락 문자열은 버리지 않고 모은다. 브라우저 검사가 이 목록으로 화면별
   번역률을 잰다. 사람이 눈으로 세면 빠뜨린다. */
const I18N_MISS = [];
/* 찾은 문자열도 센다. 누락 수만 보면 "몇 건 남았다"는 알아도 "몇 %를 옮겼다"는
   모른다. 화면별 번역률은 두 수가 다 있어야 나온다. */
const I18N_HIT = [];
const HANGUL = /[가-힣]/;
let LANG = I18N.default || 'en';
function T(s){
  if(s==null)return s;
  const k=String(s);
  if(LANG==='ko')return k;
  if(!HANGUL.test(k))return k;          /* 한글이 없으면 옮길 것이 없다 */
  const hit=I18N.map[k];
  if(hit!==undefined){
    if(I18N_HIT.indexOf(k)<0)I18N_HIT.push(k);
    return hit;
  }
  if(I18N_MISS.indexOf(k)<0)I18N_MISS.push(k);
  return I18N_DEBUG?('⟦'+k+'⟧'):k;
}
/* 두 조각을 잇는 자리. '지문 abc' 처럼 라벨과 원장 값이 붙는 문자열은
   통째로 카탈로그에 넣을 수 없다(값이 매번 다르다). 라벨만 옮긴다. */
function TP(label,value){return T(label)+' '+value}
/* 건수 표기. 한국어는 단위를 숫자에 붙이고(30건), 영문은 띄어 쓴다(30 items).
   숫자는 원장 값이라 손대지 않고 단위만 바꾼다. */
function TC(n,unit){
  const s=(typeof n==='number')?n.toLocaleString():String(n);
  return LANG==='ko'?(s+unit):(s+' '+T(unit));
}

/* el() 이 텍스트를 옮기는 자리는 **코드가 지은 이름**뿐이다. 표의 셀(td)과
   원장 컬럼 머리(th)는 손대지 않는다. 원장 값을 옮기면 화면의 이름과 원장의
   이름이 갈라져 감사 추적이 끊긴다. */
const I18N_TAGS={h1:1,h2:1,h3:1,h4:1,button:1,label:1,legend:1,caption:1,
                 figcaption:1,summary:1};
const I18N_CLASS=/(^|\s)(lead|note|meta|pill|hint|navgroup|hchip|kpi|badge|cap)(\s|$)/;
const rawEl=(t,c,x)=>{const e=document.createElement(t);if(c)e.className=c;
if(x!=null)e.textContent=x;return e};
const el=(t,c,x)=>rawEl(t,c,
  (x!=null&&(I18N_TAGS[t]||(c&&I18N_CLASS.test(c))))?T(x):x);
const esc=s=>String(s==null?'':s);
const fmtNum=v=>typeof v==='number'
  ? (Math.abs(v)>=1000?v.toLocaleString('ko-KR',{maximumFractionDigits:0})
     :v.toLocaleString('ko-KR',{maximumFractionDigits:6})) : esc(v);

/* 컬럼 표시명. 카탈로그 라벨(f.labels)이 기본이고, 설정 화면의 세션 재정의
   (STATE.labelOverrides)가 그 위에 얹힌다. 물리명은 버리지 않고 th.title로
   남긴다. 감사자는 어느 원장 컬럼인지 물리명으로 찾는다.

   원장 프레임(f.table 또는 f.labels 가 있는 것)의 컬럼명은 카탈로그
   ColumnSpec.korean 이 정본이므로 옮기지 않는다. simpleTable() 이 만든
   프레임은 둘 다 없고 컬럼명 자체가 화면이 지은 이름이라 옮긴다. */
function colLabel(f,i){
  const phys=f.columns[i];
  const ovr=f.table&&STATE.labelOverrides[f.table];
  const hit=(ovr&&ovr[phys])||(f.labels&&f.labels[i]);
  if(hit)return hit;
  return (f.table||f.labels)?phys:T(phys);
}

function table(f,{numeric=true,rowClass=null}={}){
  const w=el('div','tw'),t=el('table'),th=el('thead'),tr=el('tr');
  const isNum=f.columns.map((_,i)=>numeric&&f.rows.some(r=>typeof r[i]==='number'));
  f.columns.forEach((c,i)=>{const lab=colLabel(f,i);
    const h=el('th',isNum[i]?'num':null,lab);
    if(lab!==c)h.title=c;               /* 물리명은 툴팁으로 */
    tr.appendChild(h)});
  th.appendChild(tr);t.appendChild(th);
  const tb=el('tbody');
  f.rows.forEach((r,i)=>{const x=el('tr');
    if(rowClass){const c=rowClass(r,i);if(c)x.className=c}
    r.forEach((v,i)=>{const td=el('td',isNum[i]?'num':null,
      v===null?'-':fmtNum(v));x.appendChild(td)});
    tb.appendChild(x)});
  t.appendChild(tb);w.appendChild(t);
  const box=el('div');box.appendChild(w);
  if(f.total>f.shown){const m=rawEl('div','meta',
    `${T('미리보기')} ${f.shown.toLocaleString()}${T('행')} / ${T('전체')} ${f.total.toLocaleString()}${T('행')}`);
    box.appendChild(m)}
  return box;
}
function pill(txt,tone){const p=el('span','pill'+(tone?' '+tone:''),txt);return p}
function ok(b){return pill(b?'통과':'미통과', b?'good':'bad')}

/* 한도 심각도 어휘는 LimitBreach.severity(risk_lib/limits/limit_engine.py)가
   정본이다. CRITICAL(≥1.20) · BREACH(≥1.00) · WARN(≥0.90) · OK. 화면마다
   문자열을 다시 적으면 대소문자 하나로 판정이 조용히 빗나간다(실제로 콕핏
   인사이트와 한도관리 요약이 위반 2건을 "위반 없음"으로 적고 있었다). */
function limitBreached(sev){return sev==='BREACH'||sev==='CRITICAL'}
function limitTone(sev){
  return limitBreached(sev)?'bad':sev==='WARN'?'warn':'good'}

/* ---- 시각화 헬퍼. 모든 값은 payload 원장에서 그대로 온다 ----
   프레임이 잘려 실렸으면(shown<total) 집계가 모집단과 다르므로, 그 사실을
   차트에 적는다. 절단 사실을 적지 않으면 전량을 집계한 것으로 오독된다. */
/* 금액 단위. 한국어 화면은 조·억, 영문 화면은 tn·bn·m 이다. 배수만 바꾸고
   원래 값은 그대로다. 억을 영문에 그대로 두면 읽는 사람이 자릿수를 잘못
   센다(1억 = 100 million). */
function fmtMoney(v){
  const a=Math.abs(v);
  if(LANG==='ko'){
    if(a>=1e12)return (v/1e12).toFixed(1)+'조';
    if(a>=1e8)return (v/1e8).toFixed(0)+'억';
  }else{
    if(a>=1e12)return (v/1e12).toFixed(2)+'tn';
    if(a>=1e9)return (v/1e9).toFixed(2)+'bn';
    if(a>=1e6)return (v/1e6).toFixed(1)+'m';
  }
  /* 반올림하지 않는다. 위험가중치 0.2를 0으로 보이면 표시가 실제 값과 달라진다 */
  return fmtNum(v);
}
function frameIdx(f){const i={};f.columns.forEach((c,k)=>{i[c]=k});return i}
function srcMeta(f,extra){
  const cut=f.shown<f.total;
  /* 한도·오버레이처럼 엔진 산출을 바로 실은 프레임은 카탈로그 원장명이 없다.
     이름 자리에 null 을 찍으면 없는 원장을 가리키는 것처럼 읽히므로 뺀다. */
  const src=f.table?`${T('원장')} ${f.table} · `:'';
  const body=cut
    ? `${T('표본')} ${f.shown.toLocaleString()}/${f.total.toLocaleString()}${T('행 기준')}`
    : `${f.total.toLocaleString()}${T('행 전량')}`;
  const m=rawEl('div','meta'+(cut?' warn':''),
    `${src}${body}${extra?' · '+T(extra):''}`);
  return m;
}

/* 수평 그라디언트 막대 (구성·기여도) */
function barList(items,{money=true}={}){
  const w=el('div');
  const max=Math.max(...items.map(x=>Math.abs(x.value)))||1;
  items.forEach(x=>{
    const line=el('div');line.style.margin='7px 0';
    const head=el('div','meta');
    head.style.display='flex';head.style.justifyContent='space-between';
    const lab=el('span',null,x.label);if(x.phys)lab.title=x.phys;
    head.appendChild(lab);
    const v=el('span','mono '+(x.tone||''),
      (money?fmtMoney(x.value):fmtNum(x.value))+(x.sub?' · '+x.sub:''));
    head.appendChild(v);line.appendChild(head);
    const b=el('div','bar'),f=el('i');
    f.style.width=(Math.abs(x.value)/max*100).toFixed(1)+'%';
    if(x.tone==='bad')f.style.background='var(--bad)';
    else if(x.tone==='warn')f.style.background='var(--warn)';
    b.appendChild(f);line.appendChild(b);w.appendChild(line)});
  return w;
}
function hbars(items,{title,src,money=true}={}){
  const c=el('div','card');
  if(title)c.appendChild(el('h3',null,title));
  c.appendChild(barList(items,{money}));
  if(src)c.appendChild(src);
  return c;
}

/* 영역 곡선. 비정형 '추이' 블록용. 스파크보다 큰 캔버스, 기준선·격자·
   마지막 값 강조. 값은 전부 원장에서 온다. */
function areaLine(values,{height=190,label=null}={}){
  const w=920,h=height,padL=14,padR=64,padT=14,padB=18;
  const max=Math.max(...values,0),min=Math.min(...values,0);
  const span=(max-min)||1;
  const x=k=>padL+k*(w-padL-padR)/Math.max(values.length-1,1);
  const y=v=>h-padB-((v-min)/span)*(h-padT-padB);
  const ns='http://www.w3.org/2000/svg';
  const svg=document.createElementNS(ns,'svg');
  svg.setAttribute('viewBox',`0 0 ${w} ${h}`);svg.setAttribute('class','spark');
  svg.style.height=height+'px';
  /* 격자 3줄 */
  [0.25,0.5,0.75].forEach(t=>{
    const gy=padT+(h-padT-padB)*t;
    const l=document.createElementNS(ns,'line');
    l.setAttribute('x1',padL);l.setAttribute('x2',w-padR);
    l.setAttribute('y1',gy);l.setAttribute('y2',gy);
    l.setAttribute('stroke','currentColor');l.setAttribute('opacity','.08');
    svg.appendChild(l)});
  const pts=values.map((v,k)=>`${x(k).toFixed(1)},${y(v).toFixed(1)}`);
  /* 면 채움 */
  const area=document.createElementNS(ns,'polygon');
  area.setAttribute('points',
    `${x(0).toFixed(1)},${y(min).toFixed(1)} `+pts.join(' ')+
    ` ${x(values.length-1).toFixed(1)},${y(min).toFixed(1)}`);
  area.setAttribute('fill','var(--accent)');area.setAttribute('opacity','.10');
  svg.appendChild(area);
  const pl=document.createElementNS(ns,'polyline');
  pl.setAttribute('points',pts.join(' '));
  pl.setAttribute('fill','none');pl.setAttribute('stroke','var(--accent)');
  pl.setAttribute('stroke-width','2');svg.appendChild(pl);
  /* 마지막 값 강조 */
  const last=values[values.length-1];
  const dot=document.createElementNS(ns,'circle');
  dot.setAttribute('cx',x(values.length-1));dot.setAttribute('cy',y(last));
  dot.setAttribute('r','4');dot.setAttribute('fill','var(--accent)');
  svg.appendChild(dot);
  const t=document.createElementNS(ns,'text');
  t.setAttribute('x',x(values.length-1)+8);t.setAttribute('y',y(last)+4);
  t.setAttribute('fill','currentColor');t.setAttribute('font-size','11');
  t.setAttribute('font-weight','700');
  t.textContent=(label?label+' ':'')+fmtMoney(last);
  svg.appendChild(t);
  const box=el('div');box.appendChild(svg);return box;
}

/* 진행 미터 (증빙·검증 진행률) */
/* ── 차트 원시함수 ────────────────────────────────────────────────────────
   실무진 보고서(ops/*.html)가 쓰는 시각화 종류를 화면에도 갖춘다. 보고서에는
   bar 81 · hbar 27 · line 25 · stacked 13 · heatmap 8 · donut 7 · waterfall 6 ·
   gauge 3 이 있는데 화면에는 hbars·meter·sparkline·multiLine 넷뿐이었다.
   같은 사실을 보고서는 그림으로, 화면은 표로만 말하고 있었다.

   전부 인라인 SVG다. 외부 라이브러리를 쓰면 아티팩트 CSP에서 차단된다. */
const CHART_PALETTE=['--accent','--agent','--lineage','--human','--good','--warn'];
function svgEl(w,h,title){
  const s=document.createElementNS('http://www.w3.org/2000/svg','svg');
  s.setAttribute('viewBox',`0 0 ${w} ${h}`);
  s.setAttribute('width','100%');s.setAttribute('preserveAspectRatio','xMidYMid meet');
  /* 자연 크기(viewBox 폭)를 상한으로 둔다. 상한이 없으면 넓은 창에서 도넛 같은
     정사각 도형이 창 폭까지 늘어나고 9px 라벨도 같은 배율로 커진다. */
  s.style.cssText='display:block;width:100%;max-width:'+w+'px;height:auto;flex:0 1 auto';
  if(title){const t=document.createElementNS(s.namespaceURI,'title');
    t.textContent=title;s.appendChild(t)}
  return s;
}
function svgNode(p,tag,attrs,txt){
  const e=document.createElementNS('http://www.w3.org/2000/svg',tag);
  for(const k in attrs)e.setAttribute(k,attrs[k]);
  if(txt!=null)e.textContent=txt;
  p.appendChild(e);return e;
}
function chartBox(svg,title,note){
  const b=el('div');
  if(title)b.appendChild(el('div','meta',title));
  b.appendChild(svg);
  if(note)b.appendChild(el('div','meta',note));
  return b;
}
/* 세로 막대 (보고서의 bar_chart 대응. items=[{label,value,tone}]) */
function bars(items,{title,note,fmt}={}){
  const n=items.length||1,W=680,H=210,padL=48,padB=46,padT=12;
  const max=Math.max(...items.map(x=>Math.abs(x.value)),0)||1;
  const s=svgEl(W,H,title||'막대 차트');
  const bw=(W-padL-12)/n*0.66,gap=(W-padL-12)/n;
  svgNode(s,'line',{x1:padL,y1:H-padB,x2:W-6,y2:H-padB,
    stroke:'var(--line)','stroke-width':1});
  [0,0.5,1].forEach(f=>{
    const y=padT+(1-f)*(H-padB-padT);
    svgNode(s,'line',{x1:padL,y1:y,x2:W-6,y2:y,stroke:'var(--line)',
      'stroke-width':0.5,'stroke-dasharray':'3 3'});
    svgNode(s,'text',{x:padL-6,y:y+3,'text-anchor':'end','font-size':9,
      fill:'var(--muted)'},fmt?fmt(max*f):fmtNum(Math.round(max*f)))});
  items.forEach((it,i)=>{
    const h=Math.abs(it.value)/max*(H-padB-padT);
    const x=padL+i*gap+(gap-bw)/2;
    svgNode(s,'rect',{x:x,y:H-padB-h,width:bw,height:Math.max(h,1),rx:2,
      fill:'var('+(it.tone?'--'+it.tone:CHART_PALETTE[i%CHART_PALETTE.length])+')'})
      .appendChild(document.createElementNS(s.namespaceURI,'title')).textContent=
        `${it.label}: ${fmt?fmt(it.value):fmtNum(it.value)}`;
    const lab=svgNode(s,'text',{x:x+bw/2,y:H-padB+14,'text-anchor':'middle',
      'font-size':9,fill:'var(--muted)'},String(it.label).slice(0,12));
    if(n>7)lab.setAttribute('transform',`rotate(-32 ${x+bw/2} ${H-padB+14})`);
  });
  return chartBox(s,title,note);
}
/* 누적 막대 (stacked_bar 대응. series=[{name,values}], labels=[...]) */
function stackBars(series,labels,{title,note}={}){
  const W=680,H=220,padL=52,padB=40,padT=12,n=labels.length||1;
  const totals=labels.map((_,i)=>series.reduce((a,s)=>a+(s.values[i]||0),0));
  const max=Math.max(...totals,0)||1;
  const s=svgEl(W,H,title||'누적 막대');
  const gap=(W-padL-12)/n,bw=gap*0.62;
  labels.forEach((lb,i)=>{
    let acc=0;
    series.forEach((se,j)=>{
      const v=se.values[i]||0;if(!v)return;
      const h=v/max*(H-padB-padT);
      const y=H-padB-((acc+v)/max)*(H-padB-padT);
      svgNode(s,'rect',{x:padL+i*gap+(gap-bw)/2,y:y,width:bw,height:Math.max(h,1),
        fill:'var('+CHART_PALETTE[j%CHART_PALETTE.length]+')'})
        .appendChild(document.createElementNS(s.namespaceURI,'title')).textContent=
          `${lb} · ${se.name}: ${fmtNum(v)}`;
      acc+=v});
    svgNode(s,'text',{x:padL+i*gap+gap/2,y:H-padB+14,'text-anchor':'middle',
      'font-size':9,fill:'var(--muted)'},String(lb).slice(0,12))});
  const box=chartBox(s,title,note);
  box.appendChild(legend(series.map((se,j)=>({name:se.name,i:j}))));
  return box;
}
function legend(items){
  const w=el('div');w.style.cssText='display:flex;flex-wrap:wrap;gap:10px;margin-top:4px';
  items.forEach(it=>{const r=el('span');
    r.style.cssText='display:inline-flex;align-items:center;gap:4px;font-size:10px;color:var(--muted)';
    const d=el('span');d.style.cssText='width:9px;height:9px;border-radius:2px;background:var('+
      CHART_PALETTE[it.i%CHART_PALETTE.length]+')';
    r.appendChild(d);r.appendChild(el('span',null,it.name));w.appendChild(r)});
  return w;
}
/* 트리맵 (donut_chart 대응). 구역 넓이가 곧 비중이고 라벨을 구역 안에 넣는다.
   범례를 따로 두지 않으므로 이름과 비중을 눈이 한 번에 받는다. */
function squarify(data,rect){
  /* 각 구역이 정사각형에 가깝게 나오도록 행을 끊는다 (Bruls 외 squarified). */
  const out=[],items=data.slice();
  let cur={...rect};
  const ratio=(row,side,scale)=>{
    const a=row.reduce((t,x)=>t+x.v,0)*scale;
    const mx=Math.max(...row.map(x=>x.v))*scale;
    const mn=Math.min(...row.map(x=>x.v))*scale;
    return Math.max(side*side*mx/(a*a),(a*a)/(side*side*mn));
  };
  while(items.length&&cur.w>0.5&&cur.h>0.5){
    const rest=items.reduce((t,x)=>t+x.v,0)||1;
    const scale=(cur.w*cur.h)/rest;
    const side=Math.min(cur.w,cur.h);
    let row=[items.shift()],best=ratio(row,side,scale);
    while(items.length){
      const cand=row.concat([items[0]]),r=ratio(cand,side,scale);
      if(r>best)break;
      best=r;row=cand;items.shift();
    }
    const area=row.reduce((t,x)=>t+x.v,0)*scale,thick=area/side;
    let off=0;
    if(cur.w>=cur.h){
      row.forEach(it=>{const h=(it.v*scale)/thick;
        out.push({...it,x:cur.x,y:cur.y+off,w:thick,h:h});off+=h});
      cur={x:cur.x+thick,y:cur.y,w:cur.w-thick,h:cur.h};
    }else{
      row.forEach(it=>{const w=(it.v*scale)/thick;
        out.push({...it,x:cur.x+off,y:cur.y,w:w,h:thick});off+=w});
      cur={x:cur.x,y:cur.y+thick,w:cur.w,h:cur.h-thick};
    }
  }
  return out;
}
/* 묶음이 있으면 2단으로 그린다. 상위 묶음이 제목띠를 달고 그 안에서 항목이
   다시 넓이로 갈린다. 묶음 색은 팔레트에서 하나씩 가져가고, 그 안의 항목은
   같은 색을 옅게 써서 한 묶음이 한 색 계열로 읽히게 한다.

   글자색이 두 종류인 이유. 제목띠는 불투명해서 --on-accent 가 맞다. 항목은
   투명도를 낮춰 바탕색과 섞이므로 라이트에서는 밝아지고 다크에서는 어두워진다.
   두 경우 모두 --text 가 대비를 유지한다. --on-accent 를 항목에 쓰면 한쪽
   테마에서 읽히지 않는다. */
function tmCell(s,c,col,op,txtVar,fmt,frac,sub){
  const G=2,pad=7;
  const g=svgNode(s,'g',{});
  svgNode(g,'rect',{x:c.x+G/2,y:c.y+G/2,width:Math.max(c.w-G,1),
    height:Math.max(c.h-G,1),rx:2,fill:'var('+col+')','fill-opacity':op})
    .appendChild(document.createElementNS(s.namespaceURI,'title')).textContent=
      `${c.label}: ${fmt?fmt(c.value):fmtNum(c.value)} (${(frac*100).toFixed(1)}%)`;
  const cx=c.x+c.w/2,fit=Math.floor((c.w-pad*2)/6.5);
  if(c.w>52&&c.h>30){
    const two=c.h>52;
    svgNode(g,'text',{x:cx,y:c.y+c.h/2+(two?-3:4),'text-anchor':'middle',
      'font-size':11,'font-weight':600,fill:'var('+txtVar+')'},
      String(c.label).slice(0,Math.max(fit,1)));
    if(two)svgNode(g,'text',{x:cx,y:c.y+c.h/2+13,'text-anchor':'middle',
      'font-size':10,fill:'var('+txtVar+')','fill-opacity':0.8},sub);
  }
}
function donut(items,{title,note,fmt}={}){
  const W=1180,H=520,HDR=21;
  const tot=items.reduce((a,x)=>a+Math.abs(x.value),0)||1;
  const s=svgEl(W,H,title||'트리맵');
  const clean=items.map(it=>({label:String(it.label),group:it.group,
    value:it.value,v:Math.abs(it.value)})).filter(d=>d.v>0);
  if(!clean.length)return chartBox(s,title,note);
  const pct=v=>(v/tot*100).toFixed(1)+'%';
  const money=v=>fmt?fmt(v):fmtNum(v);

  if(!clean.some(d=>d.group!=null)){
    /* 묶음이 없으면 1단이다. */
    clean.sort((a,b)=>b.v-a.v);
    squarify(clean,{x:0,y:0,w:W,h:H}).forEach((c,i)=>
      tmCell(s,c,CHART_PALETTE[i%CHART_PALETTE.length],1,'--on-accent',
        fmt,c.v/tot,money(c.value)+' · '+pct(c.v)));
    return chartBox(s,title,note);
  }

  const m=new Map();
  clean.forEach(d=>{
    const g=d.group==null?'(미지정)':String(d.group);
    if(!m.has(g))m.set(g,{label:g,v:0,value:0,kids:[]});
    const e=m.get(g);e.v+=d.v;e.value+=d.value;e.kids.push(d)});
  const groups=[...m.values()].sort((a,b)=>b.v-a.v);
  groups.forEach(g=>g.kids.sort((a,b)=>b.v-a.v));

  squarify(groups,{x:0,y:0,w:W,h:H}).forEach((gc,gi)=>{
    const col=CHART_PALETTE[gi%CHART_PALETTE.length];
    const G=2;
    /* 제목띠. 묶음이 너무 낮으면 띠를 빼고 항목만 채운다. */
    const band=gc.h>=HDR+26?HDR:0;
    if(band){
      const gg=svgNode(s,'g',{});
      svgNode(gg,'rect',{x:gc.x+G/2,y:gc.y+G/2,width:Math.max(gc.w-G,1),
        height:band-G/2,rx:2,fill:'var('+col+')'})
        .appendChild(document.createElementNS(s.namespaceURI,'title')).textContent=
          `${gc.label}: ${money(gc.value)} (${pct(gc.v)})`;
      if(gc.w>70)svgNode(gg,'text',{x:gc.x+gc.w/2,y:gc.y+band-6,
        'text-anchor':'middle','font-size':11,'font-weight':700,
        fill:'var(--on-accent)'},
        gc.label.slice(0,Math.floor((gc.w-12)/6.5))+'  '+pct(gc.v));
    }
    const inner={x:gc.x,y:gc.y+band,w:gc.w,h:gc.h-band};
    if(inner.h<=1)return;
    const n=gc.kids.length;
    squarify(gc.kids,inner).forEach((c,ki)=>{
      /* 같은 묶음 안에서 큰 항목일수록 진하다. 순위가 색으로도 읽힌다. */
      const op=n<2?0.60:0.60-(ki/(n-1))*0.32;
      tmCell(s,c,col,op,'--text',fmt,c.v/tot,money(c.value)+' · '+pct(c.v));
    });
  });
  return chartBox(s,title,note);
}
/* 히트맵 (heatmap 대응. rows/cols 라벨 + 값 행렬) */
function heat(matrix,rowLabels,colLabels,{title,note,fmt}={}){
  const cw=Math.max(38,Math.min(76,560/(colLabels.length||1))),ch=22,padL=110,padT=26;
  const W=padL+cw*colLabels.length+8,H=padT+ch*rowLabels.length+8;
  const flat=matrix.flat().filter(v=>typeof v==='number');
  const max=Math.max(...flat,0)||1,min=Math.min(...flat,0);
  const s=svgEl(W,H,title||'히트맵');
  colLabels.forEach((c,j)=>svgNode(s,'text',{x:padL+j*cw+cw/2,y:padT-8,
    'text-anchor':'middle','font-size':9,fill:'var(--muted)'},String(c).slice(0,10)));
  rowLabels.forEach((r,i)=>{
    svgNode(s,'text',{x:padL-6,y:padT+i*ch+15,'text-anchor':'end','font-size':9,
      fill:'var(--muted)'},String(r).slice(0,16));
    colLabels.forEach((c,j)=>{
      const v=matrix[i][j];
      const t=(v==null)?0:(max===min?0.5:(v-min)/(max-min));
      svgNode(s,'rect',{x:padL+j*cw+1,y:padT+i*ch+1,width:cw-2,height:ch-2,rx:2,
        fill:'var(--accent)','fill-opacity':(0.08+0.82*t).toFixed(3)})
        .appendChild(document.createElementNS(s.namespaceURI,'title')).textContent=
          `${r} × ${c}: ${v==null?'-':(fmt?fmt(v):fmtNum(v))}`})});
  return chartBox(s,title,note);
}
/* 폭포 (waterfall 대응. steps=[{label,delta}] + 시작값) */
function waterfall(steps,start,{title,note,fmt}={}){
  const W=680,H=220,padL=56,padB=44,padT=12,n=steps.length+1;
  let acc=start;const pts=[{label:'시작',v:start,d:null}];
  steps.forEach(s0=>{acc+=s0.delta;pts.push({label:s0.label,v:acc,d:s0.delta})});
  const max=Math.max(...pts.map(p=>p.v),start)||1,min=Math.min(...pts.map(p=>p.v),0);
  const span=(max-min)||1;
  const s=svgEl(W,H,title||'폭포 차트');
  const gap=(W-padL-12)/n,bw=gap*0.6;
  const Y=v=>H-padB-((v-min)/span)*(H-padB-padT);
  pts.forEach((p,i)=>{
    const x=padL+i*gap+(gap-bw)/2;
    const y0=p.d==null?Y(0):Y(p.v-p.d),y1=Y(p.v);
    const top=Math.min(y0,y1),h=Math.max(Math.abs(y1-y0),1.5);
    const tone=p.d==null?'--accent':(p.d>=0?'--good':'--bad');
    svgNode(s,'rect',{x:x,y:p.d==null?y1:top,width:bw,
      height:p.d==null?Math.max(Y(min)-y1,1.5):h,rx:2,fill:'var('+tone+')'})
      .appendChild(document.createElementNS(s.namespaceURI,'title')).textContent=
        `${p.label}: ${fmt?fmt(p.v):fmtNum(p.v)}`+
        (p.d==null?'':` (${p.d>=0?'+':''}${fmt?fmt(p.d):fmtNum(p.d)})`);
    const lab=svgNode(s,'text',{x:x+bw/2,y:H-padB+14,'text-anchor':'middle',
      'font-size':9,fill:'var(--muted)'},String(p.label).slice(0,11));
    if(n>6)lab.setAttribute('transform',`rotate(-30 ${x+bw/2} ${H-padB+14})`)});
  return chartBox(s,title,note);
}
/* 게이지 (gauge 대응) */
function gauge(value,max,{title,note,tone,fmt}={}){
  const W=240,H=140,cx=120,cy=118,R=92,r=64;
  const frac=Math.max(0,Math.min(1,max?value/max:0));
  const s=svgEl(W,H,title||'게이지');
  const arc=(f,col,op)=>{
    const a0=Math.PI,a1=Math.PI+f*Math.PI;
    const p=(ra,an)=>[cx+ra*Math.cos(an),cy+ra*Math.sin(an)];
    const [x0,y0]=p(R,a0),[x1,y1]=p(R,a1),[x2,y2]=p(r,a1),[x3,y3]=p(r,a0);
    svgNode(s,'path',{d:`M${x0},${y0} A${R},${R} 0 ${f>0.5?1:0},1 ${x1},${y1} `+
      `L${x2},${y2} A${r},${r} 0 ${f>0.5?1:0},0 ${x3},${y3} Z`,
      fill:col,'fill-opacity':op||1})};
  arc(1,'var(--line)',1);
  if(frac>0)arc(frac,'var(--'+(tone||'accent')+')',1);
  svgNode(s,'text',{x:cx,y:cy-14,'text-anchor':'middle','font-size':22,
    'font-weight':700,fill:'var(--text)'},fmt?fmt(value):fmtNum(value));
  return chartBox(s,title,note);
}
/* KRI 카드 격자 (viz_advanced.kri_scorecard 대응. 스파크라인·등급 배지 포함) */
function kriCards(kris){
  const g=el('div');
  g.style.cssText='display:grid;gap:10px;margin-top:8px;'+
    'grid-template-columns:repeat(auto-fill,minmax(240px,1fr))';
  const tone={RED:'bad',AMBER:'warn',WATCH:'accent',GREEN:'good'};
  kris.forEach(k=>{
    const t=tone[k.grade]||'muted';
    const c=el('div');
    c.style.cssText='border:1px solid var(--'+t+');border-radius:7px;padding:9px 11px;'+
      'background:color-mix(in srgb, var(--'+t+') 9%, transparent)';
    const hd=el('div');hd.style.cssText='display:flex;align-items:center;gap:6px';
    const cat=rawEl('span','meta',k.category);cat.style.flex='1';
    hd.appendChild(cat);
    const bg=el('span');bg.textContent=k.grade;
    bg.style.cssText='font-size:9.5px;font-weight:700;color:var(--on-accent);'+
      'background:var(--'+t+');border-radius:9px;padding:2px 8px';
    hd.appendChild(bg);c.appendChild(hd);
    const nm=el('div',null,k.name);
    nm.style.cssText='font-size:12px;font-weight:600;margin-top:2px';c.appendChild(nm);
    const row=el('div');row.style.cssText='display:flex;align-items:flex-end;gap:8px';
    const val=el('div',null,k.actual_text);
    val.style.cssText='font-size:19px;font-weight:700;color:var(--'+t+');flex:none';
    row.appendChild(val);
    if(k.spark&&k.spark.length>=3){
      const sp=svgEl(104,30,k.name+' 12개월 추이');
      const mx=Math.max(...k.spark),mn=Math.min(...k.spark),sn=(mx-mn)||1;
      const pts=k.spark.map((v,i,a)=>
        `${(3+i*98/Math.max(a.length-1,1)).toFixed(1)},${(27-((v-mn)/sn)*24).toFixed(1)}`
      ).join(' ');
      svgNode(sp,'polyline',{points:pts,fill:'none',stroke:'var(--muted)','stroke-width':1.3});
      const last=k.spark[k.spark.length-1];
      svgNode(sp,'circle',{cx:101,cy:(27-((last-mn)/sn)*24).toFixed(1),r:2.6,
        fill:'var(--'+t+')'});
      sp.style.flex='1';row.appendChild(sp);
    }
    c.appendChild(row);
    const ft=el('div');ft.style.cssText='display:flex;gap:6px;margin-top:3px';
    const th=rawEl('span','meta',k.threshold_text);th.style.flex='1';ft.appendChild(th);
    if(k.trend)ft.appendChild(el('span','meta '+(k.trend==='악화'?'bad':'good'),
      '12M '+(k.trend==='악화'?'↘':'↗')+' '+k.trend));
    c.appendChild(ft);
    g.appendChild(c)});
  return g;
}

function meter(label,num,den,tone){
  const line=el('div');line.style.margin='8px 0';
  const head=el('div','meta');
  head.style.display='flex';head.style.justifyContent='space-between';
  head.appendChild(el('span',null,label));
  head.appendChild(el('span','mono '+(tone||''),`${num} / ${den}`));
  line.appendChild(head);
  const b=el('div','bar'),f=el('i');
  f.style.width=(den?num/den*100:0).toFixed(1)+'%';
  if(tone==='warn')f.style.background='var(--warn)';
  if(tone==='bad')f.style.background='var(--bad)';
  b.appendChild(f);line.appendChild(b);
  return line;
}

/* 색점 상태 큐 (의사결정·KRI) */
function dotlist(items){
  const w=el('div');
  items.forEach(x=>{
    const r=el('div');r.style.cssText=
      'display:flex;gap:9px;align-items:center;padding:6px 2px;'+
      'border-bottom:1px solid var(--line);font-size:11.5px';
    const dot=el('span');dot.style.cssText=
      'width:8px;height:8px;border-radius:50%;flex:none;background:var(--'+
      (x.tone||'muted')+')';
    r.appendChild(dot);
    const lab=el('span',null,x.label);lab.style.flex='1';r.appendChild(lab);
    if(x.right)r.appendChild(el('span','meta '+(x.tone||''),x.right));
    w.appendChild(r)});
  return w;
}

/* 백테스트 예외 달력 (영업일 1칸, 예외는 위반색) */
function calheat(f){
  const i=frameIdx(f);
  const c=el('div','card');
  c.appendChild(el('h3',null,'백테스팅 예외 달력'));
  const wrap=el('div');
  wrap.style.cssText='display:flex;flex-wrap:wrap;gap:3px';
  let nEx=0;
  f.rows.slice().sort((a,b)=>String(a[i.obs_date]).localeCompare(String(b[i.obs_date])))
   .forEach(r=>{
    const ex=!!r[i.exception];if(ex)nEx++;
    const d=el('span');
    d.title=`${r[i.obs_date]} · 손익 ${fmtMoney(r[i.pnl])} · VaR ${fmtMoney(r[i.var_99])}`+
            (ex?' · 예외':'');
    d.style.cssText='width:11px;height:11px;border-radius:3px;background:'+
      (ex?'var(--bad)':'var(--chip)')+';border:1px solid var(--line)';
    wrap.appendChild(d)});
  c.appendChild(wrap);
  c.appendChild(el('div','meta',
    `예외 ${nEx}건 / 관측 ${f.rows.length}일 (신호등 구간은 원장 zone 열)`));
  c.appendChild(srcMeta(f));
  return c;
}

/* 손익 대 VaR 경계 (관측일 순 이중 곡선, 예외는 점) */
function pnlChart(f){
  const i=frameIdx(f);
  const rows=f.rows.slice().sort((a,b)=>
    String(a[i.obs_date]).localeCompare(String(b[i.obs_date])));
  const w=920,h=200,padL=10,padR=10,padT=10,padB=10;
  const pnl=rows.map(r=>r[i.pnl]),neg=rows.map(r=>-r[i.var_99]);
  const all=pnl.concat(neg);
  const max=Math.max(...all),min=Math.min(...all),span=(max-min)||1;
  const x=k=>padL+k*(w-padL-padR)/Math.max(rows.length-1,1);
  const y=v=>h-padB-((v-min)/span)*(h-padT-padB);
  const ns='http://www.w3.org/2000/svg';
  const svg=document.createElementNS(ns,'svg');
  svg.setAttribute('viewBox',`0 0 ${w} ${h}`);svg.setAttribute('class','spark');
  svg.style.height='200px';
  [[pnl,'var(--accent)'],[neg,'var(--bad)']].forEach(([vs,col])=>{
    const pl=document.createElementNS(ns,'polyline');
    pl.setAttribute('points',vs.map((v,k)=>`${x(k).toFixed(1)},${y(v).toFixed(1)}`).join(' '));
    pl.setAttribute('fill','none');pl.setAttribute('stroke',col);
    pl.setAttribute('stroke-width',col.includes('bad')?'1.4':'1.8');
    if(col.includes('bad'))pl.setAttribute('stroke-dasharray','5 3');
    svg.appendChild(pl)});
  rows.forEach((r,k)=>{
    if(!r[i.exception])return;
    const dot=document.createElementNS(ns,'circle');
    dot.setAttribute('cx',x(k));dot.setAttribute('cy',y(r[i.pnl]));
    dot.setAttribute('r','3.5');dot.setAttribute('fill','var(--bad)');
    svg.appendChild(dot)});
  const c=el('div','card');
  c.appendChild(el('h3',null,'일별 손익 대 VaR 경계 (99%)'));
  c.appendChild(svg);
  c.appendChild(el('div','meta','실선 손익 · 점선 −VaR (점선 아래 손익이 백테스팅 예외다)'));
  c.appendChild(srcMeta(f));
  return c;
}

/* 프레임 → 그룹 합계 (잘린 프레임이면 합계가 모집단이 아님을 호출자가 안다) */
function groupSum(f,keyCol,valCol){
  const i=frameIdx(f),m=new Map();
  f.rows.forEach(r=>{
    const k=r[i[keyCol]];
    const cur=m.get(k)||{sum:0,n:0};
    cur.sum+=(r[i[valCol]]||0);cur.n++;m.set(k,cur)});
  return [...m.entries()].map(([k,v])=>({key:k,sum:v.sum,n:v.n}))
    .sort((a,b)=>b.sum-a.sum);
}

/* ---- 부문별 분석 차트 (원장이 있는 부문에만 그린다) ---- */
const DOMAIN_CHARTS={
  'PRD-RWA':root=>{
    const sa=D.data['rwa_sa_bucket'];
    if(sa){const i=frameIdx(sa);
      root.appendChild(hbars(sa.rows.map(r=>({
        label:`${r[i.asset_class]} · RW ${(r[i.risk_weight]*100).toFixed(0)}%`,
        value:r[i.rwa],sub:`EAD ${fmtMoney(r[i.ead])}`}))
        .sort((a,b)=>b.value-a.value),
        {title:'위험가중자산 구성 (표준방법 자산군×위험가중치)',src:srcMeta(sa)}))}
    const irb=D.data['rwa_irb_pool'];
    if(irb){const i=frameIdx(irb);
      root.appendChild(hbars(irb.rows.map(r=>({
        label:`${r[i.asset_class]} · PD ${r[i.pd_band]}`,
        value:r[i.rwa],sub:`평균 RW ${(r[i.rw_average]*100).toFixed(0)}%`}))
        .sort((a,b)=>b.value-a.value).slice(0,10),
        {title:'내부등급법 풀별 위험가중자산 (PD 구간)',src:srcMeta(irb)}))}
  },
  'PRD-MKT':root=>{
    const bt=D.data['mkt_backtest_exception'];
    if(bt){root.appendChild(pnlChart(bt));root.appendChild(calheat(bt))}
    const ipv=D.data['mkt_ipv'];
    if(ipv){const i=frameIdx(ipv);
      const open=ipv.rows.filter(r=>r[i.is_break]);
      root.appendChild(hbars(open.sort((a,b)=>b[i.days_open]-a[i.days_open])
        .slice(0,8).map(r=>({label:`${r[i.trade_id]} · ${r[i.source]}`,
          value:r[i.days_open],sub:`차이 ${fmtMoney(r[i.diff])}`,
          tone:r[i.days_open]>=5?'bad':'warn'})),
        {title:'독립가격검증(IPV) 미해소 (경과일 상위)',money:false,
         src:srcMeta(ipv,TP('미해소',TC(open.length,'건')))}))}
  },
  'PRD-ECL':root=>{
    const f=D.data['ecl_result'];
    if(!f)return;
    const g=groupSum(f,'stage','ecl');
    root.appendChild(hbars(g.map(x=>({
      label:`Stage ${x.key}${x.key===2?' (SICR 전이)':x.key===3?' (손상)':''}`,
      value:x.sum,sub:`${x.n.toLocaleString()}건`,
      tone:x.key===3?'bad':x.key===2?'warn':undefined})),
      {title:'기대신용손실 구성 (단계별)',src:srcMeta(f)}));
  },
  'PRD-CRM':root=>{
    const f=D.data['crm_ews_signal'];
    if(!f)return;
    const i=frameIdx(f),g=groupSum(f,'level','ead');
    root.appendChild(hbars(g.map(x=>({
      label:`조기경보 ${x.key}`,value:x.sum,sub:`${x.n.toLocaleString()}건`,
      tone:x.key==='경보'?'bad':x.key==='주의'?'warn':undefined})),
      {title:'조기경보 단계별 익스포저(EAD)',src:srcMeta(f)}));
  },
  'PRD-ALM':root=>{
    const f=D.data['alm_lcr_item'];
    if(!f)return;
    const i=frameIdx(f);
    root.appendChild(hbars(f.rows.map(r=>({
      label:`${r[i.section]} · ${r[i.category]}`,value:Math.abs(r[i.weighted]),
      sub:`적용률 ${(r[i.factor]*100).toFixed(0)}%`,
      tone:r[i.section]==='OUTFLOW'?'warn':undefined}))
      .sort((a,b)=>b.value-a.value),
      {title:'유동성커버리지비율 구성 (가중 후 금액)',src:srcMeta(f)}));
  },
  'PRD-OPR':root=>{
    const f=D.data['opr_loss_event'];
    if(f){const g=groupSum(f,'event_type','net_loss');
      root.appendChild(hbars(g.map(x=>({label:x.key,value:x.sum,
        sub:`${x.n.toLocaleString()}건`})),
        {title:'운영손실 순손실 구성 (사건유형별)',src:srcMeta(f)}))}
    const k=D.data['opr_kri'];
    if(k){const i=frameIdx(k);
      const c=el('div','card');
      c.appendChild(el('h3',null,'핵심리스크지표(KRI) 상태'));
      c.appendChild(dotlist(k.rows.map(r=>({
        label:r[i.kri_name],
        right:`${fmtNum(r[i.value])} / ${T('경보')} ${fmtNum(r[i.threshold_red])}`,
        tone:r[i.status]==='red'?'bad':r[i.status]==='amber'?'warn':'good'}))));
      c.appendChild(srcMeta(k));root.appendChild(c)}
  },
};


/* ---- 00 콕핏 ---- */
function cockpit(root){
  const g=el('div','grid');
  D.kpis.forEach(k=>{const c=el('div','card kpi');
    c.appendChild(el('div','lab',k.label));
    c.appendChild(el('div','val '+(k.tone||''),k.value));
    c.appendChild(el('div','sub',k.sub));
    c.appendChild(el('div','ln','↗ 계보 · '+k.lineage));
    g.appendChild(c)});
  root.appendChild(g);

  /* --- 인사이트 리본 (전 부문 원장에서 규칙으로 뽑은 문장들) --- */
  const ins=cockpitInsights();
  if(ins.length){
    const rib=el('div','card');
    rib.appendChild(el('h3',null,'인사이트 (한계 위반·미해소 예외·검증 상태)'));
    rib.appendChild(dotlist(ins.map(x=>({label:x.t,
      tone:x.tone==='bad'?'bad':x.tone==='warn'?'warn':'good'}))));
    rib.appendChild(el('div','meta',
      '규칙 기반 자동 분석. 같은 데이터면 같은 문장이 나오는 결정론이며 외부 LLM 을 호출하지 않는다'));
    root.appendChild(rib);
  }

  /* --- 위기 경로 + 역스트레스 (전사 자본의 앞날) --- */
  const two0=el('div');two0.style.cssText=
    'display:grid;gap:12px;grid-template-columns:1.5fr 1fr';
  if(window.matchMedia('(max-width:900px)').matches)
    two0.style.gridTemplateColumns='1fr';
  const cp=D.data['st_capital_path'];
  if(cp){const i=frameIdx(cp);
    const scenarios=[...new Set(cp.rows.map(r=>r[i.scenario]))];
    const quarters=[...new Set(cp.rows.map(r=>r[i.quarter]))];
    const series=scenarios.map(sc=>({name:sc,
      values:quarters.map(q=>{const r=cp.rows.find(x=>x[i.scenario]===sc&&
        x[i.quarter]===q);return r?r[i.cet1_ratio]:null})}));
    const c=el('div','card');
    c.appendChild(el('h3',null,'위기상황 보통주자본비율 경로 (3시나리오)'));
    c.appendChild(multiLine(series,quarters,0.08));
    c.appendChild(srcMeta(cp));
    two0.appendChild(c)}
  const rv=D.reverse_stress;
  if(rv){const c=el('div','card');
    c.appendChild(el('h3',null,'역스트레스 (임계까지의 거리)'));
    c.appendChild(meter('임계 심도 (심각=1.0 기준)',
      Math.min(rv.critical_severity,1),1,
      rv.critical_severity<1?'bad':undefined));
    c.appendChild(el('div','meta',
      `심도 ${rv.critical_severity.toFixed(3)}에서 ${rv.metric.toUpperCase()} `+
      `${(rv.target_ratio*100).toFixed(0)}% 붕괴 · 함의 GDP `+
      `${(rv.implied_gdp_shock*100).toFixed(2)}% · LGD +`+
      `${(rv.implied_lgd_addon*100).toFixed(2)}%p`));
    const lm=D.limits,li2=frameIdx(lm);
    c.appendChild(el('h3',null,'한도 소진 상위'));
    c.appendChild(barList(lm.rows.slice()
      .sort((a,b)=>b[li2.utilisation]-a[li2.utilisation]).slice(0,4)
      .map(r=>({label:`${r[li2.limit]} · ${r[li2.bucket]}`,
        value:r[li2.utilisation]*100,
        tone:limitTone(r[li2.severity])})),{money:false}));
    two0.appendChild(c)}
  root.appendChild(two0);

  /* --- 예외 스트림 (조치가 붙은 미해소 예외 상위) --- */
  const exq=D.data['gov_exception_action'];
  if(exq){const xi=frameIdx(exq);
    const c=el('div','card');
    c.appendChild(el('h3',null,'예외 스트림 (자동상계 금지)'));
    c.appendChild(dotlist(exq.rows.slice(0,6).map(r=>({
      label:`${r[xi.exception_id]} · ${r[xi.finding]}`,
      right:`${r[xi.status]} · 기한 ${r[xi.due_days]}일`,
      tone:r[xi.severity]==='중대'?'bad':'warn'}))));
    if(exq.shown<exq.total)c.appendChild(el('div','meta',
      `표시 6건 / 전체 ${exq.total.toLocaleString()}건 (예외·조치 화면에서 전량)`));
    root.appendChild(c)}

  /* --- 구성 브리지 + 통제 진행 (캡처(v9.5.0)의 콕핏 모듈) --- */
  const two=el('div');two.style.cssText=
    'display:grid;gap:12px;grid-template-columns:1.4fr 1fr';
  if(window.matchMedia('(max-width:900px)').matches)
    two.style.gridTemplateColumns='1fr';
  const sa=D.data['rwa_sa_bucket'];
  if(sa){const i=frameIdx(sa);
    two.appendChild(hbars(sa.rows.map(r=>({
      label:`${r[i.asset_class]} · RW ${(r[i.risk_weight]*100).toFixed(0)}%`,
      value:r[i.rwa]})).sort((a,b)=>b.value-a.value).slice(0,7),
      {title:'위험가중자산 구성 (표준방법)',src:srcMeta(sa)}))}
  const ctl=el('div','card');
  ctl.appendChild(el('h3',null,'통제 진행 (증빙·대사·검증)'));
  const ev=D.evidence_nodes,evi=frameIdx(ev);
  ctl.appendChild(meter('증빙 계보 완결',
    ev.rows.filter(r=>r[evi.status]==='완결').length,ev.rows.length));
  const rc=D.reconciliation,rci=frameIdx(rc);
  ctl.appendChild(meter('집계·대사 통과',
    rc.rows.filter(r=>r[rci.status]==='PASS').length,rc.rows.length));
  const vl=D.validation,vli=frameIdx(vl);
  const nfail=vl.rows.filter(r=>r[vli.status]==='FAIL').length;
  ctl.appendChild(meter('자체검증 PASS',
    vl.rows.filter(r=>r[vli.status]==='PASS').length,vl.rows.length,
    nfail?'bad':undefined));
  const ap=D.approvals,api=frameIdx(ap);
  const pend=ap.rows.filter(r=>r[api.decision]!=='승인');
  ctl.appendChild(el('h3',null,'의사결정 큐'));
  ctl.appendChild(dotlist((pend.length?pend:ap.rows).slice(0,6).map(r=>({
    label:`${r[api.subject_type]} · ${r[api.subject_id]}`,
    right:r[api.decision],
    tone:r[api.decision]==='승인'?'good':r[api.decision]==='반려'?'bad':'warn'}))));
  if(ap.shown<ap.total)ctl.appendChild(el('div','meta',
    `표시 범위 (승인 원장 ${ap.total.toLocaleString()}건 중 ${ap.shown.toLocaleString()}건)`));
  two.appendChild(ctl);
  root.appendChild(two);

  const c1=el('div','card');c1.appendChild(el('h3',null,'증빙 계보 · 7단계 (단계를 누르면 상세)'));
  const flow=el('div','flow');
  const drill=el('div');                     /* 드릴다운 패널 (PLT-018) */
  D.evidence_nodes.rows.forEach((r,i)=>{
    const [ , nid, stage, label, ref, status]=r;
    const n=el('div','node');n.style.cursor='pointer';
    n.appendChild(el('b',null,`0${i+1} ${stage}`));
    n.appendChild(el('div',null,label));
    const s=el('div');s.appendChild(pill(status,
      status==='완결'?'good':status==='검토'?'warn':'bad'));
    n.appendChild(s);flow.appendChild(n);
    n.onclick=()=>{
      drill.innerHTML='';
      const d=el('div','note');
      d.textContent=`단계 ${stage} · ${label} (참조 ${ref||'-'} · 상태 ${status} · 노드 ${nid})`;
      drill.appendChild(d);
      /* 실행 간 대조 (실은 실행 전부의 지문·규모를 나란히 (버전 diff)) */
      const runs=Object.keys(RUNS).sort();
      drill.appendChild(table({columns:
        ['기준일','실행 ID','산출 지문','제출 서식','원장 행수','3선 게이트'],
        rows:runs.map(a=>{const m=RUNS[a].meta,iv=RUNS[a].independent;
          return [a,m.run_id,m.digest.slice(0,16),
                  RUNS[a].forms.length,m.n_rows,iv.status]}),
        total:runs.length,shown:runs.length},{numeric:false}));
      if(runs.length>1){
        const uniq=new Set(runs.map(a=>RUNS[a].meta.digest));
        drill.appendChild(el('div','meta',uniq.size===1
          ?'실행 간 산출 지문 동일'
          :`실행 간 산출 지문 ${uniq.size}종 (실행 ${runs.length}건)`));
      }
    };
    if(i<D.evidence_nodes.rows.length-1)flow.appendChild(el('span','arrow','→'));
  });
  c1.appendChild(flow);
  c1.appendChild(drill);
  c1.appendChild(table(D.evidence_edges));
  root.appendChild(c1);

  const c2=el('div','card');c2.appendChild(el('h3',null,'집계·대사 예외 큐 (자동상계 금지)'));
  c2.appendChild(table(D.reconciliation,{rowClass:r=>r[8]==='FAIL'?'':null}));
  c2.appendChild(el('h3',null,'원천 인터페이스 계약 (Interface Watch)'));
  c2.appendChild(table(D.contracts));
  root.appendChild(c2);

  const c3=el('div','card');c3.appendChild(el('h3',null,'의사결정 큐 · 4-Eyes 승인'));
  c3.appendChild(table(D.approvals));
  root.appendChild(c3);
}

/* ---- 정형 조회 스튜디오 (라이브) ---- */
const STATE = {killed: false, killScope: '전사', approved: {}, history: {},
  labelOverrides: {}};

function viewSelect(onChange, filterFn){
  const sel=el('select','sel');
  Object.values(D.view_meta).filter(filterFn||(()=>true))
    .sort((a,b)=>a.domain.localeCompare(b.domain))
    .forEach(v=>{const o=el('option');o.value=v.view_id;
      o.textContent=`${v.domain} · ${v.view_name}`;sel.appendChild(o)});
  sel.onchange=()=>onChange(sel.value);
  return sel;
}
function chips(items, onPick){
  const box=el('div','chips');
  items.forEach(t=>{const b=el('button','chip',t);
    b.onclick=()=>onPick(t);box.appendChild(b)});
  return box;
}

function structured(root){
  root.appendChild(el('p','lead',
    '문장을 고치면 조회계획이 즉시 다시 만들어진다. 자연어는 승인된 스키마·필드·연산자·권한으로만 번역되며, '+
    '인식하지 못한 필드는 차단 사유로 남는다. 화면 열과 레이아웃은 고정이다.'));

  const bar=el('div','toolbar');
  let viewId=(D.demo_queries[0]||{}).view_id||Object.keys(D.view_meta)[0];
  const sel=viewSelect(v=>{viewId=v;syncMeta();run()});
  sel.value=viewId;
  const input=el('input','input');
  input.type='text';
  input.placeholder='예) 연체일수 30 이상 그리고 잔액 100억 이상';
  input.value=(D.demo_queries[0]||{}).utterance||'';
  bar.appendChild(sel);bar.appendChild(input);
  root.appendChild(bar);

  const presetBox=el('div');root.appendChild(presetBox);
  const metaLine=el('div','meta');root.appendChild(metaLine);
  const pane=el('div');root.appendChild(pane);

  function syncMeta(){
    const v=D.view_meta[viewId];
    presetBox.innerHTML='';
    const mine=D.demo_queries.filter(q=>q.view_id===viewId).map(q=>q.utterance);
    const usable=v.fields.filter(f=>f.permitted&&f.min_aggregation===1);
    const num=usable.filter(f=>D.data[v.table_ref].rows.some(
      r=>typeof r[D.data[v.table_ref].columns.indexOf(f.field_name)]==='number'));
    const fallback=[];
    if(num.length>=2)fallback.push(`${num[0].korean} 0 초과 그리고 ${num[1].korean} 0 이상`);
    usable.slice(0,2).forEach(f=>fallback.push(`${f.korean} 0 이상`));
    /* 차단 시연. 마스킹 필드가 있으면 그것을 조건으로 쓰는 문장을 하나 준다.
       통제가 실제로 걸리는 걸 눈으로 보여주는 게 시연의 핵심이다. */
    const masked=v.fields.find(f=>f.masking!=='none'||!f.permitted);
    fallback.push(masked
      ? `${masked.korean} X0001  ← 차단 시연`
      /* 마스킹 필드가 없는 View라도 차단 경로는 보여줄 수 있어야 한다.
         조건 없는 문장은 전건 조회로 통과하지 않는다. */
      : '전부 다 보여줘  ← 차단 시연');
    presetBox.appendChild(chips(mine.concat(fallback),t=>{
      input.value=t.replace(/\s*←.*$/,'');run()}));
    metaLine.textContent=
      `View ${v.view_id} · 원장 ${v.table_ref} · 조회 가능 필드 `+
      `${v.fields.filter(f=>f.permitted).length}/${v.fields.length} · 화면 내 데이터 `+
      `${v.embedded_rows.toLocaleString()}행 (모집단 ${v.total_rows.toLocaleString()}행) · 행 상한 ${v.row_limit}`;
  }

  function run(){
    const v=D.view_meta[viewId];
    const plan=RY.compileQuery(input.value,{viewId:v.view_id,asof:D.meta.asof,
      fields:v.fields, population:v.view_name});
    const res=RY.execute(plan, D.data[v.table_ref], v.row_limit);
    renderLivePlan(pane, res.plan, res, v);
  }
  input.addEventListener('input',run);
  syncMeta();run();
}

function renderLivePlan(pane, plan, res, v){
  pane.innerHTML='';
  const c=el('div','card');
  const killed=killedFor(v.domain);       /* 범위형 (부문 밖 조회는 산다) */
  const st=el('div','steps');
  const cond=plan.conditions.map(RY.describe).join(' ∧ ')||'-';
  [['01 의도',plan.utterance.slice(0,40)||'조회'],['02 기준일',plan.asof],
   ['03 모집단',v.view_name],['04 조건',cond],['05 정책',plan.policy]]
   .forEach(([k,val])=>{const b=el('div','step');
     b.appendChild(el('b',null,k));b.appendChild(el('div',null,val));st.appendChild(b)});
  c.appendChild(st);

  const m=el('div','meta');
  m.appendChild(document.createTextNode('조회 지문 '+plan.query_hash+' · 계획 '+plan.plan_id+' · '));
  m.appendChild(pill(killed?'비상정지 (실행 차단)'
    :plan.status==='validated'?'Read-only 실행':'차단',
    killed?'bad':plan.status==='validated'?'good':'bad'));
  c.appendChild(m);
  c.appendChild(el('div','mono','AST: '+plan.ast));
  if(plan.block_reason)c.appendChild(el('div','note','차단 사유 ('+plan.block_reason+')'));
  if(killed)c.appendChild(el('div','note',
    'Kill Switch가 걸려 있어 신규 조회를 실행하지 않는다. 진행 중이던 결정론적 계산은 완료 후 중단된다.'));

  if(plan.status==='validated'&&!killed){
    c.appendChild(el('h3',null,
      `고정 컬럼 결과 · 모집단 ${plan.n_rows.toLocaleString()}건`));
    const src=D.data[v.table_ref];
    c.appendChild(table({table:src.table,columns:res.columns,
      labels:res.columns.map(x=>colLabel(src,src.columns.indexOf(x))),
      rows:res.rows,total:plan.n_rows,shown:res.rows.length}));
    if(v.embedded_rows<v.total_rows)c.appendChild(el('div','meta',
      `※ 화면에는 원장 ${v.total_rows.toLocaleString()}행 중 ${v.embedded_rows.toLocaleString()}행이 실려 있다. 위 건수는 그 범위 기준이다.`));
  }
  pane.appendChild(c);
}

/* ---- 비정형 Adaptive UI (라이브) ---- */
function adaptive(root){
  root.appendChild(el('p','lead',
    '프롬프트를 고치면 레이아웃 제안이 즉시 바뀐다. 프롬프트는 UI 구성안만 만들 뿐 승인되지 않은 필드, '+
    '행 수준 개인정보, 규제산출 변경, 판단 확정은 하지 않는다. 세 검증을 모두 통과해야 사람이 승인할 수 있고, '+
    '승인 전에는 화면에 반영되지 않는다.'));

  const bar=el('div','toolbar');
  let viewId=(D.demo_prompts[0]||{}).view_id||Object.keys(D.view_meta)[0];
  const sel=viewSelect(v=>{viewId=v;syncMeta();run()});
  sel.value=viewId;
  const ta=el('textarea','input');
  ta.rows=2;
  ta.placeholder='예) 자산군별 기여도를 막대차트로 보여주고 아래에 EAD·위험가중치 검토 표를 배치해줘. 상위 10건.';
  ta.value=(D.demo_prompts[0]||{}).prompt||'';
  bar.appendChild(sel);bar.appendChild(ta);
  root.appendChild(bar);

  const presetBox=el('div');root.appendChild(presetBox);
  const fieldHint=el('div','meta');root.appendChild(fieldHint);
  const pane=el('div');root.appendChild(pane);

  function syncMeta(){
    const v=D.view_meta[viewId];
    presetBox.innerHTML='';
    const mine=D.demo_prompts.filter(q=>q.view_id===viewId).map(q=>q.prompt);
    /* 예시 문장은 열 타입을 보고 만든다. 앞에서 4개를 자르면 기준일·식별자
       같은 열이 문장에 들어가 막대에 값 열이 없거나 라벨이 전부 같은,
       요청 의도가 드러나지 않는 레이아웃이 된다 (검수 지적). */
    const frame=D.data[v.table_ref];
    const fi={};frame.columns.forEach((c,k)=>{fi[c]=k});
    const usable=v.fields.filter(f=>f.permitted&&f.masking==='none'
      &&f.field_name in fi);
    const distinct=f=>new Set(frame.rows.slice(0,50)
      .map(r=>r[fi[f.field_name]])).size>1;
    const nums=usable.filter(f=>frame.rows.some(
      r=>typeof r[fi[f.field_name]]==='number')&&distinct(f));
    const cats=usable.filter(f=>frame.rows.some(
      r=>typeof r[fi[f.field_name]]==='string')&&distinct(f));
    const fallback=[];
    if(cats[0]&&nums[0])fallback.push(
      `${cats[0].korean}별 ${nums[0].korean} 기여도를 막대차트로 보여주고 아래에 `+
      `${nums.slice(0,3).map(f=>f.korean).join('·')} 검토 표를 배치해줘. 상위 10건.`);
    if(nums[0])fallback.push(`${nums[0].korean} 추이를 보여줘`);
    if(nums.length>=2)fallback.push(
      `${nums.slice(0,3).map(f=>f.korean).join('와 ')}를 카드로 보여줘`);
    else if(cats[0]&&nums[0])fallback.push(
      `${cats[0].korean}와 ${nums[0].korean}를 카드로 보여줘`);
    presetBox.appendChild(chips(mine.concat(fallback),t=>{ta.value=t;run()}));
    fieldHint.textContent='사용 가능한 열 '+v.fields
      .filter(f=>f.permitted&&f.masking==='none').map(f=>f.korean).join(' · ');
  }
  function run(){
    const v=D.view_meta[viewId];
    const pr=RY.compose(ta.value,{viewId:v.view_id,fields:v.fields,
      rowLimit:v.row_limit});
    renderProposal(pane, pr, v, run);
  }
  ta.addEventListener('input',run);
  syncMeta();run();
}

function renderProposal(pane, pr, v, rerun){
  pane.innerHTML='';
  const approved=STATE.approved[v.view_id];
  const c=el('div','card');
  c.appendChild(el('h3',null,pr.proposal_id+' · '+v.view_name));
  const st=el('div','steps');
  [['필드 권한',pr.field_policy_pass],['스키마·단위',pr.schema_pass],
   ['집계 최소단위',pr.aggregation_pass],
   ['사람 적용승인',!!(approved&&approved.proposal_id===pr.proposal_id)]]
   .forEach(([k,val])=>{const b=el('div','step');
     b.appendChild(el('b',null,k));const d=el('div');d.appendChild(ok(val));
     b.appendChild(d);st.appendChild(b)});
  c.appendChild(st);
  const m=el('div','meta');
  m.appendChild(document.createTextNode('제안 레이아웃 '));
  m.appendChild(el('span','mono',pr.layout_text));
  c.appendChild(m);

  const acts=el('div','toolbar');
  const bPrev=el('button','btn','미리보기 생성');
  const bApp=el('button','btn primary','승인 적용');
  const bRb=el('button','btn','Rollback');
  /* 비상정지는 이 탭에도 미친다. 정형 조회만 막고 여기를 열어 두면
     "정지"가 화면 절반에만 걸린 통제가 된다. */
  bApp.disabled=!pr.all_pass||killedFor(v.domain);
  bRb.disabled=!STATE.history[v.view_id]||!STATE.history[v.view_id].length;
  acts.appendChild(bPrev);acts.appendChild(bApp);acts.appendChild(bRb);
  c.appendChild(acts);

  const status=el('div','meta');
  status.appendChild(pill(
    approved&&approved.proposal_id===pr.proposal_id?'승인 적용':
    pr.all_pass?'미리보기 · 승인 대기':'정책 거부',
    approved&&approved.proposal_id===pr.proposal_id?'good':
    pr.all_pass?'warn':'bad'));
  c.appendChild(status);

  if(pr.rejected_fields.length)c.appendChild(el('div','note',
    '차단된 열 '+pr.rejected_fields.join(', ')+' (미승인 필드는 레이아웃에 세울 수 없다)'));
  else if(!pr.aggregation_pass)c.appendChild(el('div','note',
    '집계 최소단위 위반 (마스킹 필드를 행 단위 열로 세울 수 없다)'));
  else if(!pr.schema_pass)c.appendChild(el('div','note',
    '승인된 열을 하나도 짚지 못했다. 위 "사용 가능한 열"의 이름을 문장에 포함할 것'));

  /* 거부 사유는 화면에 적는다. alert()은 샌드박스 iframe에서 차단되므로
     승인이 거부돼도 아무 말 없이 끝난다. 거부 사실을 보지 못한 채 다음 단계로 넘어간다. */
  const errBox=el('div','note bad');errBox.hidden=true;
  c.appendChild(errBox);

  const previewBox=el('div');
  c.appendChild(previewBox);
  pane.appendChild(c);

  function draw(applied){
    previewBox.innerHTML='';
    if(killedFor(v.domain)){previewBox.appendChild(el('div','note',
      'Kill Switch가 걸려 있어 미리보기·승인을 실행하지 않는다.'));return}
    if(!pr.all_pass){previewBox.appendChild(el('div','note',
      '정책검증 미통과. 미리보기를 그리지 않는다.'));return}
    previewBox.appendChild(el('h3',null,
      applied?'승인 적용 화면':'미리보기 (운영 반영 전)'));
    renderBlocks(previewBox, pr, v);
  }
  bPrev.onclick=()=>{errBox.hidden=true;draw(false);};
  bApp.onclick=()=>{
    try{
      const a=RY.approve(pr,'리스크관리부장');
      (STATE.history[v.view_id]=STATE.history[v.view_id]||[])
        .push(STATE.approved[v.view_id]||null);
      STATE.approved[v.view_id]=a;
      errBox.hidden=true;
      rerun();
    }catch(e){
      errBox.textContent='승인 거부 ('+e.message+')';
      errBox.hidden=false;
    }
  };
  bRb.onclick=()=>{
    const h=STATE.history[v.view_id]||[];
    STATE.approved[v.view_id]=h.pop()||null;
    rerun();
  };
  if(approved&&approved.proposal_id===pr.proposal_id)draw(true);
  else if(pr.all_pass)draw(false);
  else draw(false);
}

function renderBlocks(box, pr, v){
  const frame=D.data[v.table_ref];
  const idx={};frame.columns.forEach((c,i)=>{idx[c]=i});
  const lab=c=>colLabel(frame, idx[c]);          /* 물리명 → 표시명 */
  const cols=pr.columns.filter(c=>c in idx);
  let numCol=cols.find(c=>frame.rows.some(r=>typeof r[idx[c]]==='number'));
  /* "기여도를 막대로"처럼 값 열이 문장에 없으면 요청한 레이아웃 자체가
     사라진다. 이 View의 승인·비마스킹 숫자 열 중 첫 번째로 그리되,
     기본 열을 썼다는 사실을 블록에 공시한다. 조용한 대체는 없다. */
  let numFallback=false;
  if(!numCol){
    const ok=new Set(v.fields.filter(f=>f.permitted&&f.masking==='none')
      .map(f=>f.field_name));
    numCol=frame.columns.find(c=>ok.has(c)&&
      frame.rows.some(r=>typeof r[idx[c]]==='number'));
    if(numCol)numFallback=true;
  }
  const isLabelish=c=>c!==numCol&&
    frame.rows.some(r=>typeof r[idx[c]]==='string')&&
    new Set(frame.rows.slice(0,50).map(r=>r[idx[c]])).size>1; /* 고유값 1개는 라벨이 아니다 */
  let labCol=cols.find(isLabelish)||frame.columns.find(isLabelish)||
    cols.find(c=>c!==numCol&&frame.rows.some(r=>typeof r[idx[c]]==='string'));
  let rows=frame.rows.slice();
  if(numCol)rows.sort((a,b)=>(b[idx[numCol]]||0)-(a[idx[numCol]]||0));
  rows=rows.slice(0,pr.row_limit);
  const sub={table:frame.table,columns:cols,labels:cols.map(lab),
             rows:rows.map(r=>cols.map(c=>r[idx[c]])),
             total:frame.total,shown:rows.length};

  /* 블록 순서는 프롬프트에 나온 순서 그대로다. 사용자가 "위에 차트, 아래에 표"
     라고 쓰면 그 순서로 배치돼야 레이아웃이 바뀐 것으로 읽힌다.
     배치는 2열 그리드다: 차트(막대·추이)는 반 폭으로 나란히 서고, 카드 줄과
     표는 전체 폭을 쓴다. 실무 요청("차트 옆에 차트, 아래 검토 표")의 기본
     구도다. 좁은 화면은 1열로 내려간다. */
  const grid=el('div','blocks');
  const blkHead=(kind,text,phys)=>{
    const h=el('div','blkhead');
    const b=el('span','pill',kind);
    h.appendChild(b);
    const t=el('span',null,text);if(phys)t.title=phys;
    h.appendChild(t);
    return h;
  };
  pr.blocks.forEach(([viz,title])=>{
    const blk=el('div','blk viz-'+viz);  /* 'bar' 원클래스는 막대 트랙(.bar)과 충돌한다 */
    if(viz==='kpi'){
      const g=el('div','grid');
      cols.slice(0,4).forEach(cName=>{
        const j=idx[cName];
        const nums=rows.map(r=>r[j]).filter(x=>typeof x==='number');
        const card=el('div','card kpi');
        const kl=el('div','lab',lab(cName));kl.title=cName;
        card.appendChild(kl);
        if(nums.length){
          const sum=nums.reduce((a,b)=>a+b,0);
          card.appendChild(el('div','val',fmtMoney(sum)));
          card.appendChild(el('div','sub',
            `평균 ${fmtMoney(sum/nums.length)} · 최대 ${fmtMoney(Math.max(...nums))} · ${nums.length}건`));
        } else {
          card.appendChild(el('div','val',String(rows.length)+'행'));
          card.appendChild(el('div','sub','건수'));
        }
        card.appendChild(el('div','ln','↗ 원장 · '+v.table_ref+'.'+cName));
        g.appendChild(card)});
      blk.appendChild(blkHead('카드',title||'핵심 지표'));
      blk.appendChild(g);
    } else if(viz==='bar'&&numCol){
      blk.appendChild(blkHead('막대',`${title} · ${lab(numCol)}`,numCol));
      if(numFallback)blk.appendChild(el('div','meta',
        `값 열이 문장에 없어 이 View의 기본 값 열(${lab(numCol)})로 그렸다. 다른 열은 문장에 이름을 적으면 된다`));
      const top=rows.slice(0,10).map((r,i)=>({
        label:labCol?esc(r[idx[labCol]]):'#'+(i+1),
        value:r[idx[numCol]]||0,
        phys:labCol}));
      /* 상위 밖은 버리지 않고 합쳐 보인다. 조용한 절단 금지 */
      if(rows.length>10){
        const rest=rows.slice(10).reduce((a,r)=>a+(r[idx[numCol]]||0),0);
        top.push({label:`그 외 ${rows.length-10}건`,value:rest,tone:'warn'});
      }
      blk.appendChild(barList(top));
    } else if(viz==='line'&&numCol){
      blk.appendChild(blkHead('추이',`${title} · ${lab(numCol)}`,numCol));
      if(numFallback)blk.appendChild(el('div','meta',
        `값 열이 문장에 없어 이 View의 기본 값 열(${lab(numCol)})로 그렸다`));
      blk.appendChild(areaLine(rows.map(r=>r[idx[numCol]]||0).slice(0,60),
        {label:lab(numCol)}));
    } else if((viz==='bar'||viz==='line')&&!numCol){
      /* 숫자 열이 안 잡혔는데 차트를 조용히 표로 바꾸면 사용자는 요청이
         무시된 줄 모른다. 무엇이 빠졌고 어떻게 고치는지 그 자리에 적는다. */
      blk.appendChild(blkHead(viz==='bar'?'막대':'추이',title||''));
      blk.appendChild(el('div','note',
        (viz==='bar'?'막대차트':'추이')+'는 숫자 열이 필요하다. 문장에 값 열'+
        '(예: '+v.fields.filter(f=>f.permitted&&f.masking==='none')
          .slice(0,3).map(f=>f.korean).join(' · ')+')을 함께 적으면 그린다.'));
      blk.classList.add('viz-table');
    } else {
      blk.appendChild(blkHead('표',title||'검토 표'));
      blk.appendChild(table(sub));
      blk.classList.add('viz-table');
    }
    grid.appendChild(blk);
  });
  box.appendChild(grid);
  box.appendChild(el('div','meta',
    `원장 ${v.table_ref} · 화면 내 ${frame.shown.toLocaleString()}행`+
    (frame.shown<frame.total?` (모집단 ${frame.total.toLocaleString()}행 중)`:' 전량')+
    ` · 정렬 ${numCol?lab(numCol)+' 내림차순':'원장 순'}`));
}

function sparkline(values, title, phys){
  const w=680,h=120,pad=6;
  const max=Math.max(...values,0),min=Math.min(...values,0);
  const span=(max-min)||1;
  const pts=values.slice(0,60).map((v,i,arr)=>{
    const x=pad+i*(w-2*pad)/Math.max(arr.length-1,1);
    const y=h-pad-((v-min)/span)*(h-2*pad);
    return `${x.toFixed(1)},${y.toFixed(1)}`}).join(' ');
  const box=el('div');
  const mt=el('div','meta',title);if(phys)mt.title=phys;
  box.appendChild(mt);
  const ns='http://www.w3.org/2000/svg';
  const svg=document.createElementNS(ns,'svg');
  svg.setAttribute('viewBox',`0 0 ${w} ${h}`);
  svg.setAttribute('class','spark');
  const pl=document.createElementNS(ns,'polyline');
  pl.setAttribute('points',pts);
  pl.setAttribute('fill','none');
  pl.setAttribute('stroke','var(--accent)');
  pl.setAttribute('stroke-width','2');
  svg.appendChild(pl);box.appendChild(svg);
  return box;
}


/* ---- E 위기상황: 심각도별 전 단계 산출과정 ---- */
const TRACE_BLOCKS=['거시','충격축','신용파라미터','신용RWA','시장','은행계정금리',
  '운영','유동성','손익','자본','RWA합계','비율','판정'];

function traceRows(){
  const f=D.data['st_calc_trace'];
  if(!f)return null;
  const i={};f.columns.forEach((c,k)=>{i[c]=k});
  return {f,i};
}
function stressDeepDive(root){
  const T=traceRows();
  if(!T){root.appendChild(el('div','note','추적표가 없다.'));return}
  const {f,i}=T;
  root.appendChild(el('p','lead',
    '14개 충격 축(신용 5 · 시장 4 · 운영 1 · 유동성 2 · 수익 2)이 같은 심도에서 동시에 발동하고, '+
    '신용파라미터 → 신용RWA → 시장 → 은행계정금리 → 운영 → 유동성 → 손익 → 자본 → RWA합계 → '+
    '비율 → 판정으로 전이되는 전 과정을 심각도별·분기별로 펼친다. 각 단계는 산식·투입값·규정 '+
    '근거를 함께 가지며, 마지막 단계 값은 스트레스 경로 결과와 정확히 일치한다.'));

  const scenarios=[...new Set(f.rows.map(r=>r[i.scenario]))];
  const quarters=[...new Set(f.rows.map(r=>r[i.quarter]))];
  let scenario=scenarios[scenarios.length-1], quarter=quarters[0];
  const collapsed=new Set();

  /* 저점 분기 = 선택 시나리오의 보통주자본비율 최솟값 분기 */
  function troughQuarter(sc){
    let best=null,bv=Infinity;
    f.rows.forEach(r=>{
      if(r[i.scenario]===sc&&r[i.step]==='보통주자본비율'&&r[i.value]<bv){
        bv=r[i.value];best=r[i.quarter]}});
    return best;
  }
  quarter=troughQuarter(scenario)||quarters[0];

  const bar=el('div','toolbar');
  const scBox=el('div','chips');
  scenarios.forEach(sc=>{const b=el('button','chip',sc);
    b.onclick=()=>{scenario=sc;quarter=troughQuarter(sc)||quarters[0];draw()};
    scBox.appendChild(b)});
  const qsel=el('select','sel');
  quarters.forEach(q=>{const o=el('option');o.value=q;o.textContent=q;qsel.appendChild(o)});
  qsel.onchange=()=>{quarter=qsel.value;draw()};
  const btnTrough=el('button','btn','저점 분기로');
  btnTrough.onclick=()=>{quarter=troughQuarter(scenario);draw()};
  bar.appendChild(scBox);bar.appendChild(qsel);bar.appendChild(btnTrough);
  root.appendChild(bar);

  const pane=el('div');root.appendChild(pane);

  function pick(sc,q,step){
    const r=f.rows.find(x=>x[i.scenario]===sc&&x[i.quarter]===q&&x[i.step]===step);
    return r?r[i.value]:null;
  }
  function fmtUnit(v,u){
    if(v===null)return '-';
    if(u==='ratio')return (v*100).toFixed(4)+'%';
    if(u==='count')return fmtNum(v);
    return fmtNum(v);
  }

  function draw(){
    [...scBox.children].forEach(b=>b.classList.toggle('on',b.textContent===scenario));
    qsel.value=quarter;
    pane.innerHTML='';

    /* --- 심각도 비교: 같은 분기, 모든 시나리오 --- */
    const cmp=el('div','card');
    cmp.appendChild(el('h3',null,`심각도 비교 · ${quarter}`));
    /* 비율 열은 %로 환산해 둔다. 0.0819를 그대로 두면 금액 열과 자릿수가
       섞여 읽히지 않는다. 열 이름에 단위를 박아 오해를 없앤다. */
    const pc=v=>v===null?null:v*100;
    cmp.appendChild(table({
      columns:['시나리오','충격 심도','PD(충격) %','LGD(충격) %','충당금 전입',
               '트레이딩 손익','운영손실','당기순이익','RWA 합계','LCR %',
               'CET1 %','총자본비율 %','요구치 충족'],
      rows:scenarios.map(sc=>[sc,
        pick(sc,quarter,'충격 심도 (severity)'),
        pc(pick(sc,quarter,'PD (충격 후)')),
        pc(pick(sc,quarter,'LGD (충격 후)')),
        pick(sc,quarter,'충당금 전입'),
        pick(sc,quarter,'트레이딩 손익 합계'),
        pick(sc,quarter,'운영손실 (연간)'),
        pick(sc,quarter,'당기순이익'),
        pick(sc,quarter,'위험가중자산 합계'),
        pc(pick(sc,quarter,'유동성커버리지비율')),
        pc(pick(sc,quarter,'보통주자본비율')),
        pc(pick(sc,quarter,'총자본비율')),
        pick(sc,quarter,'요구치 충족')===1?'충족':'침범']),
      total:scenarios.length,shown:scenarios.length}));
    pane.appendChild(cmp);

    /* --- CET1 경로: 시나리오별 --- */
    const path=el('div','card');
    path.appendChild(el('h3',null,'보통주자본비율 경로 · 심각도별'));
    const series=scenarios.map(sc=>({name:sc,
      values:quarters.map(q=>pick(sc,q,'보통주자본비율'))}));
    const req=pick(scenario,quarter,'보통주자본 요구비율');
    path.appendChild(multiLine(series,quarters,req));
    pane.appendChild(path);

    /* --- 전 단계 워터폴 --- */
    const steps=f.rows.filter(r=>r[i.scenario]===scenario&&r[i.quarter]===quarter)
                      .sort((a,b)=>a[i.seq]-b[i.seq]);
    TRACE_BLOCKS.forEach(bk=>{
      const rows=steps.filter(r=>r[i.block]===bk);
      if(!rows.length)return;
      const c=el('div','card');
      const h=el('button','blockhead');
      h.appendChild(el('span','bnum',String(TRACE_BLOCKS.indexOf(bk)+1).padStart(2,'0')));
      h.appendChild(document.createTextNode(' '+bk));
      h.appendChild(el('small',null,`${rows.length}단계`));
      const body=el('div');
      const open=!collapsed.has(bk);
      h.onclick=()=>{collapsed.has(bk)?collapsed.delete(bk):collapsed.add(bk);draw()};
      c.appendChild(h);
      if(open){
        body.appendChild(table({
          columns:['#','단계','산출값','단위','산식','투입값','근거'],
          rows:rows.map(r=>[r[i.seq],r[i.step],
            fmtUnit(r[i.value],r[i.unit]),r[i.unit],r[i.formula],
            r[i.inputs],r[i.citation]]),
          total:rows.length,shown:rows.length},{numeric:false}));
        c.appendChild(body);
      }
      pane.appendChild(c);
    });

    const note=el('div','note',
      '자본은 세후이익 변화로 롤포워드되며(증분 ECL은 이미 이익에 반영돼 있다), '+
      '산출하한 분모도 함께 충격받는다. 추적표의 값은 스트레스 경로 결과와 정확히 일치한다.');
    pane.appendChild(note);
  }
  draw();
}

function multiLine(series, labels, threshold){
  const w=900,h=240,padL=56,padR=10,padT=12,padB=26;
  const all=series.flatMap(s=>s.values).filter(v=>v!==null);
  if(threshold!==null&&threshold!==undefined)all.push(threshold);
  const max=Math.max(...all),min=Math.min(...all);
  const span=(max-min)||1;
  const x=k=>padL+k*(w-padL-padR)/Math.max(labels.length-1,1);
  const y=v=>h-padB-((v-min)/span)*(h-padT-padB);
  const ns='http://www.w3.org/2000/svg';
  const svg=document.createElementNS(ns,'svg');
  svg.setAttribute('viewBox',`0 0 ${w} ${h}`);
  svg.setAttribute('class','spark');
  svg.style.height='240px';
  /* ok·watch·danger·engine (상태 3색 + 엔진 파랑 (v9.5.0 역할 팔레트)) */
  const colors=['#44d19d','#f6bb56','#fb6472','#42a9ff'];
  if(threshold!==null&&threshold!==undefined){
    const l=document.createElementNS(ns,'line');
    l.setAttribute('x1',padL);l.setAttribute('x2',w-padR);
    l.setAttribute('y1',y(threshold));l.setAttribute('y2',y(threshold));
    l.setAttribute('stroke','currentColor');l.setAttribute('stroke-dasharray','4 3');
    l.setAttribute('opacity','.5');svg.appendChild(l);
    const t=document.createElementNS(ns,'text');
    t.setAttribute('x',padL);t.setAttribute('y',y(threshold)-4);
    t.setAttribute('fill','currentColor');t.setAttribute('font-size','10');
    t.setAttribute('opacity','.7');
    t.textContent=`요구 ${(threshold*100).toFixed(2)}%`;svg.appendChild(t);
  }
  series.forEach((s,si)=>{
    const pts=s.values.map((v,k)=>v===null?null:`${x(k)},${y(v)}`)
                      .filter(Boolean).join(' ');
    const pl=document.createElementNS(ns,'polyline');
    pl.setAttribute('points',pts);pl.setAttribute('fill','none');
    pl.setAttribute('stroke',colors[si%colors.length]);
    pl.setAttribute('stroke-width','2');svg.appendChild(pl);
    const t=document.createElementNS(ns,'text');
    t.setAttribute('x',w-padR);t.setAttribute('y',y(s.values[s.values.length-1])-4);
    t.setAttribute('text-anchor','end');t.setAttribute('font-size','10');
    t.setAttribute('fill',colors[si%colors.length]);
    t.textContent=s.name;svg.appendChild(t);
  });
  labels.forEach((lb,k)=>{
    if(k%2)return;
    const t=document.createElementNS(ns,'text');
    t.setAttribute('x',x(k));t.setAttribute('y',h-8);
    t.setAttribute('text-anchor','middle');t.setAttribute('font-size','9');
    t.setAttribute('fill','currentColor');t.setAttribute('opacity','.6');
    t.textContent=lb;svg.appendChild(t);
  });
  const box=el('div');box.appendChild(svg);return box;
}

/* ---- 부문 뷰 ---- */
function domain(root, product, title, lead){
  root.appendChild(el('p','lead',lead));
  /* 캡처(v9.5.0)식 분석 모듈 (이 부문 원장이 payload에 있으면 그린다) */
  if(DOMAIN_CHARTS[product])DOMAIN_CHARTS[product](root);
  const wrap=el('div','split');
  const list=el('div','list');const pane=el('div');
  const rows=D.catalog.filter(r=>r.product===product);
  rows.forEach((r,i)=>{
    const b=el('button');b.appendChild(document.createTextNode(r.korean));
    b.appendChild(el('small',null,`${r.name} · ${r.rows.toLocaleString()}행 · ${r.columns}열`));
    b.onclick=()=>{[...list.children].forEach(x=>x.classList.remove('on'));
      b.classList.add('on');renderTable(pane,r)};
    list.appendChild(b);
    if(i===0){b.classList.add('on');renderTable(pane,r)}
  });
  wrap.appendChild(list);wrap.appendChild(pane);root.appendChild(wrap);
}
/* 원장 하나를 그림으로도 말한다. 실무진 보고서가 그리는 것을 화면도 그린다.
   부문별 전용 차트(DOMAIN_CHARTS)는 그 부문의 헤드라인을 다루고, 여기는 **선택한
   원장 그 자체**를 다룬다. 원장 107장을 손으로 차트 붙이는 대신 스펙에서 축을
   고른다. 새 원장이 늘어도 자동으로 그려진다.

   축 선택 규칙: 범주형 1열(카디널리티 2~24) × 금액/수치 1열. 규칙에 맞는 축이
   없으면 그리지 않는다. 축을 고를 수 없는 원장에 차트를 붙이면 잘못 읽힌다. */
function autoChart(f,r){
  /* 미리보기(12행)로 분포를 그리면 원장을 잘못 말한다. 2,980행 익스포저
     원장의 12행짜리 막대는 표본이지 분포가 아니다. 전량이 실린 프레임
     (D.data, 107장 중 92장)을 우선 쓰고, 그것이 잘려 있으면 그리지 않는다.
     "축이 없어서" 안 그리는 것과 "표본이라 못 그리는" 것은 다르고, 후자를
     그럴듯하게 그리는 쪽이 더 나쁘다. */
  const full=D.data&&D.data[r.name];
  if(full&&full.shown>=full.total)f=full;
  else if(!f||f.shown<f.total)return null;
  if(!f||!f.rows||f.rows.length<2)return null;
  const cols=f.columns;
  const isNum=i=>f.rows.some(x=>typeof x[i]==='number');
  const uniq=i=>new Set(f.rows.map(x=>x[i])).size;
  /* 기준일·식별자 축은 범주가 아니다. 그리면 의미 없는 막대가 된다 */
  const skip=/(_id|asof|date|digest|hash|note|detail|reason)$/i;
  let cat=-1;
  for(let i=0;i<cols.length;i++){
    if(isNum(i)||skip.test(cols[i]))continue;
    const u=uniq(i);
    if(u>=2&&u<=24){cat=i;break}}
  if(cat<0)return null;
  /* 수치축은 **우선순위 순**으로 고른다. 컬럼 순서로 첫 매치를 잡으면
     `n_exposures`가 `rwa`보다 앞에 있다는 이유로 RWA 원장이 "익스포저 수"를
     그린다. 실제로 그랬다. 건수는 금액이 하나도 없을 때만 쓴다. */
  const PREF=[/^rwa$|_rwa$|^rwa_/i, /^ead|_ead$/i, /exposure_amount|^amount$|_amount$/i,
              /^balance$|_balance$/i, /^ecl$|_ecl$/i, /loss$/i, /notional/i,
              /^value$|_value$/i, /ratio$|share$/i, /^n_|count$/i];
  const nums=cols.map((c,i)=>i).filter(i=>isNum(i)&&!skip.test(cols[i]));
  let val=-1;
  for(const rx of PREF){const hit=nums.find(i=>rx.test(cols[i]));
    if(hit!=null){val=hit;break}}
  if(val<0&&nums.length)val=nums[0];
  if(val<0)return null;

  /* 범주형이 하나 더 있고 그것이 cat 보다 성기면 상위 묶음으로 쓴다. 묶음이
     있으면 트리맵이 2단이 되어 "어느 묶음의 어느 항목인지"를 같이 말한다.
     cat 선택 규칙은 건드리지 않는다. 묶음만 얹는다. */
  const uCat=uniq(cat);
  let grp=-1;
  for(let i=0;i<cols.length;i++){
    if(i===cat||isNum(i)||skip.test(cols[i]))continue;
    const u=uniq(i);
    if(u>=2&&u<=8&&u<uCat){grp=i;break}}

  const agg=new Map();
  f.rows.forEach(x=>{
    const g=grp>=0?String(x[grp]):null;
    const k=String(x[cat]),v=typeof x[val]==='number'?x[val]:0;
    const key=g==null?k:g+'\x00'+k;
    const e=agg.get(key);
    if(e)e.value+=v;else agg.set(key,{group:g,label:k,value:v})});
  let items=[...agg.values()]
    .filter(x=>x.value!==0).sort((a,b)=>Math.abs(b.value)-Math.abs(a.value));
  if(items.length<2)return null;
  const label=(i)=>colLabel(f,i);
  const axis=grp>=0?`${label(grp)} > ${label(cat)}`:label(cat);
  const note=`축 ${axis} × ${label(val)} (스펙에서 자동 선택) · `+
    `원장 전량 ${f.total.toLocaleString()}행 집계`;
  const title=`${r.korean} (${label(val)} 구성)`;
  /* 전부 같은 부호면 구성비를 넓이로 읽는 편이 낫다. 그 외는 막대다 */
  const allPos=items.every(x=>x.value>0);
  if(allPos&&items.length<=24)return donut(items,{title,note});
  return bars(items.slice(0,14),{title,note});
}

function renderTable(pane,r){
  pane.innerHTML='';
  const c=el('div','card');
  c.appendChild(el('h3',null,`${r.korean} · ${r.name}`));
  /* 입도·기본키 문구는 라벨만 옮긴다. 입도 본문·기본키 컬럼명은 TableSpec
     이 정본이라 옮기면 스펙과 화면의 이름이 갈라진다. 수치가 섞인 문장은
     통째로 카탈로그에 넣을 수 없어(값이 원장마다 다르다) 라벨을 따로 잇는다. */
  c.appendChild(rawEl('div','meta',`${T('입도')} (${r.grain})`));
  c.appendChild(rawEl('div','meta',
    `${T('기본키')} ${r.pk} · ${T('외래키')} ${r.fk} · ${T('컬럼')} ${r.columns}`));
  const f=D.previews[r.name];
  if(f){
    const ch=autoChart(f,r);
    if(ch){const box=el('div');box.style.cssText='margin:8px 0 12px';
      box.appendChild(ch);c.appendChild(box)}
    c.appendChild(table(f));
  }else c.appendChild(el('div','note','미실체화 테이블'));
  pane.appendChild(c);
}

/* ---- 감독보고 ---- */
function regulatory(root){
  root.appendChild(el('p','lead',
    '금융감독원 배포 기준 업무보고서. 라인마다 산식·규정근거·산출 모듈을 함께 남긴다. '+
    '서식 식별자(BR-01…)는 내부 코드이며 배포본 서식번호와의 매핑이 필요하다.'));
  const wrap=el('div','split');
  const list=el('div','list');const pane=el('div');
  let sec=null;
  D.forms.forEach((f,i)=>{
    if(f.section!==sec){sec=f.section;list.appendChild(el('div','listsec',sec))}
    const b=el('button');b.appendChild(document.createTextNode(`${f.form_no} ${f.form_name}`));
    b.appendChild(el('small',null,`${f.form_id} · ${f.frequency} · ${f.n_lines}행 · 검증 ${f.n_checks}건 실패 ${f.n_failed}`));
    b.onclick=()=>{[...list.children].forEach(x=>x.classList.remove('on'));
      b.classList.add('on');renderForm(pane,f)};
    list.appendChild(b);
    if(i===0){b.classList.add('on');renderForm(pane,f)}
  });
  wrap.appendChild(list);wrap.appendChild(pane);root.appendChild(wrap);
  const c=el('div','card');c.appendChild(el('h3',null,'서식 자체 대사'));
  c.appendChild(table(D.form_checks,{rowClass:r=>r[6]==='FAIL'?'bad':null}));
  root.appendChild(c);
}
function renderForm(pane,f){
  pane.innerHTML='';
  const c=el('div','card');
  c.appendChild(el('h3',null,`[${f.form_no}] ${f.form_name}`));
  c.appendChild(rawEl('div','meta',`${f.section} · ${T('내부 ID')} ${f.form_id} · ${T('제출주기')} ${f.frequency} · ${T('근거')} ${f.citation}`));
  if(!f.official)c.appendChild(el('div','note',
    '서식번호는 내부 배정 코드다. 금감원 배포본 서식번호 확보 후 대조가 필요하다.'));
  const w=el('div','tw'),t=el('table'),th=el('thead'),tr=el('tr');
  ['라인','항목명','단위','값','산식','규정 근거'].forEach(x=>tr.appendChild(el('th',null,x)));
  th.appendChild(tr);t.appendChild(th);
  const tb=el('tbody');
  f.lines.forEach(ln=>{
    const x=el('tr',ln.subtotal?'sub':null);
    x.appendChild(el('td',null,ln.code));
    x.appendChild(el('td',null,' '.repeat(ln.level*4)+ln.name));
    x.appendChild(el('td',null,ln.unit));
    let v=ln.value;
    if(ln.unit==='ratio'&&typeof v==='number')v=(v*100).toFixed(4)+'%';
    else if(typeof v==='number')v=fmtNum(v);
    x.appendChild(el('td','num',v==null?'-':v));
    x.appendChild(el('td',null,ln.formula));
    x.appendChild(el('td',null,ln.citation));
    tb.appendChild(x)});
  t.appendChild(tb);w.appendChild(t);c.appendChild(w);
  pane.appendChild(c);
}

/* ---- 검증 · 에이전트 · 변경 · 카탈로그 ---- */

/* 3선 도전 가정 목록.

   원문(D.independent.assumptions)은 요청 패키지의 known_assumptions 그대로다.
   같은 문자열이 3선에 요청 지문으로 넘어가므로 화면에서 문장을 고치지 않는다.
   여기서 만드는 것은 접힌 줄에 쓸 요약과 부문 분류뿐이고, 펼치면 원문이 나온다.

   부문은 원문에 없다. 지적번호(F-xxx)와 키워드로 화면이 붙이는 것이라 정확한
   소관 구분이 아니며, 어느 부문에도 안 걸린 항목은 '기타'로 남기고 숨기지
   않는다. 걸러 버리면 분류 규칙이 놓친 가정이 화면에서 사라진다. */
const ASMP_CATS=[
  ['자본',['자본금','CET1','보통주자본','자기자본','레버리지비율','레버리지',
           'AT1','이익잉여금','자본비율','발행자본','완충자본','자본 가정',
           '자본 수준','자본 원장','기본자본','합성 자본']],
  ['RWA',['RWA','위험가중','위험계수','산출하한','output floor','CRM','CVA',
          '신용위험경감','표준방법','내부모형','시장리스크','집합투자','유동화',
          '익스포저']],
  ['ECL',['ECL','기대신용손실','기대손실','Stage','충당금','대손','커버리지',
          '자산건전성','연체일수','PD 스케일']],
  ['서식',['서식','FINES','업무보고서','제출대상','서식번호','가맹점수수료']],
  ['검증통제',['검증','통제','기준선','회귀','항진명제','지문','request_id',
              '대조','대사','등록','게이트','인용']],
  ['데이터',['원장','파생','실측','합성','시드','provenance','난수','통화 구분',
            '대용']],
];

/* 걸린 키워드가 가장 많은 부문. 동점이면 위에 선언된 부문을 쓴다.
   선언 순서가 곧 우선순위이고, 화면 표시 순서도 같다. */
function asmpCat(text){
  const low=text.toLowerCase();
  let best='기타',n=0;
  ASMP_CATS.forEach(([name,kws])=>{
    const hit=kws.reduce((a,k)=>a+(low.includes(k.toLowerCase())?1:0),0);
    if(hit>n){n=hit;best=name}});
  return best;
}

/* 요약 한 줄. 첫 문장을 쓰되 80자를 넘으면 자른다. 문장 끝 마침표는 뒤가
   공백이거나 끝인 것만 인정한다. 소수점(8.1%)·모듈 경로(risk_lib.stress.axes)의
   마침표는 뒤에 글자가 붙어 있어 여기서 걸리지 않는다.
   강조 표시(**)는 접힌 줄에서 잡음이라 요약에서만 뗀다. 전문은 원문 그대로다. */
function asmpSummary(text){
  const t=text.replace(/\*\*/g,'').replace(/\s+/g,' ').trim();
  const m=t.match(/^.*?\.(?=\s|$)/);
  let head=m?m[0]:t;
  if(head.length>80)head=head.slice(0,80).trim()+'…';
  return head;
}

function assumptionList(list){
  const wrap=el('div');
  const rows=list.map(text=>({
    text:text, low:text.toLowerCase(), cat:asmpCat(text),
    ids:[...new Set(text.match(/\bF-[0-9A-Z]{3}\b/g)||[])]}));
  const nId=rows.filter(r=>r.ids.length).length;
  wrap.appendChild(el('div','meta',
    `총 ${rows.length}건 · 지적번호가 붙은 항목 ${nId}건. 접힌 줄은 요약이고 `+
    `펼치면 요청서 원문이 나온다. 부문은 지적번호와 키워드로 나눈 화면 분류이며, `+
    `3선에 넘어가는 문장은 원문 그대로다.`));

  const bar=el('div','toolbar');
  const q=el('input','input');q.type='search';
  q.placeholder='가정 검색 (예: 합성 · 레버리지 · F-603)';
  const bOpen=el('button','btn','전체 펼치기');
  const bShut=el('button','btn','전체 접기');
  bar.appendChild(q);bar.appendChild(bOpen);bar.appendChild(bShut);
  wrap.appendChild(bar);
  const hit=el('div','meta');hit.hidden=true;
  wrap.appendChild(hit);

  const secs=[];
  [...ASMP_CATS.map(c=>c[0]),'기타'].forEach(name=>{
    const mine=rows.filter(r=>r.cat===name);
    if(!mine.length)return;
    const sec=el('div','asmp-sec');
    const hd=el('div','asmp-hd');
    hd.appendChild(el('span',null,name));
    const badge=rawEl('span','pill',TC(mine.length,'건'));
    hd.appendChild(badge);
    sec.appendChild(hd);
    const items=mine.map(r=>{
      const d=el('details','asmp-row');
      const sm=el('summary');
      r.ids.forEach(f=>sm.appendChild(el('span','asmp-fid',f)));
      sm.appendChild(el('span','asmp-sum',asmpSummary(r.text)));
      d.appendChild(sm);
      d.appendChild(el('div','asmp-body',r.text));
      sec.appendChild(d);
      return {node:d,row:r}});
    secs.push({node:sec,badge:badge,items:items,total:mine.length});
    wrap.appendChild(sec)});

  let hadKw=false;
  function apply(){
    const kw=q.value.trim().toLowerCase();
    let vis=0;
    secs.forEach(s=>{
      let n=0;
      s.items.forEach(it=>{
        const on=!kw||it.row.low.includes(kw);
        it.node.hidden=!on;
        /* 검색어가 접힌 전문에만 있으면 요약 줄만 보고는 왜 걸렸는지 알 수
           없다. 걸린 항목은 펴서 보여주고, 검색어를 지우면 도로 접는다. */
        if(kw)it.node.open=on; else if(hadKw)it.node.open=false;
        if(on)n++});
      s.node.hidden=n===0;
      s.badge.textContent=(kw&&n<s.total)?(n+'/'+TC(s.total,'건')):TC(s.total,'건');
      vis+=n});
    hit.textContent=`검색어 '${q.value.trim()}' (${rows.length}건 중 ${vis}건)`;
    hit.hidden=!kw;
    hadKw=!!kw;
  }
  q.addEventListener('input',apply);
  bOpen.onclick=()=>secs.forEach(s=>s.items.forEach(
    it=>{if(!it.node.hidden)it.node.open=true}));
  bShut.onclick=()=>secs.forEach(s=>s.items.forEach(it=>{it.node.open=false}));
  apply();
  return wrap;
}

function validation(root){
  root.appendChild(el('p','lead',
    '검증은 두 층이다. 자체검증(2선)은 같은 코드·같은 가정으로 점검하고, 상시 독립검증(3선)은 '+
    '개발조직과 분리된 적합성검증 팀에이전트가 다시 계산한다. 2선 PASS만으로는 결재할 수 없다.'));

  /* --- 3선 게이트 --- */
  const iv=D.independent;
  const g=el('div','card');
  g.appendChild(el('h3',null,'상시 독립검증 (3선) 게이트'));
  const tone=iv.status==='적합'?'good':iv.status==='부적합'?'bad':'warn';
  const kg=el('div','grid');
  [['게이트 상태',iv.status,tone],['요청 식별자',iv.request_id,''],
   ['수신 팀',iv.requested_to,''],['수신 브랜치',iv.branch,''],
   ['재계산 대상',iv.n_targets+'종',''],
   ['자체검증(2선)',iv.self_validation,'']].forEach(([k,v,t])=>{
    const c=el('div','card kpi');
    c.appendChild(el('div','lab',k));
    c.appendChild(el('div','val '+(t||''),String(v)));
    kg.appendChild(c)});
  g.appendChild(kg);
  g.appendChild(el('div','note',
    '이 판정은 화면을 산출한 실행 시점의 스냅샷이다. 이후 도착한 3선 응답이나 '+
    '판정 변경은 이 화면에 반영되지 않는다. 현재 상태의 정본은 저장소 게이트'+
    '(check_gate)다.'));
  g.appendChild(el('div','note',iv.reason+
    '. 게이트는 fail-closed다. 응답이 없으면 상태가 응답대기로 남고 결재 상신이 막힌다.'+
    '판정이 경부적합이면 상태는 조건부이며, 결재 책임자가 잔여위험·후속조건·이행기한·'+
    '배포 범위를 기록해야만 통과한다. 조건부는 후속조건 이행을 전제로 한 상태이며 적합 판정과 구분한다.'));
  g.appendChild(el('h3',null,'독립 재계산 대상'));
  g.appendChild(table(D.independent_targets));
  g.appendChild(el('h3',null,
    `3선이 도전해야 할 가정 (${iv.assumptions.length}건)`));
  g.appendChild(iv.assumptions.length
    ? assumptionList(iv.assumptions)
    : el('div','note bad',
        '가정 목록이 비어 있다. 독립검증 요청 패키지가 만들어지지 않았다.'));
  root.appendChild(g);

  const c=el('div','card');
  c.appendChild(el('h3',null,'자체검증 (2선) 결과 (같은 코드·같은 가정)'));
  c.appendChild(table(D.validation,{rowClass:r=>r[2]==='FAIL'?'bad':null}));
  root.appendChild(c);
}
function agents(root){
  root.appendChild(el('p','lead',
    '계획·등록도구·데이터범위·승인·로그를 확인한다. 사람의 승인을 받기 전 에이전트는 조회 전용 또는 제안 전용이며, '+
    '운영 반영 권한(write_allowed)은 전 에이전트가 거짓이다.'));
  const a=el('div','card');a.appendChild(el('h3',null,'에이전트 레지스트리 · 최소 권한'));
  a.appendChild(table(D.agents));root.appendChild(a);
  const b=el('div','card');b.appendChild(el('h3',null,'활동 원장 (주체·도구·출력·게이트)'));
  b.appendChild(table(D.activity));root.appendChild(b);
  const k=el('div','card');k.appendChild(el('h3',null,'범위형 비상정지 이력'));
  k.appendChild(table(D.killswitch));
  k.appendChild(el('div','note',
    '안전중지는 진행 중 결정론적 계산을 마치고 신규 도구 호출을 차단한다. 중요 범위는 독립된 2차 확인이 필요하다.'));
  root.appendChild(k);
}
function changes(root){
  root.appendChild(el('p','lead',
    '신규 익스포저·상품·규정·데이터 변경의 영향을 분석하고 계산·보고서를 매핑하며 통제된 브랜치와 테스트를 작성한다. 자동배포하지 않는다.'));
  [['변경 요청',D.changes],['영향도 맵 · 데이터→산식→보고→담당자',D.change_impacts],
   ['회귀테스트 매트릭스',D.change_tests]].forEach(([t,f])=>{
    const c=el('div','card');c.appendChild(el('h3',null,t));
    c.appendChild(table(f));root.appendChild(c)});
  const m=el('div','card');m.appendChild(el('h3',null,'표준코드 매핑 (미매핑은 산출 누락으로 직결)'));
  m.appendChild(table(D.canonical_map));root.appendChild(m);
}
function catalogView(root){
  root.appendChild(el('p','lead',
    `정규 테이블 ${D.meta.n_tables}장 · 컬럼 ${D.meta.n_columns}개 · 실체화 행 ${D.meta.n_rows.toLocaleString()}행. `+
    '각 View의 필드 권한과 마스킹 정책이 조회 가능 범위를 결정한다.'));
  const sel=el('select','sel');
  const opt=el('option');opt.value='';opt.textContent='전체 부문';sel.appendChild(opt);
  D.domains.forEach(d=>{const o=el('option');o.value=d;o.textContent=d;sel.appendChild(o)});
  root.appendChild(sel);
  const c=el('div','card');root.appendChild(c);
  const draw=()=>{c.innerHTML='';
    const rows=D.catalog.filter(r=>!sel.value||r.product===sel.value);
    c.appendChild(el('h3',null,`테이블 ${rows.length}장`));
    c.appendChild(table({columns:['테이블','한글명','부문','입도','컬럼','기본키','FK','행'],
      rows:rows.map(r=>[r.name,r.korean,r.product,r.grain,r.columns,r.pk,r.fk,r.rows]),
      total:rows.length,shown:rows.length}))};
  sel.onchange=draw;draw();
  const p=el('div','card');p.appendChild(el('h3',null,'승인 View 원장'));
  p.appendChild(table(D.views));root.appendChild(p);
}

/* ---- ⚙ 설정 ----
   설정 화면의 원칙: **화면은 계산기가 아니다.** 표시명·기준일 전환은 세션
   안에서 즉시 적용되지만(산출값 무관), 서식번호 매핑·시나리오 파라미터는
   산출물의 정체를 바꾸므로 화면에서 적용하지 않는다. 변경 제안서를 만들어
   주고, 적용은 코드 반영 + 파이프라인 재실행(2선 자체검증 + 3선 재요청)으로만
   이뤄진다. 화면에서 바꾼 값이 제출 지문과 다른 수치를 그리는 순간 그 화면은
   산출물이 아니라 조작이 된다. */

function runRegistry(root){
  const c=el('div','card set-runs');
  c.appendChild(el('h3',null,'실은 실행 (기준일 전환 대상)'));
  c.appendChild(el('div','meta',
    '기준일 전환은 미리 산출해 실은 실행 사이의 전환이다. 새 기준일은 '+
    'run_pipeline 재실행으로만 생긴다. 화면이 즉석에서 만들 수 없다. '+
    '게이트 열은 각 실행을 산출한 시점의 스냅샷이며, 이후 3선 응답은 '+
    '반영되지 않는다.'));
  c.appendChild(table({columns:['기준일','실행 ID','산출 지문','시드',
      '3선 요청','게이트','자체검증(2선)'],
    rows:Object.keys(RUNS).sort().map(a=>{const r=RUNS[a];
      return [a,r.meta.run_id,r.meta.digest.slice(0,12),r.meta.seed,
        r.independent.request_id,r.independent.status,
        r.independent.self_validation]}),
    total:Object.keys(RUNS).length,shown:Object.keys(RUNS).length},
    {numeric:false}));
  root.appendChild(c);
}

function labelSettings(root){
  const c=el('div','card set-labels');
  c.appendChild(el('h3',null,'컬럼 표시명 매핑'));
  c.appendChild(el('div','meta',
    '정본은 데이터모델 카탈로그(ColumnSpec.korean)다. 여기서 바꾼 표시명은 이 '+
    '세션의 화면에만 적용되며, 영구 반영은 카탈로그 수정으로 한다. 물리명은 '+
    '항상 열 머리글 툴팁으로 남는다.'));
  const bar=el('div','toolbar');
  const sel=el('select','sel');
  Object.keys(D.data).sort().forEach(t=>{const o=el('option');
    o.value=t;o.textContent=t;sel.appendChild(o)});
  bar.appendChild(sel);c.appendChild(bar);
  const pane=el('div');c.appendChild(pane);
  function draw(){
    pane.innerHTML='';
    const f=D.data[sel.value];
    const ovr=STATE.labelOverrides[sel.value]||{};
    const w=el('div','tw'),t=el('table'),th=el('thead'),tr=el('tr');
    ['물리명','카탈로그 표시명','세션 재정의'].forEach(x=>tr.appendChild(el('th',null,x)));
    th.appendChild(tr);t.appendChild(th);
    const tb=el('tbody'), inputs={};
    f.columns.forEach((cName,i)=>{
      const x=el('tr');
      x.appendChild(el('td','mono',cName));
      x.appendChild(el('td',null,(f.labels&&f.labels[i])||'-'));
      const td=el('td');
      const inp=el('input','input');inp.type='text';
      inp.value=ovr[cName]||'';inp.placeholder='(카탈로그 표시명 사용)';
      inp.style.minWidth='140px';
      inputs[cName]=inp;td.appendChild(inp);x.appendChild(td);
      tb.appendChild(x)});
    t.appendChild(tb);w.appendChild(t);pane.appendChild(w);
    const acts=el('div','toolbar');
    const apply=el('button','btn primary','세션에 적용');
    const reset=el('button','btn','재정의 지우기');
    apply.onclick=()=>{
      const m={};
      Object.entries(inputs).forEach(([k,inp])=>{
        const v=inp.value.trim();if(v)m[k]=v});
      if(Object.keys(m).length)STATE.labelOverrides[sel.value]=m;
      else delete STATE.labelOverrides[sel.value];
      repaintAll();};
    reset.onclick=()=>{delete STATE.labelOverrides[sel.value];repaintAll();};
    acts.appendChild(apply);acts.appendChild(reset);pane.appendChild(acts);
  }
  sel.onchange=draw;draw();
  root.appendChild(c);
}

/* FINES 서식번호 형식. 배포 코드는 B/BA/BF + 숫자 3~5자리(+ -가지번호),
   내부 관리 서식은 RM-####. 마스터(fss_master)의 실존 형식에서 온 규칙이다.
   B10101(금리인하요구권)·B11101~07(투자자문업)처럼 5자리 숫자부가 실재하므로
   4자리로 자르면 실코드 9종이 형식 위반으로 거부된다. */
const FORM_NO_RE=/^(?:B[AF]?\d{3,5}(?:-\d+)?|RM-\d{4})$/;
/* 중복 비교는 표시문자열이 아니라 코드로 한다. 내부관리 서식의 form_no는
   "RM-6401 (내부관리)"처럼 접미사가 붙어, 그대로 키로 쓰면 "RM-6401" 입력이
   중복 검사를 지나간다. */
const formNoKey=s=>String(s).split(' ')[0];

function formMapSettings(root){
  const c=el('div','card set-formmap');
  c.appendChild(el('h3',null,'서식번호 매핑 (내부 코드 ↔ 금감원 배포 서식번호)'));
  c.appendChild(el('div','meta',
    '서식번호는 제출본을 식별한다. 이 화면은 매핑 변경 제안서만 만들고, 적용은 '+
    'risk_lib/regulatory/form_ids.py 반영 후 파이프라인 재실행으로 한다.'));
  const w=el('div','tw'),t=el('table'),th=el('thead'),tr=el('tr');
  ['내부 코드','서식명','현행 서식번호','배포본 확정','변경 제안'].forEach(
    x=>tr.appendChild(el('th',null,x)));
  th.appendChild(tr);t.appendChild(th);
  const tb=el('tbody'), inputs={};
  D.forms.forEach(f=>{
    const x=el('tr');
    x.appendChild(el('td','mono',f.form_id));
    x.appendChild(el('td',null,f.form_name));
    x.appendChild(el('td','mono',f.form_no));
    const td0=el('td');td0.appendChild(pill(f.official?'확정':'내부 배정',
      f.official?'good':'warn'));x.appendChild(td0);
    const td=el('td');
    const inp=el('input','input');inp.type='text';inp.placeholder='(유지)';
    inp.style.minWidth='110px';inputs[f.form_id]=inp;
    td.appendChild(inp);x.appendChild(td);
    tb.appendChild(x)});
  t.appendChild(tb);w.appendChild(t);c.appendChild(w);

  const acts=el('div','toolbar');
  const gen=el('button','btn primary','변경 제안 생성');
  acts.appendChild(gen);c.appendChild(acts);
  const err=el('div','note bad');err.hidden=true;c.appendChild(err);
  const out=el('pre','mono');out.style.whiteSpace='pre-wrap';c.appendChild(out);
  gen.onclick=()=>{
    err.hidden=true;out.textContent='';
    if(STATE.killed){err.textContent='비상정지 중. 변경 제안을 만들지 않는다.';
      err.hidden=false;return}
    const changes=[],bad=[];
    const used={};D.forms.forEach(f=>{used[formNoKey(f.form_no)]=f.form_id});
    Object.entries(inputs).forEach(([fid,inp])=>{
      const v=inp.value.trim();if(!v)return;
      if(!FORM_NO_RE.test(v)){bad.push(`${fid}: '${v}' (형식 위반 (B/BA/BF+숫자(-가지) 또는 RM-####))`);return}
      if(used[formNoKey(v)]&&used[formNoKey(v)]!==fid){bad.push(`${fid}: '${v}' (${used[formNoKey(v)]}가 이미 사용)`);return}
      const cur=D.forms.find(f=>f.form_id===fid);
      used[formNoKey(v)]=fid;       /* 제안값끼리의 충돌도 잡는다 */
      changes.push({form_id:fid,from:cur.form_no,to:v})});
    if(bad.length){err.textContent='검증 실패 '+bad.length+'건 ('+bad.join(' · ')+')';
      err.hidden=false;return}
    if(!changes.length){err.textContent='변경된 행이 없다.';err.hidden=false;return}
    out.textContent=JSON.stringify({
      proposal:'서식번호 매핑 변경',asof:D.meta.asof,run_id:D.meta.run_id,
      changes,
      apply_path:'risk_lib/regulatory/form_ids.py',
      procedure:['코드 반영','파이프라인 재실행','자체검증(2선) FAIL 0 확인',
                 '독립검증(3선) 재요청','게이트 통과 후 결재'],
      note:'화면에는 적용되지 않는다. 서식번호는 제출 지문에 포함된다.'},null,2);
  };
  root.appendChild(c);
}

function scenarioSettings(root){
  const T=traceRows();
  const c=el('div','card set-scenario');
  c.appendChild(el('h3',null,'위기상황 시나리오 설정 (충격 축 파라미터)'));
  c.appendChild(el('div','meta',
    '충격 축 14종의 단위충격 × 심도 구조를 편집해 변경 제안서를 만든다. '+
    '화면은 재계산하지 않는다. 시나리오 파라미터는 RWA·비율·판정 전체에 '+
    '전이되므로, 적용은 파이프라인 재실행과 검증 두 층을 다시 거쳐야 한다.'));
  if(!T){c.appendChild(el('div','note','추적표가 없다.'));root.appendChild(c);return}
  const {f,i}=T;
  const scenarios=[...new Set(f.rows.map(r=>r[i.scenario]))];
  /* 축별 단위충격은 산식 문자열('심도 × 단위충격(0.05 ratio)')에서 읽는다.
     추적표가 정본이고, 여기 따로 적으면 두 벌이 갈라진다. */
  const axes=[];const seen=new Set();
  f.rows.forEach(r=>{
    if(r[i.block]!=='충격축'||seen.has(r[i.step]))return;
    seen.add(r[i.step]);
    const m=/단위충격\(([-\d.]+)\s*(\S+)\)/.exec(r[i.formula]||'');
    axes.push({step:r[i.step],unit:m?m[2]:r[i.unit],base:m?parseFloat(m[1]):null})});
  /* 심도는 분기마다 다르고 정점까지 선형 상승한다. 첫 행(1분기)을 집으면
     시나리오 정의 심도를 최대 4~5배 과소 표기한다. 검토자가 단위충격 × 심도로
     정점 충격을 어림하는 화면이므로 **정점(최대) 심도**를 뽑는다. */
  const sever={};
  scenarios.forEach(sc=>{
    let mx=null;
    f.rows.forEach(x=>{
      if(x[i.scenario]===sc&&/심도/.test(x[i.step])&&typeof x[i.value]==='number')
        mx=mx===null?x[i.value]:Math.max(mx,x[i.value])});
    sever[sc]=mx});

  const w=el('div','tw'),t=el('table'),th=el('thead'),tr=el('tr');
  ['충격 축','단위','현행 단위충격','제안 단위충격'].forEach(
    x=>tr.appendChild(el('th',null,x)));
  th.appendChild(tr);t.appendChild(th);
  const tb=el('tbody'),inputs={};
  axes.forEach(a=>{
    const x=el('tr');
    x.appendChild(el('td',null,a.step));
    x.appendChild(el('td','mono',a.unit));
    x.appendChild(el('td','num',a.base===null?'-':String(a.base)));
    const td=el('td');
    const inp=el('input','input');inp.type='text';inp.placeholder='(유지)';
    inp.style.minWidth='90px';inputs[a.step]=inp;
    td.appendChild(inp);x.appendChild(td);tb.appendChild(x)});
  t.appendChild(tb);w.appendChild(t);c.appendChild(w);
  c.appendChild(el('div','meta','시나리오별 정점 심도 '+scenarios.map(
    sc=>`${sc} ${sever[sc]===null?'-':sever[sc]}`).join(' · ')+
    ' (분기별 심도는 정점까지 선형 상승)'));

  const acts=el('div','toolbar');
  const gen=el('button','btn primary','변경 제안 생성');
  acts.appendChild(gen);c.appendChild(acts);
  const err=el('div','note bad');err.hidden=true;c.appendChild(err);
  const out=el('pre','mono');out.style.whiteSpace='pre-wrap';c.appendChild(out);
  gen.onclick=()=>{
    err.hidden=true;out.textContent='';
    if(STATE.killed){err.textContent='비상정지 중. 변경 제안을 만들지 않는다.';
      err.hidden=false;return}
    const changes=[],bad=[];
    Object.entries(inputs).forEach(([step,inp])=>{
      const v=inp.value.trim();if(!v)return;
      if(!/^-?\d+(?:\.\d+)?$/.test(v)){bad.push(`${step}: '${v}' (숫자가 아니다)`);return}
      const cur=axes.find(a=>a.step===step);
      changes.push({axis:step,unit:cur.unit,from:cur.base,to:parseFloat(v)})});
    if(bad.length){err.textContent='검증 실패 ('+bad.join(' · ')+')';
      err.hidden=false;return}
    if(!changes.length){err.textContent='변경된 축이 없다.';err.hidden=false;return}
    out.textContent=JSON.stringify({
      proposal:'위기상황 시나리오 충격 축 변경',asof:D.meta.asof,
      run_id:D.meta.run_id,changes,
      impact:['신용파라미터→신용RWA→시장→은행계정금리→운영→유동성→손익→자본→비율→판정 전 단계',
              '업무보고서 위기상황 서식','자본계획·회복계획 연계 경보'],
      apply_path:'risk_lib/stress/axes.py (충격 축 · 심도 정의)',
      procedure:['코드 반영','파이프라인 재실행','자체검증(2선) FAIL 0 확인',
                 '독립검증(3선) 재요청','게이트 통과 후 결재'],
      note:'화면은 재계산하지 않는다.'},null,2);
  };
  root.appendChild(c);
}

/* ---- 요건 추적 (v9.6.0 BRD 131건 대비 구현 재고조사) ---- */
/* 경영진 요약. 02_reports/executive.html 과 **같은 생성기**(risk_lib.html_exec)
   에서 나온 값을 그린다. 화면이 따로 계산하지 않으므로 두 산출물의 수치가
   갈라질 자리가 없다. 서식이 달라도 같은 생성기의 산출값을 쓴다. */
/* 브리핑·액션 문장에 박힌 딥링크는 리포트 페이지(ops/*.html)를 가리킨다. 화면에는
   그 파일이 없으므로 스튜디오 화면으로 바꿔 건다. 대응 화면이 없는 셋(자본 스택·
   귀속분석·RAF)은 이 화면 안에 절로 두고 그리로 스크롤한다. */
const EXEC_LINKS={
  'ops/32_capital_stack.html':          {sec:'sec-capital-stack'},
  'ops/23_attribution.html':            {sec:'sec-rwa-attr'},
  'ops/19_raf.html':                    {sec:'sec-raf'},
  'ops/37_macro_scenario.html':         {tab:'ECL'},
  'ops/38_provisioning_attribution.html':{tab:'ECL'},
  'ops/18_concentration_deep.html':     {tab:'한도관리'},
  'ops/49_ccar_path.html':              {tab:'위기상황'},
  'ops/48_reverse_stress_multi.html':   {tab:'역스트레스'},
  'ops/11b_lcr.html':                   {tab:'유동성리스크'},
  'ops/61_intraday.html':               {tab:'유동성리스크'},
  'ops/17_model_risk.html':             {tab:'모형리스크'},
};
function wireExecLinks(scope){
  scope.querySelectorAll('a[href]').forEach(a=>{
    const raw=a.getAttribute('href')||'';
    const key=Object.keys(EXEC_LINKS).find(k=>raw.indexOf(k)>=0);
    if(!key){                       /* 매핑이 없으면 링크를 없앤다. 죽은 링크를
                                       남기면 눌러 보고 나서야 없다는 걸 안다 */
      const t=el('span','meta',a.textContent);a.replaceWith(t);return}
    const to=EXEC_LINKS[key];
    a.removeAttribute('href');a.style.cursor='pointer';
    a.title=to.tab?`${to.tab} 화면으로 이동`:'아래 절로 이동';
    a.onclick=e=>{e.preventDefault();
      /* nav 버튼 순서는 NAVGROUPS 트리 순서라 TABS 인덱스와 다르다.
         인덱스로 집으면 엉뚱한 화면이 열린다(실제로 LCR이 코드 매핑으로 갔다).
         라벨로 찾는다. */
      if(to.tab){const btn=[...document.querySelectorAll('nav button')]
          .find(b=>b.textContent.trim()===to.tab);
        if(btn)btn.click()}
      else{const s=document.getElementById(to.sec);
        if(s)s.scrollIntoView({behavior:'smooth',block:'start'})}};
  });
}

function executiveReport(root){
  const E=D.executive;
  if(!E){root.appendChild(el('p','lead','경영진 요약 데이터가 없다.'));return}
  const F=E.facts;
  const pct=v=>(v*100).toFixed(2)+'%';
  const pp=v=>(v>=0?'+':'')+v.toFixed(3)+'%p';

  root.appendChild(el('p','lead',
    '02_reports/executive.html 과 같은 산출값이다. 문장 안의 링크는 해당 화면으로 '+
    '이동하고, 자본 스택·RWA 귀속·RAF는 아래 절에 있다.'));

  /* --- 자본·유동성 한눈에 --- */
  const g=el('div','grid');
  [['보통주자본비율(CET1)',pct(F.cet1),
    '최저 대비 '+pp(F.cet1_surplus_pp),F.cet1_surplus_pp<0?'bad':'good'],
   ['최대 RWA 구성',F.top_rwa_component,
    '비중 '+pct(F.top_rwa_share),''],
   /* 바로 아래 CRO 브리핑이 십억원으로 말한다. 같은 화면에서 같은 수치가
      두 표기로 나오면 읽는 사람이 둘을 다른 값으로 본다. */
   ['ECL, PIT(확률가중)',(F.pit/1e9).toFixed(1)+'십억원',
    'TTC '+(F.ttc/1e9).toFixed(1)+'십억원 대비 '
    +(F.gap_pct>=0?'+':'')+F.gap_pct.toFixed(1)+'%',''],
   ['유동성커버리지(LCR)',pct(F.lcr),
    'NSFR '+pct(F.nsfr),F.lcr<1?'bad':'good'],
   ['집중도 최대 축',F.conc_dim,
    'HHI '+F.conc_hhi.toFixed(4)+' · 최대 '+pct(F.conc_top1),''],
   ['역스트레스 임계 심도',F.rev_severity.toFixed(4),
    '함의 GDP 충격 '+(F.rev_gdp*100).toFixed(2)+'%',
    F.rev_severity<1?'bad':'good']
  ].forEach(([lab,val,sub,tone])=>{
    const c=el('div','card kpi');
    c.appendChild(el('div','lab',lab));
    c.appendChild(el('div','val '+(tone||''),val));
    c.appendChild(el('div','sub',sub));
    g.appendChild(c)});
  root.appendChild(g);

  /* --- CRO 브리핑 --- */
  if(E.briefing&&E.briefing.length){
    const c=el('div','card');
    c.appendChild(el('h3',null,'CRO 브리핑'));
    const ul=el('ul');ul.style.cssText='margin:6px 0 0 18px;font-size:12px';
    E.briefing.forEach(t=>{const li=el('li');li.innerHTML=t;ul.appendChild(li)});
    c.appendChild(ul);
    wireExecLinks(ul);
    c.appendChild(el('div','meta','원장에서 규칙으로 생성 · 외부 LLM 호출 없음'));
    root.appendChild(c);
  }

  /* --- 자본 스택 (리포트 ops/32) --- */
  const cs=D.data&&D.data['cap_stack'];
  if(cs&&cs.rows.length){
    const c=el('div','card');c.id='sec-capital-stack';
    c.appendChild(el('h3',null,'자본 스택 (계층별 요구 대비 여유)'));
    const i=frameIdx(cs);
    c.appendChild(hbars(cs.rows.map(r=>({
      label:r[i.tier],value:r[i.amount],
      sub:`비율 ${(r[i.ratio]*100).toFixed(2)}% · 요구 ${(r[i.required]*100).toFixed(2)}%`+
          ` · ${r[i.surplus]>=0?'여유':'부족'} ${(Math.abs(r[i.surplus])*100).toFixed(3)}%p`,
      tone:r[i.surplus]<0?'bad':'good'})),
      {title:'계층별 자본과 규제 요구',src:srcMeta(cs)}));
    const short=cs.rows.filter(r=>r[i.surplus]<0).map(r=>r[i.tier]);
    if(short.length)c.appendChild(el('div','meta bad',
      `요구 미달 계층. ${short.join(' · ')}. 배당·성과급 제한 대상.`));
    root.appendChild(c);
  }

  /* --- RWA 귀속 (리포트 ops/23) --- */
  const at=E.attribution;
  if(at&&at.length){
    const c=el('div','card');c.id='sec-rwa-attr';
    c.appendChild(el('h3',null,'위험가중자산 귀속 (구성요소별 비중)'));
    c.appendChild(donut(at.map(x=>({label:x.component,value:x.rwa})),
      {note:'구성요소별 위험가중자산 · 합계는 공표 RWA와 같다'}));
    root.appendChild(c);
  }

  /* --- 심각 시나리오 (리포트 ops/49) --- */

  /* --- KRI 스코어카드 (리포트(viz_advanced.kri_scorecard)와 같은 카드 격자) --- */
  if(E.kris&&E.kris.length){
    const c=el('div','card');c.id='sec-raf';
    c.appendChild(el('h3',null,'KRI 스코어카드 (Risk Appetite Framework)'));
    c.appendChild(el('p','meta',
      '12개 핵심 지표를 board/management/operational 3단 한계로 채점. RED는 board '+
      '한계 위반(즉시 대응), AMBER는 management 한계(에스컬레이션), WATCH는 '+
      'operational 조기경보, GREEN은 한계 이내.'));
    c.appendChild(kriCards(E.kris));
    const n=g=>E.kris.filter(k=>k.grade===g).length;
    c.appendChild(el('div','meta',
      `RED ${n('RED')} · AMBER ${n('AMBER')} · WATCH ${n('WATCH')} · `+
      `GREEN ${n('GREEN')} · 전체 ${E.kris.length} (임계는 RAF 원장에서 온다)`));
    root.appendChild(c);
  }

  /* --- CRO 액션 --- */
  if(E.actions&&E.actions.length){
    const c=el('div','card');
    c.appendChild(el('h3',null,'CRO 액션 (즉시·단기 조치)'));
    const ul=el('ul');ul.style.cssText='margin:6px 0 0 18px;font-size:12px';
    E.actions.forEach(t=>{const li=el('li');li.innerHTML=t;ul.appendChild(li)});
    c.appendChild(ul);
    wireExecLinks(ul);
    c.appendChild(el('div','meta','RAF 임계 위반과 자체검증 WARN·FAIL에서 자동 추출'));
    root.appendChild(c);
  }

  /* --- 위기 시나리오 --- */
  if(F.sev){
    const c=el('div','card');
    c.appendChild(el('h3',null,'심각 시나리오 (자본 저점)'));
    c.appendChild(dotlist([
      {label:'CET1 저점 '+pct(F.sev.trough)+' ('+F.sev.trough_q+')',
       tone:F.sev.first_breach?'bad':'good'},
      {label:'종료 시점 CET1 '+pct(F.sev.end),tone:'muted'},
      {label:F.sev.first_breach
        ? '최초 침범 '+F.sev.first_breach+' (침범 비율 '+(F.sev.breach_ratio||'-')+')'
        : '요구 비율 침범 없음',
       tone:F.sev.first_breach?'bad':'good'},
    ]));
    root.appendChild(c);
  }

  root.appendChild(el('div','meta','출처 '+E.source));
  wireExecLinks(root);
}

function reqTrace(root){
  const R=D.req_trace;
  root.appendChild(el('p','lead',
    'RYNTA v9.6.0 업무요건정의서 Level 1 요건 131건을 이 하네스의 실재 증빙'+
    '(모듈·원장·화면·테스트)에 대조한다. 증빙 참조는 tests/test_req_trace.py 가 '+
    '실재를 검증한 것만 싣는다. 미반영 요건도 그대로 표시한다.'));

  const c0=el('div','card');
  c0.appendChild(el('h3',null,'커버리지 '+R.coverage.source));
  const g=el('div','grid');
  [['반영',R.coverage['반영'],'good'],['부분',R.coverage['부분'],'warn'],
   ['미반영',R.coverage['미반영'],'bad'],
   ['검증된 증빙 참조',R.coverage.n_evidence,'']].forEach(([k,v,t])=>{
    const c=el('div','card kpi');
    c.appendChild(el('div','lab',k));
    c.appendChild(el('div','val '+t,String(v)));
    if(k!=='검증된 증빙 참조')
      c.appendChild(el('div','sub',(v/R.coverage.n*100).toFixed(0)+'% / '+R.coverage.n+'건'));
    g.appendChild(c)});
  c0.appendChild(g);
  c0.appendChild(meter('반영(부분 포함 안 함)',R.coverage['반영'],R.coverage.n));
  c0.appendChild(el('div','meta','원문 SHA-256 '+R.coverage.source_sha256.slice(0,16)+
    '… (레지스터는 tools/gen_requirements.py 가 원문에서 생성한다)'));
  root.appendChild(c0);

  const bar=el('div','toolbar');
  const fSt=el('select','sel');
  ['전체 상태','반영','부분','미반영'].forEach(x=>{const o=el('option');
    o.value=x==='전체 상태'?'':x;o.textContent=x;fSt.appendChild(o)});
  const fPr=el('select','sel');
  ['전체 영역'].concat([...new Set(R.rows.map(r=>r.id.split('-')[0]))].sort())
    .forEach(x=>{const o=el('option');o.value=x==='전체 영역'?'':x;
      o.textContent=x;fPr.appendChild(o)});
  const q=el('input','input');q.type='text';q.placeholder='ID·제목 검색';
  bar.appendChild(fSt);bar.appendChild(fPr);bar.appendChild(q);
  root.appendChild(bar);

  const pane=el('div','card');root.appendChild(pane);
  function draw(){
    pane.innerHTML='';
    const kw=q.value.trim().toLowerCase();
    const rows=R.rows.filter(r=>
      (!fSt.value||r.status===fSt.value)&&
      (!fPr.value||r.id.startsWith(fPr.value+'-'))&&
      (!kw||(r.id+' '+r.title).toLowerCase().includes(kw)));
    pane.appendChild(rawEl('h3',null,TP('요건',TC(rows.length,'건'))));
    const w=el('div','tw'),t=el('table'),th=el('thead'),tr=el('tr');
    ['요건','업권','우선순위','상태','증빙 (검증됨)','비고'].forEach(
      x=>tr.appendChild(el('th',null,x)));
    th.appendChild(tr);t.appendChild(th);
    const tb=el('tbody');
    rows.forEach(r=>{
      const x=el('tr');
      const td0=el('td');td0.appendChild(el('div','mono',r.id));
      td0.appendChild(el('div',null,r.title));x.appendChild(td0);
      x.appendChild(el('td',null,r.sector));
      x.appendChild(el('td',null,r.priority));
      const td3=el('td');td3.appendChild(pill(r.status,
        r.status==='반영'?'good':r.status==='부분'?'warn':'bad'));
      x.appendChild(td3);
      const td4=el('td');
      r.evidence.forEach(e=>{
        const s=el('span','pill');s.style.marginRight='4px';
        s.textContent=e.kind+' · '+e.ref;s.title=e.kind;td4.appendChild(s)});
      if(!r.evidence.length)td4.appendChild(el('span','meta','-'));
      x.appendChild(td4);
      /* 비고는 요건 레지스터(req_trace.py)가 원문에서 생성한 값이다. 옮기면
         화면의 문장과 레지스터의 문장이 갈라져 BRD 대조가 끊긴다. */
      x.appendChild(rawEl('td','meta',r.note||''));
      tb.appendChild(x)});
    t.appendChild(tb);w.appendChild(t);pane.appendChild(w);
  }
  fSt.onchange=draw;fPr.onchange=draw;q.addEventListener('input',draw);
  draw();
}

/* ---- 오버레이 (인간 수정) (기록 없는 조정은 재현 불가의 시작이다) ---- */
function overlay(root){
  root.appendChild(el('p','lead',
    '엔진 산출값을 사람이 덮어쓴 기록(수동조정 원장)과 새 오버레이 제안. 전 건이 '+
    '사유·증빙·승인자·만료일을 갖는다. 이 화면은 값을 바꾸지 않는다. 제안서를 '+
    '만들고, 적용은 원장 등재 + 파이프라인 재실행 + 검증 두 층을 거친다.'));
  const f=D.adjustments;
  const c0=el('div','card');
  c0.appendChild(el('h3',null,'수동조정 원장'));
  c0.appendChild(table(f));c0.appendChild(srcMeta(f));
  root.appendChild(c0);

  const c=el('div','card set-overlay');
  c.appendChild(el('h3',null,'새 오버레이 제안'));
  const bar=el('div','toolbar');
  const sel=el('select','sel');
  D.kpis.forEach(k=>{const o=el('option');o.value=k.label;
    o.textContent=k.label+' (현재 '+k.value+')';sel.appendChild(o)});
  const val=el('input','input');val.type='text';val.placeholder='수정값';
  val.style.maxWidth='160px';
  const why=el('input','input');why.type='text';
  why.placeholder='사유 (필수, 데이터 지연·일회성 사건·모형 한계 등)';
  const ev=el('input','input');ev.type='text';
  ev.placeholder='증빙 참조 (필수, 문서번호·티켓)';ev.style.maxWidth='220px';
  bar.appendChild(sel);bar.appendChild(val);bar.appendChild(why);bar.appendChild(ev);
  c.appendChild(bar);
  const gen=el('button','btn primary','오버레이 제안 생성');
  c.appendChild(gen);
  const err=el('div','note bad');err.hidden=true;c.appendChild(err);
  const out=el('pre','mono');out.style.whiteSpace='pre-wrap';c.appendChild(out);
  gen.onclick=()=>{
    err.hidden=true;out.textContent='';
    if(STATE.killed&&STATE.killScope==='전사'){
      err.textContent='비상정지 중. 제안을 만들지 않는다.';err.hidden=false;return}
    if(!why.value.trim()||!ev.value.trim()){
      err.textContent='사유와 증빙 참조는 필수다.';
      err.hidden=false;return}
    if(!val.value.trim()){err.textContent='수정값이 비어 있다.';err.hidden=false;return}
    const k=D.kpis.find(x=>x.label===sel.value);
    out.textContent=JSON.stringify({
      proposal:'수동조정(오버레이)',asof:D.meta.asof,run_id:D.meta.run_id,
      target:k.label,engine_value:k.value,proposed_value:val.value.trim(),
      reason:why.value.trim(),evidence_ref:ev.value.trim(),
      apply_path:'risk_lib/adjustments.py (ManualAdjustment 등재)',
      procedure:['원장 등재(승인자·만료일 포함)','4-Eyes 승인',
                 '파이프라인 재실행','자체검증(2선)','독립검증(3선) 재요청'],
      note:'화면 값은 바뀌지 않는다.'},null,2);
  };
  root.appendChild(c);
}

/* ---- 코드 마스터 관리. 코드그룹 / 코드 2단 구성 ----
   왼쪽은 코드그룹(코드셋) 목록과 그 속성, 오른쪽은 선택한 그룹의 코드 목록.
   그룹을 고르지 않고 코드만 나열하면 91개 코드셋 428행이 한 표에 섞여
   "어느 그룹의 코드인가"를 사람이 눈으로 세게 된다. */
function codeMasterAdmin(root){
  root.appendChild(el('p','lead',
    '정렬·표시의 정본(rdm_code_master)을 코드그룹 단위로 관리한다. 왼쪽에서 '+
    '그룹을 고르면 오른쪽에 그 그룹의 코드가 순서대로 뜬다. 순서 재정의는 이 '+
    '세션의 화면 정렬에 즉시 적용되고, 정본 변경은 카탈로그 수정 제안으로만 한다.'));
  const f=D.data['rdm_code_master'];
  const i=frameIdx(f);
  STATE.codeOverride=STATE.codeOverride||{};

  /* 그룹 요약 (코드 수·출처 테이블·재정의 여부) */
  const groups={};
  f.rows.forEach(r=>{
    const g=r[i.code_set];
    (groups[g]=groups[g]||{n:0,src:new Set()});
    groups[g].n++;groups[g].src.add(r[i.source_table]);
  });
  const names=Object.keys(groups).sort();
  let sel=names[0];

  const wrap=el('div','split');
  const left=el('div','card set-codegroup');
  const right=el('div','card set-codemaster');
  wrap.appendChild(left);wrap.appendChild(right);
  root.appendChild(wrap);

  function drawGroups(){
    left.innerHTML='';
    left.appendChild(el('h3',null,`코드그룹 ${names.length}종`));
    const q=el('input','input');q.type='search';
    q.placeholder='그룹명 검색 (예: grade · status)';
    left.appendChild(q);
    const list=el('div','list');list.style.marginTop='8px';
    function fill(){
      list.innerHTML='';
      const kw=q.value.trim().toLowerCase();
      names.filter(g=>!kw||g.toLowerCase().includes(kw)).forEach(g=>{
        const b=el('button');
        b.appendChild(document.createTextNode(g));
        const ovr=STATE.codeOverride[g]?' · 재정의됨':'';
        b.appendChild(el('small',null,
          `코드 ${groups[g].n}개 · 출처 ${[...groups[g].src][0]}${ovr}`));
        if(g===sel)b.classList.add('on');
        b.onclick=()=>{sel=g;fill();drawCodes()};
        list.appendChild(b)});
    }
    q.addEventListener('input',fill);fill();
    left.appendChild(list);
    left.appendChild(el('div','meta',
      `총 코드 ${f.total.toLocaleString()}행 (카탈로그 allowed 선언에서 생성)`));
  }

  function currentCodes(){
    const ovr=STATE.codeOverride[sel];
    if(ovr)return [...ovr];
    return f.rows.filter(r=>r[i.code_set]===sel)
      .sort((a,b)=>a[i.sort_order]-b[i.sort_order]).map(r=>r[i.code]);
  }

  function drawCodes(){
    right.innerHTML='';
    right.appendChild(el('h3',null,`코드 (${sel})`));
    right.appendChild(el('div','meta',
      `출처 ${[...groups[sel].src].join(' · ')} · 정렬은 카탈로그 선언 순서를 따른다`));
    const codes=currentCodes();
    const w=el('div','tw'),t=el('table'),th=el('thead'),tr=el('tr');
    ['순서','코드','이동'].forEach(x=>tr.appendChild(el('th',null,x)));
    th.appendChild(tr);t.appendChild(th);
    const tb=el('tbody');
    codes.forEach((code,k)=>{
      const x=el('tr');
      x.appendChild(el('td','num',String(k)));
      x.appendChild(el('td','mono',code));
      const td=el('td');
      const up=el('button','btn','↑');up.disabled=k===0;
      const dn=el('button','btn','↓');dn.disabled=k===codes.length-1;
      up.onclick=()=>{const c2=[...codes];[c2[k-1],c2[k]]=[c2[k],c2[k-1]];
        STATE.codeOverride[sel]=c2;drawCodes()};
      dn.onclick=()=>{const c2=[...codes];[c2[k+1],c2[k]]=[c2[k],c2[k+1]];
        STATE.codeOverride[sel]=c2;drawCodes()};
      td.appendChild(up);td.appendChild(dn);x.appendChild(td);
      tb.appendChild(x)});
    t.appendChild(tb);w.appendChild(t);right.appendChild(w);

    const acts=el('div','toolbar');
    const apply=el('button','btn primary','세션에 적용');
    const reset=el('button','btn','재정의 지우기');
    const gen=el('button','btn','정본 변경 제안');
    const outBox=el('pre','mono');outBox.style.whiteSpace='pre-wrap';
    apply.onclick=()=>{
      _CODE_ORDER=null;
      const ovr=STATE.codeOverride[sel];
      if(ovr){codeRank('','');_CODE_ORDER[sel]=
        Object.fromEntries(ovr.map((c2,k)=>[c2,k]))}
      repaintAll();};
    reset.onclick=()=>{delete STATE.codeOverride[sel];
      _CODE_ORDER=null;repaintAll();};
    gen.onclick=()=>{
      const ovr=STATE.codeOverride[sel];
      outBox.textContent=JSON.stringify({
        proposal:'코드 마스터 순서 변경',code_set:sel,
        from:f.rows.filter(r=>r[i.code_set]===sel)
          .sort((a,b)=>a[i.sort_order]-b[i.sort_order]).map(r=>r[i.code]),
        to:ovr||'(변경 없음)',
        apply_path:'risk_lib/datamodel/catalog.py (allowed 선언 순서)',
        note:'정본은 카탈로그다. 세션 재정의는 이 화면을 닫으면 사라진다.'},null,2);
    };
    acts.appendChild(apply);acts.appendChild(reset);acts.appendChild(gen);
    right.appendChild(acts);right.appendChild(outBox);
  }
  drawGroups();drawCodes();
}

/* ---- 거시·금융지표 모니터링 ----
   최근값·경보·충격 배수는 payload(D.macro)가 들고 있는 엔진 산출을 그대로
   쓴다. 화면은 고르고 그릴 뿐 다시 집계하지 않는다. */
function macroFmt(v,u){
  if(v===null||v===undefined)return '-';
  if(u==='원')return fmtNum(Math.round(v))+'원';
  if(u==='지수')return v.toFixed(1);
  if(u==='bp')return v.toFixed(1)+'bp';
  return v.toFixed(2)+u;                 /* % · %p */
}
function macroMonitor(root){
  const M=D.macro;
  if(!M){root.appendChild(el('div','note','거시지표 원장이 payload에 없다'));return}
  root.appendChild(el('p','lead',
    '통합위기상황분석 시나리오의 입력이 되는 거시·금융지표 12종이다. 부문별 '+
    '최근값과 이탈 경보, 계열 추이, 그리고 시나리오 가정값이 어느 지표의 어떤 '+
    '값에서 나왔는지를 같은 원장에서 읽는다.'));
  root.appendChild(el('div','note',
    '값의 근거는 '+Object.entries(M.basis_mix)
      .map(([k,v])=>k+' '+v.toLocaleString()+'행').join(' · ')+
    '이다. 이 환경은 외부 통계 API 로 나가는 통신이 막혀 있어 실측 피드가 없다. '+
    '출처 코드(한국은행 ECOS 통계표코드 · 통계청 KOSIS 표ID)는 실제 계열을 '+
    '가리키므로, 피드가 열리면 macro_monitor 의 관측치만 교체하면 된다.'));

  const g=el('div','grid');
  [['모니터링 지표',M.latest.length+'종',''],
   ['관측',M.observations.total.toLocaleString()+'행',''],
   ['이탈 경보 (|z| ≥ '+M.z_threshold+')',String(M.alerts.length),
    M.alerts.length?'warn':'good'],
   ['시나리오 연결',
    new Set(M.links.map(x=>x.scenario)).size+'종 · '+M.links.length+'행','']]
  .forEach(([k,v,t])=>{
    const c=el('div','card kpi');c.appendChild(el('div','lab',k));
    c.appendChild(el('div','val '+t,v));g.appendChild(c)});
  root.appendChild(g);

  /* --- 1. 경보 --- */
  const ac=el('div','card');
  ac.appendChild(el('h3',null,'이탈 경보 (최근 관측이 자기 계열의 평소 범위를 벗어난 지표)'));
  if(!M.alerts.length){
    ac.appendChild(el('div','meta','이탈 지표 없음'));
  }else{
    const w=el('div','tw'),t=el('table'),th=el('thead'),htr=el('tr');
    ['지표','부문','관측시점','값','z','움직이는 축'].forEach((x,k)=>
      htr.appendChild(el('th',k===4?'num':null,x)));
    th.appendChild(htr);t.appendChild(th);
    const tb=el('tbody');
    M.alerts.forEach(a=>{
      const r=el('tr');
      r.appendChild(el('td',null,a.name));
      r.appendChild(el('td',null,a.category));
      r.appendChild(el('td','mono',a.period));
      r.appendChild(el('td','mono',macroFmt(a.value,a.unit)));
      const zd=el('td','num');
      zd.appendChild(pill((a.z>0?'+':'')+a.z.toFixed(2),
        Math.abs(a.z)>=2?'bad':'warn'));
      r.appendChild(zd);
      /* 지표명·부문·움직이는 축은 지표 마스터 원장(macro_monitor.py)의 값이다.
         옮기면 화면의 이름과 원장의 이름이 갈라진다. */
      r.appendChild(rawEl('td','meta',a.drives));
      tb.appendChild(r)});
    t.appendChild(tb);w.appendChild(t);ac.appendChild(w);
  }
  ac.appendChild(el('div','meta',
    '임계는 계열 자신의 표준편차다. 수준·단위가 지표마다 달라 절대값 임계를 '+
    '두면 환율만 계속 걸린다.'));
  root.appendChild(ac);

  /* --- 3. 시계열 (표에서 지표를 눌러도 여기로 온다) --- */
  const sc=el('div','card');
  sc.appendChild(el('h3',null,'계열 추이'));
  const bar=el('div','toolbar');
  const sel=el('select','sel');
  M.latest.forEach(x=>{const o=el('option');o.value=x.indicator_id;
    o.textContent=x.category+' · '+x.name;sel.appendChild(o)});
  bar.appendChild(sel);sc.appendChild(bar);
  const spane=el('div');sc.appendChild(spane);
  const oi=frameIdx(M.observations);
  function drawSeries(){
    spane.innerHTML='';
    const id=sel.value;
    const m=M.latest.find(x=>x.indicator_id===id);
    const rows=M.observations.rows.filter(r=>r[oi.indicator_id]===id);
    if(!m||!rows.length){spane.appendChild(el('div','meta','계열이 없다'));return}
    const labels=rows.map(r=>r[oi.period]);
    spane.appendChild(multiLine(
      [{name:m.name+' ('+m.unit+')',values:rows.map(r=>r[oi.value])}],labels,null));
    spane.appendChild(el('div','meta',
      labels[0]+'~'+labels[labels.length-1]+' '+rows.length+'기 · 주기 '+m.freq+
      ' · 최근값 '+macroFmt(m.value,m.unit)+
      ' · 전년동기대비 '+(m.yoy==null?'-':(m.yoy>=0?'+':'')+(m.yoy*100).toFixed(1)+'%')+
      ' · 출처 '+m.source+' '+m.source_code+' · 근거 '+m.basis+
      ' · 움직이는 축 '+m.drives));
    const al=M.alerts.find(a=>a.indicator_id===id);
    if(al)spane.appendChild(el('div','note',
      '이탈 경보. 최근값이 직전 구간 평균에서 표준편차의 '+al.z.toFixed(2)+
      '배만큼 떨어져 있다.'));
  }
  sel.onchange=drawSeries;

  /* --- 2. 부문별 지표 표 --- */
  const tc=el('div','card');
  tc.appendChild(el('h3',null,'부문별 지표 (최근값)'));
  const byCat=new Map();
  M.latest.forEach(x=>{if(!byCat.has(x.category))byCat.set(x.category,[]);
    byCat.get(x.category).push(x)});
  const tw=el('div','tw'),tt=el('table'),tth=el('thead'),thr=el('tr');
  ['지표','최근값','전년동기대비','관측시점','주기','출처','출처코드','움직이는 축']
    .forEach((x,k)=>thr.appendChild(el('th',(k===1||k===2)?'num':null,x)));
  tth.appendChild(thr);tt.appendChild(tth);
  const ttb=el('tbody');
  byCat.forEach((list,cat)=>{
    const hr=el('tr'),hd=el('td','listsec',cat+' · '+list.length+'종');
    hd.colSpan=8;hr.appendChild(hd);ttb.appendChild(hr);
    list.forEach(x=>{
      const r=el('tr'),nd=el('td');
      /* 표에서 바로 계열을 고른다. select 하나만 두면 표에서 눈에 띈 지표를
         목록에서 다시 찾아야 한다 */
      const b=rawEl('button','chip',x.name);   /* 지표명은 원장 값이다 */
      b.onclick=()=>{sel.value=x.indicator_id;drawSeries();
        sc.scrollIntoView({block:'nearest'})};
      nd.appendChild(b);r.appendChild(nd);
      r.appendChild(el('td','num mono',macroFmt(x.value,x.unit)));
      r.appendChild(el('td','num mono',
        x.yoy==null?'-':(x.yoy>=0?'+':'')+(x.yoy*100).toFixed(1)+'%'));
      r.appendChild(el('td','mono',x.period));
      r.appendChild(el('td',null,x.freq));
      r.appendChild(el('td',null,x.source));
      r.appendChild(el('td','mono',x.source_code));
      r.appendChild(rawEl('td','meta',x.drives));
      ttb.appendChild(r)})});
  tt.appendChild(ttb);tw.appendChild(tt);tc.appendChild(tw);
  /* 수준이 %인 지표(금리·실업률)는 전년동기대비를 %p 차이로 읽기 쉬워, 원장
     yoy 의 정의를 표 밑에 적는다. */
  tc.appendChild(el('div','meta',
    '전년동기대비는 1년 전 값 대비 비율 변화다. 수준이 %인 지표도 같은 기준으로 '+
    '계산한다. 지표명을 누르면 아래 추이가 그 계열로 바뀐다.'));
  tc.appendChild(srcMeta(M.observations,'지표 '+M.latest.length+'종의 최근 1행'));
  root.appendChild(tc);
  root.appendChild(sc);
  drawSeries();

  /* --- 4. 시나리오 연결 --- */
  const lc=el('div','card');
  lc.appendChild(el('h3',null,'시나리오 연결 (가정값이 어느 지표에서 나왔나)'));
  lc.appendChild(el('div','meta',
    '시나리오 가정값 = 최근 관측값 + 배수 × 그 지표의 분기 변동성. 배수를 '+
    '표준편차 단위로 두는 이유는, 수준이 다른 지표를 같은 %로 때리면 환율과 '+
    '실업률이 같은 충격을 받은 셈이 되기 때문이다.'));
  const chips=el('div','chips');
  const scens=[...new Set(M.links.map(x=>x.scenario))];
  let scen=scens[scens.length-1];
  scens.forEach(s0=>{const b=rawEl('button','chip',s0);  /* 시나리오명은 원장 값 */
    b.onclick=()=>{scen=s0;drawLinks()};chips.appendChild(b)});
  lc.appendChild(chips);
  const lpane=el('div');lc.appendChild(lpane);
  function drawLinks(){
    [...chips.children].forEach(b=>b.classList.toggle('on',b.textContent===scen));
    lpane.innerHTML='';
    const rows=M.links.filter(x=>x.scenario===scen);
    /* 배수가 원장에 없는 행은 0으로 채우지 않는다. 0으로 채우면 충격이
       없다는 뜻과 배수를 모른다는 뜻이 한 칸에서 섞인다. */
    const moved=rows.filter(x=>x.sigma!=null&&x.sigma!==0)
      .sort((a,b)=>Math.abs(b.sigma)-Math.abs(a.sigma));
    if(moved.length){
      lpane.appendChild(hbars(moved.map(x=>({label:x.name,value:x.sigma,
        sub:macroFmt(x.latest,x.unit)+' → '+macroFmt(x.scenario_value,x.unit)})),
        {title:'충격 배수 (표준편차 단위, 음수는 하락, 양수는 상승)',money:false}));
    }else{
      const unknown=rows.filter(x=>x.sigma==null).length;
      lpane.appendChild(el('div','meta',
        unknown?('배수가 원장에 없는 지표 '+unknown+'종. 값을 채우지 않는다.')
               :'충격 없음. 관측값을 그대로 가정값으로 쓴다.'));
    }
    lpane.appendChild(table({
      columns:['지표','최근 관측','시나리오 가정','충격폭','배수(σ)','움직이는 축'],
      rows:rows.map(x=>[x.name,macroFmt(x.latest,x.unit),
        macroFmt(x.scenario_value,x.unit),
        (x.shock>0?'+':'')+macroFmt(x.shock,x.unit),
        x.sigma==null?'-':(x.sigma>0?'+':'')+x.sigma.toFixed(1),x.drives]),
      total:rows.length,shown:rows.length},{numeric:false}));
    lpane.appendChild(el('div','meta',
      '원장 macro_scenario_link · '+M.links.length+'행 중 '+scen+' '+rows.length+'행'));
  }
  drawLinks();
  root.appendChild(lc);

  /* 지표 정의 마스터. 수기입력 원장이므로 승인란과 근거 판정이 보여야 한다. */
  if(M.master){
    const f=M.master,i=frameIdx(f);
    const mc=el('div','card');
    mc.appendChild(el('h3',null,'지표 정의 마스터 (승인·근거)'));
    const rows=f.rows.map(r=>[r[i.indicator_id],r[i.name],r[i.category],
      r[i.source],r[i.source_code],r[i.unit],r[i.freq],r[i.drives],
      r[i.input_source],r[i.entered_by]||'-',r[i.approved_by]||'(미승인)',
      r[i.approved_on]||'-',r[i.evidence_status]]);
    const AP=10;
    mc.appendChild(table({columns:['지표','명칭','부문','출처','출처 코드',
      '단위','주기','움직이는 축','입력출처','입력자','승인자','승인일','근거'],
      rows:rows,total:rows.length,shown:rows.length},
      {numeric:false,rowClass:r=>r[AP]==='(미승인)'?'warn':null}));
    mc.appendChild(srcMeta(f));
    mc.appendChild(el('div','meta',
      '지표 목록·출처 코드·움직이는 축은 이 마스터 원장이 정한다. 화면과 '+
      '엔진이 같은 원장을 읽으므로 지표를 늘리면 두 곳이 함께 바뀐다.'));
    root.appendChild(mc)}
}

/* ---- 역스트레스 ---- */
function reverseStress(root){
  root.appendChild(el('p','lead',
    '자본 임계를 뚫는 충격 심도를 역산한다. 값은 파이프라인 산출이며 화면에서 '+
    '계산하지 않는다.'));
  const r=D.reverse_stress;
  const g=el('div','grid');
  [['대상 지표',r.metric.toUpperCase()+' 비율',''],
   ['임계 비율',(r.target_ratio*100).toFixed(2)+'%',''],
   ['현행 비율',(r.base_ratio*100).toFixed(2)+'%','good'],
   ['임계 심도',r.critical_severity.toFixed(3),r.resilient?'good':'warn'],
   ['파열점 비율',(r.ratio_at_break*100).toFixed(3)+'%','warn'],
   ['함의 GDP 충격',(r.implied_gdp_shock*100).toFixed(2)+'%','bad'],
  ].forEach(([k,v,t])=>{
    const c=el('div','card kpi');
    c.appendChild(el('div','lab',k));
    c.appendChild(el('div','val '+t,String(v)));
    g.appendChild(c)});
  root.appendChild(g);
  const c=el('div','card');
  c.appendChild(el('h3',null,'파열점의 산출 상태'));
  c.appendChild(table({columns:['항목','값'],rows:[
    ['수렴 여부',r.converged?'수렴':'미수렴'],
    ['현행이 이미 임계 이하인가',r.resilient===false&&r.base_ratio>r.target_ratio?'아니오':'검토'],
    ['파열점 위험가중자산',fmtMoney(r.rwa_at_break)],
    ['파열점 기대신용손실',fmtMoney(r.ecl_at_break)],
    ['함의 LGD 가산',(r.implied_lgd_addon*100).toFixed(2)+'%p'],
  ],total:5,shown:5},{numeric:false}));
  c.appendChild(el('div','note',
    '심도 1.0 미만에서 임계가 뚫리면(임계 심도 < 1) 심각 시나리오보다 약한 '+
    '충격에도 요구비율을 지키지 못한다는 뜻이다. 자본계획·회복계획 연계 대상.'));
  root.appendChild(c);
}

/* ---- 코드 매핑 (계정·상품 × 리스크 대상·특성 (공통=RDM, 그 외=각 스키마)) */
function codeScope(root){
  root.appendChild(el('p','lead',
    '계정·상품 코드가 어느 리스크의 모집단에 들어가는지의 매핑이다. 매핑이 '+
    '없으면 그 코드는 모든 산출에서 빠지고, 대사에도 걸리지 않는다. '+
    '대상여부는 특성에서 규칙으로 파생되고(code_scope), 예외는 '+
    '여기서 제안으로만 만든다.'));
  const bar=el('div','toolbar');
  const mode=el('select','sel');
  [['account','계정코드'],['product','상품코드']].forEach(([v,t])=>{
    const o=el('option');o.value=v;o.textContent=t;mode.appendChild(o)});
  bar.appendChild(mode);root.appendChild(bar);
  const pane=el('div');root.appendChild(pane);
  const yn=v=>pill(v?'대상':'제외', v?'good':undefined);
  function draw(){
    pane.innerHTML='';
    if(mode.value==='account'){
      const am=D.data['rdm_account_master'],ai=frameIdx(am);
      const cr=D.data['crm_code_scope'],ci=frameIdx(cr);
      const al=D.data['alm_code_scope'],li=frameIdx(al);
      const crBy={};cr.rows.forEach(r=>{crBy[r[ci.account_code]]=r});
      const alBy={};al.rows.forEach(r=>{alBy[r[li.account_code]]=r});
      const c=el('div','card');
      c.appendChild(el('h3',null,'계정코드 × 리스크 대상·엔진 연계 매트릭스'));
      c.appendChild(el('div','meta',
        '신용환산율·위험가중 범위는 산출 엔진 상수(capital.crm·rwa_sa), '+
        '모집단(건수·EAD)은 익스포저 원장, LCR 적용률은 산출 원장에서 읽는다.'));
      const w=el('div','tw'),t=el('table'),th=el('thead'),tr=el('tr');
      ['계정','명칭','신용','자산군·접근법','위험가중',
       '신용환산(CCF)','모집단 실측','금리','유동성','LCR 분류·적용률']
        .forEach(x=>tr.appendChild(el('th',null,x)));
      th.appendChild(tr);t.appendChild(th);
      const tb=el('tbody');
      am.rows.forEach(r=>{
        const code=r[ai.account_code];
        const c2=crBy[code],l2=alBy[code];
        const x=el('tr');
        x.appendChild(el('td','mono',code));
        x.appendChild(el('td',null,r[ai.account_name]));
        const td0=el('td');td0.appendChild(yn(!!(c2&&c2[ci.in_scope])));x.appendChild(td0);
        x.appendChild(rawEl('td','meta',c2&&c2[ci.asset_class]!=='-'
          ?c2[ci.asset_class]+' · '+c2[ci.approach]:'-'));
        x.appendChild(rawEl('td','meta',c2?c2[ci.rw_range]:'-'));
        x.appendChild(rawEl('td','meta',c2&&c2[ci.ccf_type]!=='-'
          ?c2[ci.ccf_type]+' · '+(c2[ci.ccf_rate]*100).toFixed(0)+'%':'-'));
        x.appendChild(rawEl('td','meta',c2&&c2[ci.n_exposures]
          ?TC(c2[ci.n_exposures],'건')+' · '+fmtMoney(c2[ci.ead_total]):'-'));
        [[l2&&l2[li.irrbb_scope]],[l2&&l2[li.liquidity_scope]]]
          .forEach(([v])=>{const td=el('td');td.appendChild(yn(!!v));x.appendChild(td)});
        x.appendChild(rawEl('td','meta',l2&&l2[li.lcr_category]!=='-'
          ?l2[li.lcr_category]+(l2[li.lcr_factor]!=null
            ?' · '+(l2[li.lcr_factor]*100).toFixed(0)+'%':''):'-'));
        tb.appendChild(x)});
      t.appendChild(tb);w.appendChild(t);c.appendChild(w);
      c.appendChild(srcMeta(am,'대상여부: crm_code_scope · alm_code_scope (규칙 파생)'));
      pane.appendChild(c);
    } else {
      const pm=D.data['rdm_product_master'],pi=frameIdx(pm);
      const mk=D.data['mkt_code_scope'],mi=frameIdx(mk);
      const op=D.data['opr_code_scope'],oi=frameIdx(op);
      const mkBy={};mk.rows.forEach(r=>{mkBy[r[mi.product_code]]=r});
      const opBy={};op.rows.forEach(r=>{opBy[r[oi.product_code]]=r});
      const c=el('div','card');
      c.appendChild(el('h3',null,'상품코드 × 리스크 대상 매트릭스'));
      const w=el('div','tw'),t=el('table'),th=el('thead'),tr=el('tr');
      ['상품','명칭','북','시장','FRTB 위험군','거래 실측','운영',
       '손실사건 매핑·실측','산출방법']
        .forEach(x=>tr.appendChild(el('th',null,x)));
      th.appendChild(tr);t.appendChild(th);
      const tb=el('tbody');
      pm.rows.forEach(r=>{
        const code=r[pi.product_code];
        const m2=mkBy[code],o2=opBy[code];
        const x=el('tr');
        x.appendChild(el('td','mono',code));
        x.appendChild(el('td',null,r[pi.product_name]));
        x.appendChild(el('td',null,r[pi.book]));
        const td0=el('td');td0.appendChild(yn(!!(m2&&m2[mi.in_scope])));x.appendChild(td0);
        x.appendChild(rawEl('td','meta',m2?m2[mi.frtb_class]:'-'));
        x.appendChild(rawEl('td','meta',m2&&m2[mi.n_trades]
          ?m2[mi.trade_kind]+' · '+TC(m2[mi.n_trades],'건'):'-'));
        const td1=el('td');td1.appendChild(yn(!!(o2&&o2[oi.in_scope])));x.appendChild(td1);
        x.appendChild(rawEl('td','meta',o2
          ?o2[oi.event_mapping]+' · '+TC(o2[oi.n_events],'건'):'-'));
        x.appendChild(rawEl('td','meta',o2?o2[oi.capital_method]:'-'));
        tb.appendChild(x)});
      t.appendChild(tb);w.appendChild(t);c.appendChild(w);
      c.appendChild(srcMeta(pm,'대상여부: mkt_code_scope · opr_code_scope (규칙 파생)'));
      pane.appendChild(c);
    }
    /* 예외 제안 */
    const c3=el('div','card set-codescope');
    c3.appendChild(el('h3',null,'대상여부 예외 제안'));
    const b2=el('div','toolbar');
    const code=el('input','input');code.type='text';code.placeholder='코드 (예: 1340 / P-CRD)';
    code.style.maxWidth='170px';
    const risk=el('select','sel');
    ['신용','시장','운영','금리(IRRBB)','유동성'].forEach(x=>{
      const o=el('option');o.value=x;o.textContent=x;risk.appendChild(o)});
    const to=el('select','sel');
    [['true','대상 포함'],['false','대상 제외']].forEach(([v,t2])=>{
      const o=el('option');o.value=v;o.textContent=t2;to.appendChild(o)});
    const why=el('input','input');why.type='text';why.placeholder='사유 (필수)';
    b2.appendChild(code);b2.appendChild(risk);b2.appendChild(to);b2.appendChild(why);
    c3.appendChild(b2);
    const gen=el('button','btn primary','예외 제안 생성');c3.appendChild(gen);
    const err=el('div','note bad');err.hidden=true;c3.appendChild(err);
    const out=el('pre','mono');out.style.whiteSpace='pre-wrap';c3.appendChild(out);
    gen.onclick=()=>{
      err.hidden=true;out.textContent='';
      if(!code.value.trim()||!why.value.trim()){
        err.textContent='코드와 사유는 필수다.';err.hidden=false;return}
      out.textContent=JSON.stringify({
        proposal:'코드 대상여부 예외',code:code.value.trim(),
        risk:risk.value,to_in_scope:to.value==='true',reason:why.value.trim(),
        apply_path:'risk_lib/datamodel/code_scope.py (규칙 또는 예외 등재)',
        procedure:['규칙·예외 반영','파이프라인 재실행','자체검증(2선)',
                   '독립검증(3선) 재요청'],
        note:'화면 매트릭스는 규칙 파생이다. 예외도 코드가 돼야 산출에 반영된다.'},null,2);
    };
    pane.appendChild(c3);
  }
  mode.onchange=draw;draw();
}

/* ---- 화면 요약. 조회 순간의 데이터에서 규칙으로 뽑는 한 줄 ----
   외부 LLM 호출은 하지 않는다(폐쇄망·CSP 차단·재현성). 같은 데이터면 같은
   문장이 나온다. 요약도 산출물이므로 결정론이어야 한다. */
function cockpitInsights(){
  const out=[];
  try{
    /* 완충자본 미달은 콕핏에서 제일 먼저 읽혀야 한다. 배당·성과급이 제한되는
       상태다. 판정은 KPI 원장에서 그대로 가져온다(별계산 금지). */
    const cap=D.kpis[0];
    if(cap&&cap.tone==='bad')
      out.push({t:`${cap.label} ${cap.value} (${cap.sub})`,tone:'bad'});
    const sev=D.kpis.find(k=>k.label.includes('위기상황'));
    if(sev&&sev.tone==='warn')out.push({t:`위기 ${sev.label.replace(' CET1 저점','')} 저점 ${sev.value} (요구비율 침범, 자본계획·회복계획 연계 대상)`,tone:'bad'});
    const rv=D.reverse_stress;
    if(rv&&rv.critical_severity<1)out.push({t:`역스트레스 임계 심도 ${rv.critical_severity.toFixed(2)} (심각(1.0)보다 약한 충격에 임계 붕괴)`,tone:'bad'});
    const lm=D.limits,li=frameIdx(lm);
    const br=lm.rows.filter(r=>limitBreached(r[li.severity]));
    if(br.length){
      /* 최고 소진율과 한도명은 **같은 행**에서 뽑는다. 원장은 소진율 순이
         아니라서 br[0] 이름에 전체 최대값을 붙이면 엉뚱한 한도가 115%
         소진된 것으로 오독된다. */
      const top=lm.rows.reduce((a,b)=>b[li.utilisation]>a[li.utilisation]?b:a);
      out.push({t:`한도 위반 ${br.length}건. 최고 소진 ${(top[li.utilisation]*100).toFixed(0)}% (${top[li.limit]} · ${top[li.bucket]})`,tone:'bad'});
    }
    const ex=D.data['gov_exception_action'];
    if(ex){const xi=frameIdx(ex);
      const grave=ex.rows.filter(r=>r[xi.severity]==='중대').length;
      if(grave)out.push({t:`미해소 예외 ${ex.total}건 중 중대 ${grave}건 (예외·조치 화면에서 기한 추적)`,tone:'warn'})}
    const ipv=D.data['mkt_ipv'];
    if(ipv){const ii=frameIdx(ipv);
      const old=ipv.rows.filter(r=>r[ii.is_break]&&r[ii.days_open]>=5).length;
      if(old)out.push({t:`가격검증 미해소 5일 초과 ${old}건 (상위보고 대상)`,tone:'warn'})}
    const v=D.validation,vi=frameIdx(v);
    if(!v.rows.some(r=>r[vi.status]==='FAIL'))
      out.push({t:`자체검증 ${v.rows.length}건 FAIL 0 · 서식 대사 ${D.form_checks.total.toLocaleString()}건 실패 0 (3선 게이트 ${D.independent.status})`,tone:'good'});
  }catch(e){}
  return out;
}
const SUMMARIES={
  '콕핏':()=>cockpitInsights()[0],
  /* 요약은 화면 본문과 같은 프레임(전량)을 세야 한다. D.limits 는 90% 이상만
     담은 위반 보고서라, 그걸 세면 "한도 4건" 이 25행 원장 위에 붙는다. */
  '한도관리':()=>{const f=D.limits_full||D.limits,i=frameIdx(f);
    const br=f.rows.filter(r=>limitBreached(r[i.severity])).length;
    const wr=f.rows.filter(r=>r[i.severity]==='WARN').length;
    return br?{t:`한도 ${f.total}건 중 위반 ${br} · 경보 ${wr}`,tone:'bad'}
      :{t:`한도 ${f.total}건 (위반 없음 · 경보 ${wr}건)`,tone:wr?'warn':'good'}},
  '역스트레스':()=>{const r=D.reverse_stress;
    return {t:`임계 심도 ${r.critical_severity.toFixed(2)}에서 ${r.metric.toUpperCase()} ${(r.target_ratio*100).toFixed(0)}% 붕괴 (함의 GDP ${(r.implied_gdp_shock*100).toFixed(1)}%)`,
      tone:r.critical_severity<1?'bad':'good'}},
  '오버레이':()=>{const f=D.adjustments,i=frameIdx(f);
    const pend=f.rows.filter(r=>r[i.status]!=='approved').length;
    return {t:`수동조정 ${f.total}건 (미승인 ${pend}건 · 전 건 사유·증빙·만료 보유)`,
      tone:pend?'warn':'good'}},
  '예외·조치':()=>{const f=D.data['gov_exception_action'],i=frameIdx(f);
    const g=f.rows.filter(r=>r[i.severity]==='중대').length;
    return {t:`예외 ${f.total}건 (중대 ${g}). 자동상계 금지, 종결은 사람 승인 후`,
      tone:g?'warn':'good'}},
  '백테스팅':()=>{const f=D.data['mkt_backtest_exception'],i=frameIdx(f);
    const n=f.rows.filter(r=>r[i.exception]).length;
    return {t:`관측 ${f.rows.length}일 중 예외 ${n}건 (${n<=4?'녹색':'주의'} 구간)`,
      tone:n<=4?'good':'warn'}},
  /* ALM 여섯 화면의 요약은 ALM 구간에서 붙인다(ALM_SUMMARIES). 요약도 원장
     컬럼에서만 나와야 하므로 화면 코드와 같은 자리에 둔다. */
  '모형 인벤토리':()=>{const f=D.data['crm_model'];if(!f)return null;
    const i=frameIdx(f);
    const dom=new Set(f.rows.map(r=>r[i.domain])).size;
    const over=f.rows.filter(r=>r[i.is_overdue]).length;
    return {t:`모형 ${f.total}건 · 도메인 ${dom}종 (검증 기한 초과 ${over}건)`,
      tone:over?'bad':'good'}},
  '검증 일정':()=>{const f=D.data['crm_model'];if(!f)return null;
    const i=frameIdx(f);
    const nxt=f.rows.slice().sort((a,b)=>String(a[i.next_due]).localeCompare(String(b[i.next_due])))[0];
    return {t:`가장 이른 차기 기한 ${nxt[i.next_due]} (${nxt[i.model_id]})`,tone:'warn'}},
  '변별력·안정성':()=>{const f=D.data['crm_performance'];if(!f)return null;
    const i=frameIdx(f);
    const low=f.rows.filter(r=>(r[i.gini]||0)<0.4).length;
    return {t:`성능 ${f.total}건 (Gini 양호기준(40%) 미달 ${low}건)`,
      tone:low?'warn':'good'}},
  '등급 보정':()=>{const f=D.data['crm_pd_calibration'];if(!f)return null;
    const i=frameIdx(f);
    const bad=f.rows.filter(r=>!r[i.within_tolerance]).length;
    return {t:`등급 ${f.total}건 중 허용범위 밖 ${bad}건 (O/E 괴리가 기준을 넘은 등급은 재보정 대상)`,
      tone:bad?'warn':'good'}},
  '모형리스크':()=>({t:'Tier 1 은 연 1회 독립검증·챌린저 모형 유지 (검증 주기는 등급이 정한다)',tone:'good'}),
  /* 이 원장은 "등급 유지" 와 "부도(D) 전이" 만 만든다. 등급 간 상·하향은
     관측 구조상 존재할 수 없다. 상향 0건을 발견처럼 적으면 재등급을 측정해
     보니 없더라는 뜻이 되어 읽는 사람을 속인다. 있는 것만 말한다. */
  '등급 전이':()=>{const f=D.data['crm_rating_migration'];if(!f)return null;
    const i=frameIdx(f);
    const seg=new Set(f.rows.map(r=>r[i.segment])).size;
    const dflt=f.rows.filter(r=>r[i.to_grade]==='D');
    const mx=dflt.reduce((a,r)=>(r[i.share]||0)>(a?a[i.share]||0:0)?r:a,null);
    return {t:mx
      ? `세그먼트 ${seg}종 · 전이 ${f.total}쌍 (등급 유지 대 부도). 최대 부도전이 ${mx[i.segment]} ${mx[i.from_grade]}→D ${((mx[i.share]||0)*100).toFixed(1)}%`
      : `세그먼트 ${seg}종 · 전이 ${f.total}쌍 (관측 부도전이 없음)`,
      tone:mx&&(mx[i.share]||0)>=0.1?'warn':'good'}},
  '집합투자증권':()=>{const f=D.data['rwa_fund_result'];if(!f)return null;
    const i=frameIdx(f);const m={};
    f.rows.forEach(r=>{m[r[i.adopted_method]]=(m[r[i.adopted_method]]||0)+1});
    return {t:`펀드 ${f.total}건 (채택 ${Object.entries(m).map(([k,v])=>k+' '+v).join(' · ')} · 정보 부족은 1250% fallback)`,tone:'good'}},
  '유동화':()=>{const f=D.data['rwa_sec_result'];if(!f)return null;
    const i=frameIdx(f);
    const fl=f.rows.filter(r=>r[i.floor_applied]).length;
    return {t:`트렌치 ${f.total}건. 하한 적용 ${fl}건 (15%, STC 선순위 10%), 계층 IRBA→ERBA→SA`,tone:'good'}},
  '파생상품':()=>{const f=D.data['rdm_derivative_master'];if(!f)return null;
    const i=frameIdx(f);
    const n=f.rows.reduce((a,r)=>a+(r[i.notional]||0),0);
    return {t:`거래 ${f.total}건 · 명목 ${fmtMoney(n)} (SA-CCR 은 기존 엔진(α=1.4) 재사용)`,tone:'good'}},
  '집계 원장':()=>{const f=D.data['agg_credit_exposure'];if(!f)return null;
    const i=frameIdx(f);
    const e=f.rows.reduce((a,r)=>a+(r[i.ead]||0),0);
    return {t:`신용 축 집계 ${f.total}행 · EAD ${fmtMoney(e)} (도메인마다 축이 다르다)`,tone:'good'}},
  '거시지표 모니터링':()=>{const M=D.macro;if(!M)return null;
    const n=M.alerts.length;
    return {t:`지표 ${M.latest.length}종 · 관측 ${M.observations.total}행 (이탈 ${n}건)`+
      (n?` (최대 ${M.alerts[0].name} z ${M.alerts[0].z.toFixed(2)})`:'')+
      ` · 근거 `+Object.entries(M.basis_mix).map(([k,v])=>k+' '+v+'행').join(' · '),
      tone:n?'warn':'good'}},
  '산출 방법론':()=>({t:'원장에 세 방법 결과가 다 있다. 방법 변경 영향을 재계산 없이 본다. 적용은 재실행·검증 두 층',tone:'warn'}),
  '코드 매핑':()=>{const cr=D.data['crm_code_scope'],i=frameIdx(cr);
    const n=cr.rows.filter(r=>r[i.in_scope]).length;
    return {t:`계정 ${cr.total}종 중 신용 대상 ${n} (대상여부는 규칙 파생, 예외는 제안으로만)`,tone:'good'}},
  '시뮬레이션':()=>({t:'설명용 산술 (승인·제출값 아님. 실제 영향은 재실행·검증으로만 확정된다)',tone:'warn'}),
  '상업성':()=>{const q=D.commercial.quotes,i=frameIdx(q);
    const best=q.rows.reduce((a,r)=>r[i.payback_years]<a[i.payback_years]?r:a,q.rows[0]);
    return {t:`회수기간 최단 ${best[i.name]} ${best[i.payback_years]}년 (전 수치 가정 원장 파생·이중계상 검증 통과)`,tone:'good'}},
  '요건 추적':()=>{const c=D.req_trace.coverage;
    return {t:`131건 중 반영 ${c['반영']} · 부분 ${c['부분']} · 미반영 ${c['미반영']} (증빙 ${c.n_evidence}건 전부 기계 검증)`,tone:'good'}},
  '감독보고':()=>({t:`서식 ${D.forms.length}장 · 검증 ${D.form_checks.total.toLocaleString()}건 실패 ${D.forms.reduce((a,f)=>a+f.n_failed,0)} (편제·라인·인용 기준선 고정)`,tone:'good'}),
  '검증':()=>({t:`2선 ${D.independent.self_validation} · 3선 게이트 ${D.independent.status} (게이트는 fail-closed)`,
    tone:D.independent.status==='적합'?'good':'warn'}),
};
function insertSummary(label,section){
  const f=SUMMARIES[label];
  if(!f)return;
  let sm=null;try{sm=f()}catch(e){return}
  if(!sm)return;
  const d=el('div','aisum '+(sm.tone||''));
  d.appendChild(el('span','aisum-tag','요약'));
  d.appendChild(el('span',null,sm.t));
  d.title='규칙 기반 자동 분석. 같은 데이터면 같은 문장이 나오는 결정론이며, 폐쇄망이라 외부 LLM 을 호출하지 않는다';
  const h2=section.querySelector('h2');
  h2?h2.after(d):section.prepend(d);
}

/* ══════════════ ALM 화면 (시작) ═══════════════════════════════════════════
   금리리스크(IRRBB) · 현금흐름 원장 · 유동성 사다리 · LCR/NSFR 상세 ·
   생존기간 · 계수 원장. 여섯 화면.

   이 구간에는 수치 리터럴을 두지 않는다. 충격폭·계수·상한·버킷 경계·유출률은
   전부 원장 컬럼에서 읽는다. 화면에 적어 두면 원장이 바뀌어도 화면은 옛 값을
   말하고, 그 어긋남은 감사에서 가장 늦게 발견된다.

   근거가 미확인인 값은 숨기지 않는다. 특히 금리충격폭은 원화 계정이 비어
   있어 USD 계정을 대용하고 있으므로, 그 사실을 화면 위쪽에 적는다. 감독당국이
   화면만 보고 원화 계정 산출로 읽는 것이 이 화면이 낼 수 있는 최악의 결과다.
   (tests/test_ui_alm.py 가 이 구간을 스캔해 고정한다) */

function almF(n){return D.data[n]||null}

/* 연결 원장. 화면이 읽는 원장과 실린 행수를 화면 안에 적는다. 표본으로
   그린 그림은 모집단으로 읽히므로 잘림 여부를 같이 남긴다. */
function almSources(names,note){
  const c=el('div','card');
  c.appendChild(el('h3',null,'연결 원장 (이 화면의 모든 수치가 나오는 곳)'));
  const cols=['원장','명칭','입도','모집단','화면 탑재'];
  const POP=cols.indexOf('모집단');
  const rows=names.map(n=>{
    const f=almF(n),m=D.catalog.find(x=>x.name===n);
    return [n,m?m.korean:'-',m?m.grain:'-',
            f?f.total.toLocaleString()+'행':'미탑재',
            f?(f.shown>=f.total?'전량':'표본 '+f.shown.toLocaleString()+'행'):'-']});
  c.appendChild(table({columns:cols,rows:rows,
    total:rows.length,shown:rows.length},
    {numeric:false,rowClass:r=>r[POP]==='미탑재'?'bad':null}));
  if(note)c.appendChild(el('div','note',note));
  return c;
}
/* 원장이 없으면 빈 화면을 그리지 않는다. 빈 화면은 해당 사항이 없는 것으로 오독된다. */
function almHas(root,names){
  const miss=names.filter(n=>!almF(n));
  if(miss.length){const n=el('div','note bad');
    n.textContent='원장 미탑재 '+miss.join(' · ')+'. 그림을 그리지 않는다.';
    root.appendChild(n)}
  return miss.length===0;
}
/* 근거 판정 분포. evidence_status 컬럼을 가진 원장을 그대로 센다. */
function almEvidence(names){
  const rows=[];
  names.forEach(n=>{const f=almF(n);if(!f)return;const i=frameIdx(f);
    if(i.evidence_status===undefined)return;
    const m=new Map();
    f.rows.forEach(r=>{
      const k=r[i.evidence_status]==null?'-':String(r[i.evidence_status]);
      m.set(k,(m.get(k)||0)+1)});
    [...m.entries()].sort(([,x],[,y])=>y-x)
      .forEach(([k,v])=>rows.push([n,k,v]))});
  const c=el('div','card');
  c.appendChild(el('h3',null,'근거 상태 (원장 evidence_status 그대로)'));
  const cols=['원장','근거 판정','행수'],EV=cols.indexOf('근거 판정');
  c.appendChild(table({columns:cols,rows:rows,
    total:rows.length,shown:rows.length},
    {rowClass:r=>r[EV]==='미확인'?'bad':null}));
  c.appendChild(el('div','meta',
    '미확인은 1차자료를 확인하지 못한 값이다. 엔진은 그 조정을 건너뛰고 원장은 '+
    '칸을 비워 둔다. 화면도 채우지 않는다.'));
  return c;
}
/* 시나리오 순서는 정의 원장이 정한다. 화면에서 다시 적으면 원장에 시나리오가
   늘어도 화면만 옛 순서로 남는다. */
function almScenOrder(){
  const d=almF('alm_scenario_def');
  return d?d.rows.map(r=>r[frameIdx(d).scenario]):[]}
/* 정의 원장에 없는 시나리오는 충격을 주지 않은 기준선(base)이다. 뒤로
   밀면 화면의 기본 선택이 충격 시나리오가 되어, 사다리·현금흐름을 처음 열 때
   충격 후 그림을 무충격으로 읽게 된다. 앞에 둔다. */
function almSortScen(list){
  const ord=almScenOrder();
  const rank=v=>{const k=ord.indexOf(v);return k<0?-1:k};
  return list.slice().sort((a,b)=>rank(a)-rank(b))}
/* 버킷 순서는 seq 컬럼이다. 라벨을 문자열로 정렬하면 10y+ 가 1-2y 앞에 온다. */
function almBuckets(i,rows){
  const m=new Map();
  rows.forEach(r=>m.set(r[i.bucket],r[i.seq]));
  return [...m.entries()].sort(([,x],[,y])=>x-y).map(([k])=>k)}
function almSelect(bar,label,values,initial){
  const w=el('label','meta');
  w.style.cssText='display:flex;gap:6px;align-items:center';
  w.appendChild(el('span',null,label));
  const s=el('select','sel');
  values.forEach(v=>{const o=el('option');o.value=v;o.textContent=v;
    s.appendChild(o)});
  if(initial!=null&&values.indexOf(initial)>=0)s.value=initial;
  w.appendChild(s);bar.appendChild(w);return s}
function almCard(title,child,src){
  const c=el('div','card');
  if(title)c.appendChild(el('h3',null,title));
  if(child)c.appendChild(child);
  if(src)c.appendChild(src);
  return c}

/* ---- ① 금리리스크(IRRBB) ------------------------------------------------ */

/* 헤드라인 기준(계약/행동조정)은 종합 원장의 IRRBB_EVE 분자와 맞는 쪽이다.
   화면이 따로 고르면 콕핏·종합보고서와 다른 기준을 그린다. */
function almHeadlineBasis(f,i){
  const cand=f.rows.filter(r=>r[i.is_worst]);
  if(!cand.length)return f.rows[0][i.basis];
  const a=almF('alm_result');
  if(a){const ai=frameIdx(a);
    const row=a.rows.find(r=>String(r[ai.metric]).indexOf('IRRBB_EVE')>=0);
    if(row&&row[ai.numerator]!=null){
      const num=Math.abs(row[ai.numerator]);
      const gap=r=>Math.abs(Math.abs(r[i.delta_eve])-num);
      return cand.reduce((x,r)=>gap(r)<gap(x)?r:x,cand[0])[i.basis]}}
  return cand[0][i.basis];
}
/* 충격폭 고지. 프록시 사용과 공란을 화면 위쪽에 적는다. */
function almShockDisclosure(root){
  const p=almF('alm_rate_shock_param');if(!p)return;
  const i=frameIdx(p);
  const c=el('div','card');
  c.appendChild(el('h3',null,'충격폭의 근거'));
  const res=almF('alm_irrbb_result');
  if(res){const ri=frameIdx(res),r0=res.rows[0];
    const m=el('div','meta');
    m.textContent='적용 계정 '+r0[ri.framework_version]+' ('+
      r0[ri.framework_status]+') · 충격 출처 '+r0[ri.shock_source]+
      ' · 근거 판정 '+r0[ri.evidence_status];
    c.appendChild(m)}
  /* 프록시는 다른 통화 충격폭을 대용한 경우다. 대용이 없으면 이 문단이
     나오지 않는다. 대용 사실을 화면에 남기는 것이 이 문단의 목적이다. */
  const proxy=p.rows.filter(r=>r[i.proxy_for_ccy]!=null);
  if(proxy.length){const n=el('div','note bad');
    n.textContent='프록시 '+proxy.map(r=>r[i.ccy]+' '+r[i.shock_type]+' '+
      fmtNum(r[i.shock_bp])+'bp 를 '+r[i.proxy_for_ccy]+' 산출에 대용한다')
      .join(' · ')+'. 그 통화의 ΔEVE는 자기 계정 충격폭으로 낸 값이 아니다.';
    c.appendChild(n)}
  /* 공란은 두 종류다. 폐지된 계정에는 충격표가 존재하지 않아 비어 있고,
     그 외의 공란은 1차자료를 확인하지 못한 것이다. 두 사유를 구분해 적는다. */
  const empty=p.rows.filter(r=>r[i.shock_bp]==null);
  const dead=empty.filter(r=>r[i.status]==='폐지');
  const unknown=empty.filter(r=>r[i.status]!=='폐지');
  if(dead.length){const n=el('div','note');
    n.textContent='폐지 계정 '+[...new Set(dead.map(r=>r[i.framework_version]))]
      .join(' · ')+' 의 충격폭 '+dead.length+'칸이 비어 있다. 그 체계에는 '+
      '통화별 금리충격표가 없다. 이력 보존용이며 산출에 쓰지 않는다.';
    c.appendChild(n)}
  if(unknown.length){const n=el('div','note bad');
    n.textContent='공란 '+unknown.map(r=>r[i.framework_version]+' '+r[i.ccy]+' '+
      r[i.shock_type]).join(' · ')+' 의 충격폭이 원장에서 비어 있다. 1차자료를 '+
      '확인하지 못했으므로 값을 지어 채우지 않는다.';
    c.appendChild(n)}
  c.appendChild(table(p));c.appendChild(srcMeta(p));
  root.appendChild(c);
}
/* 아웃라이어 판정은 산출 원장 컬럼이다. 화면이 임계를 다시 적어 판정하면
   원장과 화면이 서로 다른 판정을 갖게 된다. */
function almOutlierCard(root){
  const f=almF('alm_irrbb_result');if(!f)return;
  const i=frameIdx(f);
  if(i.outlier_test_pass===undefined)return;
  const fail=f.rows.filter(r=>r[i.outlier_test_pass]===false);
  const w=f.rows.reduce((a,r)=>
    Math.abs(r[i.delta_eve])>Math.abs(a[i.delta_eve])?r:a,f.rows[0]);
  const c=el('div','card');
  c.appendChild(el('h3',null,'아웃라이어 판정'));
  const n=el('div','note'+(fail.length?' bad':' '));
  n.textContent=fail.length
    ? ('판정 미통과 '+fail.length+'/'+f.rows.length+' 시나리오. 최대는 '+
       w[i.basis]+' 기준 '+w[i.scenario]+' 이고 기본자본 대비 '+
       ((w[i.delta_eve_to_tier1]||0)*100).toFixed(2)+'%다.')
    : ('전 시나리오 판정 통과. 최대는 '+w[i.basis]+' 기준 '+w[i.scenario]+
       ' 이고 기본자본 대비 '+((w[i.delta_eve_to_tier1]||0)*100).toFixed(2)+'%다.');
  c.appendChild(n);
  const cols=['기준','시나리오','ΔEVE','기본자본 대비','최대','판정'];
  const V=cols.indexOf('판정');
  const rows=f.rows.map(r=>[r[i.basis],r[i.scenario],r[i.delta_eve],
    r[i.delta_eve_to_tier1],r[i.is_worst]?'최대':'',
    r[i.outlier_test_pass]?'통과':'미통과']);
  c.appendChild(table({columns:cols,
    rows:rows,total:rows.length,shown:rows.length},
    {rowClass:r=>r[V]==='미통과'?'bad':null}));
  const duty=f.rows.filter(r=>r[i.outlier_duty]!=null);
  if(duty.length)c.appendChild(el('div','meta','초과 시 의무: '+
    duty[0][i.outlier_duty]));
  c.appendChild(srcMeta(f));
  root.appendChild(c);
}
function almIrrbbCharts(root){
  root.appendChild(almSources(['alm_irrbb_result','alm_irrbb_bucket_pv',
    'alm_nii_result','alm_rate_shock_param','alm_scenario_def',
    'alm_post_shock_floor','alm_result']));
  if(!almHas(root,['alm_irrbb_result']))return;
  almOutlierCard(root);
  almShockDisclosure(root);
  const f=almF('alm_irrbb_result'),i=frameIdx(f);
  const bases=[...new Set(f.rows.map(r=>r[i.basis]))];
  const scen=almSortScen([...new Set(f.rows.map(r=>r[i.scenario]))]);

  /* 기준 대비는 토글과 무관하게 늘 둘 다 보인다. 비만기예금이 계약상 익일물
     이라 두 기준의 ΔEVE가 자릿수로 갈리고, 감독당국이 비교하는 것이 그 차이다. */
  const mat=bases.map(b=>scen.map(sc=>{
    const r=f.rows.find(x=>x[i.basis]===b&&x[i.scenario]===sc);
    return r?r[i.delta_eve_to_tier1]:null}));
  const hc=almCard('계약기준 대 행동조정 (기본자본 대비 ΔEVE)',
    heat(mat,bases,scen,{fmt:v=>(v*100).toFixed(2)+'%'}),srcMeta(f));
  hc.appendChild(el('div','meta',
    '부호는 원장 그대로다. 음수가 경제적가치 감소다. 계약기준은 비만기예금 '+
    '전액이 최단 버킷에 있고, 행동조정은 코어를 상한 안에서 장기로 슬로팅한 '+
    '결과다.'));
  root.appendChild(hc);

  const bar=el('div','toolbar');root.appendChild(bar);
  const sel=almSelect(bar,'산출기준',bases,almHeadlineBasis(f,i));
  const pane=el('div');root.appendChild(pane);
  function draw(){
    pane.innerHTML='';
    const b=sel.value;
    const rows=scen.map(sc=>f.rows.find(x=>x[i.basis]===b&&x[i.scenario]===sc))
                   .filter(Boolean);
    if(!rows.length)return;
    const worst=rows.find(r=>r[i.is_worst])||rows[0];
    const tier1=worst[i.tier1];
    const decline=Math.max(-worst[i.delta_eve],0);
    const pass=worst[i.outlier_test_pass];
    const g=el('div','grid');
    [['최악 시나리오',worst[i.scenario],b+' 기준 · is_worst','warn'],
     ['ΔEVE',fmtMoney(worst[i.delta_eve]),worst[i.margin_treatment],
      worst[i.delta_eve]<0?'bad':'good'],
     ['기본자본 대비',(worst[i.delta_eve_to_tier1]*100).toFixed(2)+'%',
      '기본자본 '+fmtMoney(tier1),worst[i.delta_eve_to_tier1]<0?'bad':'good'],
     ['아웃라이어 판정',pass==null?'미판정':(pass?'통과':'미통과'),
      pass==null?'판정 기준값이 원장에 없다':'원장 outlier_test_pass',
      pass==null?'warn':(pass?'good':'bad')],
    ].forEach(([lab,val,sub,tone])=>{const c=el('div','card kpi');
      c.appendChild(el('div','lab',lab));
      c.appendChild(el('div','val '+tone,String(val)));
      c.appendChild(el('div','sub',String(sub)));g.appendChild(c)});
    pane.appendChild(g);

    pane.appendChild(almCard(null,gauge(decline,tier1,
      {title:'ΔEVE 감소 대 기본자본(Tier1)',fmt:fmtMoney,
       tone:decline?'bad':'good',
       note:'감소액 '+fmtMoney(decline)+' / 기본자본 '+fmtMoney(tier1)+' = '+
         (tier1?(decline/tier1*100).toFixed(2):'-')+'%. 감소가 아닌 시나리오는 '+
         '0으로 둔다. 아웃라이어 판정 기준값은 원장에 없다.'}),srcMeta(f)));

    pane.appendChild(almCard(null,bars(rows.map(r=>({label:r[i.scenario],
      value:r[i.delta_eve],tone:r[i.delta_eve]<0?'bad':'good'})),
      {title:'시나리오별 ΔEVE ('+b+' 기준)',fmt:fmtMoney,
       note:'막대 높이는 절대값이고 색이 부호다. 붉은색이 경제적가치 감소.'}),
      srcMeta(f)));

    const pv=almF('alm_irrbb_bucket_pv');
    if(pv){const pi=frameIdx(pv);
      const sub=pv.rows.filter(r=>r[pi.basis]===b&&
        r[pi.scenario]===worst[i.scenario]);
      if(sub.length){
        const bks=almBuckets(pi,sub);
        const base=sub.reduce((a,r)=>a+(r[pi.pv_base]||0),0);
        const steps=bks.map(k=>({label:k,
          delta:sub.filter(r=>r[pi.bucket]===k)
                   .reduce((a,r)=>a+(r[pi.delta_pv]||0),0)}));
        pane.appendChild(almCard(null,waterfall(steps,base,
          {title:'버킷별 현재가치 효과 ('+worst[i.scenario]+' · '+b+' 기준)',
           fmt:fmtMoney,
           note:'시작은 충격 전 순현재가치, 각 막대는 그 버킷의 충격 전후 차이다. '+
             '자산과 부채를 합한 순액이며 마진 처리는 '+
             sub[0][pi.margin_treatment]+'다.'}),srcMeta(pv)))}}

    const ni=almF('alm_nii_result');
    if(ni){const xi=frameIdx(ni);
      const c=almCard(null,bars(ni.rows.map(r=>({label:r[xi.scenario],
        value:r[xi.delta_nii],tone:r[xi.delta_nii]<0?'bad':'good'})),
        {title:'ΔNII (평행충격)',fmt:fmtMoney}),srcMeta(ni));
      const d=almF('alm_scenario_def');
      const n=d?d.rows.filter(r=>r[frameIdx(d).applies_to_nii]).length:null;
      c.appendChild(el('div','meta','시계 '+fmtNum(ni.rows[0][xi.horizon_years])+
        '년 · '+ni.rows[0][xi.balance_sheet_assumption]+' · 상업마진 '+
        ni.rows[0][xi.margin_treatment]+
        (n==null?'':' · 정의 원장이 ΔNII 대상으로 표시한 시나리오 '+n+'개')));
      c.appendChild(el('div','meta','ΔNII에는 산출기준(계약/행동조정) 축이 '+
        '없다. 재가격 시뮬레이션이라 EVE 현금흐름을 재활용하지 않는다.'));
      c.appendChild(rawEl('div','meta',String(ni.rows[0][xi.citation])));
      pane.appendChild(c)}
  }
  sel.onchange=draw;draw();
}

/* ---- ② 현금흐름 원장 ---------------------------------------------------- */
function almCashflowCharts(root){
  root.appendChild(almSources(['alm_cashflow_bucket','alm_cashflow_contract',
    'alm_cashflow_behavioural','alm_contract','alm_time_bucket'],
    '계약·행동조정 현금흐름은 계약 단위라 화면에는 표본만 실린다. 그림은 버킷 '+
    '집계 원장과, 파이프라인이 행동조정 원장 전량을 집계한 기여도로 그린다.'));
  if(!almHas(root,['alm_cashflow_bucket']))return;
  const f=almF('alm_cashflow_bucket'),i=frameIdx(f);
  const scens=almSortScen([...new Set(f.rows.map(r=>r[i.scenario]))]);
  const bases=[...new Set(f.rows.map(r=>r[i.basis]))];
  const sides=[...new Set(f.rows.map(r=>r[i.side]))];
  const bar=el('div','toolbar');root.appendChild(bar);
  const ss=almSelect(bar,'시나리오',scens,scens[0]);
  const sd=almSelect(bar,'측',sides,sides[0]);
  const sb=almSelect(bar,'산출기준',bases,bases[bases.length-1]);
  const pane=el('div');root.appendChild(pane);
  function draw(){
    pane.innerHTML='';
    const sub=f.rows.filter(r=>r[i.scenario]===ss.value&&r[i.side]===sd.value);
    if(!sub.length)return;
    const bks=almBuckets(i,sub);
    const val=(b,k,col)=>{
      const r=sub.find(x=>x[i.basis]===b&&x[i.bucket]===k);
      return r?(r[col]||0):0};
    const c1=almCard('계약 현금흐름 대 행동조정 현금흐름',
      multiLine(bases.map(b=>({name:b,values:bks.map(k=>val(b,k,i.total_cf))})),
        bks,null),srcMeta(f));
    c1.appendChild(el('div','meta',
      '두 선이 겹치는 버킷은 행동가정이 걸리지 않은 곳이다. 비만기예금은 계약 '+
      '기준에서 전액이 최단 버킷에 있고, 행동 기준에서 코어가 장기로 퍼진다.'));
    pane.appendChild(c1);
    pane.appendChild(almCard(null,stackBars([
      {name:'원금',values:bks.map(k=>val(sb.value,k,i.principal_cf))},
      {name:'이자(상업마진 제외)',
       values:bks.map(k=>val(sb.value,k,i.interest_cf_ex_margin))},
      {name:'상업마진',values:bks.map(k=>val(sb.value,k,i.margin_cf))}],bks,
      {title:'현금흐름 구성 ('+sb.value+' 기준 · '+sd.value+')',
       note:'ΔEVE는 상업마진을 제외하고 ΔNII는 포함한다. 그래서 마진을 별도 '+
         '컬럼으로 담는다.'}),srcMeta(f)));
    const A=D.alm&&D.alm.behaviour_contrib;
    if(A){const ai=frameIdx(A);
      const rows=A.rows.filter(r=>r[ai.scenario]===ss.value);
      if(rows.length){
        const c3=almCard(null,bars(rows.map(r=>({label:r[ai.behaviour_model],
          value:r[ai.adjustment_cf],
          tone:r[ai.adjustment_cf]<0?'bad':'good'})),
          {title:'행동모형별 조정액 ('+ss.value+', 행동 − 계약)',fmt:fmtMoney}));
        c3.appendChild(table({columns:A.columns,labels:A.labels,rows:rows,
          total:rows.length,shown:rows.length}));
        c3.appendChild(el('div','meta','원장 '+D.alm.behaviour_source+' 전량 집계, '+
          D.alm.behaviour_rows.toLocaleString()+'행 · 계약 '+
          D.alm.behaviour_contracts.toLocaleString()+'건. 조정액은 원장 '+
          'adjustment_cf 를 그대로 더한 값이다.'));
        pane.appendChild(c3)}}
  }
  ss.onchange=draw;sd.onchange=draw;sb.onchange=draw;draw();
}

/* ---- ③ 유동성 사다리 ---------------------------------------------------- */
function almLadderCharts(root){
  root.appendChild(almSources(['alm_maturity_ladder','alm_time_bucket'],
    '만기 사다리는 잔존만기 축이다. 리프라이싱 축과 다른 축이며, 10년 변동금리 '+
    '대출은 최단 버킷에서 금리가 재설정되지만 그 기간에 현금화되지 않는다. '+
    '두 축을 한 원장으로 합치면 유동성비율 분자가 구조적으로 부풀려진다.'));
  if(!almHas(root,['alm_maturity_ladder']))return;
  const f=almF('alm_maturity_ladder'),i=frameIdx(f);
  const scens=almSortScen([...new Set(f.rows.map(r=>r[i.scenario]))]);
  const bases=[...new Set(f.rows.map(r=>r[i.basis]))];
  const bar=el('div','toolbar');root.appendChild(bar);
  const ss=almSelect(bar,'시나리오',scens,scens[0]);
  const sb=almSelect(bar,'산출기준',bases,bases[0]);
  const pane=el('div');root.appendChild(pane);
  function draw(){
    pane.innerHTML='';
    const all=f.rows.filter(r=>r[i.scenario]===ss.value);
    const sub=all.filter(r=>r[i.basis]===sb.value);
    if(!sub.length)return;
    const bks=almBuckets(i,sub);
    const at=(b,k)=>all.find(r=>r[i.basis]===b&&r[i.bucket]===k);
    const c1=almCard(null,heat(
      [bks.map(k=>{const r=at(sb.value,k);return r?r[i.inflow]:null}),
       bks.map(k=>{const r=at(sb.value,k);return r?r[i.outflow]:null})],
      ['유입','유출'],bks,
      {title:'버킷별 유입·유출 ('+sb.value+' 기준 · '+ss.value+')',fmt:fmtMoney}));
    c1.appendChild(bars(bks.map(k=>{const r=at(sb.value,k);
      return {label:k,value:r?r[i.net_gap]:0,
              tone:(r&&r[i.net_gap]<0)?'bad':'good'}}),
      {title:'버킷별 순갭 (유입 − 유출)',fmt:fmtMoney}));
    c1.appendChild(srcMeta(f));pane.appendChild(c1);
    const c2=almCard('누적갭 (계약기준 대 행동조정)',
      multiLine(bases.map(b=>({name:b,values:bks.map(k=>{
        const r=at(b,k);return r?r[i.cumulative_gap]:null})})),bks,null),
      srcMeta(f));
    c2.appendChild(el('div','meta',
      '계약기준은 비만기예금 전액이 최단 버킷에서 빠져나간다고 본다. 계약상 '+
      '만기가 없어 계약기준에서는 최조기 유출을 가정하고, 행동조정에서는 코어 부분을 장기 버킷에 남긴다.'));
    pane.appendChild(c2);
    const cbc=sub.reduce((a,r)=>a+(r[i.counterbalancing_capacity]||0),0);
    const worst=sub.reduce((a,r)=>Math.min(a,r[i.cumulative_gap]),0);
    const g=el('div','grid');
    [['반대매매가능자산',fmtMoney(cbc),'전 버킷 합계 · counterbalancing_capacity',''],
     ['최대 누적부족',fmtMoney(worst),'누적갭 최저점',worst<0?'bad':'good'],
     ['차감 후 잔량',fmtMoney(cbc+Math.min(worst,0)),
      '두 원장 컬럼의 합 (소진 경로는 생존기간 화면이 낸다)',
      cbc+Math.min(worst,0)<0?'bad':'good'],
    ].forEach(([lab,val,sub,tone])=>{const c=el('div','card kpi');
      c.appendChild(el('div','lab',lab));
      c.appendChild(el('div','val '+tone,String(val)));
      c.appendChild(el('div','sub',String(sub)));g.appendChild(c)});
    pane.appendChild(g);
    pane.appendChild(almCard('사다리 원장 ('+ss.value+' · '+sb.value+' 기준)',
      table({columns:f.columns,labels:f.labels,rows:sub,
        total:sub.length,shown:sub.length}),srcMeta(f)));
  }
  ss.onchange=draw;sb.onchange=draw;draw();
}

/* ---- ④ LCR·NSFR 상세 ---------------------------------------------------- */
function almLcrDetail(root){
  const f=almF('alm_lcr_flow'),i=frameIdx(f);
  const k=almF('alm_lcr_factor'),ki=frameIdx(k);
  const kby=new Map();
  k.rows.forEach(r=>kby.set(r[ki.section]+'|'+r[ki.category],r));
  const rows=f.rows.map(r=>{
    const kr=kby.get(r[i.section]+'|'+r[i.category]);
    return [r[i.section],r[i.category],r[i.balance],r[i.factor],r[i.weighted],
            r[i.factor_source],r[i.evidence_status],
            kr?kr[ki.citation_bcbs]:'-',kr?kr[ki.citation_kr]:'-']});
  const cols=['구분','항목','잔액','적용계수','가중액','계수 출처','근거 판정',
    'BCBS 근거','국내 근거'];
  const EV=cols.indexOf('근거 판정');
  const c=almCard('유동성커버리지비율 (항목별 잔액 × 계수 = 가중액)',
    table({columns:cols,rows:rows,total:rows.length,shown:rows.length},
      {rowClass:r=>r[EV]==='미확인'?'bad':null}),srcMeta(f));
  const secs=[...new Set(f.rows.map(r=>r[i.section]))];
  const wsum=rs=>rs.reduce((a,r)=>a+(r[i.weighted]||0),0);
  const rec=secs.map(s=>['구분 소계 · '+s,
    fmtMoney(wsum(f.rows.filter(r=>r[i.section]===s))),'alm_lcr_flow']);
  const a=almF('alm_result');
  if(a){const ai=frameIdx(a);
    const row=a.rows.find(r=>r[ai.metric]==='LCR');
    if(row){
      rec.push(['비율 분자 (고유동성자산)',fmtMoney(row[ai.numerator]),'alm_result']);
      rec.push(['비율 분모 (순현금유출)',fmtMoney(row[ai.denominator]),'alm_result']);
      rec.push(['LCR',(row[ai.value]*100).toFixed(1)+'%',
        '최저 '+(row[ai.minimum]*100).toFixed(0)+'%'])}}
  c.appendChild(table({columns:['항목','금액','출처'],rows:rec,
    total:rec.length,shown:rec.length},{numeric:false}));
  c.appendChild(el('div','meta',
    '구분 소계와 비율 분자·분모가 어긋나면 그 차이가 상한 조정액이다.'));
  root.appendChild(c);
}
/* 상한이 문 자리. 계수는 상한 원장에서 읽는다. 상한 적용은 엔진이 하고
   화면은 어느 상한이 물었는지만 대조한다. */
function almLcrCaps(root){
  const f=almF('alm_lcr_flow'),i=frameIdx(f);
  const k=almF('alm_lcr_factor'),ki=frameIdx(k);
  const flowSecs=new Set(f.rows.map(r=>r[i.section]));
  const caps=k.rows.filter(r=>!flowSecs.has(r[ki.section]));
  if(!caps.length)return;
  const wsum=rs=>rs.reduce((a,r)=>a+(r[i.weighted]||0),0);
  const hq=f.rows.filter(r=>/^level_/.test(String(r[i.category])));
  const SPEC={
    cap_l2b:{what:'Level 2B 대 고유동성자산',base:()=>wsum(hq),
             act:()=>wsum(hq.filter(r=>/2b/.test(String(r[i.category]))))},
    cap_l2:{what:'Level 2 대 고유동성자산',base:()=>wsum(hq),
            act:()=>wsum(hq.filter(r=>/2a|2b/.test(String(r[i.category]))))},
    cap_inflow:{what:'인정 유입 대 총유출',
                base:()=>wsum(f.rows.filter(r=>/유출/.test(String(r[i.section])))),
                act:()=>wsum(f.rows.filter(r=>/유입/.test(String(r[i.section]))))}};
  const rows=[],unknown=[];
  caps.forEach(r=>{const s=SPEC[r[ki.category]];
    if(!s){unknown.push(String(r[ki.category]));return}
    const lim=(r[ki.factor]||0)*s.base(),act=s.act();
    rows.push([r[ki.category],s.what,(r[ki.factor]*100).toFixed(0)+'%',
      fmtMoney(lim),fmtMoney(act),act>lim?'구속':'미구속',r[ki.citation_bcbs]])});
  const cols=['상한','대상','계수','상한액','산출액','판정','근거'];
  const JD=cols.indexOf('판정');
  const c=almCard('상한 (어느 상한이 물었는가)',
    table({columns:cols,rows:rows,total:rows.length,shown:rows.length},
      {numeric:false,rowClass:r=>r[JD]==='구속'?'bad':null}),srcMeta(k));
  if(unknown.length)c.appendChild(el('div','note',
    '대조 규칙이 없는 상한 '+unknown.join(' · ')+'. 원장에는 있으나 화면이 '+
    '대상 집계를 정하지 못한다.'));
  c.appendChild(el('div','meta',
    '상한액은 상한 원장의 계수를 대상 집계에 곱한 값이다. 실제 적용은 엔진 '+
    '(risk_lib/alm/lcr.py)이 하고 화면은 구속 여부만 표시한다.'));
  root.appendChild(c);
}
/* 등재됐지만 산출에 들어가지 않은 항목. 부재가 보여야 한다. 분모에 아예
   없는 유출 항목은 화면에서도 없던 일이 된다. */
function almNotComputed(root){
  const f=almF('alm_lcr_flow'),i=frameIdx(f);
  const k=almF('alm_lcr_factor'),ki=frameIdx(k);
  const flowSecs=new Set(f.rows.map(r=>r[i.section]));
  const used=new Set(f.rows.map(r=>r[i.section]+'|'+r[i.category]));
  const miss=k.rows.filter(r=>flowSecs.has(r[ki.section])&&
    !used.has(r[ki.section]+'|'+r[ki.category]));
  if(!miss.length)return;
  const rows=miss.map(r=>[r[ki.section],r[ki.category],r[ki.factor],
    r[ki.source],r[ki.evidence_status],r[ki.citation_bcbs]]);
  const cols=['구분','항목','계수','산출 상태','근거 판정','BCBS 근거'];
  const EV=cols.indexOf('근거 판정');
  const c=almCard('계수 원장에 등재됐으나 산출에 들어가지 않은 항목',
    table({columns:cols,rows:rows,total:rows.length,shown:rows.length},
      {rowClass:r=>r[EV]==='미확인'?'bad':null}),srcMeta(k));
  c.appendChild(el('div','meta',
    '담보부조달·파생 유출·등급하락 트리거처럼 원천 원장이 없어 산출하지 못한 '+
    '항목이다. 등재해 두지 않으면 분모에 없다는 사실 자체가 보이지 않는다.'));
  root.appendChild(c);
}
function almNsfrDetail(root){
  const f=almF('alm_nsfr_item'),i=frameIdx(f);
  const k=almF('alm_nsfr_factor'),ki=frameIdx(k);
  const secs=[...new Set(f.rows.map(r=>r[i.section]))];
  const wsum=rs=>rs.reduce((a,r)=>a+(r[i.weighted]||0),0);
  const c=almCard('순안정자금조달비율 (항목별 금액 × 계수 = 가중액)',
    bars(secs.map(s=>({label:s,
      value:wsum(f.rows.filter(r=>r[i.section]===s))})),
      {title:'구분별 가중 후 금액',fmt:fmtMoney}),srcMeta(f));
  const cols=['구분','항목','금액','적용계수','가중액','만기구간','근거 판정','근거'];
  const EV=cols.indexOf('근거 판정');
  c.appendChild(table({columns:cols,
    rows:f.rows.map(r=>[r[i.section],r[i.category],r[i.amount],r[i.factor],
      r[i.weighted],r[i.maturity_band],r[i.evidence_status],r[i.citation]]),
    total:f.rows.length,shown:f.rows.length},
    {rowClass:r=>r[EV]==='미확인'?'bad':null}));
  const a=almF('alm_result');
  if(a){const ai=frameIdx(a);
    const row=a.rows.find(r=>r[ai.metric]==='NSFR');
    if(row)c.appendChild(el('div','meta','NSFR '+(row[ai.value]*100).toFixed(1)+
      '% (분자 '+fmtMoney(row[ai.numerator])+' / 분모 '+
      fmtMoney(row[ai.denominator])+') · 최저 '+
      (row[ai.minimum]*100).toFixed(0)+'% (원장 alm_result)'))}
  const nul=k.rows.filter(r=>r[ki.factor]==null);
  if(nul.length){const n=el('div','note bad');
    n.textContent='계수 공란 '+nul.map(r=>r[ki.section]+' '+r[ki.category])
      .join(' · ')+'. 국내 채택값을 확인하지 못해 비워 두었고, 그 항목은 산출에 '+
      '들어가지 않는다.';
    c.appendChild(n)}
  root.appendChild(c);
}
function almLiquidityCharts(root){
  root.appendChild(almSources(['alm_lcr_flow','alm_lcr_factor','alm_nsfr_item',
    'alm_nsfr_factor','alm_result']));
  if(!almHas(root,['alm_lcr_flow','alm_lcr_factor','alm_nsfr_item',
    'alm_nsfr_factor']))return;
  almLcrDetail(root);almLcrCaps(root);almNotComputed(root);almNsfrDetail(root);
  root.appendChild(almEvidence(['alm_lcr_factor','alm_lcr_flow',
    'alm_nsfr_factor','alm_nsfr_item']));
}

/* ---- ⑤ 생존기간 --------------------------------------------------------- */
function almSurvivalCharts(root){
  root.appendChild(almSources(['alm_survival_path','alm_liquidity_stress_param']));
  if(!almHas(root,['alm_survival_path']))return;
  const f=almF('alm_survival_path'),i=frameIdx(f);
  const scens=[...new Set(f.rows.map(r=>r[i.scenario]))];
  const days=[...new Set(f.rows.map(r=>r[i.day]))].sort((a,b)=>a-b);
  const at=(s,d)=>f.rows.find(x=>x[i.scenario]===s&&x[i.day]===d);
  const c=almCard('스트레스별 반대매매가능자산 잔량 경로',
    multiLine(scens.map(s=>({name:s,
      values:days.map(d=>{const r=at(s,d);return r?r[i.cbc_remaining]:null})})),
      days.map(d=>d%10?'':String(d)),null),srcMeta(f));
  c.appendChild(el('div','meta',
    '가로축은 일자다. 선이 0을 뚫는 날이 소진일이고, 그 이전까지가 생존기간이다.'));
  root.appendChild(c);
  const p=almF('alm_liquidity_stress_param');
  const pi=p?frameIdx(p):null;
  const horizon=s=>{if(!p)return null;
    const r=p.rows.find(x=>x[pi.stress_scenario]===s);
    return r?r[pi.horizon_days]:null};
  const rows=scens.map(s=>{
    const path=f.rows.filter(x=>x[i.scenario]===s)
                     .slice().sort((a,b)=>a[i.day]-b[i.day]);
    const brk=path.find(x=>x[i.survived]===false);
    const last=path[path.length-1];
    return [s,brk?fmtNum(brk[i.day])+'일차 소진':'관측 구간 내 미소진',
            fmtNum(last[i.day])+'일',fmtMoney(last[i.cbc_remaining]),
            fmtMoney(last[i.net_outflow_cum]),
            horizon(s)==null?'-':fmtNum(horizon(s))+'일']});
  const cols=['스트레스','소진','관측 마지막','최종 잔량','누적 순유출','원장 시계'];
  const BK=cols.indexOf('소진');
  const c2=almCard('시나리오별 소진일',
    table({columns:cols,rows:rows,total:rows.length,shown:rows.length},
      {numeric:false,rowClass:r=>/소진$/.test(r[BK])?'bad':null}),srcMeta(f));
  c2.appendChild(el('div','meta',
    '생존기간 목표에는 규정값이 없다. 이사회가 정하고 승인한다. 그래서 이 '+
    '화면은 경로와 소진일만 내고 합격·불합격을 판정하지 않는다.'));
  root.appendChild(c2);
  if(p){
    const defined=[...new Set(p.rows.map(r=>r[pi.stress_scenario]))];
    const gone=defined.filter(s=>scens.indexOf(s)<0);
    const c3=almCard('스트레스 유출률 (시나리오 × 항목)',
      table(p,{rowClass:r=>r[frameIdx(p).cum_runoff_rate]==null?'bad':null}),
      srcMeta(p));
    if(gone.length){const n=el('div','note bad');
      n.textContent='경로가 없는 스트레스 '+gone.join(' · ')+
        '. 유출률이 원장에서 비어 있어(근거 미확인) 엔진이 산출을 건너뛰었다. '+
        '0으로 채우지 않는다.';
      c3.appendChild(n)}
    root.appendChild(c3)}
}

/* ---- ⑥ ALM 계수 원장 ---------------------------------------------------- */
const ALM_PARAM_TABLES=['alm_time_bucket','alm_product_terms',
  'alm_behaviour_param','alm_prepay_scurve_param','alm_behaviour_scenario_mult',
  'alm_nmd_param','alm_rate_shock_param','alm_scenario_def',
  'alm_post_shock_floor','alm_liquidity_stress_param'];
/* 승인 이력. 수기입력 원장은 입력자·승인자·승인일이 채워져야 결재 대상이다.
   비어 있으면 비어 있다고 적는다. */
function almApproval(names){
  const KEY=['input_source','entered_by','approved_by','approved_on'];
  const rows=[];
  names.forEach(n=>{const f=almF(n);if(!f)return;const i=frameIdx(f);
    if(!KEY.some(c=>i[c]!==undefined))return;
    rows.push([n,f.rows.length].concat(KEY.map(c=>i[c]===undefined?'-':
      (f.rows.filter(r=>r[i[c]]!=null).length+' / '+f.rows.length))))});
  const c=almCard('수기입력 원장의 승인 상태 (기입된 행 / 전체 행)',
    table({columns:['원장','행수','입력 출처','입력자','승인자','승인일'],
      rows:rows,total:rows.length,shown:rows.length},{numeric:false}));
  c.appendChild(el('div','meta',
    '조기상환율·중도해지율 기준값은 규제가 주지 않는다. 은행 자체추정과 감독 '+
    '승인 기록이 근거가 된다. 이 원장들은 수기입력이며, 승인란이 비어 있는 '+
    '동안에는 그 값으로 결재를 올릴 수 없다.'));
  return c;
}
/* 빈칸. 미확인은 화면에서도 비어 보여야 한다. */
function almBlanks(names){
  const rows=[];
  names.forEach(n=>{const f=almF(n);if(!f)return;
    f.columns.forEach((col,k)=>{
      const nul=f.rows.filter(r=>r[k]==null).length;
      if(nul)rows.push([n,col,colLabel(f,k),nul+' / '+f.rows.length])})});
  const c=almCard('빈칸 재고 (어느 원장의 어느 칸이 비어 있는가)',
    table({columns:['원장','컬럼','표시명','빈칸 / 행수'],rows:rows,
      total:rows.length,shown:rows.length},{numeric:false}));
  c.appendChild(el('div','meta',
    '값을 확인하지 못한 칸은 기본값으로 채우지 않는다. 엔진은 그 조정을 '+
    '건너뛰고 경고를 남기며, 화면은 이 목록으로 그 사실을 드러낸다.'));
  return c;
}
function almParamCharts(root){
  root.appendChild(almSources(ALM_PARAM_TABLES));
  root.appendChild(almApproval(ALM_PARAM_TABLES));
  root.appendChild(almBlanks(ALM_PARAM_TABLES));
  root.appendChild(almEvidence(ALM_PARAM_TABLES));
}

/* ---- 화면 정의 ---------------------------------------------------------- */
const almIrrbbScreen=screenOf({
  lead:'은행계정 금리리스크(IRRBB). 6개 금리충격의 ΔEVE와 평행충격 ΔNII를 '+
    '계약기준·행동조정 두 벌로 낸다. 충격폭의 근거 상태를 화면 위에 함께 적는다.',
  charts:almIrrbbCharts,
  tables:[['IRRBB 시나리오별 결과','alm_irrbb_result'],
          ['버킷별 현재가치 효과','alm_irrbb_bucket_pv'],
          ['ΔNII 12개월 전방','alm_nii_result'],
          ['금리 시나리오 정의','alm_scenario_def'],
          ['충격후 금리하한','alm_post_shock_floor'],
          /* 리프라이싱 갭은 금리 재설정 축이다. 잔존만기 축(만기 사다리)은
             유동성 사다리 화면에 있다. 두 축을 한 화면에 나란히 두면 같은
             사다리의 두 판본으로 오독된다. */
          ['리프라이싱 갭','alm_repricing_gap'],
          ['ALM 종합','alm_result']]});
const almCashflowScreen=screenOf({
  lead:'ALM 현금흐름 원장. 계약 현금흐름과 행동조정 현금흐름을 나란히 둔다.'+
    '조정액(adjustment_cf)이 컬럼으로 있으므로 어느 모형이 얼마를 움직였는지 '+
    '원장에서 조인된다.',
  charts:almCashflowCharts,
  tables:[['버킷 집계 현금흐름','alm_cashflow_bucket'],
          ['계약 현금흐름','alm_cashflow_contract'],
          ['행동조정 현금흐름','alm_cashflow_behavioural'],
          ['ALM 계약 원장','alm_contract']]});
const almLadderScreen=screenOf({
  lead:'만기 사다리. 버킷별 유입·유출과 누적갭, 반대매매가능자산을 본다. '+
    '계약기준과 행동조정을 토글로 바꾼다.',
  charts:almLadderCharts,
  tables:[['만기 사다리','alm_maturity_ladder'],['시간버킷 정의','alm_time_bucket']]});
const almLiquidityScreen=screenOf({
  lead:'유동성비율 상세. 항목별 잔액 × 계수 = 가중액, 상한이 문 자리, 계수의 '+
    '출처와 근거 판정까지 한 화면에 둔다.',
  charts:almLiquidityCharts,
  tables:[['LCR 유출입','alm_lcr_flow'],['LCR 계수 원장','alm_lcr_factor'],
          ['NSFR 항목','alm_nsfr_item'],['NSFR 계수 원장','alm_nsfr_factor']]});
const almSurvivalScreen=screenOf({
  lead:'생존기간. 스트레스별 반대매매가능자산 소진 경로다. LCR 30일은 최소 '+
    '시계이며 내부 스트레스는 더 긴 구간을 본다.',
  charts:almSurvivalCharts,
  tables:[['생존기간 경로','alm_survival_path'],
          ['유동성 스트레스 유출률','alm_liquidity_stress_param']]});
const almParamScreen=screenOf({
  lead:'ALM 계수·수기입력 모수. 입력자·승인자·승인일과 근거 판정을 함께 본다. '+
    '확인하지 못한 값은 비워 두고, 비어 있다는 사실을 화면에 표시한다.',
  charts:almParamCharts,
  tables:[['시간버킷 정의','alm_time_bucket'],['상품 상환·이자 관행','alm_product_terms'],
          ['행동모형 기준 파라미터','alm_behaviour_param'],
          ['조기상환 S-curve 계수','alm_prepay_scurve_param'],
          ['행동모형 시나리오 승수','alm_behaviour_scenario_mult'],
          ['비만기예금 코어 분해','alm_nmd_param'],
          ['금리충격 모수','alm_rate_shock_param']]});

/* ALM 요약. 요약도 원장 컬럼에서만 나와야 하므로 화면과 같은 자리에 둔다. */
Object.assign(SUMMARIES,{
  '금리리스크':()=>{const f=almF('alm_irrbb_result');if(!f)return null;
    const i=frameIdx(f),b=almHeadlineBasis(f,i);
    const w=f.rows.find(r=>r[i.basis]===b&&r[i.is_worst]);
    if(!w)return null;
    /* 폐지 계정에는 충격표가 없어 칸이 비어 있다. 그것을 미확인 공란과 같이
       세면 요약이 근거 없는 산출을 한 것처럼 읽힌다. 폐지분은 뺀다. */
    const p=almF('alm_rate_shock_param');
    const pi=p?frameIdx(p):null;
    const un=p?p.rows.filter(r=>r[pi.shock_bp]==null&&r[pi.status]!=='폐지').length
             :null;
    const fail=f.rows.filter(r=>r[i.outlier_test_pass]===false).length;
    return {t:'최악 '+w[i.scenario]+' ('+b+' 기준). ΔEVE '+fmtMoney(w[i.delta_eve])+
      ' · 기본자본 대비 '+(w[i.delta_eve_to_tier1]*100).toFixed(2)+'% · 충격 출처 '+
      w[i.shock_source]+' · 아웃라이어 미통과 '+fail+'/'+f.rows.length+
      (un?' · 충격폭 공란 '+un+'행':''),
      tone:'warn'}},
  '현금흐름 원장':()=>{const A=D.alm&&D.alm.behaviour_contrib;if(!A)return null;
    const i=frameIdx(A);
    const m=[...new Set(A.rows.map(r=>r[i.behaviour_model]))];
    return {t:'행동조정 원장 '+D.alm.behaviour_rows.toLocaleString()+'행 · 계약 '+
      D.alm.behaviour_contracts.toLocaleString()+'건, 적용 모형 '+m.join(' · ')+
      '. 계약 현금흐름은 시나리오와 무관한 한 벌이다.',tone:'good'}},
  '유동성 사다리':()=>{const f=almF('alm_maturity_ladder');if(!f)return null;
    const i=frameIdx(f);
    const w=f.rows.reduce((a,r)=>r[i.cumulative_gap]<a[i.cumulative_gap]?r:a,
      f.rows[0]);
    return {t:'누적갭 최저 '+fmtMoney(w[i.cumulative_gap])+' ('+w[i.bucket]+
      ' 버킷, '+w[i.basis]+' 기준 · '+w[i.scenario]+'). 잔존만기 축이며 '+
      '리프라이싱 축과 다르다',tone:w[i.cumulative_gap]<0?'warn':'good'}},
  '유동성리스크':()=>{const f=almF('alm_result');if(!f)return null;
    const i=frameIdx(f);
    const bad=f.rows.filter(r=>r[i.passes]===false).length;
    const k=almF('alm_lcr_factor');
    const un=k?k.rows.filter(r=>r[frameIdx(k).factor]==null).length:null;
    return {t:(bad?'유동성 지표 '+bad+'건 최저치 미달':'LCR·NSFR 최저치 상회')+
      (un==null?'':' · LCR 계수 공란 '+un+'행(관할재량 미확인)'),
      tone:bad?'bad':'warn'}},
  '생존기간':()=>{const f=almF('alm_survival_path');if(!f)return null;
    const i=frameIdx(f);
    const brk=f.rows.filter(r=>r[i.survived]===false);
    const n=new Set(f.rows.map(r=>r[i.scenario])).size;
    return {t:brk.length?'소진 관측 '+brk.length+'행, 최초 '+
        fmtNum(brk[0][i.day])+'일차 ('+brk[0][i.scenario]+')'
      :'스트레스 '+n+'종 모두 관측 구간 내 미소진 (판정 기준은 이사회 승인 사항)',
      tone:brk.length?'bad':'warn'}},
  'ALM 계수 원장':()=>{
    let tot=0,un=0;
    ALM_PARAM_TABLES.forEach(n=>{const f=almF(n);if(!f)return;
      const i=frameIdx(f);if(i.evidence_status===undefined)return;
      tot+=f.rows.length;
      un+=f.rows.filter(r=>r[i.evidence_status]==='미확인').length});
    return {t:'계수 원장 '+tot+'행 중 근거 미확인 '+un+'행. 미확인 값은 '+
      '채우지 않는다',tone:un?'warn':'good'}},
});
/* ══════════════ ALM 화면 (끝) ═══════════════════════════════════════════ */

/* ══════════════ 공통 헬퍼 (신규 화면) ══════════════════════════════════ */

/* 표 하나를 만들 때마다 total·shown 을 손으로 채우면 언젠가 한 곳이 틀린다.
   화면에서 만든 배열은 잘린 프레임이 아니므로 두 값이 같다. */
function simpleTable(cols,rows,opt){
  return table({columns:cols,rows:rows,total:rows.length,shown:rows.length},
               opt||{numeric:false})}
function cardOf(title,child,note){
  const c=el('div','card');
  if(title)c.appendChild(el('h3',null,title));
  if(child)c.appendChild(child);
  if(note)c.appendChild(el('div','meta',note));
  return c}
/* 판정 컬럼이 비어 있으면 판정하지 않는다. 임계가 승인되지 않았거나 표본이
   모자라면 원장이 그 사유를 judgment_status 에 담고 판정 컬럼을 비운다.
   비어 있는 판정을 미통과로 찍으면 화면이 원장에 없는 판정을 만든다. */
function judgeCell(flag,status){
  if(flag===null||flag===undefined)return status||'미판정';
  return flag?'통과':'미통과'}
function judgeTone(v){return v==='미통과'?'bad':(v==='통과'?null:'warn')}
function pctv(v,d){
  return (v===null||v===undefined)?'-':(v*100).toFixed(d===undefined?2:d)+'%'}
function numOrDash(v,d){
  return (v===null||v===undefined)?'-':(d===undefined?fmtNum(v):v.toFixed(d))}
function moneyOrDash(v){return (v===null||v===undefined)?'-':fmtMoney(v)}
/* 판정 임계가 원장에 없으면 통과·미통과를 찍지 않는다. 임계 없는 판정은
   화면이 만든 값이 된다. */
function verdictPill(v){
  if(v===null||v===undefined)return pill('미판정','warn');
  return pill(v?'통과':'미통과', v?'good':'bad')}

/* 소관 부서는 원장에서 읽는다. 실행 도메인 원장(gov_run_domain)의 도메인
   라벨로 시작하는 역할을 역할 원장(gov_role)에서 찾는 규칙이다. 화면에
   부서명을 적어 두면 조직이 바뀔 때 화면만 옛 이름으로 남는다. */
function ownerRoles(domainCode){
  const d=almF('gov_run_domain'),g=almF('gov_role');
  if(!d||!g)return null;
  const di=frameIdx(d),gi=frameIdx(g);
  const row=d.rows.find(r=>r[di.domain]===domainCode);
  if(!row)return null;
  const label=String(row[di.domain_label]||'');
  if(!label)return null;
  /* 두 규칙을 쓴다. 역할 식별자가 'R-'+도메인코드인 역할, 또는 역할명이
     도메인 라벨로 시작하는 역할. 도메인과 역할을 잇는 원장이 따로 없어
     두 원장의 키 규칙에서 파생한다. */
  const key='R-'+domainCode;
  const hit=g.rows.filter(r=>String(r[gi.role_id])===key||
    String(r[gi.role_name]).indexOf(label)===0);
  return {label:label,
    rows:hit.map(r=>[r[gi.org_unit],r[gi.role_name],r[gi.line_of_defence],
                     r[gi.description]])};
}
/* 합성데이터 고지. 이 하네스의 모든 수치는 생성된 포트폴리오에서 나오므로,
   화면을 보는 사람이 실적 수치로 오인하지 않도록 화면 맨 위에 적는다. */
function reviewNotice(root,domainCode){
  const c=el('div','card');
  c.appendChild(el('h3',null,'검토 안내'));
  const n=el('div','note warn');
  n.textContent='이 화면의 수치는 LLM 이 생성한 합성데이터를 파이프라인에 '+
    '넣어 낸 산출이다. 실제 기관 수치가 아니며, 사용하기 전에 소관 부서의 '+
    '검토를 거쳐야 한다. 검토 결과는 승인 원장에 남는다.';
  c.appendChild(n);
  const o=ownerRoles(domainCode);
  if(o&&o.rows.length){
    c.appendChild(simpleTable(['소관 부서','역할','방어선','권한 범위'],o.rows));
    c.appendChild(el('div','meta',
      '소관은 실행 도메인 원장(gov_run_domain)의 도메인 코드 '+domainCode+
      ' 또는 도메인 라벨 "'+o.label+'"로 역할 원장(gov_role)에서 찾은 결과다. '+
      '부서명을 화면에 적어 두지 않으므로 조직이 바뀌면 원장만 고치면 된다.'));
  }else{
    c.appendChild(el('div','note',
      '소관 부서를 원장에서 확정하지 못했다. 도메인과 역할을 잇는 원장이 '+
      '없으므로 부서명을 화면에 적지 않는다.'));
  }
  root.appendChild(c);
}

/* ══════════════ 국내 금리리스크 [별표 9-1] ═════════════════════════════ */

const KR_IRRBB_TABLES=['alm_rate_shock_param','alm_post_shock_floor',
  'alm_time_bucket','alm_repricing_gap','alm_irrbb_result','alm_nii_result',
  'kr_nmd_category','alm_nmd_param','kr_retail_criteria',
  'kr_retail_behavioural_scope','kr_auto_option_param','kr_irrbb_governance',
  'disc_irrbb_table6','disc_irrbb_table7_qualitative',
  'disc_irrbb_table7_quantitative'];

/* 산출 통화는 버킷 현재가치 원장에 실제로 나타난 통화다. 화면에서 통화를
   적어 두면 포트폴리오 통화가 바뀌어도 화면만 옛 통화를 그린다. */
function krPortfolioCcy(){
  const b=almF('alm_irrbb_bucket_pv');
  if(!b)return null;
  const i=frameIdx(b);
  const m=new Map();
  b.rows.forEach(r=>{const k=r[i.ccy];
    m.set(k,(m.get(k)||0)+Math.abs(r[i.delta_pv]||0))});
  const e=[...m.entries()].sort((a,b2)=>b2[1]-a[1]);
  return e.length?e[0][0]:null;
}
function krFrameworkTable(root){
  const p=almF('alm_rate_shock_param');if(!p)return;
  const i=frameIdx(p);
  const fl=almF('alm_post_shock_floor');
  const fi=fl?frameIdx(fl):null;
  const ccys=[...new Set(p.rows.map(r=>r[i.ccy]))].sort();
  const home=krPortfolioCcy();
  const bar=el('div','toolbar');
  const sel=almSelect(bar,'통화',ccys,
    (home&&ccys.indexOf(home)>=0)?home:ccys[0]);
  const pane=el('div');
  function draw(){
    pane.innerHTML='';
    const rows=[];
    const vers=[];
    p.rows.forEach(r=>{if(vers.indexOf(r[i.framework_version])<0)
      vers.push(r[i.framework_version])});
    vers.forEach(v=>{
      const sub=p.rows.filter(r=>r[i.framework_version]===v&&r[i.ccy]===sel.value);
      if(!sub.length)return;
      const bp=k=>{const x=sub.find(r=>r[i.shock_type]===k);
        return x&&x[i.shock_bp]!=null?fmtNum(x[i.shock_bp])+'bp':'-'};
      const f0=fl?fl.rows.find(r=>r[fi.framework_version]===v):null;
      rows.push([v,sub[0][i.status],sub[0][i.effective_from],
        sub[0][i.effective_to]||'-',sub[0][i.superseded_by]||'-',
        bp('parallel'),bp('short'),bp('long'),
        f0?(f0[fi.floor_on_bp]==null?'-':fmtNum(f0[fi.floor_on_bp])+'bp'):'미등재',
        f0?f0[fi.evidence_status]:'-',sub[0][i.evidence_status]])});
    const ST=1;
    pane.appendChild(simpleTable(
      ['계정','상태','시행','종료','대체 계정','평행','단기','장기',
       '충격후 하한','하한 근거','충격폭 근거'],rows,
      {numeric:false,rowClass:r=>r[ST]==='폐지'?'bad':(r[ST]==='현행'?null:'warn')}));
    const dead=p.rows.filter(r=>r[i.status]==='폐지'&&r[i.ccy]===sel.value);
    if(dead.length){
      const n=el('div','note');
      n.textContent='폐지 계정의 근거: '+dead[0][i.source_ref];
      pane.appendChild(n)}
  }
  sel.onchange=draw;draw();
  const c=cardOf('금리충격 계정 대비 (통화별 <표5>)',null);
  c.appendChild(bar);c.appendChild(pane);
  c.appendChild(srcMeta(p));
  c.appendChild(el('div','meta',
    '상태·시행일·대체 계정·근거 판정은 전부 충격폭 원장 컬럼이다. 어느 계정이 '+
    '산출에 쓰였는지는 아래 산출 결과의 적용 계정 칸에 있다.'));
  root.appendChild(c);
}
/* 아웃라이어 판정은 산출 원장의 컬럼(outlier_test_pass·outlier_duty)이다.
   화면이 임계를 다시 적어 판정하면 원장과 화면이 두 판정을 갖게 된다. */
function krOutlierCard(root){
  const f=almF('alm_irrbb_result');if(!f)return;
  const i=frameIdx(f);
  const g=el('div','grid');
  const bases=[...new Set(f.rows.map(r=>r[i.basis]))];
  bases.forEach(b=>{
    const sub=f.rows.filter(r=>r[i.basis]===b);
    const w=sub.reduce((a,r)=>
      Math.abs(r[i.delta_eve])>Math.abs(a[i.delta_eve])?r:a,sub[0]);
    const fail=sub.filter(r=>r[i.outlier_test_pass]===false);
    const c=el('div','card kpi');
    c.appendChild(el('div','lab',b+' 기준 ΔEVE / 기본자본'));
    c.appendChild(el('div','val '+(fail.length?'bad':'good'),
      pctv(w[i.delta_eve_to_tier1])));
    c.appendChild(el('div','sub',
      '최대 '+w[i.scenario]+' · ΔEVE '+moneyOrDash(w[i.delta_eve])+
      ' · 기본자본 '+moneyOrDash(w[i.tier1])));
    c.appendChild(el('div','ln','판정 미통과 '+fail.length+'/'+sub.length+
      ' 시나리오'));
    g.appendChild(c)});
  root.appendChild(g);
  const rows=f.rows.map(r=>[r[i.basis],r[i.scenario],r[i.delta_eve],
    r[i.delta_eve_to_tier1],r[i.delta_nii],
    r[i.is_worst]?'최대':'',r[i.outlier_test_pass]?'통과':'미통과']);
  const PASS=6;
  const c2=cardOf('아웃라이어 판정 (원장 컬럼 그대로)',
    simpleTable(['기준','시나리오','ΔEVE','기본자본 대비','ΔNII','최대','판정'],
      rows,{numeric:true,rowClass:r=>r[PASS]==='미통과'?'bad':null}));
  const duty=f.rows.filter(r=>r[i.outlier_duty]!=null);
  if(duty.length){
    const n=el('div','note bad');
    n.textContent='초과 시 의무: '+duty[0][i.outlier_duty];
    c2.appendChild(n)}
  c2.appendChild(el('div','meta',
    '적용 계정 '+f.rows[0][i.framework_version]+' ('+
    f.rows[0][i.framework_status]+') · 충격 출처 '+f.rows[0][i.shock_source]+
    ' · 근거 '+f.rows[0][i.evidence_status]+' · '+f.rows[0][i.citation]));
  c2.appendChild(srcMeta(f));
  root.appendChild(c2);
}
function krGapChart(root){
  const f=almF('alm_repricing_gap');if(!f)return;
  const i=frameIdx(f);
  const rows=f.rows.slice().sort((a,b)=>a[i.seq]-b[i.seq]);
  const c=el('div','card');
  c.appendChild(el('h3',null,'금리개정(리프라이싱) 갭 (<표2> 만기구간)'));
  c.appendChild(bars(rows.map(r=>({label:r[i.bucket],value:r[i.gap],
    tone:r[i.gap]<0?'bad':undefined})),
    {title:null,fmt:fmtMoney,
     note:'막대는 구간별 자산 − 부채다. 음수는 부채가 먼저 재설정되는 구간이다.'}));
  c.appendChild(bars(rows.map(r=>({label:r[i.bucket],value:r[i.cumulative_gap],
    tone:r[i.cumulative_gap]<0?'bad':undefined})),
    {title:'누적 갭',fmt:fmtMoney}));
  c.appendChild(simpleTable(['구간','자산','부채','갭','누적갭'],
    rows.map(r=>[r[i.bucket],r[i.asset],r[i.liability],r[i.gap],
      r[i.cumulative_gap]]),{numeric:true}));
  c.appendChild(srcMeta(f));
  const tb=almF('alm_time_bucket');
  if(tb){const ti=frameIdx(tb);
    c.appendChild(el('div','meta','만기구간 정의 '+tb.rows[0][ti.framework_version]+
      ' · '+tb.rows.length+'구간 · '+tb.rows[0][ti.citation]))}
  root.appendChild(c);
}
function krNmdCard(root){
  const p=almF('alm_nmd_param');
  const k=almF('kr_nmd_category');
  if(p){
    const i=frameIdx(p);
    const rows=p.rows.map(r=>[r[i.nmd_category],r[i.korean],
      pctv(r[i.core_ratio]),pctv(r[i.core_ratio_cap]),
      (r[i.core_ratio]!=null&&r[i.core_ratio_cap]!=null
        &&r[i.core_ratio]>=r[i.core_ratio_cap])?'상한 적용':'',
      numOrDash(r[i.avg_maturity_years],2),
      numOrDash(r[i.avg_maturity_cap_years],2),
      (r[i.avg_maturity_years]!=null&&r[i.avg_maturity_cap_years]!=null
        &&r[i.avg_maturity_years]>=r[i.avg_maturity_cap_years])?'상한 적용':'',
      r[i.slotting_method],r[i.non_core_bucket_label],r[i.evidence_status]]);
    const B1=4,B2=7;
    const c=cardOf('비만기성예금 범주별 코어 (<표3> 상한)',
      simpleTable(['범주','명칭','코어비율','코어 상한','','평균만기(년)',
                   '만기 상한(년)','','배분방법','비코어 배분','근거'],rows,
        {numeric:false,rowClass:r=>(r[B1]||r[B2])?'warn':null}));
    c.appendChild(el('div','meta',
      '비핵심예금은 익일물로 보아 최단 구간에 배분한다. 배분방법·비코어 구간은 '+
      '원장 컬럼이며 화면이 정하지 않는다.'));
    c.appendChild(srcMeta(p));
    root.appendChild(c)}
  if(k){
    const i=frameIdx(k);
    const rows=k.rows.map(r=>[r[i.account_id],r[i.depositor_type],
      r[i.balance],r[i.is_retail]?'예':'아니오',
      r[i.is_retail_like]?'예':'아니오',
      moneyOrDash(r[i.funding_total_amount]),
      moneyOrDash(r[i.threshold_amount]),
      r[i.has_regular_transaction]?'예':'아니오',
      r[i.category],r[i.rule_code],r[i.evidence_status]]);
    const c=cardOf('범주 판정 (제8항 가)',
      simpleTable(['계정','예금자','잔액','소매','소매 유사','조달총액',
                   '기준금액','정기거래','범주','규칙','근거'],rows,
        {numeric:false}));
    c.appendChild(rawEl('div','meta',T('규칙 적용 근거')+': '+k.rows[0][i.citation]));
    c.appendChild(srcMeta(k));
    root.appendChild(c)}
}
function krRetailScopeCard(root){
  const f=almF('kr_retail_behavioural_scope');
  const cr=almF('kr_retail_criteria');
  if(cr){
    const i=frameIdx(cr);
    const c=cardOf('소매 판정 기준 (제9항·제10항)',
      simpleTable(['규칙','기준명','대상','측정','기준금액','비교','연결기준','근거'],
        cr.rows.map(r=>[r[i.rule_code],r[i.rule_name],r[i.applies_to],
          r[i.measure],moneyOrDash(r[i.threshold_amount]),r[i.comparison],
          r[i.consolidation_basis],r[i.evidence_status]])));
    c.appendChild(rawEl('div','meta',cr.rows[0][i.citation]));
    root.appendChild(c)}
  if(!f)return;
  const i=frameIdx(f);
  const m=new Map();
  f.rows.forEach(r=>{
    const key=r[i.behaviour_class]+' · '+(r[i.in_scope]?'대상':'제외')+' · '+
      (r[i.treatment]||'-');
    const cur=m.get(key)||{n:0,amt:0};
    cur.n+=1;cur.amt+=(r[i.notional]||0);m.set(key,cur)});
  const rows=[...m.entries()].sort((a,b)=>b[1].amt-a[1].amt)
    .map(([k2,v])=>[k2,v.n,v.amt]);
  const c=cardOf('행동옵션 표준화 적합도 판정',
    simpleTable(['행동유형 · 대상여부 · 처리','건수','명목'],rows,{numeric:true}));
  const outs=f.rows.filter(r=>!r[i.in_scope]&&r[i.excluded_reason]!=null);
  if(outs.length){
    const m2=new Map();
    outs.forEach(r=>m2.set(r[i.excluded_reason],(m2.get(r[i.excluded_reason])||0)+1));
    c.appendChild(el('div','meta','제외 사유: '+[...m2.entries()]
      .map(([k2,v])=>k2+' '+v+'건').join(' · ')))}
  c.appendChild(srcMeta(f));
  root.appendChild(c);
}
function krAutoOptionCard(root){
  const f=almF('kr_auto_option_param');if(!f)return;
  const i=frameIdx(f);
  const c=cardOf('자동금리옵션 계수 (제11항)',
    simpleTable(['계정','코드','명칭','값','단위','적용','근거'],
      f.rows.map(r=>[r[i.framework_version],r[i.param_code],r[i.param_name],
        numOrDash(r[i.value]),r[i.value_unit],r[i.application],
        r[i.evidence_status]])));
  c.appendChild(el('div','note warn',
    '옵션 계약 인벤토리(계약별 종류·행사금리·내재변동성) 원장이 저장소에 '+
    '없어 재평가를 산출하지 않는다. 계수만 등재돼 있고 ΔEVE 에 옵션 리스크가 '+
    '더해지지 않았다.'));
  c.appendChild(rawEl('div','meta',f.rows[0][i.citation]));
  c.appendChild(srcMeta(f));
  root.appendChild(c);
}
function krGovernanceCard(root){
  const f=almF('kr_irrbb_governance');if(!f)return;
  const i=frameIdx(f);
  const rows=f.rows.map(r=>[r[i.requirement_code],r[i.clause],r[i.requirement],
    r[i.responsible_body],r[i.frequency_text],
    numOrDash(r[i.min_count_per_year]),numOrDash(r[i.count_in_period]),
    r[i.last_fulfilled_date]||'-',
    r[i.is_fulfilled]===null?'미판정':(r[i.is_fulfilled]?'이행':'미이행'),
    r[i.verdict_reason]||'']);
  const V=8;
  const c=cardOf('관리체계 이행 (제15항~제20항)',
    simpleTable(['요건','조문','내용','책임주체','주기','최소횟수','기간내 횟수',
                 '최근 이행','판정','사유'],rows,
      {numeric:false,rowClass:r=>r[V]==='미이행'?'bad':(r[V]==='미판정'?'warn':null)}));
  c.appendChild(srcMeta(f));
  root.appendChild(c);
}
function krDisclosureCard(root){
  const t6=almF('disc_irrbb_table6');
  if(t6){
    const i=frameIdx(t6);
    const c=cardOf('<표6> 금리리스크 수준 공시',table(t6));
    const blank=t6.rows.filter(r=>r[i.value]==null&&r[i.blank_reason]!=null);
    if(blank.length){
      const m=new Map();
      blank.forEach(r=>m.set(r[i.blank_reason],(m.get(r[i.blank_reason])||0)+1));
      const n=el('div','note warn');
      n.textContent='공란 '+blank.length+'칸. 사유: '+[...m.entries()]
        .map(([k,v])=>k+' '+v+'칸').join(' · ');
      c.appendChild(n)}
    const adj=t6.rows.filter(r=>r[i.is_adjustable]===false).length;
    if(adj)c.appendChild(el('div','meta',
      '이 양식은 자체 조정이 금지된 칸 '+adj+'개를 포함한다 (제22항 나).'));
    c.appendChild(srcMeta(t6));
    root.appendChild(c)}
  const q=almF('disc_irrbb_table7_qualitative');
  if(q){
    const i=frameIdx(q);
    const rows=q.rows.map(r=>[r[i.item_no],r[i.item_name],
      r[i.is_optional]?'선택':'필수',
      r[i.is_disclosed]?'작성':'미작성',
      r[i.input_by]||'-',r[i.approved_by]||'-',r[i.approved_date]||'-',
      r[i.is_approved]?'승인':'미승인']);
    const D2=3,A=7;
    const c=cardOf('<표7> 정성공시 8항목',
      simpleTable(['번호','항목','구분','작성','입력자','승인자','승인일','승인'],
        rows,{numeric:false,
          rowClass:r=>(r[D2]==='미작성'||r[A]==='미승인')?'warn':null}));
    c.appendChild(srcMeta(q));
    root.appendChild(c)}
  const qn=almF('disc_irrbb_table7_quantitative');
  if(qn){
    const i=frameIdx(qn);
    const c=cardOf('<표7> 정량공시',
      simpleTable(['코드','항목','값','단위','기준','공시','근거'],
        qn.rows.map(r=>[r[i.item_code],r[i.item_name],numOrDash(r[i.value],2),
          r[i.value_unit],r[i.basis]||'-',r[i.is_disclosed]?'공시':'미공시',
          r[i.evidence_status]])));
    c.appendChild(srcMeta(qn));
    root.appendChild(c)}
}
function krIrrbbCharts(root){
  root.appendChild(almSources(KR_IRRBB_TABLES,
    '국내 감독기준 [별표 9-1] 금리리스크 산출기준(개정 2026.1.29)의 화면이다. '+
    'BCBS 계정으로 낸 산출은 ALM > 금리리스크 화면에 있다. 두 화면은 같은 '+
    '엔진을 쓰되 적용 계정이 다르므로 섞어 읽지 않는다.'));
  if(!almHas(root,['alm_irrbb_result','alm_rate_shock_param']))return;
  krOutlierCard(root);
  krFrameworkTable(root);
  krGapChart(root);
  krNmdCard(root);
  krRetailScopeCard(root);
  krAutoOptionCard(root);
  krGovernanceCard(root);
  krDisclosureCard(root);
  root.appendChild(almEvidence(KR_IRRBB_TABLES));
}
const krIrrbbScreen=screenOf({
  lead:'국내 감독기준 [별표 9-1] 금리리스크 산출기준으로 낸 은행계정 금리리스크다. '+
    '측정지표는 ΔEVE 와 ΔNII 이고, 아웃라이어 판정 분모는 기본자본이다. '+
    '충격폭·만기구간·상한은 전부 원장에서 오며 화면은 다시 계산하지 않는다.',
  charts:krIrrbbCharts,
  tables:[['금리충격 계수','alm_rate_shock_param'],
          ['충격후 금리 하한','alm_post_shock_floor'],
          ['만기구간 정의','alm_time_bucket'],
          ['금리개정 갭','alm_repricing_gap'],
          ['소매 행동옵션 범위','kr_retail_behavioural_scope'],
          ['관리체계 이행','kr_irrbb_governance']]});

/* ══════════════ 내부등급법 추정 ═══════════════════════════════════════ */

const IRB_COMMON=['crm_estimation_run','crm_estimation_param','crm_input_floor',
  'crm_moc_component','crm_irb_scope','crm_dev_sample'];

/* 추정 실행 원장 한 줄을 화면 위에 편다. 관측기간·최소요건·MoC·하한·검토기한이
   한 화면에서 같이 보여야 그 추정치를 쓸 수 있는지 판단할 수 있다. */
function irbRunCard(root,param){
  const f=almF('crm_estimation_run');if(!f)return;
  const i=frameIdx(f);
  const rows=f.rows.filter(r=>r[i.parameter]===param);
  if(!rows.length){root.appendChild(el('div','note',
    '추정 실행 원장에 '+param+' 행이 없다.'));return}
  const MEET=5;
  const c=cardOf(param+' 추정 실행',
    simpleTable(['세그먼트','익스포저군','방법','관측기간','최소요건','충족',
                 'MoC','하한 적용','미해소 입력','차기 검토','상태'],
      rows.map(r=>[r[i.segment],r[i.exposure_class],r[i.method],
        numOrDash(r[i.observation_years],1)+'년',
        numOrDash(r[i.min_observation_years],1)+'년',
        r[i.meets_minimum]===null?'미판정':(r[i.meets_minimum]?'충족':'미달'),
        r[i.moc_status]||'-',
        r[i.floor_applied]?('적용 · 건 '+numOrDash(r[i.n_floor_binding])):'미적용',
        r[i.unresolved_inputs]||'-',r[i.next_review_due]||'-',r[i.status]]),
      {numeric:false,rowClass:r=>r[MEET]==='미달'?'bad':
        (r[MEET]==='미판정'?'warn':null)}));
  c.appendChild(el('div','meta',
    '부도 정의 '+(rows[0][i.default_definition]||'-')+
    ' · 모집단 정합 '+(rows[0][i.population_alignment]||'-')+
    ' · 검토주기 '+numOrDash(rows[0][i.review_interval_months])+'개월'));
  c.appendChild(srcMeta(f));
  root.appendChild(c);
}
/* 하한 원장. 값이 비어 있으면 그 자리를 비워 두고 하한이 걸리지 않았다는
   사실을 남긴다. 화면이 기본값을 채우면 산출과 화면이 다른 하한을 말한다. */
function irbFloorCard(root,param){
  const f=almF('crm_input_floor');if(!f)return;
  const i=frameIdx(f);
  const rows=f.rows.filter(r=>r[i.parameter]===param);
  if(!rows.length)return;
  const ST=4;
  const c=cardOf(param+' 입력 하한 원장',
    simpleTable(['계정','익스포저군','담보유형','하한값','상태','근거 판정','비고'],
      rows.map(r=>[r[i.framework_version],r[i.exposure_class],
        r[i.collateral_type]||'-',
        r[i.floor_value]==null?'(비어 있음)':pctv(r[i.floor_value],3),
        r[i.floor_status],r[i.evidence_status],r[i.note]||'']),
      {numeric:false,rowClass:r=>r[ST]==='미확인'?'warn':null}));
  c.appendChild(el('div','meta',
    '하한값이 비어 있는 행은 1차자료를 확인하지 못한 것이다. 엔진은 그 하한을 '+
    '적용하지 않고 경고를 남긴다.'));
  c.appendChild(srcMeta(f));
  root.appendChild(c);
}
/* 원시추정 → 하한 → MoC → 최종의 단계별 폭포. 단계값은 전부 원장 컬럼이다. */
function irbWaterfall(root,f,i,rows,label,fmt){
  if(!rows.length)return;
  const bar=el('div','toolbar');
  const keys=rows.map(r=>r[i.segment]+(i.grade!==undefined?' · '+r[i.grade]:''));
  const sel=almSelect(bar,'대상',keys,keys[0]);
  const pane=el('div');
  function draw(){
    pane.innerHTML='';
    const r=rows[keys.indexOf(sel.value)];
    if(!r)return;
    const raw=r[i.raw_estimate];
    const steps=[];
    if(r[i.after_floor]!=null)steps.push({label:'하한 적용',
      delta:r[i.after_floor]-raw});
    if(r[i.seasoning_addon]!=null&&r[i.seasoning_addon]!==0)
      steps.push({label:'경과효과 가산',delta:r[i.seasoning_addon]});
    if(r[i.after_moc]!=null&&r[i.after_floor]!=null)
      steps.push({label:'MoC 가산',delta:r[i.after_moc]-r[i.after_floor]});
    if(r[i.final_applied]!=null&&r[i.after_moc]!=null&&
       r[i.final_applied]!==r[i.after_moc])
      steps.push({label:'기타 조정',delta:r[i.final_applied]-r[i.after_moc]});
    pane.appendChild(waterfall(steps,raw,{title:label+' 단계별 폭포',
      fmt:fmt,note:'시작은 원시추정이고 마지막이 적용값이다. '+
        '하한 상태 '+(r[i.floor_status]||'-')+' · MoC 상태 '+(r[i.moc_status]||'-')}));
    const rowsx=[['원시추정',fmt(raw)],
      ['하한값',r[i.floor_value]==null?'(비어 있음)':fmt(r[i.floor_value])],
      ['하한 적용 후',r[i.after_floor]==null?'-':fmt(r[i.after_floor])],
      ['하한이 물었는가',r[i.floor_binding]?'예':'아니오'],
      ['MoC',r[i.moc_amount]==null?'-':fmt(r[i.moc_amount])],
      ['MoC 적용 후',r[i.after_moc]==null?'-':fmt(r[i.after_moc])],
      ['최종 적용값',r[i.final_applied]==null?'-':fmt(r[i.final_applied])]];
    pane.appendChild(simpleTable(['단계','값'],rowsx));
  }
  sel.onchange=draw;draw();
  const c=cardOf(label+' 추정 단계',null);
  c.appendChild(bar);c.appendChild(pane);c.appendChild(srcMeta(f));
  root.appendChild(c);
}
function irbMocCard(root,param){
  const f=almF('crm_moc_component');if(!f)return;
  const i=frameIdx(f);
  const rows=f.rows.filter(r=>r[i.parameter]===param);
  if(!rows.length)return;
  const AV=6;
  const c=cardOf(param+' MoC 구성요소',
    simpleTable(['세그먼트','등급','원인','점추정','MoC','산식','모수 확보'],
      rows.map(r=>[r[i.segment],r[i.grade]||'-',r[i.moc_driver],
        numOrDash(r[i.point_estimate],5),numOrDash(r[i.moc_amount],5),
        r[i.moc_formula]||'-',r[i.param_available]?'확보':'미확보']),
      {numeric:false,rowClass:r=>r[AV]==='미확보'?'warn':null}));
  c.appendChild(srcMeta(f));
  root.appendChild(c);
}

function pdEstimateScreen(root){
  reviewNotice(root,'CRE');
  root.appendChild(almSources(['crm_pd_estimate','crm_pd_yearly_dr'].concat(IRB_COMMON),
    '등급별 장기평균 부도율과 그 재료가 되는 연도별 실적이다. 하한·MoC 적용 '+
    '전후 값이 원장에 각각 있으므로 어느 단계에서 값이 움직였는지 볼 수 있다.'));
  if(!almHas(root,['crm_pd_estimate']))return;
  const f=almF('crm_pd_estimate'),i=frameIdx(f);
  const g=el('div','grid');
  const bind=f.rows.filter(r=>r[i.floor_binding]).length;
  const moc=f.rows.filter(r=>r[i.moc_amount]>0).length;
  [['추정 등급 수',String(f.rows.length),''],
   ['하한이 문 등급',String(bind),bind?'warn':'good'],
   ['MoC 가산 등급',String(moc),''],
   ['관측기간',(f.rows[0][i.observation_years]==null?'-':
     numOrDash(f.rows[0][i.observation_years],1)+'년'),'']]
  .forEach(([k,v,t])=>{const c=el('div','card kpi');
    c.appendChild(el('div','lab',k));c.appendChild(el('div','val '+t,v));
    g.appendChild(c)});
  root.appendChild(g);

  const rows=f.rows.slice().sort((a,b)=>String(a[i.grade])<String(b[i.grade])?-1:1);
  const c1=cardOf('등급별 PD 추정',
    simpleTable(['세그먼트','등급','추정방법','산출기준','차주수','부도수',
                 '원시추정','하한','하한 적용','MoC','최종 적용','익스포저'],
      rows.map(r=>[r[i.segment],r[i.grade],r[i.estimation_method],
        r[i.estimation_basis],r[i.n_obligors],r[i.n_defaults],
        pctv(r[i.raw_estimate],3),
        r[i.floor_value]==null?'(비어 있음)':pctv(r[i.floor_value],3),
        r[i.floor_binding]?'적용':'',
        numOrDash(r[i.moc_amount],5),pctv(r[i.final_applied],3),
        r[i.exposure_amount]]),
      {numeric:false,rowClass:r=>r[8]==='적용'?'warn':null}));
  c1.appendChild(el('div','meta',
    '산출기준이 차주가중과 익스포저가중으로 갈리면 원장의 basis_gap 컬럼에 '+
    '차이가 남는다.'));
  c1.appendChild(srcMeta(f));
  root.appendChild(c1);

  root.appendChild(hbars(rows.map(r=>({label:r[i.segment]+' · '+r[i.grade],
    value:+((r[i.final_applied]||0)*100).toFixed(3),
    sub:'원시 '+pctv(r[i.raw_estimate],3),
    tone:r[i.floor_binding]?'warn':undefined})),
    {title:'등급별 최종 적용 PD (%)',money:false,src:srcMeta(f)}));

  const y=almF('crm_pd_yearly_dr');
  if(y){
    const yi=frameIdx(y);
    const segs=[...new Set(y.rows.map(r=>r[yi.segment]))];
    const bar=el('div','toolbar');
    const ssel=almSelect(bar,'세그먼트',segs,segs[0]);
    const pane=el('div');
    function draw(){
      pane.innerHTML='';
      const sub=y.rows.filter(r=>r[yi.segment]===ssel.value);
      const grades=[...new Set(sub.map(r=>r[yi.grade]))].sort();
      const years=[...new Set(sub.map(r=>r[yi.cohort_year]))].sort();
      const matrix=grades.map(gr=>years.map(yr=>{
        const r=sub.find(x=>x[yi.grade]===gr&&x[yi.cohort_year]===yr);
        return r?r[yi.default_rate]:null}));
      pane.appendChild(heat(matrix,grades,years,
        {title:'등급 × 코호트연도 실적 부도율',
         fmt:v=>pctv(v,2),
         note:'추정표본에 포함되지 않은 연도는 원장 in_estimation_sample 컬럼으로 구분한다.'}));
      const out=sub.filter(r=>r[yi.in_estimation_sample]===false);
      if(out.length)pane.appendChild(el('div','meta',
        '추정표본 제외 관측 '+out.length+'행 (연도 '+
        [...new Set(out.map(r=>r[yi.cohort_year]))].join(' · ')+')'));
    }
    ssel.onchange=draw;draw();
    const c=cardOf('연도별 실적 부도율',null);
    c.appendChild(bar);c.appendChild(pane);c.appendChild(srcMeta(y));
    root.appendChild(c)}

  irbWaterfall(root,f,i,rows,'PD',v=>pctv(v,4));
  irbFloorCard(root,'PD');
  irbMocCard(root,'PD');
  irbRunCard(root,'PD');
  const ds=almF('crm_dev_sample');
  if(ds){const di=frameIdx(ds);
    const M=6;
    root.appendChild(cardOf('개발표본과 최소 관측기간',
      simpleTable(['모형','세그먼트','관측 시작','관측 종료','관측연수',
                   '최소요건','충족','관측수','부도수','부도율','목표정의','근거'],
        ds.rows.map(r=>[r[di.model_id],r[di.segment],r[di.observation_start],
          r[di.observation_end],numOrDash(r[di.observation_years],1),
          numOrDash(r[di.min_observation_years],1),
          r[di.meets_minimum]?'충족':'미달',r[di.n_obs],r[di.n_default],
          pctv(r[di.default_rate],2),r[di.target_definition],
          r[di.evidence_status]]),
        {numeric:false,rowClass:r=>r[M]==='미달'?'bad':null}),
      '최소 관측기간 요건은 원장 컬럼이며 개정 전 판본 값이라는 사실이 '+
      '근거 판정에 실려 있다.'));
  }
  root.appendChild(almEvidence(['crm_input_floor','crm_estimation_param',
    'crm_irb_scope','crm_dev_sample']));
}

function lgdEstimateScreen(root){
  reviewNotice(root,'CRE');
  root.appendChild(almSources(['crm_lgd_estimate','crm_lgd_discount_rate',
    'crm_recovery_history','crm_default_observation'].concat(IRB_COMMON),
    '회수곡선과 담보유형별 LGD, 경기침체 LGD, 하한이 문 자리, 관측중단의 영향을 '+
    '한 화면에서 본다. 회수곡선은 회수이력 원장 전량 집계다.'));
  if(!almHas(root,['crm_lgd_estimate']))return;
  const f=almF('crm_lgd_estimate'),i=frameIdx(f);
  const g=el('div','grid');
  f.rows.forEach(r=>{
    const c=el('div','card kpi');
    c.appendChild(el('div','lab',r[i.segment]+' 최종 적용 LGD'));
    c.appendChild(el('div','val '+(r[i.floor_binding]?'warn':''),
      pctv(r[i.final_applied],2)));
    c.appendChild(el('div','sub','장기 부도가중평균 '+
      pctv(r[i.longrun_default_weighted_lgd],2)+' · 경기침체 '+
      pctv(r[i.downturn_lgd],2)));
    c.appendChild(el('div','ln','관측중단 '+numOrDash(r[i.n_censored])+'건 · '+
      '종결 '+numOrDash(r[i.n_closed])+'건'));
    g.appendChild(c)});
  root.appendChild(g);

  const c1=cardOf('LGD 추정 (관측중단 처리 전후)',
    simpleTable(['세그먼트','할인율','할인율 근거','부도건수','종결','관측중단',
                 '중단 제외 LGD','중단 포함 LGD','차이','장기평균','경기침체',
                 '하한','하한 적용','MoC','최종'],
      f.rows.map(r=>[r[i.segment],pctv(r[i.discount_rate],2),
        r[i.discount_rate_status],r[i.n_defaults],r[i.n_closed],r[i.n_censored],
        pctv(r[i.lgd_excl_censored],2),pctv(r[i.lgd_incl_censored],2),
        numOrDash(r[i.censoring_impact],4),
        pctv(r[i.longrun_default_weighted_lgd],2),pctv(r[i.downturn_lgd],2),
        r[i.floor_value]==null?'(비어 있음)':pctv(r[i.floor_value],2),
        r[i.floor_binding]?'적용':'',numOrDash(r[i.moc_amount],4),
        pctv(r[i.final_applied],2)])));
  c1.appendChild(el('div','meta',
    '관측중단 처리방식은 원장 컬럼(censoring_treatment)이며 상태가 '+
    (f.rows[0][i.censoring_treatment_status]||'-')+'이다. 경기침체 정의는 '+
    (f.rows[0][i.downturn_definition]||'-')+'.'));
  c1.appendChild(srcMeta(f));
  root.appendChild(c1);

  const R=D.irb&&D.irb.recovery_curve;
  if(R&&R.length){
    const segs=[...new Set(R.map(x=>x.segment))];
    const bar=el('div','toolbar');
    const sel=almSelect(bar,'세그먼트',segs,segs[0]);
    const pane=el('div');
    function draw(){
      pane.innerHTML='';
      const sub=R.filter(x=>x.segment===sel.value)
        .sort((a,b)=>a.month-b.month);
      pane.appendChild(areaLine(
        sub.map(x=>+(x.cum_recovery_rate*100).toFixed(2)),
        {label:'누적 회수율 (%)'}));
      pane.appendChild(el('div','meta',
        '부도 후 경과월별 누적 회수율이다. 회수액에서 직·간접 비용을 뺀 '+
        '순회수를 부도시점 익스포저로 나눈 값이며, 관측 '+sub.length+
        '개월까지 있다.'));
    }
    sel.onchange=draw;draw();
    const c=cardOf('회수곡선',null);
    c.appendChild(bar);c.appendChild(pane);
    c.appendChild(el('div','meta','회수이력 원장 전량 '+
      D.irb.recovery_rows.toLocaleString()+'행 · 부도건 '+
      D.irb.recovery_defaults.toLocaleString()+'건 집계'));
    root.appendChild(c)}

  const obs=almF('crm_default_observation');
  if(obs){
    const oi=frameIdx(obs);
    const m=new Map();
    obs.rows.forEach(r=>{
      const k=r[oi.collateral_type]||'(무담보)';
      const cur=m.get(k)||{n:0,sum:0,est:0};
      cur.n+=1;cur.sum+=(r[oi.lgd_realized]||0);cur.est+=(r[oi.lgd_estimated]||0);
      m.set(k,cur)});
    const rows=[...m.entries()].sort((a,b)=>b[1].n-a[1].n)
      .map(([k,v])=>[k,v.n,pctv(v.est/v.n,2),pctv(v.sum/v.n,2),
        numOrDash(v.sum/v.n-v.est/v.n,4)]);
    root.appendChild(cardOf('담보유형별 실현 LGD 대 추정 LGD',
      simpleTable(['담보유형','부도건수','추정 평균','실현 평균','편의'],rows),
      '담보유형은 부도관측 원장 컬럼이다. 편의는 실현에서 추정을 뺀 값이며 '+
      '양수가 과소추정이다.'));
    const C=D.irb&&D.irb.censoring;
    if(C&&C.length){
      root.appendChild(cardOf('관측중단 현황',
        simpleTable(['세그먼트','관측상태','건수','부도시 익스포저'],
          C.map(x=>[x.segment,x.status,x.n,x.ead]),{numeric:true}),
        '워크아웃이 끝나지 않은 건을 제외하고 추정하면 회수가 긴 건이 빠져 '+
        'LGD 가 낮게 나온다. 위 추정표는 두 방식을 모두 싣는다.'))}
  }
  irbWaterfall(root,f,i,f.rows,'LGD',v=>pctv(v,3));
  irbFloorCard(root,'LGD');
  irbMocCard(root,'LGD');
  irbRunCard(root,'LGD');
  const dr=almF('crm_lgd_discount_rate');
  if(dr){const di=frameIdx(dr);
    root.appendChild(cardOf('회수 할인율',
      simpleTable(['세그먼트','회수범위','할인율','산정근거','무위험금리 출처',
                   '베타 출처','추정기간','입력출처','근거 판정'],
        dr.rows.map(r=>[r[di.segment],r[di.recovery_scope],
          pctv(r[di.discount_rate],2),r[di.basis],r[di.rf_source],
          r[di.beta_source],r[di.estimation_period],r[di.input_source],
          r[di.evidence_status]]))))}
}

function ccfEstimateScreen(root){
  reviewNotice(root,'CRE');
  root.appendChild(almSources(['crm_ccf_estimate','crm_ccf_backtest',
    'crm_facility_drawdown_history'].concat(IRB_COMMON),
    '상품유형별 CCF 실측과 적용값, 관측설계(코호트 대 고정시계), 분모 이상치 '+
    '처리 건수, 부도율과 EAD 의 상관에 따른 추가 보수화 여부를 본다.'));
  if(!almHas(root,['crm_ccf_estimate']))return;
  const f=almF('crm_ccf_estimate'),i=frameIdx(f);
  const EX=10;
  const c1=cardOf('CCF 추정',
    simpleTable(['세그먼트','CCF 유형','관측설계','산출기준','관측연수','한도수',
                 '유효','원시추정','경기침체','하한','하한 적용','MoC','최종',
                 '상관계수','추가 보수화'],
      f.rows.map(r=>[r[i.segment],r[i.ccf_type],r[i.observation_design],
        r[i.estimation_basis],numOrDash(r[i.observation_years],1),
        r[i.n_facilities],r[i.n_valid],pctv(r[i.raw_estimate],2),
        r[i.downturn_applied]?pctv(r[i.downturn_ccf],2):'미적용',
        r[i.floor_value]==null?'(비어 있음)':pctv(r[i.floor_value],2),
        r[i.floor_binding]?'적용':'',numOrDash(r[i.moc_amount],4),
        pctv(r[i.final_applied],2),numOrDash(r[i.pd_ead_correlation],3),
        r[i.extra_conservatism_required]?'필요':'불필요']),
      {numeric:false,rowClass:r=>r[14]==='필요'?'warn':null}));
  c1.appendChild(el('div','meta',
    '분모 0 건 '+f.rows.reduce((a,r)=>a+(r[i.n_zero_denominator]||0),0)+
    ' · 분모 음수 건 '+f.rows.reduce((a,r)=>a+(r[i.n_negative_denominator]||0),0)+
    ' · CCF 0 미만 '+f.rows.reduce((a,r)=>a+(r[i.n_ccf_below_zero]||0),0)+
    ' · CCF 1 초과 '+f.rows.reduce((a,r)=>a+(r[i.n_ccf_above_one]||0),0)+
    ' · 제외 익스포저 '+fmtMoney(f.rows.reduce((a,r)=>
      a+(r[i.excluded_exposure_amount]||0),0))));
  c1.appendChild(el('div','meta',
    '부도 후 추가인출 처리 '+(f.rows[0][i.post_default_drawdown_treatment]||'-')+
    ' · 자체추정 허용 '+(f.rows[0][i.self_estimation_allowed]?'예':'아니오')));
  c1.appendChild(srcMeta(f));
  root.appendChild(c1);
  const dsg=new Map();
  f.rows.forEach(r=>{const k=r[i.observation_design]||'-';
    dsg.set(k,(dsg.get(k)||0)+1)});
  root.appendChild(hbars([...dsg.entries()].map(([k,v])=>({label:k,value:v})),
    {title:'관측설계별 추정 건수',money:false,src:srcMeta(f)}));
  const b=almF('crm_ccf_backtest');
  if(b){
    const bi=frameIdx(b);
    root.appendChild(cardOf('CCF 유형·등급별 실측 대 적용',
      simpleTable(['CCF 유형','등급대','한도수','기준시 인출','기준시 미인출',
                   '부도시 인출','실측 CCF','적용 CCF','편의','판정'],
        b.rows.map(r=>[r[bi.ccf_type],r[bi.grade_band],r[bi.n_facilities],
          r[bi.drawn_at_ref],r[bi.undrawn_at_ref],r[bi.drawn_at_default],
          pctv(r[bi.ccf_realized_mean],2),pctv(r[bi.ccf_applied],2),
          numOrDash(r[bi.bias],4),
          judgeCell(r[bi.pass_flag],r[bi.judgment_status])]),
        {numeric:false,rowClass:r=>judgeTone(r[9])}),
      '판정 임계는 내부기준이며 원장 crm_backtest_criteria 에 있다. '+
      '임계가 비어 있으면 미판정으로 둔다.'));
    root.appendChild(hbars(b.rows.map(r=>({
      label:r[bi.ccf_type]+' · '+r[bi.grade_band],
      value:+((r[bi.ccf_realized_mean]||0)*100).toFixed(2),
      sub:'적용 '+pctv(r[bi.ccf_applied],1),
      tone:(r[bi.ccf_realized_mean]||0)>(r[bi.ccf_applied]||0)?'warn':undefined})),
      {title:'실측 CCF (%) · 적용값 대비',money:false,src:srcMeta(b)}))}
  irbWaterfall(root,f,i,f.rows,'CCF',v=>pctv(v,3));
  irbFloorCard(root,'CCF');
  irbMocCard(root,'CCF');
  irbRunCard(root,'CCF');
}

function defaultedLgdScreen(root){
  reviewNotice(root,'CRE');
  root.appendChild(almSources(['crm_defaulted_lgd','crm_default_observation',
    'crm_recovery_history'],
    '부도자산의 예상손실 최적추정치(ELBE)와 부도자산 LGD 다. 개별충당금과 '+
    '부분상각 합계와의 비교가 원장에 있고, 최적추정치가 더 작으면 정당화 '+
    '대상으로 표시된다.'));
  if(!almHas(root,['crm_defaulted_lgd']))return;
  const f=almF('crm_defaulted_lgd'),i=frameIdx(f);
  const g=el('div','grid');
  f.rows.forEach(r=>{
    const c=el('div','card kpi');
    c.appendChild(el('div','lab',r[i.segment]+' ELBE'));
    c.appendChild(el('div','val '+(r[i.justification_required]?'bad':''),
      pctv(r[i.elbe],2)));
    c.appendChild(el('div','sub','부도자산 LGD '+pctv(r[i.lgd_in_default],2)+
      ' · 예상외손실 가산 '+numOrDash(r[i.unexpected_loss_addon],4)));
    c.appendChild(el('div','ln','미종결 부도 '+numOrDash(r[i.n_defaulted_open])+'건'));
    g.appendChild(c)});
  root.appendChild(g);
  const J=6;
  const c1=cardOf('ELBE 와 개별충당금 + 부분상각 비교',
    simpleTable(['세그먼트','ELBE 금액','개별충당금','부분상각','합계','차액',
                 '정당화 필요','증빙','산출방법','상태'],
      f.rows.map(r=>[r[i.segment],r[i.elbe_amount],r[i.specific_provision],
        r[i.partial_writeoff],
        (r[i.specific_provision]||0)+(r[i.partial_writeoff]||0),
        r[i.shortfall],r[i.justification_required]?'필요':'불필요',
        r[i.justification_ref]||'(없음)',r[i.elbe_method],r[i.status]]),
      {numeric:false,rowClass:r=>r[J]==='필요'?'bad':null}));
  c1.appendChild(el('div','meta',
    '최적추정치가 개별충당금과 부분상각 합계보다 작으면 그 정당성을 '+
    '입증해야 한다 ([별표3] 185.바).'));
  c1.appendChild(srcMeta(f));
  root.appendChild(c1);
  const obs=almF('crm_default_observation');
  if(obs){
    const oi=frameIdx(obs);
    /* 이 화면은 경과월 분포와 산출방법만 싣는다. 곡선 자체는 곡선 원장
       (crm_beel_curve)이 만들고 BEEL·PLGD 화면이 그린다. 두 화면이 같은
       곡선을 각자 그리면 두 벌이 된다. */
    const open=obs.rows.filter(r=>r[oi.workout_complete]===false);
    const m=new Map();
    open.forEach(r=>{const k=r[oi.months_since_default];
      m.set(k,(m.get(k)||0)+1)});
    const pts=[...m.entries()].sort((a,b)=>a[0]-b[0]);
    if(pts.length){
      const c=cardOf('미종결 부도의 경과월 분포',
        bars(pts.map(([k,v])=>({label:k+'개월',value:v})),
          {fmt:v=>fmtNum(v)}),
        '미종결 부도관측 '+open.length+'건의 부도 후 경과월 분포다.');
      /* 산출방법은 원장 값이다. 화면이 지은 문장만 옮기고 원장 값은 원문
         그대로 잇는다. */
      c.appendChild(rawEl('div','meta',
        T('산출방법')+': '+
        (f.rows.length?f.rows[0][i.elbe_method]:T('(원장 없음)'))));
      c.appendChild(el('div','note',
        '경과월별 BEEL 곡선과 분모 두 방식 대비는 BEEL·PLGD 화면에 있다.'));
      root.appendChild(c)}
    const cure=obs.rows.filter(r=>String(r[oi.censoring_status]).indexOf('정상화')>=0);
    root.appendChild(cardOf('정상화(cure) 인식',
      simpleTable(['관측상태','건수','평균 실현 LGD'],
        [...new Set(obs.rows.map(r=>r[oi.censoring_status]))].map(st=>{
          const sub=obs.rows.filter(r=>r[oi.censoring_status]===st);
          return [st,sub.length,pctv(sub.reduce((a,r)=>
            a+(r[oi.lgd_realized]||0),0)/sub.length,2)]})),
      cure.length?('정상화 '+cure.length+'건이 실현 LGD 평균을 끌어내린다.')
        :'정상화로 분류된 관측이 원장에 없다.'));
  }
  root.appendChild(cardOf('PLGD 는 어디에 있나',null,
    'PLGD(Potential LGD)는 BEEL 분포의 일정 신뢰수준 극단값이다. 곡선·분모 '+
    '판정·신뢰수준 민감도는 BEEL·PLGD 화면이 낸다. 신뢰수준 q 는 1차자료에 '+
    '없는 내부기준이라 승인 전에는 PLGD 값이 비어 있고, 그 상태도 그 화면이 '+
    '표시한다.'));
}

/* ---- 회수 할인율 (CAPM) ------------------------------------------------ */

/* 할인율 한 칸이 비면 LGD·BEEL 곡선·PLGD가 통째로 산출불가로 멈춘다. 그래서
   관측·추정·승인·적용을 한 화면에 두고 값이 어느 단계에서 왔는지 화면에서
   바로 읽히게 한다. 회귀선은 추정 원장의 절편·기울기를 그대로 긋는다. 화면이
   점에서 다시 회귀하면 원장의 베타와 화면의 선이 갈라져도 드러나지 않는다. */

const CAPM_TABLES=['crm_capm_observation','crm_capm_estimate',
  'crm_lgd_discount_rate','crm_lgd_estimate'];

function capmDiscountScreen(root){
  reviewNotice(root,'CRE');
  root.appendChild(almSources(CAPM_TABLES,
    '회수 할인율의 관측·추정·승인·적용이다. [별표 3] 184.(1)은 회수기간에 '+
    '따른 할인효과를 고려하라고만 정하고 할인율의 수준·산식·세그먼트 구분을 '+
    '주지 않으므로, 값과 승인 기록이 원장에 함께 있어야 한다.'));
  if(!almHas(root,['crm_capm_estimate','crm_capm_observation',
                   'crm_lgd_discount_rate']))return;
  const e=almF('crm_capm_estimate'),ei=frameIdx(e);
  if(!e.rows.length){
    root.appendChild(el('div','note bad','추정 원장에 행이 없다.'));return}
  const r=e.rows[0];
  const prem=r[ei.market_premium];
  const g=el('div','grid');
  /* 'lab'·'sub' 는 el() 이 옮기는 클래스가 아니므로 T() 를 직접 부른다.
     원장 값(추정 상태·출처)은 옮기지 않고 원문 그대로 붙인다. */
  [['무위험이자율 R_f',pctv(r[ei.riskfree_annual],4),
    T('관측 만기수익률 평균'),''],
   ['시장수익률 R_M',pctv(r[ei.market_return_applied],4),
    TP('출처',String(r[ei.market_return_source]||'-')),''],
   ['위험프리미엄',pctv(prem,4),T('시장수익률에서 무위험이자율을 뺀 값'),
    (prem!=null&&prem<=0)?'bad':''],
   ['베타',numOrDash(r[ei.beta],4),
    TP('표준오차',numOrDash(r[ei.beta_stderr],4)),''],
   ['자기자본비용 k_e',pctv(r[ei.cost_of_equity],4),
    String(r[ei.ke_status]||''),r[ei.cost_of_equity]==null?'bad':'']]
  .forEach(([k,v,s,t])=>{
    const c=el('div','card kpi');
    c.appendChild(rawEl('div','lab',T(k)));
    c.appendChild(el('div','val '+t,v));
    c.appendChild(rawEl('div','sub',s));
    g.appendChild(c)});
  root.appendChild(g);

  /* 산점은 백분율 축으로 그린다. 초과수익률은 소수점 두세 자리라 비율 그대로
     그리면 눈금 라벨이 전부 같은 값으로 찍힌다. 기울기는 축을 같은 배수로
     늘려도 그대로이고 절편만 같은 배수를 곱한다. */
  const o=almF('crm_capm_observation'),oi=frameIdx(o);
  const pts=o.rows.filter(x=>x[oi.excess_market_return]!=null
                          &&x[oi.excess_bank_return]!=null)
    .map(x=>({x:x[oi.excess_market_return]*100,
              y:x[oi.excess_bank_return]*100,
              label:String(x[oi.period])}));
  if(pts.length){
    const c2=cardOf('베타 회귀 (초과수익률 산점과 적합선)',
      scatterXY(pts,{xlabel:T('시장 초과수익률 (백분율)'),
        ylabel:T('은행주 초과수익률 (백분율)'),
        fit:{slope:r[ei.beta],intercept:(r[ei.alpha]||0)*100},
        tick:v=>v.toFixed(1)}));
    c2.appendChild(simpleTable(
      ['관측수','산출대상기간','기울기 (베타)','표준오차','t 값','결정계수',
       '절편 (월)'],
      [[r[ei.n_observations],r[ei.estimation_period],numOrDash(r[ei.beta],4),
        numOrDash(r[ei.beta_stderr],4),numOrDash(r[ei.beta_tstat],2),
        numOrDash(r[ei.beta_r2],4),numOrDash(r[ei.alpha],6)]]));
    c2.appendChild(el('div','meta',
      '점 하나가 관측 한 달이다. 가로는 시장 초과수익률, 세로는 은행주 '+
      '초과수익률이며, 파선은 추정 원장의 절편과 기울기로 그은 적합선이다.'));
    c2.appendChild(srcMeta(o));
    root.appendChild(c2)}

  /* 근거 고지. 관측 계열 자체가 합성이라 여기서 나온 베타는 실측 베타와 같은
     칸에 둘 수 없다. 원장의 출처 문구를 그대로 싣는다. */
  const c3=el('div','card');
  c3.appendChild(el('h3',null,'근거와 산출 상태'));
  c3.appendChild(simpleTable(['항목','원장 값'],
    [['무위험이자율 출처',String(r[ei.rf_source]||'-')],
     ['베타 출처',String(r[ei.beta_source]||'-')],
     ['시장수익률 출처',String(r[ei.market_return_source]||'-')],
     ['자기자본비용 상태',String(r[ei.ke_status]||'-')],
     ['근거 판정',String(r[ei.evidence_status]||'-')],
     ['규정 근거',String(r[ei.citation]||'-')],
     ['타행 참고',String(r[ei.reference_note]||'-')]]));
  c3.appendChild(el('div','note warn',
    '이 화면의 베타는 합성 관측으로 낸 추정치다. 관측 가능한 은행 주가 계열이 '+
    '원장에 없어 결정론 합성 표본으로 회귀했고, 근거 판정이 그 사실을 든다. '+
    '실측 베타로 읽지 않는다.'));
  root.appendChild(c3);

  /* 회수유형별 할인율. 값이 원장에 들어가는 경로는 승인 함수 하나뿐이므로
     값·승인자·승인일이 같은 행에 있다. 승인자 칸이 비면 값도 없어야 한다. */
  const d=almF('crm_lgd_discount_rate'),di=frameIdx(d);
  const AP=6;
  const c4=cardOf('회수유형별 할인율 (승인 기록 포함)',
    simpleTable(['세그먼트','회수유형','할인율','산출근거','근거 판정','값의 근거',
                 '승인자','승인일'],
      d.rows.map(x=>[x[di.segment],x[di.recovery_scope],
        pctv(x[di.discount_rate],4),x[di.basis],x[di.evidence_status],
        x[di.input_source],x[di.approved_by]||'(미승인)',
        x[di.approval_date]||'-']),
      {numeric:false,rowClass:x=>String(x[AP]).indexOf('미승인')>=0?'warn':null}));
  c4.appendChild(el('div','meta',
    '예적금 상계처럼 회수 불확실성이 없는 회수를 무위험회수로 나눠 둔다. '+
    '하나의 할인율로 묶으면 회수 타이밍이 다른 세그먼트 사이의 LGD 서열이 '+
    '왜곡된다.'));
  c4.appendChild(srcMeta(d));
  root.appendChild(c4);

  /* 타행 실측 대비. 참고치는 승인 판단의 자료이고 엔진이 읽는 값이 아니다. */
  const c5=cardOf('타행 참고치와의 대비',
    simpleTable(['세그먼트','회수유형','적용 할인율','참고치','차이'],
      d.rows.map(x=>[x[di.segment],x[di.recovery_scope],
        pctv(x[di.discount_rate],4),pctv(x[di.reference_value],4),
        (x[di.discount_rate]==null||x[di.reference_value]==null)?'-'
          :numOrDash((x[di.discount_rate]-x[di.reference_value])*100,4)])),
    '차이는 적용 할인율에서 참고치를 뺀 값이며 단위는 백분율 포인트다.');
  c5.appendChild(rawEl('div','meta',
    T('참고치 근거')+': '+
    String((d.rows.length?d.rows[0][di.reference_citation]:null)||'-')));
  root.appendChild(c5);

  /* 할인율이 실제로 LGD를 열었는지. 승인 상태만 보이고 산출 결과가 안 보이면
     화면이 통제 상태만 말하고 산출물은 말하지 않는 것이 된다. */
  const L=almF('crm_lgd_estimate');
  if(L){const li=frameIdx(L),ST=4;
    root.appendChild(cardOf('할인율 적용 결과 (LGD 산출 상태)',
      simpleTable(['세그먼트','적용 할인율','할인율 상태','원시 추정','산출 상태'],
        L.rows.map(x=>[x[li.segment],pctv(x[li.discount_rate],4),
          x[li.discount_rate_status],pctv(x[li.raw_estimate],2),x[li.status]]),
        {numeric:false,rowClass:x=>x[ST]==='산출불가'?'bad':null}),
      '할인율이 비어 있으면 그 세그먼트 LGD 산출을 건너뛰고 산출불가로 남긴다. '+
      '엔진이 조용히 기본값을 쓰지 않는다.'))}

  root.appendChild(almEvidence(['crm_capm_observation','crm_capm_estimate',
    'crm_lgd_discount_rate']));
}

/* ---- 부도자산 LGD (BEEL 곡선·PLGD) ------------------------------------- */

/* 경과월별 BEEL 곡선, 분모 두 방식 대비, 신뢰수준 민감도, PLGD 대 ELBE,
   185.바의 개별충당금+부분상각 비교를 한 화면에 둔다. 신뢰수준 q 는 1차자료에
   없는 내부기준이라 승인 전에는 PLGD 값이 비고, 그 상태를 화면이 적는다. */

const BEEL_TABLES=['crm_beel_curve','crm_plgd','crm_plgd_sensitivity',
  'crm_defaulted_lgd','crm_lgd_discount_rate'];

function beelPlgdScreen(root){
  reviewNotice(root,'CRE');
  root.appendChild(almSources(BEEL_TABLES,
    '부도 후 경과월별 예상손실 최적추정치(BEEL) 곡선과 그 곡선의 극단값인 '+
    'PLGD 다. [별표 3] 185.바가 부도자산 예상손실에 예상외 손실 가능성을 추가 '+
    '반영하라고 정하고, 120.가(2) 주4)가 부도자산 예상손실을 그 최적추정치로 '+
    '정한다.'));
  if(!almHas(root,['crm_beel_curve','crm_plgd']))return;
  const c=almF('crm_beel_curve'),ci=frameIdx(c);
  const p=almF('crm_plgd'),pi=frameIdx(p);
  if(!c.rows.length){
    root.appendChild(el('div','note bad','곡선 원장에 행이 없다.'));return}

  /* 판정 카드. 세 판정 모두 원장 컬럼이며 화면이 다시 정하지 않는다. */
  const p0=p.rows.length?p.rows[0]:null;
  const applied=c.rows.filter(x=>x[ci.is_applied_denominator]);
  const g=el('div','grid');
  [['적용 분모',String(applied.length?applied[0][ci.beel_denominator]:'-'),
    T('경과월과 곡선의 순위상관 부호로 판정'),''],
   ['DSF 반영형태',String((p0&&p0[pi.dsf_form])||'미정'),
    T('분포 분위수 대 평균의 변동계수 비교'),''],
   ['신뢰수준 q',(p0?numOrDash(p0[pi.confidence_q],2):'-'),
    String((p0&&p0[pi.confidence_q_status])||'-'),
    (p0&&p0[pi.confidence_q]==null)?'warn':''],
   ['PLGD 산출 상태',String((p0&&p0[pi.status])||'-'),
    T('값이 비면 신뢰수준이 승인되지 않은 것'),
    (p0&&p0[pi.plgd]==null)?'bad':'']]
  .forEach(([k,v,s,t])=>{
    const x=el('div','card kpi');
    x.appendChild(rawEl('div','lab',T(k)));
    x.appendChild(el('div','val '+t,v));
    x.appendChild(rawEl('div','sub',s));
    g.appendChild(x)});
  root.appendChild(g);

  /* 곡선. 적용 분모 쪽만 그린다. 두 분모를 한 그림에 겹치면 어느 쪽이 원장의
     적용값인지 화면에서 사라진다. 대비는 아래 표가 맡는다. */
  const segs=[...new Set(c.rows.map(x=>x[ci.segment]))].sort();
  const bar=el('div','toolbar');
  const sel=almSelect(bar,'세그먼트',segs,segs[0]);
  const pane=el('div');
  function draw(){
    pane.innerHTML='';
    const sub=c.rows.filter(x=>x[ci.segment]===sel.value
                             &&x[ci.is_applied_denominator]
                             &&x[ci.beel_mean]!=null)
      .sort((a,b)=>a[ci.months_since_default]-b[ci.months_since_default]);
    if(!sub.length){
      pane.appendChild(el('div','note bad',
        '이 세그먼트의 적용 분모 곡선이 산출되지 않았다.'));return}
    pane.appendChild(areaLine(
      sub.map(x=>+(x[ci.beel_mean]*100).toFixed(2)),
      {label:T('BEEL 평균 (백분율)')}));
    const first=sub[0],last=sub[sub.length-1];
    pane.appendChild(simpleTable(
      ['경과월','부도건수','BEEL 평균','관측중단 제외 영향','단조성 판정',
       '순위상관'],
      [[first[ci.months_since_default],first[ci.n_defaults],
        pctv(first[ci.beel_mean],2),numOrDash(first[ci.censoring_impact],4),
        first[ci.monotonicity_verdict],
        numOrDash(first[ci.monotonicity_rho],4)],
       [last[ci.months_since_default],last[ci.n_defaults],
        pctv(last[ci.beel_mean],2),numOrDash(last[ci.censoring_impact],4),
        last[ci.monotonicity_verdict],
        numOrDash(last[ci.monotonicity_rho],4)]]));
    pane.appendChild(el('div','meta',
      '곡선 평균은 회수가 끝난 건만 쓴다. 관측중단 제외 영향은 미종결 건을 '+
      '관측분만으로 포함했을 때와의 차이이며, 양수면 제외 처리가 낙관적이라는 '+
      '뜻이다.'))}
  sel.onchange=draw;draw();
  const c1=cardOf('경과월별 BEEL 곡선 (적용 분모)',null);
  c1.appendChild(bar);c1.appendChild(pane);c1.appendChild(srcMeta(c));
  root.appendChild(c1);

  /* 분모 두 방식 대비. 원장이 두 분모를 모두 산출하고 적용 표시만 다르다. */
  const key=new Map();
  c.rows.forEach(x=>{
    const k=x[ci.segment]+'||'+x[ci.beel_denominator];
    const cur=key.get(k);
    if(!cur||x[ci.months_since_default]>cur[ci.months_since_default])
      key.set(k,x)});
  const AP=2,VD=3;
  const c2=cardOf('분모 두 방식 대비',
    simpleTable(['세그먼트','분모구분','적용','단조성 판정','순위상관',
                 '유의확률','마지막 경과월 BEEL'],
      [...key.entries()].sort().map(([k,x])=>[
        x[ci.segment],x[ci.beel_denominator],
        x[ci.is_applied_denominator]?'적용':'',
        x[ci.monotonicity_verdict],numOrDash(x[ci.monotonicity_rho],4),
        numOrDash(x[ci.monotonicity_pvalue],4),pctv(x[ci.beel_mean],2)]),
      {numeric:false,
       rowClass:x=>x[VD]==='단조증가아님'?'warn':(x[AP]==='적용'?'good':null)}),
    '분모를 부도시 익스포저로 두면 할인 되감기 항이 사라져 곡선이 경과월에 '+
    '따라 올라간다. 잔여익스포저로 두면 분모도 함께 줄어 곡선이 무너지는 '+
    '세그먼트가 생긴다. 판정은 순위상관 부호이며 원장 컬럼이다.');
  root.appendChild(c2);

  /* 신뢰수준 민감도. q 는 승인 대상이므로 화면이 고르지 않는다. */
  const S=almF('crm_plgd_sensitivity');
  if(S&&S.rows.length){
    const si=frameIdx(S);
    const c3=cardOf('신뢰수준 q 민감도',
      simpleTable(['세그먼트','신뢰수준 q','PLGD','소요자기자본 K',
                   '위험가중자산','최저 q 대비 증가','충당금 소요',
                   '꼬리 관측 최소'],
        S.rows.map(x=>[x[si.segment],numOrDash(x[si.confidence_q],2),
          pctv(x[si.plgd],2),numOrDash(x[si.capital_requirement_k],4),
          moneyOrDash(x[si.rwa]),moneyOrDash(x[si.rwa_delta_vs_lowest_q]),
          moneyOrDash(x[si.provision_requirement]),
          numOrDash(x[si.min_tail_observations])]),
        {numeric:false}));
    c3.appendChild(rawEl('div','meta',
      T('충당금 산출 근거')+': '+String(S.rows[0][si.provision_basis]||'-')));
    c3.appendChild(el('div','note warn',
      '표의 어느 줄도 승인된 값이 아니다. q 는 시뮬레이션이 정해 주는 값이 '+
      '아니고 승인기구 의결이 효력 요건이라, 원장의 신뢰수준 칸은 비어 있다. '+
      '꼬리 관측이 적은 줄은 분위수가 표본 밖 순서통계량에 기댄다.'));
    c3.appendChild(srcMeta(S));
    root.appendChild(c3)}

  /* PLGD 대 ELBE. 예상외 손실 가산은 둘의 차이이며 음수가 될 수 없다. */
  const SS=10;
  const c4=cardOf('PLGD 대 ELBE',
    simpleTable(['세그먼트','미종결 부도','부도상태 익스포저','ELBE','PLGD',
                 '예상외손실 가산','부도자산 LGD','침체가산 배수','반영형태',
                 '소요자기자본 K','산출 상태'],
      p.rows.map(x=>[x[pi.segment],numOrDash(x[pi.n_defaulted_open]),
        moneyOrDash(x[pi.ead_at_default_open]),pctv(x[pi.elbe],2),
        pctv(x[pi.plgd],2),numOrDash(x[pi.unexpected_loss_addon],4),
        pctv(x[pi.lgd_in_default],2),numOrDash(x[pi.dsf],4),
        x[pi.dsf_form]||'-',numOrDash(x[pi.capital_requirement_k],4),
        x[pi.status]]),
      {numeric:false,
       rowClass:x=>String(x[SS]).indexOf('산출불가')>=0?'warn':null}));
  c4.appendChild(rawEl('div','meta',
    T('부도자산 LGD 의 근거')+': '+
    String((p0&&p0[pi.lgd_in_default_basis])||'-')));
  const few=p.rows.filter(x=>x[pi.insufficient_sample]);
  if(few.length)c4.appendChild(el('div','note warn',
    '꼬리 표본이 모자란 세그먼트가 있다. 표본이 모자란 분위수는 순서통계량이 '+
    '표본 밖으로 나가 값이 관측에 기대지 않는다.'));
  c4.appendChild(srcMeta(p));
  root.appendChild(c4);

  /* 185.바 후단. 비대칭이므로 반대 방향은 입증 대상이 아니다. */
  const JR=6;
  const c5=cardOf('개별충당금 + 부분상각 비교',
    simpleTable(['세그먼트','ELBE 금액','다른 분모 기준 금액','개별충당금',
                 '부분상각','차액','입증 필요','증빙'],
      p.rows.map(x=>[x[pi.segment],moneyOrDash(x[pi.elbe_amount]),
        moneyOrDash(x[pi.elbe_amount_alt_denominator]),
        moneyOrDash(x[pi.specific_provision]),
        moneyOrDash(x[pi.partial_writeoff]),moneyOrDash(x[pi.shortfall]),
        x[pi.justification_required]==null?'미판정'
          :(x[pi.justification_required]?'필요':'불필요'),
        x[pi.justification_ref]||'(없음)']),
      {numeric:false,rowClass:x=>x[JR]==='필요'?'bad':
        (x[JR]==='미판정'?'warn':null)}),
    '최적추정치가 개별충당금과 부분상각 합계보다 작으면 그 정당성을 입증해야 '+
    '한다 ([별표 3] 185.바). 반대 방향은 입증 대상이 아니다. 충당금 자료가 '+
    '원장에 없으면 판정하지 않고 미판정으로 둔다.');
  c5.appendChild(el('div','meta',
    '다른 분모 기준 금액은 적용하지 않은 분모로 같은 계산을 한 결과다. 분모 '+
    '판정이 바뀌면 이 비교의 방향이 뒤집힐 수 있어 함께 싣는다.'));
  root.appendChild(c5);

  root.appendChild(almEvidence(['crm_beel_curve','crm_plgd']));
}

function irbGovernanceScreen(root){
  reviewNotice(root,'CRE');
  root.appendChild(almSources(['crm_model_governance','crm_backtest_result',
    'crm_backtest_criteria','crm_representativeness','crm_lgd_backtest',
    'crm_ccf_backtest','crm_sample_representativeness'],
    '등급별 실적 부도율과 추정 PD 의 대조, LGD·CCF 실적 대비, 대표성 지표, '+
    '연 1회 점검 이행 이력과 승인 기록이다.'));
  const cr=almF('crm_backtest_criteria');
  if(cr){
    const ci=frameIdx(cr);
    const c=cardOf('합격 임계 (내부기준)',
      simpleTable(['기준셋','모수','대상','값','단위','비교','산식','근거',
                   '승인기구','승인자','승인일','근거 판정'],
        cr.rows.map(r=>[r[ci.criteria_set_id],r[ci.param],r[ci.target],
          numOrDash(r[ci.param_value],4),r[ci.param_unit],r[ci.comparator],
          r[ci.threshold_formula],r[ci.basis],r[ci.approval_body]||'-',
          r[ci.approved_by]||'-',r[ci.approved_on]||'-',r[ci.evidence_status]])));
    c.appendChild(el('div','note warn',
      '이 임계는 규정이 정한 값이 아니라 내부기준이다. 승인기구 의결이 효력 '+
      '요건이며, 임계가 비어 있는 항목은 판정하지 않고 미판정으로 둔다.'));
    c.appendChild(srcMeta(cr));
    root.appendChild(c)}
  const b=almF('crm_backtest_result');
  if(b){
    const i=frameIdx(b);
    const IN=9;
    const c=cardOf('사후검증 (적용값 · 실측값 · 허용범위)',
      simpleTable(['모수','세그먼트','등급','연도','표본외','관측수','부도수',
                   '적용 추정값','실측값','범위 안','허용 하한','허용 상한',
                   '검정','유의수준','판정'],
        b.rows.map(r=>[r[i.parameter],r[i.segment],r[i.grade]||'-',
          String(r[i.backtest_year]),r[i.out_of_sample]?'예':'아니오',
          r[i.n_observations],r[i.n_defaults],
          numOrDash(r[i.estimated_value],5),numOrDash(r[i.realised_value],5),
          r[i.inside_range]==null?(r[i.judgment_status]||'미판정'):
            (r[i.inside_range]?'안':'밖'),
          numOrDash(r[i.range_lower],5),numOrDash(r[i.range_upper],5),
          r[i.test_method],numOrDash(r[i.significance_level],3),
          judgeCell(r[i.test_pass],r[i.judgment_status])]),
        {numeric:false,rowClass:r=>r[IN]==='밖'?'bad':(r[IN]==='안'?null:'warn')}));
    c.appendChild(el('div','meta',
      '적용 추정값은 추정 원장의 최종 적용값이고, 허용범위는 검정과 신뢰수준이 '+
      '정한 구간이다. 세 값을 한 행에서 본다.'));
    c.appendChild(srcMeta(b));
    root.appendChild(c);
    const pd=b.rows.filter(r=>r[i.parameter]==='PD'&&r[i.grade]);
    if(pd.length)root.appendChild(hbars(pd.map(r=>({
      label:r[i.grade]+' · '+r[i.backtest_year],
      value:+((r[i.realised_value]||0)*100).toFixed(3),
      sub:'추정 '+pctv(r[i.estimated_value],3)+' · 상한 '+
        pctv(r[i.range_upper],3),
      tone:r[i.inside_range]===false?'bad':undefined})),
      {title:'등급별 실측 부도율 (%) · 추정과 허용 상한 대비',money:false,
       src:srcMeta(b)}))}
  const lb=almF('crm_lgd_backtest');
  if(lb){
    const i=frameIdx(lb);
    root.appendChild(cardOf('LGD 사후검증',
      simpleTable(['축','구간','부도수','관측중단','추정 평균','실현 평균',
                   '편의','MAE','RMSE','신뢰구간','판정'],
        lb.rows.map(r=>[r[i.segment_axis],r[i.segment_value],r[i.n_defaults],
          r[i.n_censored],pctv(r[i.lgd_estimated_mean],2),
          pctv(r[i.lgd_realized_mean],2),numOrDash(r[i.bias],4),
          numOrDash(r[i.mae],4),numOrDash(r[i.rmse],4),
          numOrDash(r[i.ci_low],4)+' ~ '+numOrDash(r[i.ci_high],4),
          judgeCell(r[i.pass_flag],r[i.judgment_status])]),
        {numeric:false,rowClass:r=>judgeTone(r[10])}),
      '관측중단 처리규칙은 원장 컬럼(censoring_rule)이다.'))}
  const rep=almF('crm_representativeness');
  if(rep){
    const i=frameIdx(rep);
    root.appendChild(cardOf('대표성 지표 (PSI)',
      simpleTable(['모수','세그먼트','축','PSI','추정표본 수','현재 수',
                   '경고 임계','불합격 임계','판정','증빙'],
        rep.rows.map(r=>[r[i.parameter],r[i.segment],r[i.axis],
          numOrDash(r[i.psi],4),r[i.n_estimation],r[i.n_current],
          numOrDash(r[i.warn_threshold],3),numOrDash(r[i.fail_threshold],3),
          r[i.psi]==null?(r[i.judgment_status]||'미판정'):r[i.judgment],
          r[i.evidence]||'-']),
        {numeric:false,
         rowClass:r=>r[8]==='미판정'||r[8]==='기준미승인'?'warn':null})))}
  const gv=almF('crm_model_governance');
  if(gv){
    const i=frameIdx(gv);
    const OV=8;
    root.appendChild(cardOf('연 1회 점검 이행과 승인',
      simpleTable(['모수','세그먼트','모형','승인일','승인자','승인기구',
                   '최근 검토','기한 초과','차기 기한','검토주기(월)',
                   '최근 사후검증','검토 횟수','상태'],
        gv.rows.map(r=>[r[i.parameter],r[i.segment],r[i.model_id],
          r[i.approval_date]||'-',r[i.approved_by]||'-',r[i.approval_body]||'-',
          r[i.last_review_date]||'-',r[i.review_overdue]?'초과':'',
          r[i.next_review_due]||'-',numOrDash(r[i.review_interval_months]),
          r[i.last_backtest_date]||'-',numOrDash(r[i.n_reviews]),r[i.status]]),
        {numeric:false,rowClass:r=>r[7]==='초과'?'bad':null}),
      gv.rows[0][i.citation]||''))}
}

/* ══════════════ LGD·EAD 실측 검증 ═════════════════════════════════════ */

function lgdEadBacktestScreen(root){
  reviewNotice(root,'CRE');
  root.appendChild(almSources(['crm_lgd_backtest','crm_ccf_backtest',
    'crm_default_observation','crm_backtest_criteria'],
    '추정 LGD·CCF 와 실현값의 대조다. 등급·담보별 산점과 편의·MAE, 관측중단 '+
    '건수, CCF 유형별 실측 대 적용을 한 화면에서 본다.'));
  if(!almHas(root,['crm_lgd_backtest','crm_ccf_backtest']))return;
  const lb=almF('crm_lgd_backtest'),i=frameIdx(lb);
  const g=el('div','grid');
  const nfail=lb.rows.filter(r=>r[i.pass_flag]===false).length;
  const nund=lb.rows.filter(r=>r[i.pass_flag]==null).length;
  const cens=lb.rows.reduce((a,r)=>a+(r[i.n_censored]||0),0);
  [['LGD 검증 구간',String(lb.rows.length),''],
   ['미통과',String(nfail),nfail?'bad':'good'],
   ['미판정',String(nund),nund?'warn':'good'],
   ['관측중단 건수',cens.toLocaleString(),cens?'warn':'']]
  .forEach(([k,v,t])=>{const c=el('div','card kpi');
    c.appendChild(el('div','lab',k));c.appendChild(el('div','val '+t,v));
    g.appendChild(c)});
  root.appendChild(g);

  /* 추정 대 실현 산점. 45도선 위쪽이 과소추정이다. */
  const obs=almF('crm_default_observation');
  if(obs){
    const oi=frameIdx(obs);
    const pts=obs.rows.filter(r=>r[oi.lgd_realized]!=null&&r[oi.lgd_estimated]!=null);
    root.appendChild(cardOf('추정 LGD 대 실현 LGD (부도건별)',
      scatter45(pts.map(r=>({x:r[oi.lgd_estimated],y:r[oi.lgd_realized],
        label:r[oi.exposure_id]+' · '+(r[oi.collateral_type]||'무담보'),
        tone:r[oi.censoring_status]&&r[oi.censoring_status]!=='종결'
          ?'warn':undefined}))),
      '가로가 추정, 세로가 실현이다. 대각선 위쪽 점이 과소추정 건이고, '+
      '주황 점은 워크아웃이 끝나지 않은 관측이다. 관측 '+pts.length+'건.'))}

  root.appendChild(hbars(lb.rows.map(r=>({
    label:r[i.segment_axis]+' · '+r[i.segment_value],
    value:+((r[i.bias]||0)*100).toFixed(2),
    sub:'MAE '+numOrDash(r[i.mae],4)+' · 부도 '+r[i.n_defaults]+'건',
    tone:r[i.pass_flag]==null?'warn':(r[i.pass_flag]?undefined:'bad')})),
    {title:'구간별 편의 (%p, 실현 − 추정)',money:false,src:srcMeta(lb)}));

  root.appendChild(cardOf('LGD 실측 검증',
    simpleTable(['축','구간','부도수','관측중단','추정 평균','실현 평균','편의',
                 'MAE','RMSE','t','p','판정','방법'],
      lb.rows.map(r=>[r[i.segment_axis],r[i.segment_value],r[i.n_defaults],
        r[i.n_censored],pctv(r[i.lgd_estimated_mean],2),
        pctv(r[i.lgd_realized_mean],2),numOrDash(r[i.bias],4),
        numOrDash(r[i.mae],4),numOrDash(r[i.rmse],4),
        numOrDash(r[i.t_stat],3),numOrDash(r[i.p_value],4),
        judgeCell(r[i.pass_flag],r[i.judgment_status]),
        r[i.method]]),
      {numeric:false,rowClass:r=>judgeTone(r[11])}),
    '판정 임계는 내부기준(crm_backtest_criteria)이며 규정값이 아니다.'));

  const cb=almF('crm_ccf_backtest');
  if(cb){
    const ci=frameIdx(cb);
    root.appendChild(hbars(cb.rows.map(r=>({
      label:r[ci.ccf_type]+' · '+r[ci.grade_band],
      value:+((r[ci.ccf_realized_mean]||0)*100).toFixed(2),
      sub:'적용 '+pctv(r[ci.ccf_applied],1)+' · 편의 '+numOrDash(r[ci.bias],4),
      tone:r[ci.pass_flag]===false?'bad':undefined})),
      {title:'CCF 유형·등급별 실측 (%)',money:false,src:srcMeta(cb)}));
    root.appendChild(cardOf('CCF 실측 검증',
      simpleTable(['CCF 유형','등급대','한도수','기준시 인출','기준시 미인출',
                   '부도시 인출','실측 CCF','적용 CCF','편의','신뢰구간','판정'],
        cb.rows.map(r=>[r[ci.ccf_type],r[ci.grade_band],r[ci.n_facilities],
          r[ci.drawn_at_ref],r[ci.undrawn_at_ref],r[ci.drawn_at_default],
          pctv(r[ci.ccf_realized_mean],2),pctv(r[ci.ccf_applied],2),
          numOrDash(r[ci.bias],4),
          numOrDash(r[ci.ci_low],3)+' ~ '+numOrDash(r[ci.ci_high],3),
          judgeCell(r[ci.pass_flag],r[ci.judgment_status])]),
        {numeric:false,rowClass:r=>judgeTone(r[10])})))}
}

/* 45도선 산점. 축은 0~1 비율이며 값은 원장 그대로다. */
function scatter45(points){
  /* 위쪽 28px 은 y축 이름 자리다. 눈금 칸에 겹쳐 그리지 않는다. */
  const W=520,H=380,pad=44,padT=28;
  const s=svgEl(W,H,'추정 대 실현 산점');
  const X=v=>pad+Math.max(0,Math.min(1,v))*(W-pad-14);
  const Y=v=>H-pad-Math.max(0,Math.min(1,v))*(H-pad-padT);
  [0,0.25,0.5,0.75,1].forEach(t=>{
    svgNode(s,'line',{x1:X(0),x2:X(1),y1:Y(t),y2:Y(t),stroke:'var(--line)',
      'stroke-width':0.5,'stroke-dasharray':'3 3'});
    svgNode(s,'text',{x:pad-6,y:Y(t)+3,'text-anchor':'end','font-size':9,
      fill:'var(--muted)'},(t*100).toFixed(0)+'%');
    svgNode(s,'text',{x:X(t),y:H-pad+14,'text-anchor':'middle','font-size':9,
      fill:'var(--muted)'},(t*100).toFixed(0)+'%')});
  svgNode(s,'line',{x1:X(0),y1:Y(0),x2:X(1),y2:Y(1),stroke:'var(--accent)',
    'stroke-width':1,'stroke-dasharray':'5 4'});
  points.forEach(p=>{
    const c=svgNode(s,'circle',{cx:X(p.x),cy:Y(p.y),r:2.6,
      fill:'var(--'+(p.tone||'lineage')+')','fill-opacity':0.62});
    c.appendChild(document.createElementNS(s.namespaceURI,'title')).textContent=
      p.label+' · 추정 '+(p.x*100).toFixed(1)+'% · 실현 '+(p.y*100).toFixed(1)+'%'});
  svgNode(s,'text',{x:W/2,y:H-8,'text-anchor':'middle','font-size':9,
    fill:'var(--muted)'},'추정');
  svgNode(s,'text',{x:4,y:11,'font-size':9,fill:'var(--muted)'},'실현');
  return chartBox(s,null,null);
}

/* ══════════════ 고객행동모형 추정 ═════════════════════════════════════ */

const BHV_TABLES=['alm_behaviour_model','alm_behaviour_backtest',
  'alm_prepay_observation','alm_early_redemption_observation',
  'alm_prepay_scurve_param','alm_behaviour_param','alm_behaviour_scenario_mult'];

function bhvModelScreen(root){
  reviewNotice(root,'ALM');
  root.appendChild(almSources(BHV_TABLES,
    '조기상환율·중도해지율 모형의 추정 결과다. 수렴하지 못한 포트폴리오는 '+
    '모수가 비어 있고, 그 사실이 화면에 남는다.'));
  if(!almHas(root,['alm_behaviour_model']))return;
  const f=almF('alm_behaviour_model'),i=frameIdx(f);
  const g=el('div','grid');
  const conv=f.rows.filter(r=>r[i.converged]===true).length;
  const fail=f.rows.filter(r=>r[i.converged]===false).length;
  [['추정 대상',String(f.rows.length),''],
   ['수렴',String(conv),''],
   ['수렴 실패',String(fail),fail?'bad':'good'],
   ['헤드라인 채택',String(f.rows.filter(r=>r[i.headline_estimate]).length),'']]
  .forEach(([k,v,t])=>{const c=el('div','card kpi');
    c.appendChild(el('div','lab',k));c.appendChild(el('div','val '+t,v));
    g.appendChild(c)});
  root.appendChild(g);
  const CV=6;
  const c1=cardOf('포트폴리오별 적합 모수',
    simpleTable(['모형','포트폴리오','통화','추정방법','함수형태','관측수',
                 '수렴','R²','적합 상태','헤드라인','모수','메시지','승인자','근거'],
      f.rows.map(r=>[r[i.model],r[i.portfolio_id],r[i.ccy],
        r[i.estimation_method],r[i.functional_form],r[i.n_obs],
        r[i.converged]===null?'미판정':(r[i.converged]?'수렴':'실패'),
        numOrDash(r[i.r_squared],4),r[i.fit_status],
        r[i.headline_estimate]?'채택':'',r[i.params_json]||'(비어 있음)',
        r[i.message]||'',r[i.approved_by]||'(미승인)',r[i.evidence_status]]),
      {numeric:false,rowClass:r=>r[CV]==='실패'?'bad':(r[CV]==='미판정'?'warn':null)}));
  c1.appendChild(el('div','meta',
    '모수가 비어 있는 행은 추정이 수렴하지 못한 것이다. 그 포트폴리오에는 '+
    '행동가정이 적용되지 않는다.'));
  c1.appendChild(srcMeta(f));
  root.appendChild(c1);

  const po=almF('alm_prepay_observation');
  if(po){
    const oi=frameIdx(po);
    const ports=[...new Set(po.rows.map(r=>r[oi.portfolio_id]))];
    const bar=el('div','toolbar');
    const sel=almSelect(bar,'포트폴리오',ports,ports[0]);
    const pane=el('div');
    function draw(){
      pane.innerHTML='';
      const sub=po.rows.filter(r=>r[oi.portfolio_id]===sel.value);
      pane.appendChild(cardOf(null,scatterXY(
        sub.map(r=>({x:r[oi.refi_incentive_bp],y:(r[oi.observed_cpr_annual]||0)*100,
          label:r[oi.obs_month]+' · 계좌 '+fmtNum(r[oi.n_accounts])})),
        {xlabel:'차환유인 (bp)',ylabel:'관측 CPR (%)'}),
        '가로가 계약금리와 시장 차환금리의 차이이고 세로가 관측 조기상환율이다. '+
        '차환유인이 커질수록 CPR 이 오르는 S 자 형태를 확인한다.'));
      pane.appendChild(cardOf(null,scatterXY(
        sub.map(r=>({x:r[oi.wa_seasoning_months],y:(r[oi.observed_cpr_annual]||0)*100,
          label:r[oi.obs_month]})),
        {xlabel:'가중평균 경과월',ylabel:'관측 CPR (%)'}),
        '경과효과 램프다. 대출이 오래될수록 조기상환이 늘어나는 구간을 본다.'));
    }
    sel.onchange=draw;draw();
    const c=cardOf('조기상환 관측',null);
    c.appendChild(bar);c.appendChild(pane);c.appendChild(srcMeta(po));
    root.appendChild(c)}

  const eo=almF('alm_early_redemption_observation');
  if(eo){
    const ei=frameIdx(eo);
    root.appendChild(cardOf('중도해지 관측',
      scatterXY(eo.rows.map(r=>({x:r[ei.rate_gap_bp],
        y:(r[ei.observed_tdrr_annual]||0)*100,
        label:r[ei.portfolio_id]+' · '+r[ei.obs_month]})),
        {xlabel:'금리 격차 (bp)',ylabel:'관측 중도해지율 (%)'}),
      '위약금률이 높은 상품은 같은 금리 격차에서도 해지가 적다. 위약금률은 '+
      '원장 컬럼(penalty_rate)이다.'))}

  const sp=almF('alm_prepay_scurve_param');
  if(sp){
    const si=frameIdx(sp);
    root.appendChild(cardOf('S-curve 모수 원장',
      simpleTable(['모수셋','상품군','함수형태','a','b','c','d','기준금리',
                   '수수료 차감','사용','입력출처','근거','비고'],
        sp.rows.map(r=>[r[si.param_set_id],r[si.product_group],
          r[si.functional_form],numOrDash(r[si.coef_a],4),
          numOrDash(r[si.coef_b],4),numOrDash(r[si.coef_c],4),
          numOrDash(r[si.coef_d],4),r[si.refi_rate_ref],
          r[si.deduct_prepay_fee]?'차감':'미차감',r[si.enabled]?'사용':'미사용',
          r[si.input_source],r[si.evidence_status],r[si.note]||'']))))}
  const mult=almF('alm_behaviour_scenario_mult');
  if(mult){
    const mi=frameIdx(mult);
    root.appendChild(cardOf('시나리오별 승수 (<표4>)',
      simpleTable(['모형','시나리오','승수','방향 규칙','근거','근거 판정'],
        mult.rows.map(r=>[r[mi.model],r[mi.scenario],numOrDash(r[mi.multiplier],2),
          r[mi.direction_rule],r[mi.citation],r[mi.evidence_status]])),
      '회전 시나리오에서는 조기상환 승수와 중도해지 승수가 같은 값이다. '+
      '방향 규칙 컬럼이 그 사실을 담고 있다.'))}
  root.appendChild(almEvidence(BHV_TABLES));
}

function nmdCoreScreen(root){
  reviewNotice(root,'ALM');
  root.appendChild(almSources(['alm_nmd_core_method_compare','alm_nmd_param',
    'alm_nmd_balance_history','kr_nmd_category','alm_nii_result'],
    '비만기성예금 코어비율을 세 추정방법으로 나란히 낸 결과다. <표3> 상한이 '+
    '어디에서 물었는지와 방법별 ΔEVE 영향을 함께 본다.'));
  if(!almHas(root,['alm_nmd_core_method_compare']))return;
  const f=almF('alm_nmd_core_method_compare'),i=frameIdx(f);
  const CAP=7,MCAP=11;
  const c1=cardOf('추정방법별 코어비율과 평균만기',
    simpleTable(['범주','통화','방법','방법 규칙','헤드라인','기준잔액',
                 '원시 코어비율','코어비율','상한','상한 적용','평균만기(년)',
                 '만기 상한','상한 적용','달성 평균만기','코어금액','관측수'],
      f.rows.map(r=>[r[i.nmd_category],r[i.ccy],r[i.method],r[i.method_rule],
        r[i.is_headline]?'채택':'',r[i.base_balance],
        pctv(r[i.core_ratio_raw],2),pctv(r[i.core_ratio],2),
        pctv(r[i.core_ratio_cap],2),r[i.core_cap_binding]?'적용':'',
        numOrDash(r[i.avg_maturity_years],2),
        numOrDash(r[i.avg_maturity_cap_years],2),
        r[i.maturity_cap_binding]?'적용':'',
        numOrDash(r[i.achieved_avg_maturity_years],2),
        r[i.core_amount],r[i.n_obs]]),
      {numeric:false,
       rowClass:r=>(r[9]==='적용'||r[12]==='적용')?'warn':null}));
  c1.appendChild(el('div','meta',
    '상한이 문 행은 원시추정이 <표3> 상한을 넘어 상한으로 잘린 것이다. '+
    '상한값은 원장 컬럼이며 화면이 정하지 않는다.'));
  c1.appendChild(srcMeta(f));
  root.appendChild(c1);

  const cats=[...new Set(f.rows.map(r=>r[i.nmd_category]))];
  const methods=[...new Set(f.rows.map(r=>r[i.method]))];
  root.appendChild(cardOf('방법별 코어비율 (%)',
    stackBars(methods.map(m=>({name:m,
      values:cats.map(c=>{const r=f.rows.find(x=>x[i.nmd_category]===c&&
        x[i.method]===m);return r?(r[i.core_ratio]||0)*100:0})})),cats,
      {title:null,note:'같은 범주를 세 방법으로 추정한 값이다. 누적이 아니라 '+
        '나란히 읽는다.'})));

  const eve=f.rows.filter(r=>r[i.delta_eve_proxy_krw]!=null);
  if(eve.length)root.appendChild(hbars(eve.map(r=>({
    label:r[i.nmd_category]+' · '+r[i.method],
    value:r[i.delta_eve_proxy_krw],
    sub:'충격 '+numOrDash(r[i.shock_bp])+'bp · 코어 '+pctv(r[i.core_ratio],1),
    tone:r[i.is_headline]?undefined:'warn'})),
    {title:'방법별 ΔEVE 영향 (동일 충격 기준)',src:srcMeta(f)}));

  const h=almF('alm_nmd_balance_history');
  if(h){
    const hi=frameIdx(h);
    const catsh=[...new Set(h.rows.map(r=>r[hi.nmd_category]))];
    const bar=el('div','toolbar');
    const sel=almSelect(bar,'범주',catsh,catsh[0]);
    const pane=el('div');
    function draw(){
      pane.innerHTML='';
      const sub=h.rows.filter(r=>r[hi.nmd_category]===sel.value)
        .sort((a,b)=>a[hi.obs_seq]-b[hi.obs_seq]);
      pane.appendChild(areaLine(sub.map(r=>r[hi.avg_balance]),
        {label:'월평잔'}));
      const pt=sub.filter(r=>r[hi.observed_pass_through]!=null);
      if(pt.length)pane.appendChild(areaLine(
        pt.map(r=>+((r[hi.observed_pass_through]||0)*100).toFixed(2)),
        {label:'관측 전가율 (%)',height:150}));
      pane.appendChild(el('div','meta','관측 '+sub.length+'개월'));
    }
    sel.onchange=draw;draw();
    const c=cardOf('잔액 관측과 전가율',null);
    c.appendChild(bar);c.appendChild(pane);c.appendChild(srcMeta(h));
    root.appendChild(c)}

  const p=almF('alm_nmd_param');
  if(p){
    const pi=frameIdx(p);
    root.appendChild(cardOf('전가율 모수',
      simpleTable(['범주','전가율','배분방법','비코어 배분','입력자','승인자',
                   '승인일','근거'],
        p.rows.map(r=>[r[pi.nmd_category],pctv(r[pi.pass_through_beta],2),
          r[pi.slotting_method],r[pi.non_core_bucket_label],
          r[pi.entered_by]||'-',r[pi.approved_by]||'(미승인)',
          r[pi.approved_on]||'-',r[pi.evidence_status]]))))}
  const nii=almF('alm_nii_result');
  if(nii){
    const ni=frameIdx(nii);
    const c=cardOf('ΔNII 산입 범위',
      simpleTable(['시나리오','목표기간(년)','재가격 계약수','제외 계약수',
                   '제외 명목','제외 비율','대차대조표 가정','마진 처리'],
        nii.rows.map(r=>[r[ni.scenario],numOrDash(r[ni.horizon_years],1),
          r[ni.n_repricing_contracts],r[ni.n_excluded_contracts],
          r[ni.excluded_notional],pctv(r[ni.excluded_notional_ratio],2),
          r[ni.balance_sheet_assumption],r[ni.margin_treatment]])));
    c.appendChild(el('div','note',
      '원장은 현재 실행의 제외 규모만 담는다. 전가율 도입 전후를 비교하려면 '+
      '두 실행이 필요하며, 이 화면은 한 실행의 값만 싣는다.'));
    root.appendChild(c)}
}

function bhvBacktestScreen(root){
  reviewNotice(root,'ALM');
  root.appendChild(almSources(['alm_behaviour_backtest','alm_behaviour_model',
    'alm_behaviour_param'],
    '표본외 실적 대비 예측이다. 합격 임계는 내부기준이며 규정이 정한 값이 아니다.'));
  if(!almHas(root,['alm_behaviour_backtest']))return;
  const f=almF('alm_behaviour_backtest'),i=frameIdx(f);
  const g=el('div','grid');
  const oot=f.rows.filter(r=>r[i.is_out_of_time]).length;
  const bad=f.rows.filter(r=>r[i.judgement]==='미통과').length;
  [['검증 대상',String(f.rows.length),''],
   ['표본외 검증',String(oot),''],
   ['미통과',String(bad),bad?'bad':'good'],
   ['승인 완료',String(f.rows.filter(r=>r[i.approved_by]).length),'']]
  .forEach(([k,v,t])=>{const c=el('div','card kpi');
    c.appendChild(el('div','lab',k));c.appendChild(el('div','val '+t,v));
    g.appendChild(c)});
  root.appendChild(g);
  const J=10;
  const c1=cardOf('백테스트 결과',
    simpleTable(['모형','포트폴리오','검증구간','표본외','관측수','실적 평균',
                 '예측 평균','편의','MAE','RMSE','판정','표본내 MAE',
                 '임계 MAE','임계 근거','승인자','승인일','근거'],
      f.rows.map(r=>[r[i.model],r[i.portfolio_id],
        r[i.validation_window_start]+' ~ '+r[i.validation_window_end],
        r[i.is_out_of_time]?'예':'아니오',r[i.n_obs],
        numOrDash(r[i.mean_actual_pp],3),numOrDash(r[i.mean_predicted_pp],3),
        numOrDash(r[i.bias_pp],3),numOrDash(r[i.mae_pp],3),
        numOrDash(r[i.rmse_pp],3),r[i.judgement]||'미판정',
        numOrDash(r[i.in_sample_mae_pp],3),numOrDash(r[i.threshold_mae_pp],3),
        r[i.threshold_basis]||'-',r[i.approved_by]||'(미승인)',
        r[i.approved_on]||'-',r[i.evidence_status]]),
      {numeric:false,rowClass:r=>r[J]==='미통과'?'bad':
        (r[J]==='미판정'?'warn':null)}));
  c1.appendChild(el('div','note warn',
    '합격 임계(MAE)는 내부기준이다. 원장의 threshold_basis 컬럼이 그 근거를 '+
    '담으며, 임계가 비어 있으면 판정하지 않는다.'));
  c1.appendChild(srcMeta(f));
  root.appendChild(c1);
  root.appendChild(hbars(f.rows.map(r=>({
    label:r[i.model]+' · '+r[i.portfolio_id],
    value:+(r[i.mae_pp]||0).toFixed(4),
    sub:'표본내 '+numOrDash(r[i.in_sample_mae_pp],3)+' · 임계 '+
      numOrDash(r[i.threshold_mae_pp],3),
    tone:(r[i.threshold_mae_pp]!=null&&r[i.mae_pp]>r[i.threshold_mae_pp])
      ?'bad':undefined})),
    {title:'표본외 MAE (%p)',money:false,src:srcMeta(f)}));
  root.appendChild(hbars(f.rows.map(r=>({
    label:r[i.model]+' · '+r[i.portfolio_id],
    value:+(r[i.bias_pp]||0).toFixed(4),
    sub:'실적 '+numOrDash(r[i.mean_actual_pp],3)+' · 예측 '+
      numOrDash(r[i.mean_predicted_pp],3),
    tone:r[i.bias_pp]<0?'warn':undefined})),
    {title:'편의 (%p, 실적 − 예측)',money:false,src:srcMeta(f)}));
}

/* 일반 산점. 축 라벨은 호출자가 준다. */
/* `fit` 은 원장이 이미 낸 회귀계수(절편·기울기)를 그대로 받아 직선을 긋는다.
   화면이 점에서 다시 회귀하지 않는다. 다시 하면 추정 원장의 베타와 화면의
   선이 갈라져도 아무도 모른다. `tick` 은 눈금 표기 함수다. */
function scatterXY(points,{xlabel,ylabel,fit,tick}={}){
  /* padT 는 y축 이름이 앉을 자리까지 포함한다. 이름을 눈금 칸에 그리면
     맨 위 눈금 라벨과 겹친다. */
  const W=560,H=330,padL=52,padB=42,padT=28,padR=14;
  const xs=points.map(p=>p.x),ys=points.map(p=>p.y);
  const x0=Math.min(...xs,0),x1=Math.max(...xs,0)||1;
  const y0=Math.min(...ys,0),y1=Math.max(...ys,0)||1;
  const sx=v=>padL+(x1===x0?0.5:(v-x0)/(x1-x0))*(W-padL-padR);
  const sy=v=>H-padB-(y1===y0?0.5:(v-y0)/(y1-y0))*(H-padB-padT);
  const ty=tick||(v=>v.toFixed(1)),tx=tick||(v=>v.toFixed(0));
  const s=svgEl(W,H,(ylabel||'')+' 대 '+(xlabel||''));
  [0,0.25,0.5,0.75,1].forEach(t=>{
    const yv=y0+(y1-y0)*t;
    svgNode(s,'line',{x1:padL,x2:W-padR,y1:sy(yv),y2:sy(yv),
      stroke:'var(--line)','stroke-width':0.5,'stroke-dasharray':'3 3'});
    svgNode(s,'text',{x:padL-6,y:sy(yv)+3,'text-anchor':'end','font-size':9,
      fill:'var(--muted)'},ty(yv));
    const xv=x0+(x1-x0)*t;
    svgNode(s,'text',{x:sx(xv),y:H-padB+14,'text-anchor':'middle','font-size':9,
      fill:'var(--muted)'},tx(xv))});
  points.forEach(p=>{
    const c=svgNode(s,'circle',{cx:sx(p.x),cy:sy(p.y),r:3,
      fill:'var(--'+(p.tone||'accent')+')','fill-opacity':0.6});
    c.appendChild(document.createElementNS(s.namespaceURI,'title')).textContent=
      (p.label||'')+' · '+p.x+' → '+p.y.toFixed(2)});
  if(fit&&fit.slope!=null&&fit.intercept!=null){
    const ya=fit.intercept+fit.slope*x0,yb=fit.intercept+fit.slope*x1;
    svgNode(s,'line',{x1:sx(x0),y1:sy(ya),x2:sx(x1),y2:sy(yb),
      stroke:'var(--accent)','stroke-width':1.4,'stroke-dasharray':'5 4'})}
  if(xlabel)svgNode(s,'text',{x:W/2,y:H-6,'text-anchor':'middle','font-size':9,
    fill:'var(--muted)'},xlabel);
  if(ylabel)svgNode(s,'text',{x:4,y:11,'font-size':9,fill:'var(--muted)'},ylabel);
  return chartBox(s,null,null);
}

/* ══════════════ 거액익스포져 ══════════════════════════════════════════ */

const LEX_TABLES=['lex_setting','lex_position','lex_aggregate',
  'lex_connected_group','lex_exemption','lex_lookthrough','lex_substitution',
  'lex_exposure_measure'];

function lexSettingScreen(root){
  reviewNotice(root,'CRE');
  root.appendChild(almSources(['lex_setting','lex_aggregate'],
    '거액익스포져 산출의 설정 원장이다. 한도율·보고기준·연결차주 판정 임계·'+
    '면제정책이 체계별로 따로 있고, 각 항목에 근거와 근거 판정이 붙는다.'));
  if(!almHas(root,['lex_setting']))return;
  const f=almF('lex_setting'),i=frameIdx(f);
  const fws=[...new Set(f.rows.map(r=>r[i.framework]))];
  const bar=el('div','toolbar');
  const sel=almSelect(bar,'체계',fws,fws[0]);
  const pane=el('div');
  const props=[];
  function draw(){
    pane.innerHTML='';
    const sub=f.rows.filter(r=>r[i.framework]===sel.value);
    const EV=4;
    pane.appendChild(simpleTable(
      ['항목','값','단위','분모','근거 판정','재정의','근거','입력자','승인자',
       '승인일','비고'],
      sub.map(r=>[r[i.param_code],
        r[i.param_value]==null?'(비어 있음)':numOrDash(r[i.param_value],4),
        r[i.param_unit],r[i.denominator_basis],r[i.evidence_status],
        r[i.is_overridden]?'재정의':'',r[i.citation],r[i.input_by]||'-',
        r[i.approved_by]||'(미승인)',r[i.approved_at]||'-',r[i.note]||'']),
      {numeric:false,rowClass:r=>r[EV]==='미확인'?'bad':
        (r[EV]==='재량·미규정'?'warn':null)}));
    const blank=sub.filter(r=>r[i.param_value]==null);
    if(blank.length)pane.appendChild(el('div','note warn',
      '값이 비어 있는 항목 '+blank.length+'개 ('+
      blank.map(r=>r[i.param_code]).join(' · ')+'). 1차자료를 확인하지 못했거나 '+
      '규정이 값을 주지 않는 항목이며, 그 항목은 산출되지 않는다.'));
    const unapproved=sub.filter(r=>!r[i.approved_by]||
      String(r[i.approved_by]).indexOf('미승인')>=0);
    if(unapproved.length)pane.appendChild(el('div','note',
      '승인란이 채워지지 않은 항목 '+unapproved.length+'개. 승인 전에는 이 '+
      '설정으로 낸 산출을 결재에 올릴 수 없다.'));
  }
  sel.onchange=draw;draw();
  const c=cardOf('설정 원장 (체계별)',null);
  c.appendChild(bar);c.appendChild(pane);c.appendChild(srcMeta(f));
  root.appendChild(c);

  /* 값을 바꾸면 무엇이 다시 산출되는지. 화면은 제안만 만들고 값을 바꾸지 않는다. */
  const edit=el('div','card');
  edit.appendChild(el('h3',null,'설정 변경 제안'));
  edit.appendChild(el('div','note',
    '설정 변경은 승인 대상이다. 이 화면은 제안서만 만들고 값을 바꾸지 않는다. '+
    '적용은 원장 등재와 승인, 파이프라인 재실행, 검증 두 층을 거친다.'));
  const eb=el('div','toolbar');
  const codes=[...new Set(f.rows.map(r=>r[i.param_code]))];
  const csel=almSelect(eb,'항목',codes,codes[0]);
  const inp=el('input','input');inp.type='text';inp.style.maxWidth='160px';
  inp.placeholder='제안 값';
  const wl=el('label','meta','제안 값 ');wl.appendChild(inp);eb.appendChild(wl);
  const why=el('input','input');why.type='text';
  why.placeholder='사유 (필수, 원문 확인·감독 지적·정책 결정 등)';
  why.style.flex='1 1 260px';
  const wl2=el('label','meta','사유 ');wl2.appendChild(why);eb.appendChild(wl2);
  const btn=el('button','btn','제안서 만들기');eb.appendChild(btn);
  edit.appendChild(eb);
  const out=el('div');edit.appendChild(out);
  btn.onclick=()=>{
    out.innerHTML='';
    if(STATE.killed){out.appendChild(el('div','note bad',
      '비상정지 중. 제안을 만들지 않는다.'));return}
    if(!why.value.trim()||!inp.value.trim()){
      out.appendChild(el('div','note bad','제안 값과 사유가 모두 필요하다.'));
      return}
    const cur=f.rows.find(r=>r[i.param_code]===csel.value&&
      r[i.framework]===sel.value);
    props.push([sel.value,csel.value,
      cur&&cur[i.param_value]!=null?String(cur[i.param_value]):'(비어 있음)',
      inp.value.trim(),why.value.trim()]);
    out.appendChild(simpleTable(['체계','항목','현재값','제안값','사유'],props));
    out.appendChild(el('div','note',
      '이 항목을 바꾸면 다시 산출되는 것: 포지션 한도율과 소진율, 보고대상 '+
      '판정, 연결그룹 판정, look-through 귀속, 총액한도 소진율. 화면에는 '+
      '반영되지 않으며 재실행이 필요하다.'));
  };
  root.appendChild(edit);
  root.appendChild(almEvidence(['lex_setting']));
}

function lexAnalysisScreen(root){
  reviewNotice(root,'CRE');
  root.appendChild(almSources(LEX_TABLES,
    '체계별 한도 소진과 보고대상, 대체 전후, 연결그룹, 면제, look-through 귀속을 '+
    '본다. 포지션 원장은 만 행대라 화면에는 표본이 실리고, 순위·분포·합계는 '+
    '파이프라인이 전량을 집계한 값이다.'));
  const L=D.lex;
  if(!L||!L.frameworks||!L.frameworks.length){
    root.appendChild(el('div','note bad','거액익스포져 집계가 payload 에 없다.'));
    return}
  /* 체계 대비. 분모와 기준이 다르므로 한 표에서 나란히 보이되 섞지 않는다. */
  const cmp=cardOf('체계 대비 (분모와 기준이 다르다)',
    simpleTable(['체계','집계단위','분모','분모금액','한도율','한도액',
                 '포지션 수','보고대상','위반','산입액 합','면제액 합','근거'],
      L.frameworks.map(x=>[x.framework,x.aggregation_unit,x.denominator_basis,
        x.denominator_amount,x.limit_pct==null?'(비어 있음)':pctv(x.limit_pct,2),
        x.limit_amount,x.n_positions,x.n_reportable,x.n_breach,
        x.sum_included,x.sum_exempt,x.limit_citation]),
      {numeric:false,rowClass:r=>r[8]>0?'bad':null}));
  cmp.appendChild(el('div','note',
    '분모가 기본자본인 체계와 자기자본인 체계는 같은 익스포저에서 다른 비율을 '+
    '낸다. 두 비율을 더하거나 비교하지 않는다.'));
  root.appendChild(cmp);

  const ag=almF('lex_aggregate');
  if(ag){
    const i=frameIdx(ag);
    const c=cardOf('총액한도',
      simpleTable(['체계','분모','분모금액','거액 기준','거액 건수','분자',
                   '분모 대비 배수','총액한도 배수','한도금액','소진율','위반','근거'],
        ag.rows.map(r=>[r[i.framework],r[i.denominator_basis],
          r[i.denominator_amount],pctv(r[i.large_credit_threshold_pct],1),
          r[i.n_large_credits],r[i.aggregate_numerator],
          numOrDash(r[i.aggregate_ratio],2),
          r[i.aggregate_limit_pct]==null?'(없음)':numOrDash(r[i.aggregate_limit_pct],1),
          moneyOrDash(r[i.aggregate_limit_amount]),
          r[i.aggregate_utilisation]==null?'-':pctv(r[i.aggregate_utilisation],1),
          r[i.breach]?'위반':'',r[i.citation]]),
        {numeric:false,rowClass:r=>r[10]==='위반'?'bad':null}));
    c.appendChild(srcMeta(ag));
    root.appendChild(c)}

  const fws=L.frameworks.map(x=>x.framework);
  const bar=el('div','toolbar');
  const sel=almSelect(bar,'체계',fws,fws[0]);
  const pane=el('div');
  function draw(){
    pane.innerHTML='';
    const meta=L.frameworks.find(x=>x.framework===sel.value);
    const top=L.top[sel.value];
    if(top){
      const ti=frameIdx(top);
      pane.appendChild(hbars(top.rows.map(r=>({
        label:r[ti.group_id]+(r[ti.n_members]>1?' ('+r[ti.n_members]+'개사)':''),
        value:+((r[ti.utilisation]||0)*100).toFixed(1),
        sub:'산입 '+fmtMoney(r[ti.exposure_included])+' · 잔여 '+
          fmtMoney(r[ti.headroom]),
        tone:r[ti.breach]?'bad':(r[ti.reportable]?'warn':undefined)})),
        {title:'상위 익스포저 소진율 (%)',money:false,
         src:srcMeta(top,'모집단 '+meta.n_positions.toLocaleString()+'행 중 상위 15')}));
      const RP=8;
      pane.appendChild(simpleTable(
        ['그룹','구성원','분모금액','대체 전','측정액','면제','산입액','비율',
         '보고대상','한도액','소진율','잔여한도','위반','근거 판정'],
        top.rows.map(r=>[r[ti.group_id],r[ti.n_members],r[ti.denominator_amount],
          r[ti.exposure_pre_crm],r[ti.exposure_measured],r[ti.exposure_exempt],
          r[ti.exposure_included],pctv(r[ti.ratio],2),
          r[ti.reportable]?'대상':'',r[ti.limit_amount],
          pctv(r[ti.utilisation],1),r[ti.headroom],r[ti.breach]?'위반':'',
          r[ti.measure_evidence_status]]),
        {numeric:false,rowClass:r=>r[12]==='위반'?'bad':(r[RP]==='대상'?'warn':null)}));
    }
    pane.appendChild(bars(meta.histogram.map(h=>({
      label:(h.lower*100).toFixed(0)+'%'+(h.upper==null?' 이상':' ~ '+
        (h.upper*100).toFixed(0)+'%'),
      value:h.n,
      tone:h.lower>=1?'bad':(h.lower>=0.9?'warn':undefined)})),
      {title:'소진율 분포 (전량 '+meta.n_positions.toLocaleString()+'행)',
       fmt:v=>fmtNum(v),
       note:'마지막 칸이 한도를 넘긴 포지션이다.'}));
  }
  sel.onchange=draw;draw();
  const c=cardOf('체계별 소진',null);
  c.appendChild(bar);c.appendChild(pane);
  root.appendChild(c);

  if(L.providers&&L.providers.length){
    const B=3;
    const cc=cardOf('신용위험경감 대체로 익스포저를 받은 보장제공자',
      simpleTable(['보장제공자','대체 유입액','연결 건수','자체 포지션 최대 소진율',
                   '한도 위반'],
        L.providers.map(x=>[x.provider,x.substituted_in,x.n_links,
          x.max_utilisation==null?'(포지션 없음)':pctv(x.max_utilisation,1),
          x.breach===null?'-':(x.breach?'위반':'')]),
        {numeric:false,rowClass:r=>r[4]==='위반'?'bad':null}));
    cc.appendChild(el('div','meta',
      '대체는 원차주의 익스포저를 보장제공자로 옮긴다. 옮겨 받은 쪽이 한도를 '+
      '넘기는지는 그 제공자의 포지션 행에서 읽는다.'));
    root.appendChild(cc)}

  const sub=almF('lex_substitution');
  if(sub){
    const si=frameIdx(sub);
    const inel=sub.rows.filter(r=>r[si.substituted_amount]===0);
    const c2=cardOf('대체 전후',
      simpleTable(['원차주','보장제공자','보장유형','대체 전','보장액','대체액',
                   '대체 후','만기 적격','CDS 예외','적격 사유'],
        sub.rows.slice(0,20).map(r=>[r[si.original_counterparty_id],
          r[si.protection_provider_id],r[si.protection_type],
          r[si.exposure_before],r[si.covered_amount],r[si.substituted_amount],
          r[si.exposure_after],r[si.maturity_mismatch_eligible]?'적격':'부적격',
          r[si.cds_exception_applied]?'적용':'',r[si.eligibility_reason]]),
        {numeric:false,rowClass:r=>r[7]==='부적격'?'warn':null}));
    c2.appendChild(el('div','meta','대체가 인정되지 않은 건 '+inel.length+
      ' / 전체 '+sub.rows.length+'. 사유는 적격 사유 컬럼에 있다.'));
    c2.appendChild(srcMeta(sub));
    root.appendChild(c2)}

  if(L.groups&&L.groups.basis){
    const gc=cardOf('연결그룹 구성',
      simpleTable(['연결 근거','거래상대방 수'],
        L.groups.basis.map(x=>[x.basis,x.n]),{numeric:true}));
    gc.appendChild(el('div','meta','그룹 '+L.groups.n_groups.toLocaleString()+
      '개 중 2개사 이상 '+L.groups.n_multi+'개 · 경제적 상호의존 평가 대상 '+
      L.groups.n_review.toLocaleString()+'건'));
    if(L.groups.top)gc.appendChild(table(L.groups.top));
    root.appendChild(gc)}

  const lt=almF('lex_lookthrough');
  if(lt){
    const li=frameIdx(lt);
    const m=new Map();
    lt.rows.forEach(r=>{const k=r[li.attribution_type];
      const cur=m.get(k)||{n:0,amt:0};
      cur.n+=1;cur.amt+=(r[li.attributed_amount]||0);m.set(k,cur)});
    const c3=cardOf('look-through 귀속',
      simpleTable(['귀속 유형','건수','귀속액'],
        [...m.entries()].map(([k,v])=>[k,v.n,v.amt]),{numeric:true}));
    const unknown=lt.rows.filter(r=>r[li.attribution_type]==='무명고객');
    if(unknown.length)c3.appendChild(el('div','note warn',
      '기초자산을 식별하지 못한 잔여는 무명고객 버킷으로 귀속된다. '+
      unknown.length+'건 · '+fmtMoney(unknown.reduce((a,r)=>
        a+(r[li.attributed_amount]||0),0))+'.'));
    c3.appendChild(el('div','meta','귀속 임계 '+
      moneyOrDash(lt.rows[0][li.threshold_amount])+' · '+
      lt.rows[0][li.citation]));
    c3.appendChild(srcMeta(lt));
    root.appendChild(c3)}

  const ex=almF('lex_exemption');
  if(ex){
    const ei=frameIdx(ex);
    const m=new Map();
    ex.rows.forEach(r=>{const k=r[ei.exemption_type];
      const cur=m.get(k)||{n:0,amt:0,basis:r[ei.basis]};
      cur.n+=1;cur.amt+=(r[ei.exempt_amount]||0);m.set(k,cur)});
    root.appendChild(cardOf('면제',
      simpleTable(['면제 유형','건수','면제액','근거'],
        [...m.entries()].map(([k,v])=>[k,v.n,v.amt,v.basis]),{numeric:true}),
      '면제액은 한도 산입에서 빠진 금액이다. 측정액과 산입액의 차이가 면제액이다.'))}

  if(L.measure&&L.measure.length){
    root.appendChild(hbars(L.measure.map(x=>({label:x.exposure_type,
      value:x.measured,sub:x.n.toLocaleString()+'건'})),
      {title:'익스포저 유형별 측정액'}));}
  root.appendChild(almEvidence(['lex_setting','lex_aggregate','lex_lookthrough']));
}

/* ══════════════ 시뮬레이션 (설명용 산술) ══════════════════════════════ */

/* 억원 단위 입력. 금액 칸과 비율 칸을 한 쌍으로 묶고, 어느 쪽으로 입력했는지
   태그로 남긴다. 반올림으로 두 값이 어긋나지 않도록 증감액을 원본으로 삼고
   비율은 거기서 다시 만든다. */
const EOK=1e8;
function linkedInput(label,base,onChange){
  const st={delta:0,source:'비율'};
  const wrap=el('div');
  wrap.style.cssText='display:flex;gap:6px;align-items:center;flex-wrap:wrap;'+
    'margin:5px 0;font-size:11px';
  const lab=el('span','meta',label);lab.style.minWidth='150px';
  wrap.appendChild(lab);
  const pi=el('input','input');pi.type='number';pi.step='0.5';pi.value='0';
  pi.style.maxWidth='88px';pi.title=label+' 변화율 (%)';
  const ai=el('input','input');ai.type='number';ai.step='100';ai.value='0';
  ai.style.maxWidth='120px';ai.title=label+' 변화액 (억원)';
  const tag=pill('비율 입력');
  function paint(){
    tag.textContent=st.source+' 입력';
    tag.className='pill'+(st.delta?' warn':'')}
  st.refresh=()=>{
    pi.value=base?(st.delta/base*100).toFixed(3):'0';
    ai.value=(st.delta/EOK).toFixed(0);paint()};
  pi.oninput=()=>{st.delta=base*(parseFloat(pi.value)||0)/100;st.source='비율';
    ai.value=(st.delta/EOK).toFixed(0);paint();onChange()};
  ai.oninput=()=>{st.delta=(parseFloat(ai.value)||0)*EOK;st.source='금액';
    pi.value=base?(st.delta/base*100).toFixed(3):'0';paint();onChange()};
  wrap.appendChild(pi);wrap.appendChild(el('span','meta','%'));
  wrap.appendChild(ai);wrap.appendChild(el('span','meta','억원'));
  wrap.appendChild(tag);
  const bs=rawEl('span','meta',TP('기준',fmtMoney(base)));wrap.appendChild(bs);
  st.wrap=wrap;st.base=base;
  return st;
}
/* 격자 표. 셀마다 색을 달리 줘야 요구비율 등고선을 그릴 수 있다. */
function gridTable(rowLabels,colLabels,cells,corner){
  const w=el('div','tw'),t=el('table'),th=el('thead'),tr=el('tr');
  tr.appendChild(el('th',null,corner||''));
  colLabels.forEach(c=>tr.appendChild(el('th','num',c)));
  th.appendChild(tr);t.appendChild(th);
  const tb=el('tbody');
  rowLabels.forEach((rl,i)=>{
    const x=el('tr');x.appendChild(el('th',null,rl));
    colLabels.forEach((_,j)=>{
      const cell=cells[i][j];
      const td=el('td','num'+(cell.tone?' '+cell.tone:''),cell.text);
      if(cell.title)td.title=cell.title;
      x.appendChild(td)});
    tb.appendChild(x)});
  t.appendChild(tb);w.appendChild(t);
  return w;
}
function simulation(root){
  const S=D.sim;
  if(!S||!S.components){
    root.appendChild(el('div','note bad',
      '시뮬레이션 기준값이 payload 에 없다. 화면을 그리지 않는다.'));return}
  root.appendChild(el('p','lead',
    '자본비율 항등식(비율 = 자본 ÷ 위험가중자산)의 설명용 산술이다. 위험가중자산을 '+
    '구성요소별로, 자본을 계층별로 움직여 비율이 어떻게 반응하는지 즉시 본다. '+
    '파이프라인 재계산이 아니며 승인·제출값이 아니다. 실제 영향도는 시나리오 '+
    '설정 제안, 재실행, 검증 두 층으로만 확정된다.'));
  root.appendChild(cardOf('기준값의 출처',
    simpleTable(['항목','값','출처'],
      [['위험가중자산 (내부산출 합)',fmtMoney(S.internal_total),'파이프라인 rwa'],
       ['표준방법 산출 합',fmtMoney(S.standardised_total),'파이프라인 rwa'],
       ['산출하한 비율',pctv(S.floor_pct,1),'파이프라인 rwa'],
       ['최종 위험가중자산',fmtMoney(S.final_total),'파이프라인 rwa'],
       ['보통주자본',fmtMoney(S.capital.cet1),'자본 스택'],
       ['기타기본자본',fmtMoney(S.capital.at1),'자본 스택'],
       ['보완자본',fmtMoney(S.capital.t2),'자본 스택'],
       ['레버리지 익스포저 측정치',fmtMoney(S.leverage.exposure_measure),
        '파이프라인 leverage']]),
    '구성요소 합이 내부산출 합과 같은지는 tests/test_ui_interactive.py 가 고정한다. '+
    '거래상대방과 유동화는 원장에서 별도 구성요소이고, 신용 표준방법·내부등급법에 '+
    '섞여 있지 않다.'));

  const box=el('div','card');
  box.appendChild(el('h3',null,'입력'));
  const inputs={};
  const comps=S.components;
  let redraw=()=>{};
  /* 총액 입력은 구성요소에 비중대로 나눠 넣는다. 구성요소를 직접 고치면
     총액 칸이 그 합으로 다시 채워진다. 두 방향 모두 같은 값을 가리킨다. */
  const totalRwa=linkedInput('위험가중자산 합계',S.internal_total,()=>{
    comps.forEach(c=>{
      inputs[c.key].delta=S.internal_total?
        totalRwa.delta*c.value/S.internal_total:0;
      inputs[c.key].refresh()});
    redraw()});
  box.appendChild(totalRwa.wrap);
  const compBox=el('div');
  compBox.style.cssText='border-left:2px solid var(--line);padding-left:12px;'+
    'margin:6px 0';
  comps.forEach(c=>{
    inputs[c.key]=linkedInput(c.label,c.value,()=>{
      totalRwa.delta=comps.reduce((a,x)=>a+inputs[x.key].delta,0);
      totalRwa.refresh();redraw()});
    compBox.appendChild(inputs[c.key].wrap)});
  const stdIn=linkedInput('표준방법 산출 합 (하한 분모)',S.standardised_total,
    ()=>redraw());
  compBox.appendChild(stdIn.wrap);
  box.appendChild(compBox);
  const capIn={
    cet1:linkedInput('보통주자본 (CET1)',S.capital.cet1,()=>redraw()),
    at1:linkedInput('기타기본자본 (AT1)',S.capital.at1,()=>redraw()),
    t2:linkedInput('보완자본 (T2)',S.capital.t2,()=>redraw())};
  ['cet1','at1','t2'].forEach(k=>box.appendChild(capIn[k].wrap));
  const levIn=linkedInput('레버리지 익스포저 측정치',
    S.leverage.exposure_measure,()=>redraw());
  box.appendChild(levIn.wrap);
  const btnBar=el('div','toolbar');
  const saveBtn=el('button','btn','이 조정안 저장');
  const resetBtn=el('button','btn','입력 초기화');
  btnBar.appendChild(saveBtn);btnBar.appendChild(resetBtn);
  box.appendChild(btnBar);
  root.appendChild(box);
  const pane=el('div');root.appendChild(pane);
  const saved=[];

  function state(){
    const parts=comps.map(c=>({key:c.key,label:c.label,
      base:c.value,now:c.value+inputs[c.key].delta}));
    const internal=parts.reduce((a,x)=>a+x.now,0);
    const std=S.standardised_total+stdIn.delta;
    const floorAmt=S.floor_pct*std;
    const addOn=Math.max(0,floorAmt-internal);
    const rwa=internal+addOn;
    const cet1=S.capital.cet1+capIn.cet1.delta;
    const at1=S.capital.at1+capIn.at1.delta;
    const t2=S.capital.t2+capIn.t2.delta;
    const tier1=cet1+at1,total=tier1+t2;
    const exp=S.leverage.exposure_measure+levIn.delta;
    return {parts:parts,internal:internal,std:std,floorAmt:floorAmt,
      addOn:addOn,binding:addOn>0,rwa:rwa,cet1:cet1,at1:at1,t2:t2,
      tier1:tier1,total:total,exposure:exp,
      ratios:{cet1:cet1/rwa,tier1:tier1/rwa,total:total/rwa},
      leverage:exp?tier1/exp:0};
  }
  const TIERS=[['cet1','보통주자본(CET1)'],['tier1','기본자본(Tier1)'],
               ['total','총자본']];
  function bufferRows(st){
    const bufTotal=Object.keys(S.buffers).reduce((a,k)=>a+S.buffers[k],0);
    return TIERS.map(([k,nm])=>{
      const min=S.minimums[k],req=S.required[k],cur=st.ratios[k];
      const zone=cur>=req?'요구 충족':(cur>=min?'완충자본 잠식':'최저비율 미달');
      return [nm,pctv(cur,2),pctv(min,2),pctv(bufTotal,2),pctv(req,2),
        ((cur-req)*100).toFixed(2)+'%p',zone]});
  }
  function draw(){
    pane.innerHTML='';
    const st=state();
    const g=el('div','grid');
    TIERS.forEach(([k,nm])=>{
      const req=S.required[k],min=S.minimums[k],cur=st.ratios[k];
      const before=(k==='cet1'?S.capital.cet1:k==='tier1'?
        S.capital.cet1+S.capital.at1:
        S.capital.cet1+S.capital.at1+S.capital.t2)/S.final_total;
      const c=el('div','card kpi');
      c.appendChild(el('div','lab',nm+' 비율'));
      c.appendChild(el('div','val '+(cur>=req?'good':(cur>=min?'warn':'bad')),
        pctv(cur,2)));
      c.appendChild(el('div','sub','현행 '+pctv(before,2)+' · 요구 '+pctv(req,2)+
        ' · 여유 '+((cur-req)*100).toFixed(2)+'%p'));
      c.appendChild(el('div','ln','원장 cap_stack · 파이프라인 rwa'));
      g.appendChild(c)});
    const lc=el('div','card kpi');
    lc.appendChild(el('div','lab','레버리지비율'));
    lc.appendChild(el('div','val '+(st.leverage>=S.leverage.required?'good':'bad'),
      pctv(st.leverage,2)));
    lc.appendChild(el('div','sub','현행 '+pctv(S.leverage.ratio,2)+' · 요구 '+
      pctv(S.leverage.required,2)));
    lc.appendChild(el('div','ln','분모는 익스포저 측정치이며 위험가중자산이 아니다'));
    g.appendChild(lc);
    pane.appendChild(g);

    const Z=6;
    const bc=cardOf('요구비율 층과 도달 구간',
      simpleTable(['계층','조정 후 비율','최저비율','완충자본 합','요구비율',
                   '여유','구간'],bufferRows(st),
        {numeric:false,rowClass:r=>r[Z]==='최저비율 미달'?'bad':
          (r[Z]==='완충자본 잠식'?'warn':null)}));
    bc.appendChild(simpleTable(['완충자본','비율'],
      Object.keys(S.buffers).map(k=>[k,pctv(S.buffers[k],2)])));
    bc.appendChild(el('div','meta',
      '완충자본 잠식 구간은 최저비율은 넘었으나 요구비율에 못 미치는 구간이며, '+
      '배당과 성과급 지급이 제한된다. 완충자본 구성은 파이프라인 meta.buffers 다.'));
    pane.appendChild(bc);

    const fc=cardOf('산출하한 (output floor)',
      simpleTable(['항목','값'],
        [['내부산출 합',fmtMoney(st.internal)],
         ['표준방법 산출 합',fmtMoney(st.std)],
         ['하한 비율',pctv(S.floor_pct,1)],
         ['하한 금액',fmtMoney(st.floorAmt)],
         ['가산액(add-on)',fmtMoney(st.addOn)],
         ['최종 위험가중자산',fmtMoney(st.rwa)],
         ['하한이 무는가',st.binding?'예':'아니오']]));
    if(st.binding)fc.appendChild(el('div','note warn',
      '표준방법 산출의 '+pctv(S.floor_pct,1)+'가 내부산출 합을 넘어 하한이 물었다. '+
      '이 구간에서는 내부산출을 더 줄여도 최종 위험가중자산이 줄지 않는다.'));
    fc.appendChild(el('div','meta',
      '표준방법 산출 합은 내부산출 구성요소와 별도 입력이다. 두 산출을 잇는 '+
      '원장이 없어 화면이 자동으로 연동하지 않는다.'));
    pane.appendChild(fc);

    pane.appendChild(cardOf('구성요소별 조정',
      simpleTable(['구성요소','기준','조정 후','증감','비중(조정 후)','입력 방식'],
        st.parts.map(p=>[p.label,fmtMoney(p.base),fmtMoney(p.now),
          fmtMoney(p.now-p.base),
          pctv(st.internal?p.now/st.internal:0,1),inputs[p.key].source]))));

    /* 파급효과. 자본이 움직이면 기본자본 연동 한도와 금리리스크 분모가 함께
       움직인다. 위험가중자산은 내부자본 필요액을 다시 계산하지 않는다. */
    const rip=[];
    if(S.single_obligor&&S.single_obligor.threshold_value!=null){
      const th=S.single_obligor.threshold_value;
      rip.push(['동일차주 한도액 ('+S.single_obligor.threshold_formula+')',
        fmtMoney(th*(S.capital.cet1+S.capital.at1)),fmtMoney(th*st.tier1),
        fmtMoney(th*st.tier1-th*(S.capital.cet1+S.capital.at1)),
        S.single_obligor.evidence_status])}
    if(S.icaap){
      const av=S.icaap.available_capital+capIn.cet1.delta+capIn.at1.delta+
        capIn.t2.delta;
      rip.push(['ICAAP 가용자본',fmtMoney(S.icaap.available_capital),
        fmtMoney(av),fmtMoney(av-S.icaap.available_capital),'파이프라인 icaap']);
      rip.push(['ICAAP 여유 (가용자본 − 소요 내부자본)',
        fmtMoney(S.icaap.buffer),fmtMoney(av-S.icaap.ec),
        fmtMoney(av-S.icaap.ec-S.icaap.buffer),'파이프라인 icaap'])}
    if(S.irrbb&&S.irrbb.delta_eve!=null){
      const b4=Math.abs(S.irrbb.delta_eve)/(S.capital.cet1+S.capital.at1);
      const af=Math.abs(S.irrbb.delta_eve)/st.tier1;
      rip.push(['금리리스크 ΔEVE / 기본자본 ('+S.irrbb.basis+' · '+
        S.irrbb.scenario+')',pctv(b4,2),pctv(af,2),
        ((af-b4)*100).toFixed(2)+'%p','원장 alm_irrbb_result'])}
    const rc=cardOf('파급효과',
      simpleTable(['연동 항목','현행','조정 후','변화','출처'],rip));
    rc.appendChild(el('div','note',
      '내부자본 소요액은 모형 산출이라 위험가중자산 조정으로 다시 계산되지 '+
      '않는다. 금리리스크 아웃라이어 판정은 원장 컬럼이며 이 화면이 다시 '+
      '판정하지 않는다. 위기 경로·유동성·손익의 2차 효과는 재실행으로만 본다.'));
    pane.appendChild(rc);

    /* 목표 역산. 항등식이라 닫힌 해가 있고, 하한이 무는 구간에서 꺾인다. */
    const gs=el('div','card');
    gs.appendChild(el('h3',null,'목표 역산'));
    const gb=el('div','toolbar');
    const tsel=almSelect(gb,'대상 비율',TIERS.map(x=>x[1]),TIERS[0][1]);
    const ti=el('input','input');ti.type='number';ti.step='0.1';
    ti.value=(S.required.cet1*100).toFixed(1);ti.style.maxWidth='100px';
    const wl=el('label','meta','목표 (%) ');wl.appendChild(ti);gb.appendChild(wl);
    gs.appendChild(gb);
    const gout=el('div');gs.appendChild(gout);
    function goal(){
      gout.innerHTML='';
      const key=TIERS[TIERS.map(x=>x[1]).indexOf(tsel.value)][0];
      const cap=key==='cet1'?st.cet1:key==='tier1'?st.tier1:st.total;
      const tgt=(parseFloat(ti.value)||0)/100;
      if(tgt<=0){gout.appendChild(el('div','note','목표 비율을 입력한다.'));return}
      const needRwa=cap/tgt;
      const needCap=tgt*st.rwa;
      const rows=[
        ['위험가중자산으로 맞추기',fmtMoney(needRwa),
         fmtMoney(needRwa-st.rwa),
         needRwa<st.floorAmt?'하한이 물어 도달 불가':'도달 가능'],
        ['자본으로 맞추기',fmtMoney(needCap),fmtMoney(needCap-cap),'도달 가능']];
      gout.appendChild(simpleTable(
        ['방법','필요 수준','현재 대비 증감','판정'],rows));
      if(needRwa<st.floorAmt)gout.appendChild(el('div','note warn',
        '목표 비율을 위험가중자산 축소만으로 맞추려면 '+fmtMoney(needRwa)+
        ' 까지 줄여야 하는데, 산출하한 금액이 '+fmtMoney(st.floorAmt)+
        ' 이라 그 아래로는 내려가지 않는다. 이 구간에서 해가 꺾인다.'));
      gout.appendChild(el('div','meta',
        '두 해는 항등식의 닫힌 해다. 실제로 그 수준에 도달할 수 있는지는 '+
        '포트폴리오 조치와 자본조달 계획이 정한다.'));
    }
    tsel.onchange=goal;ti.oninput=goal;goal();
    pane.appendChild(gs);

    /* 2축 민감도 격자. 요구비율 미달 칸을 색으로 표시해 등고선을 대신한다. */
    const rSteps=[-0.10,-0.05,0,0.05,0.10];
    const cSteps=[-0.10,-0.05,0,0.05,0.10];
    const cells=rSteps.map(dr=>cSteps.map(dc=>{
      const internal2=st.internal*(1+dr);
      const rwa2=internal2+Math.max(0,st.floorAmt-internal2);
      const cet2=st.cet1*(1+dc);
      const v=cet2/rwa2;
      return {text:pctv(v,2),
        tone:v>=S.required.cet1?'good':(v>=S.minimums.cet1?'warn':'bad'),
        title:'위험가중자산 '+(dr*100).toFixed(0)+'% · 보통주자본 '+
          (dc*100).toFixed(0)+'% · 최종 RWA '+fmtMoney(rwa2)}}));
    const sc=cardOf('2축 민감도 (보통주자본비율)',
      gridTable(rSteps.map(x=>'RWA '+(x>=0?'+':'')+(x*100).toFixed(0)+'%'),
        cSteps.map(x=>'CET1 '+(x>=0?'+':'')+(x*100).toFixed(0)+'%'),cells,
        'Δ'));
    sc.appendChild(el('div','meta',
      '초록은 요구비율 충족, 주황은 완충자본 잠식, 붉은색은 최저비율 미달이다. '+
      '경계선이 요구비율 등고선이다. 산출하한은 각 칸에서 다시 적용된다.'));
    pane.appendChild(sc);

    if(saved.length){
      const cols=['항목'].concat(saved.map((_,k)=>'조정안 '+(k+1)));
      const keys=[['CET1 비율',x=>pctv(x.ratios.cet1,2)],
        ['Tier1 비율',x=>pctv(x.ratios.tier1,2)],
        ['총자본 비율',x=>pctv(x.ratios.total,2)],
        ['레버리지비율',x=>pctv(x.leverage,2)],
        ['최종 위험가중자산',x=>fmtMoney(x.rwa)],
        ['하한 가산',x=>fmtMoney(x.addOn)],
        ['보통주자본',x=>fmtMoney(x.cet1)],
        ['기본자본',x=>fmtMoney(x.tier1)],
        ['총자본',x=>fmtMoney(x.total)]];
      pane.appendChild(cardOf('조정안 비교',
        simpleTable(cols,keys.map(([nm,fn])=>[nm].concat(saved.map(fn)))),
        '저장은 이 화면 안에서만 이뤄지고 원장에 쓰지 않는다. 승인·제출값이 '+
        '아니기 때문이다. 화면을 닫으면 사라진다.'))}
  }
  redraw=draw;
  saveBtn.onclick=()=>{saved.push(state());draw()};
  resetBtn.onclick=()=>{
    [totalRwa,stdIn,levIn,capIn.cet1,capIn.at1,capIn.t2]
      .concat(comps.map(c=>inputs[c.key]))
      .forEach(x=>{x.delta=0;x.source='비율';x.refresh()});
    draw()};
  draw();
}

/* ══════════════ 한도관리 ══════════════════════════════════════════════ */

/* 차원 코드를 한국어로 옮기는 사전은 한도 정의 원장이다. 화면에서 다시 적으면
   한도가 늘었을 때 화면만 옛 이름을 쓴다. */
function limitDimLabel(){
  const d=almF('lim_limit_definition');
  const m={};
  if(d){const i=frameIdx(d);
    d.rows.forEach(r=>{m[r[i.scope_key]]=r[i.limit_type]})}
  return m;
}
function limitObligorIndex(){
  const ob=almF('rdm_obligor');
  const m={};
  if(ob){const i=frameIdx(ob);
    ob.rows.forEach(r=>{m[r[i.obligor_id]]={sector:r[i.sector],
      country:r[i.country],asset_class:r[i.asset_class]}})}
  return m;
}
function limitsScreen(root){
  root.appendChild(el('p','lead',
    '차주·업종·국가·자산군·등급 다차원 한도와 소진율이다. 위반 보고서는 경보 '+
    '구간 이상만 담고, 아래 분포와 드릴다운은 위반이 아닌 구간까지 함께 본다. '+
    '경보 구간의 경계는 한도 엔진의 심각도 어휘가 정하며 화면이 정하지 않는다. '+
    '한도 정의의 근거와 승인 기록은 정의 원장에서 읽는다.'));
  const f=D.limits_full||D.limits;
  const i=frameIdx(f);
  const dimLab=limitDimLabel();
  const lab=d=>dimLab[d]||d;

  const bySev={};f.rows.forEach(r=>{const k=r[i.severity];
    bySev[k]=(bySev[k]||0)+1});
  const headroom=r=>(r[i.threshold]||0)-(r[i.exposure]||0);
  const neg=f.rows.filter(r=>headroom(r)<0);
  const g=el('div','grid');
  [['위반 (BREACH 이상)',(bySev.BREACH||0)+(bySev.CRITICAL||0),'bad'],
   ['경보 (WARN)',bySev.WARN||0,'warn'],
   ['한도 내 (OK)',bySev.OK||0,'good'],
   ['잔여한도 음수',neg.length,neg.length?'bad':'good'],
   ['차원',new Set(f.rows.map(r=>r[i.dimension])).size,'']]
  .forEach(([l,v,t])=>{
    const c=el('div','card kpi');c.appendChild(el('div','lab',l));
    c.appendChild(el('div','val '+t,String(v)));g.appendChild(c)});
  root.appendChild(g);

  /* --- 한도 정의 --- */
  const d=almF('lim_limit_definition');
  if(d){
    const di=frameIdx(d);
    const BS=3;
    const c=cardOf('한도 정의 (근거·승인)',
      simpleTable(['한도','유형','적용 축','근거 구분','임계값','단위','산식',
                   '승인기구','승인일','규정 근거','근거 판정'],
        d.rows.map(r=>[r[di.limit_id],r[di.limit_type],r[di.scope_key],
          r[di.basis],
          r[di.threshold_value]==null?'(비어 있음)':fmtNum(r[di.threshold_value]),
          r[di.threshold_unit],r[di.threshold_formula],
          r[di.approval_body]||'-',r[di.approved_on]||'(미승인)',
          r[di.citation],r[di.evidence_status]]),
        {numeric:false,rowClass:r=>r[BS]==='규정'?null:'warn'}));
    const noap=d.rows.filter(r=>!r[di.approved_on]).length;
    if(noap)c.appendChild(el('div','note warn',
      '승인일이 비어 있는 한도 '+noap+'건. 내부한도는 승인기구 의결이 효력 '+
      '요건이므로, 승인 기록 없이는 이 한도로 낸 위반 판정을 결재에 올릴 수 없다.'));
    c.appendChild(el('div','meta',
      '규정 근거가 있는 한도와 내부한도가 근거 구분 컬럼으로 갈린다. '+
      '임계값·산식·근거는 전부 정의 원장 컬럼이다.'));
    c.appendChild(srcMeta(d));
    root.appendChild(c)}
  else root.appendChild(el('div','note bad',
    '한도 정의 원장(lim_limit_definition)이 payload 에 없다. 근거와 승인 기록을 '+
    '표시하지 않는다.'));

  /* --- 잔여한도 --- */
  const byDimH={};
  f.rows.forEach(r=>{const dd=r[i.dimension];
    const cur=byDimH[dd]||{head:0,exp:0,th:0,n:0,max:0};
    cur.head+=headroom(r);cur.exp+=(r[i.exposure]||0);
    cur.th+=(r[i.threshold]||0);cur.n+=1;
    if((r[i.utilisation]||0)>cur.max)cur.max=r[i.utilisation]||0;
    byDimH[dd]=cur});
  root.appendChild(cardOf('차원별 잔여한도',
    simpleTable(['차원','버킷 수','익스포저 합','한도 합','잔여 합','최대 소진율'],
      Object.keys(byDimH).map(k=>[lab(k),byDimH[k].n,byDimH[k].exp,
        byDimH[k].th,byDimH[k].head,pctv(byDimH[k].max,1)]),{numeric:true}),
    '잔여한도는 한도액에서 익스포저를 뺀 값이다. 음수가 위반이다. '+
    '차원마다 버킷 정의가 달라 잔여 합을 차원 간에 더하지 않는다.'));

  root.appendChild(hbars(f.rows.slice()
    .sort((a,b)=>headroom(a)-headroom(b)).slice(0,14)
    .map(r=>({label:lab(r[i.dimension])+' · '+r[i.bucket],
      value:headroom(r),
      sub:'소진 '+pctv(r[i.utilisation],1),
      tone:limitTone(r[i.severity])})),
    {title:'잔여한도 하위 (금액)',src:srcMeta(f)}));

  /* --- 소진율 분포 --- */
  const edges=[0,0.25,0.5,0.75,0.9,1.0];
  const hist=edges.map((lo,k)=>{
    const hi=k+1<edges.length?edges[k+1]:null;
    return {lo:lo,hi:hi,n:f.rows.filter(r=>{
      const u=r[i.utilisation]||0;
      return u>=lo&&(hi==null||u<hi)}).length}});
  root.appendChild(cardOf('소진율 분포',
    bars(hist.map(h=>({label:(h.lo*100).toFixed(0)+(h.hi==null?'% 이상':
        '~'+(h.hi*100).toFixed(0)+'%'),value:h.n,
      tone:h.lo>=1?'bad':(h.lo>=0.9?'warn':undefined)})),
      {fmt:v=>fmtNum(v)}),
    '마지막 칸이 한도를 넘긴 버킷이다. 전량 '+f.total.toLocaleString()+'행 기준.'));

  /* --- 차원별 드릴다운 --- */
  const dims=[...new Set(f.rows.map(r=>r[i.dimension]))];
  const bar=el('div','toolbar');
  const dsel=almSelect(bar,'차원',dims.map(lab),lab(dims[0]));
  const pane=el('div');
  const obIdx=limitObligorIndex();
  const ex=almF('rdm_exposure');
  function drill(){
    pane.innerHTML='';
    const dcode=dims[dims.map(lab).indexOf(dsel.value)];
    const sub=f.rows.filter(r=>r[i.dimension]===dcode)
      .sort((a,b)=>b[i.utilisation]-a[i.utilisation]);
    pane.appendChild(hbars(sub.map(r=>({label:r[i.bucket],
      value:+((r[i.utilisation]||0)*100).toFixed(1),
      sub:'익스포저 '+fmtMoney(r[i.exposure])+' · 잔여 '+fmtMoney(headroom(r)),
      tone:limitTone(r[i.severity])})),
      {title:dsel.value+' 버킷별 소진율 (%)',money:false}));
    pane.appendChild(simpleTable(
      ['버킷','익스포저','한도','잔여','소진율','심각도'],
      sub.map(r=>[r[i.bucket],r[i.exposure],r[i.threshold],headroom(r),
        pctv(r[i.utilisation],1),r[i.severity]]),
      {numeric:true,rowClass:r=>limitTone(r[5])==='good'?null:limitTone(r[5])}));
    /* 상위 버킷의 익스포저 구성. 차원마다 축이 다르므로 원장을 골라 잇는다. */
    if(ex&&sub.length){
      const xi=frameIdx(ex);
      const bsel=almSelect(pane,'버킷',sub.map(r=>r[i.bucket]),sub[0][i.bucket]);
      const cpane=el('div');pane.appendChild(cpane);
      function contrib(){
        cpane.innerHTML='';
        const bkt=bsel.value;
        const keyOf=r=>{
          if(dcode==='asset_class')return r[xi.asset_class];
          if(dcode==='rating')return r[xi.rating];
          const o=obIdx[r[xi.obligor_id]];
          return o?o[dcode]:null};
        const rows=ex.rows.filter(r=>keyOf(r)===bkt);
        if(!rows.length){cpane.appendChild(el('div','note',
          '이 버킷을 채우는 익스포저를 원장에서 찾지 못했다. 축 컬럼이 '+
          '익스포저·차주 원장에 없다.'));return}
        const m=new Map();
        rows.forEach(r=>{const k=r[xi.obligor_id];
          const cur=m.get(k)||{ead:0,n:0,rating:r[xi.rating]};
          cur.ead+=(r[xi.ead]||0);cur.n+=1;m.set(k,cur)});
        const top=[...m.entries()].sort((a,b)=>b[1].ead-a[1].ead).slice(0,10);
        const tot=rows.reduce((a,r)=>a+(r[xi.ead]||0),0);
        cpane.appendChild(hbars(top.map(([k,v])=>({label:k,value:v.ead,
          sub:'등급 '+v.rating+' · '+v.n+'건 · 비중 '+
            pctv(tot?v.ead/tot:0,1)})),
          {title:bkt+' 상위 기여 차주',src:srcMeta(ex,
            '버킷 내 익스포저 '+rows.length.toLocaleString()+'건 · EAD '+
            fmtMoney(tot))}));
      }
      bsel.onchange=contrib;contrib();
    }
  }
  dsel.onchange=drill;drill();
  const dc=cardOf('차원별 드릴다운',null);
  dc.appendChild(bar);dc.appendChild(pane);
  root.appendChild(dc);
  if(dims.indexOf('obligor_id')<0)root.appendChild(el('div','note',
    '동일차주 축은 한도 소진 원장에 없다. 차주 단위 한도는 거액익스포져 화면에서 '+
    '체계별로 본다.'));

  /* --- 한도 시뮬레이션 --- */
  const sim=el('div','card');
  sim.appendChild(el('h3',null,'한도 시뮬레이션'));
  const sb=el('div','toolbar');
  const rows=f.rows.slice().sort((a,b)=>b[i.utilisation]-a[i.utilisation]);
  const ssel=almSelect(sb,'버킷',
    rows.map(r=>lab(r[i.dimension])+' · '+r[i.bucket]),
    lab(rows[0][i.dimension])+' · '+rows[0][i.bucket]);
  const amt=el('input','input');amt.type='number';amt.step='100';amt.value='0';
  amt.style.maxWidth='120px';
  const al=el('label','meta','익스포저 증감 (억원) ');al.appendChild(amt);
  sb.appendChild(al);
  sim.appendChild(sb);
  const sout=el('div');sim.appendChild(sout);
  function simDraw(){
    sout.innerHTML='';
    const k=rows.map(r=>lab(r[i.dimension])+' · '+r[i.bucket]).indexOf(ssel.value);
    const r=rows[k];if(!r)return;
    const add=(parseFloat(amt.value)||0)*EOK;
    const exp2=(r[i.exposure]||0)+add;
    const u2=r[i.threshold]?exp2/r[i.threshold]:0;
    sout.appendChild(simpleTable(['항목','현행','조정 후'],
      [['익스포저',fmtMoney(r[i.exposure]),fmtMoney(exp2)],
       ['한도',fmtMoney(r[i.threshold]),fmtMoney(r[i.threshold])],
       ['잔여',fmtMoney(headroom(r)),fmtMoney((r[i.threshold]||0)-exp2)],
       ['소진율',pctv(r[i.utilisation],1),pctv(u2,1)]]));
    const hits=f.rows.filter(x=>x[i.bucket]===r[i.bucket]&&
      x[i.dimension]!==r[i.dimension]);
    if(hits.length)sout.appendChild(el('div','meta',
      '같은 이름의 버킷이 다른 차원에도 있다. 차원마다 한도가 달라 먼저 걸리는 '+
      '한도가 갈린다.'));
    if(u2>=1)sout.appendChild(el('div','note bad',
      '이 증감이면 해당 한도를 넘긴다.'));
    if(D.sim&&D.sim.single_obligor)sout.appendChild(el('div','note',
      '기본자본 연동 한도(동일차주)는 자본이 바뀌면 한도 자체가 움직인다. '+
      '그 연동은 시뮬레이션 화면에서 본다.'));
  }
  ssel.onchange=simDraw;amt.oninput=simDraw;simDraw();
  root.appendChild(sim);

  /* --- 추이 --- */
  const asofs=Object.keys(RUNS).sort();
  const tc=el('div','card');
  tc.appendChild(el('h3',null,'소진율 추이'));
  if(asofs.length<2){
    tc.appendChild(el('div','note',
      '실린 실행이 기준일 '+asofs.join(' · ')+' 한 건이다. 추이를 그리려면 '+
      '기준일이 둘 이상이어야 하므로 그리지 않는다.'));
  }else{
    const keys=[...new Set(f.rows.map(r=>r[i.limit]+' · '+r[i.bucket]))];
    const tsel=almSelect(tc,'한도 · 버킷',keys,keys[0]);
    const tp=el('div');tc.appendChild(tp);
    function trend(){
      tp.innerHTML='';
      const vals=asofs.map(a=>{
        const ff=RUNS[a].limits_full||RUNS[a].limits;
        const ii=frameIdx(ff);
        const row=ff.rows.find(r=>r[ii.limit]+' · '+r[ii.bucket]===tsel.value);
        return row?+((row[ii.utilisation]||0)*100).toFixed(2):0});
      tp.appendChild(areaLine(vals,{label:'소진율 (%)'}));
      tp.appendChild(el('div','meta','기준일 '+asofs.join(' → ')));
    }
    tsel.onchange=trend;trend();
  }
  root.appendChild(tc);

  /* --- 위반 조치 ---
     조문 번호를 화면에 적지 않는다. 관리체계 요구사항 원장이 조문·요구내용·
     근거를 이미 갖고 있으므로 거기서 읽는다. */
  const gv=almF('kr_irrbb_governance');
  let duty=null;
  if(gv){const gi=frameIdx(gv);
    const row=gv.rows.find(r=>String(r[gi.requirement]).indexOf('한도 초과')>=0);
    if(row)duty={clause:row[gi.clause],text:row[gi.requirement],
      body:row[gi.responsible_body],cite:row[gi.citation]}}
  const act=almF('lim_breach_action');
  const bc=el('div','card');
  bc.appendChild(el('h3',null,'위반 조치'));
  if(duty)bc.appendChild(el('div','meta',
    duty.clause+' '+duty.text+' (책임주체 '+duty.body+'). 근거 '+duty.cite));
  if(act){
    bc.appendChild(table(act));bc.appendChild(srcMeta(act));
  }else{
    bc.appendChild(el('div','note bad',
      '위반 조치 원장(lim_breach_action)이 없다. 위반 '+
      ((bySev.BREACH||0)+(bySev.CRITICAL||0))+'건에 대한 원인·대응책·담당·기한을 '+
      '담는 수기입력 원장이 필요하다. 원장이 만들어지기 전까지 이 화면은 '+
      '조치 상태를 표시하지 않는다.'));
  }
  root.appendChild(bc);

  const c=el('div','card');c.appendChild(el('h3',null,'한도 소진 원장'));
  c.appendChild(table(f,{rowClass:r=>{const t=limitTone(r[i.severity]);
    return t==='good'?null:t}}));
  c.appendChild(srcMeta(f));root.appendChild(c);
}


/* 신규 화면의 한 줄 요약. 요약도 산출물이므로 원장 컬럼에서만 나온다. */
Object.assign(SUMMARIES,{
  '국내 금리리스크':()=>{const f=almF('alm_irrbb_result');if(!f)return null;
    const i=frameIdx(f);
    const fail=f.rows.filter(r=>r[i.outlier_test_pass]===false).length;
    const w=f.rows.reduce((a,r)=>
      Math.abs(r[i.delta_eve])>Math.abs(a[i.delta_eve])?r:a,f.rows[0]);
    return {t:'적용 계정 '+w[i.framework_version]+' ('+w[i.framework_status]+
      ') · 최대 '+w[i.basis]+' 기준 '+w[i.scenario]+' 기본자본 대비 '+
      ((w[i.delta_eve_to_tier1]||0)*100).toFixed(2)+'% · 아웃라이어 미통과 '+
      fail+'/'+f.rows.length,tone:fail?'bad':'good'}},
  '거액 분석':()=>{const L=D.lex;if(!L||!L.frameworks)return null;
    const br=L.frameworks.reduce((a,x)=>a+x.n_breach,0);
    const rp=L.frameworks.reduce((a,x)=>a+x.n_reportable,0);
    return {t:'체계 '+L.frameworks.length+'종 · 포지션 '+
      L.n_positions.toLocaleString()+'행 · 보고대상 '+rp+' · 한도 초과 '+br,
      tone:br?'bad':'good'}},
  '거액 설정':()=>{const f=almF('lex_setting');if(!f)return null;
    const i=frameIdx(f);
    const blank=f.rows.filter(r=>r[i.param_value]==null).length;
    return {t:'설정 '+f.rows.length+'행 · 값 공란 '+blank+
      '행 · 승인 전에는 이 설정으로 낸 산출을 결재에 올릴 수 없다',
      tone:blank?'warn':'good'}},
  'LGD·EAD 실측검증':()=>{const f=almF('crm_lgd_backtest');if(!f)return null;
    const i=frameIdx(f);
    const nf=f.rows.filter(r=>r[i.pass_flag]===false).length;
    const nu=f.rows.filter(r=>r[i.pass_flag]==null).length;
    return {t:'LGD 검증 '+f.rows.length+'구간 · 미통과 '+nf+' · 미판정 '+nu+
      ' · 합격 임계는 내부기준이다',tone:nf?'bad':(nu?'warn':'good')}},
  'PD 추정':()=>{const f=almF('crm_pd_estimate');if(!f)return null;
    const i=frameIdx(f);
    const b=f.rows.filter(r=>r[i.floor_binding]).length;
    return {t:'등급 '+f.rows.length+'건 · 하한이 문 등급 '+b+
      ' · 원시추정에서 최종 적용까지 단계가 원장에 남는다',
      tone:b?'warn':'good'}},
  '행동모형 추정':()=>{const f=almF('alm_behaviour_model');if(!f)return null;
    const i=frameIdx(f);
    const bad=f.rows.filter(r=>r[i.converged]===false).length;
    return {t:'추정 대상 '+f.rows.length+'건 · 수렴 실패 '+bad+
      ' · 수렴하지 못한 포트폴리오에는 행동가정이 적용되지 않는다',
      tone:bad?'warn':'good'}},
  '회수 할인율':()=>{const f=almF('crm_lgd_discount_rate');if(!f)return null;
    const i=frameIdx(f);
    const blank=f.rows.filter(r=>r[i.discount_rate]==null).length;
    const prov=f.rows.filter(r=>r[i.discount_rate]!=null&&
      String(r[i.approved_by]||'').indexOf('미승인')>=0).length;
    const e=almF('crm_capm_estimate');
    const ke=(e&&e.rows.length)?String(e.rows[0][frameIdx(e).ke_status]):'-';
    return {t:'할인율 '+f.rows.length+'행 · 값 공란 '+blank+'행 · 잠정 준용 '+
      prov+'행 · 자기자본비용 '+ke,
      tone:(blank||prov)?'warn':'good'}},
  'BEEL·PLGD':()=>{const f=almF('crm_beel_curve');if(!f)return null;
    const i=frameIdx(f);
    const den=f.rows.filter(r=>r[i.is_applied_denominator]);
    const brk=[...new Set(f.rows.filter(r=>r[i.is_applied_denominator]&&
      r[i.monotonicity_verdict]==='단조증가아님').map(r=>r[i.segment]))].length;
    const p=almF('crm_plgd');
    const open=p?p.rows.filter(r=>r[frameIdx(p).plgd]==null).length:0;
    return {t:'곡선 '+f.rows.length+'행 (적용 분모 '+
      String(den.length?den[0][i.beel_denominator]:'-')+') · 우상향 깨진 '+
      '세그먼트 '+brk+' · PLGD 미산출 '+open+'행',
      tone:(brk||open)?'warn':'good'}},
});

function scenarioScreen(root){
  root.appendChild(el('p','lead',
    '위기상황 시나리오 정의. 충격 축 14종의 단위충격, 시나리오별 분기 심도 '+
    '경로, 신규 시나리오 제안.'));
  /* 분기 심도 경로 (추적표에서 그대로) */
  const T=traceRows();
  if(T){
    const {f,i}=T;
    const scenarios=[...new Set(f.rows.map(r=>r[i.scenario]))];
    const quarters=[...new Set(f.rows.map(r=>r[i.quarter]))];
    const series=scenarios.map(sc=>({name:sc,
      values:quarters.map(q=>{const r=f.rows.find(x=>x[i.scenario]===sc&&
        x[i.quarter]===q&&/심도/.test(x[i.step]));return r?r[i.value]:null})}));
    const c=el('div','card');
    c.appendChild(el('h3',null,'시나리오별 분기 심도 경로 (정점까지 선형 상승)'));
    c.appendChild(multiLine(series,quarters,null));
    c.appendChild(srcMeta(f));
    root.appendChild(c);
  }
  scenarioSettings(root);
  /* 신규 시나리오 제안 */
  const c2=el('div','card set-newscen');
  c2.appendChild(el('h3',null,'신규 시나리오 제안'));
  const bar=el('div','toolbar');
  const nm=el('input','input');nm.type='text';nm.placeholder='시나리오 이름 (예: 부동산 급락)';
  const sv=el('input','input');sv.type='text';sv.placeholder='정점 심도 (예: 1.5)';
  sv.style.maxWidth='140px';
  bar.appendChild(nm);bar.appendChild(sv);c2.appendChild(bar);
  const gen=el('button','btn primary','시나리오 제안 생성');c2.appendChild(gen);
  const err=el('div','note bad');err.hidden=true;c2.appendChild(err);
  const out=el('pre','mono');out.style.whiteSpace='pre-wrap';c2.appendChild(out);
  gen.onclick=()=>{
    err.hidden=true;out.textContent='';
    if(STATE.killed&&STATE.killScope==='전사'){
      err.textContent='비상정지 중. 제안을 만들지 않는다.';err.hidden=false;return}
    if(!nm.value.trim()){err.textContent='시나리오 이름이 비어 있다.';err.hidden=false;return}
    if(!/^\d+(\.\d+)?$/.test(sv.value.trim())){
      err.textContent='정점 심도는 숫자다.';err.hidden=false;return}
    out.textContent=JSON.stringify({
      proposal:'신규 위기상황 시나리오',name:nm.value.trim(),
      peak_severity:parseFloat(sv.value),
      apply_path:'risk_lib/stress/scenario.py · axes.py',
      procedure:['시나리오 정의 코드 반영','파이프라인 재실행',
                 '자체검증(2선)','독립검증(3선) 재요청','게이트 통과 후 결재'],
      note:'심도 경로·충격 축 배수는 기존 체계를 따른다.'},null,2);
  };
  root.appendChild(c2);
}

/* ---- 산출 방법론 설정. 어느 방법으로 산출할지의 정책 ----
   방법 선택은 산출값을 바꾼다. 그래서 화면은 **제안서만** 만들고, 적용은
   코드 반영 + 파이프라인 재실행 + 검증 두 층이다. 다만 각 방법의 결과가
   이미 원장에 다 들어 있으므로(LTA/MBA/fallback · SA/ERBA/IRBA), 방법을
   바꿨을 때 값이 얼마나 달라지는지는 **재계산 없이 즉시** 보여줄 수 있다. */
/* ---- 모형 거버넌스 화면군 ----
   모형은 신용에만 있지 않다. 원장이 crm_ 스키마에 산다는 것과 그 모형이
   신용 모형이라는 것은 다른 말이다(사용자 지적). 도메인 축으로 다시 세운다. */

function modelInventory(root){
  root.appendChild(el('p','lead',
    '전 도메인 모형 인벤토리다. 신용(PD·LGD·ECL·빈티지)뿐 아니라 시장(VaR·XVA)· '+
    'ALM(IRRBB·LCR/NSFR)·위기상황·기후·전사(RAF)까지. 등급(Tier)은 모형 중요도이며 '+
    '검증 주기를 정한다. 기한이 지난 모형의 산출값은 사용 전 재검증 대상이다.'));
  const f=D.data['crm_model'];
  if(!f){root.appendChild(el('div','note','모형 원장이 없다'));return}
  const i=frameIdx(f);
  const g=el('div','grid');
  const byDom={},byTier={};
  f.rows.forEach(r=>{byDom[r[i.domain]]=(byDom[r[i.domain]]||0)+1;
    byTier['Tier '+r[i.tier]]=(byTier['Tier '+r[i.tier]]||0)+1});
  const over=f.rows.filter(r=>r[i.is_overdue]).length;
  const uat=f.rows.filter(r=>r[i.status]!=='PROD').length;
  [['등록 모형',f.total,''],['도메인',Object.keys(byDom).length,''],
   ['검증 기한 초과',over,over?'bad':'good'],
   ['운영 전(UAT 등)',uat,uat?'warn':'good']].forEach(([k,v,t])=>{
    const c=el('div','card kpi');
    c.appendChild(el('div','lab',k));c.appendChild(el('div','val '+t,String(v)));
    g.appendChild(c)});
  root.appendChild(g);

  const two=el('div');two.style.cssText=
    'display:grid;gap:12px;grid-template-columns:1fr 1fr';
  two.appendChild(hbars(Object.entries(byDom).map(([k,v])=>({label:k,value:v}))
    .sort((a,b)=>b.value-a.value),{title:'도메인별 모형 수',money:false}));
  two.appendChild(hbars(Object.entries(byTier).map(([k,v])=>({label:k,value:v}))
    .sort((a,b)=>a.label.localeCompare(b.label)),
    {title:'등급(Tier)별 모형 수 (1이 가장 중요)',money:false}));
  root.appendChild(two);

  const bar=el('div','toolbar');
  const dsel=el('select','sel');
  ['전체 도메인'].concat(Object.keys(byDom).sort()).forEach(d=>{
    const o=el('option');o.value=d==='전체 도메인'?'':d;o.textContent=d;
    dsel.appendChild(o)});
  bar.appendChild(dsel);root.appendChild(bar);
  const pane=el('div','card');root.appendChild(pane);
  function draw(){
    pane.innerHTML='';
    const rows=f.rows.filter(r=>!dsel.value||r[i.domain]===dsel.value);
    pane.appendChild(rawEl('h3',null,TP('모형',TC(rows.length,'건'))));
    pane.appendChild(table({table:'crm_model',
      columns:['model_id','model_name','domain','tier','status','owner','purpose'],
      labels:['모형','모형명','도메인','등급','상태','소유부서','목적'],
      rows:rows.map(r=>[r[i.model_id],r[i.model_name],r[i.domain],r[i.tier],
        r[i.status],r[i.owner],r[i.purpose]]),
      total:rows.length,shown:rows.length},{numeric:false}));
    pane.appendChild(srcMeta(f));
  }
  dsel.onchange=draw;draw();
}

function modelValidationSchedule(root){
  root.appendChild(el('p','lead',
    '검증 주기는 등급이 정한다. Tier 1 연 1회, Tier 2 2년, Tier 3 3년. '+
    '기한이 지난 모형의 산출은 재검증 전까지 쓸 수 없다.'));
  const f=D.data['crm_model'];
  if(!f)return;
  const i=frameIdx(f);
  const rows=f.rows.slice().sort((a,b)=>
    String(a[i.next_due]).localeCompare(String(b[i.next_due])));

  /* 기한까지 남은 일수. 경과분은 원장의 days_overdue 를 그대로 쓴다.
     화면이 날짜를 다시 빼면 원장과 어긋날 수 있다. */
  const base=Date.parse(D.meta.asof+'T00:00:00Z');
  const rem=r=>r[i.is_overdue]?-(r[i.days_overdue]||0)
    :Math.round((Date.parse(r[i.next_due]+'T00:00:00Z')-base)/86400000);
  const two=el('div');two.style.cssText=
    'display:grid;gap:12px;grid-template-columns:1fr 1fr';
  two.appendChild(hbars(rows.map(r=>({label:r[i.model_id],
    value:Math.max(rem(r),0),
    sub:r[i.is_overdue]?`기한 초과 ${r[i.days_overdue]}일`
      :`${r[i.next_due]} · Tier ${r[i.tier]}`,
    tone:r[i.is_overdue]?'bad':rem(r)<=90?'warn':undefined})),
    {title:'차기 검증까지 남은 일수 (90일 이내는 착수 대상)',money:false,
     src:srcMeta(f)}));
  const byDom={};rows.forEach(r=>{const d=r[i.domain];
    if(byDom[d]==null||rem(r)<byDom[d])byDom[d]=rem(r)});
  two.appendChild(hbars(Object.entries(byDom)
    .sort((a,b)=>a[1]-b[1])
    .map(([k,v])=>({label:k,value:Math.max(v,0),
      sub:v<0?`경과 ${-v}일`:`${v}일 남음`,
      tone:v<0?'bad':v<=90?'warn':undefined})),
    {title:'도메인별 가장 임박한 기한',money:false}));
  root.appendChild(two);

  const c=el('div','card');
  c.appendChild(el('h3',null,'검증 일정 (차기 기한 순)'));
  const w=el('div','tw'),t=el('table'),th=el('thead'),tr=el('tr');
  ['모형','도메인','등급','최근 검증','차기 기한','상태','소유부서']
    .forEach(x=>tr.appendChild(el('th',null,x)));
  th.appendChild(tr);t.appendChild(th);
  const tb=el('tbody');
  rows.forEach(r=>{
    const x=el('tr');
    x.appendChild(el('td','mono',r[i.model_id]));
    x.appendChild(el('td',null,r[i.domain]));
    x.appendChild(el('td','num',String(r[i.tier])));
    x.appendChild(el('td',null,String(r[i.last_validation]||'-')));
    x.appendChild(el('td',null,String(r[i.next_due]||'-')));
    const td=el('td');
    td.appendChild(r[i.is_overdue]
      ? pill(`기한 초과 ${r[i.days_overdue]}일`,'bad')
      : pill('기한 내','good'));
    x.appendChild(td);
    x.appendChild(rawEl('td','meta',r[i.owner]));
    tb.appendChild(x)});
  t.appendChild(tb);w.appendChild(t);c.appendChild(w);
  c.appendChild(srcMeta(f));
  root.appendChild(c);

  const c2=el('div','card');
  c2.appendChild(el('h3',null,'의존 관계와 알려진 한계'));
  c2.appendChild(el('div','meta',
    '상류 모형이 바뀌면 하류도 재검증 대상이다. 알려진 한계는 모형 원장에 '+
    '기재된 값이다.'));
  c2.appendChild(table({table:'crm_model',
    columns:['model_id','dependencies','known_limitations'],
    labels:['모형','의존 모형·데이터','알려진 한계'],
    rows:f.rows.map(r=>[r[i.model_id],r[i.dependencies],r[i.known_limitations]]),
    total:f.total,shown:f.rows.length},{numeric:false}));
  root.appendChild(c2);
}

function modelPerformance(root){
  root.appendChild(el('p','lead',
    '신용 모형의 변별력(Gini·KS)과 안정성(PSI). Gini 는 높을수록, PSI 는 낮을수록 '+
    '좋다. PSI 0.25 를 넘으면 모집단이 개발 시점과 달라졌다는 신호다.'));
  const f=D.data['crm_performance'];
  if(!f){root.appendChild(el('div','note','성능 원장이 없다'));return}
  const i=frameIdx(f);
  root.appendChild(hbars(f.rows.map(r=>({
    label:`${r[i.model_id]} · ${r[i.segment]}`, value:(r[i.gini]||0)*100,
    sub:`KS ${((r[i.ks]||0)*100).toFixed(1)} · PSI ${(r[i.psi]||0).toFixed(3)}`,
    tone:(r[i.gini]||0)<0.4?'warn':undefined})),
    {title:'변별력 Gini (%) (양호 기준 40%)',money:false,src:srcMeta(f)}));
  const c=el('div','card');
  c.appendChild(el('h3',null,'성능 지표 원장'));
  c.appendChild(table(f));root.appendChild(c);
}

function modelCalibration(root){
  root.appendChild(el('p','lead',
    '등급별 예측 PD 와 실측 부도율의 대조다. O/E 비율이 1 에서 멀수록 보정이 '+
    '어긋난 것이며, 허용범위 밖 등급은 재보정 대상이다.'));
  const f=D.data['crm_pd_calibration'];
  if(!f){root.appendChild(el('div','note','보정 원장이 없다'));return}
  const i=frameIdx(f);
  const bad=f.rows.filter(r=>!r[i.within_tolerance]).length;
  const c0=el('div','card');
  c0.appendChild(el('h3',null,'보정 상태'));
  c0.appendChild(meter('허용범위 내 등급',f.rows.length-bad,f.rows.length,
    bad?'warn':undefined));
  c0.appendChild(el('div','meta',
    `허용범위 밖 ${bad}건 (예측 PD 와 실측 부도율의 괴리가 기준을 넘은 등급)`));
  root.appendChild(c0);
  root.appendChild(hbars(f.rows.slice(0,12).map(r=>({
    label:`${r[i.segment]} · ${r[i.grade]}`, value:r[i.oe_ratio]||0,
    sub:`예측 ${((r[i.pd_predicted]||0)*100).toFixed(2)}% · 실측 ${((r[i.dr_observed]||0)*100).toFixed(2)}%`,
    tone:r[i.within_tolerance]?undefined:'bad'})),
    {title:'등급별 O/E 비율 (1.0 이 완전 일치)',money:false,src:srcMeta(f)}));
  const c=el('div','card');
  c.appendChild(el('h3',null,'보정 원장'));
  c.appendChild(table(f));root.appendChild(c);
}

function modelRiskGovernance(root){
  root.appendChild(el('p','lead',
    '모형리스크 관리. 등급별 거버넌스 요구, 운영 상태, 검증 기한.'));
  const f=D.data['crm_model'];
  if(!f)return;
  const i=frameIdx(f);
  const TIER_REQ={1:['연 1회 독립검증','상시 성능 모니터링','이사회 보고 대상',
                     '챌린저 모형 유지'],
                  2:['2년 주기 독립검증','반기 성능 모니터링','경영진 보고'],
                  3:['3년 주기 독립검증','연 1회 성능 점검']};
  const CYCLE={1:12,2:24,3:36};
  const two=el('div');two.style.cssText=
    'display:grid;gap:12px;grid-template-columns:1fr 1fr';
  two.appendChild(hbars([1,2,3].map(t=>({label:`Tier ${t}`,
    value:f.rows.filter(r=>r[i.tier]===t).length,
    sub:`검증 주기 ${CYCLE[t]}개월`,
    tone:t===1?'warn':undefined})),
    {title:'등급별 모형 수와 검증 주기',money:false,
     src:srcMeta(f)}));
  const own={};f.rows.forEach(r=>{own[r[i.owner]]=(own[r[i.owner]]||0)+1});
  two.appendChild(hbars(Object.entries(own)
    .sort((a,b)=>b[1]-a[1]).map(([k,v])=>({label:k,value:v})),
    {title:'소유부서별 모형 수',money:false}));
  root.appendChild(two);

  const c=el('div','card');
  c.appendChild(el('h3',null,'등급별 거버넌스 요구 (SR 11-7 계열)'));
  const rows=[];
  [1,2,3].forEach(t=>{
    const ms=f.rows.filter(r=>r[i.tier]===t);
    rows.push([`Tier ${t}`, ms.length,
      ms.map(r=>r[i.model_id]).join(' · ')||'-',
      TIER_REQ[t].join(' · ')]);
  });
  c.appendChild(table({columns:['등급','모형 수','해당 모형','거버넌스 요구'],
    rows, total:3, shown:3},{numeric:false}));
  root.appendChild(c);

  const c2=el('div','card');
  c2.appendChild(el('h3',null,'운영 상태 분포'));
  const st={};f.rows.forEach(r=>{st[r[i.status]]=(st[r[i.status]]||0)+1});
  c2.appendChild(dotlist(Object.entries(st).map(([k,v])=>({
    label:`${k} (${v}건)`, right:k==='PROD'?'운영 중':'운영 전',
    tone:k==='PROD'?'good':'warn'}))));
  c2.appendChild(el('div','note',
    '운영 전(UAT·개발) 모형의 산출은 공표·제출에 쓰지 않는다. 상태는 모형 '+
    '원장 값이다.'));
  root.appendChild(c2);
}

function methodology(root){
  root.appendChild(el('p','lead',
    '집합투자증권(CRE60)·유동화(CRE40) 는 여러 산출 방법이 규정에 함께 있고, '+
    '어느 것을 쓸지는 정보 가용성과 정책이 정한다. 원장에 세 방법 결과가 모두 '+
    '들어 있으므로 방법을 바꿨을 때의 차이를 재계산 없이 본다. 화면은 값을 '+
    '바꾸지 않고, 적용은 코드 반영 + 재실행 + 2선·3선 검증을 거친다.'));

  /* --- 집합투자증권 --- */
  const fr=D.data['rwa_fund_result'];
  if(fr){
    const i=frameIdx(fr);
    const c=el('div','card set-method-fund');
    c.appendChild(el('h3',null,'집합투자증권 (LTA · MBA · Fallback, CRE60)'));
    const bar=el('div','toolbar');
    const sel=el('select','sel');
    [['as_is','원장 채택값 (정보 가용성 기준)'],
     ['look_through','전건 LTA 강제 (CRE60.5)'],
     ['mandate','전건 MBA 강제 (CRE60.7)'],
     ['fallback','전건 Fallback 1250% (CRE60.9)']].forEach(([v,t])=>{
      const o=el('option');o.value=v;o.textContent=t;sel.appendChild(o)});
    bar.appendChild(sel);c.appendChild(bar);
    const pane=el('div');c.appendChild(pane);
    const COL={look_through:'rwa_lta',mandate:'rwa_mba',fallback:'rwa_fallback'};
    function draw(){
      pane.innerHTML='';
      const base=fr.rows.reduce((a,r)=>a+(r[i.adopted_rwa]||0),0);
      const pick=sel.value;
      const alt=fr.rows.reduce((a,r)=>a+(pick==='as_is'
        ? (r[i.adopted_rwa]||0) : (r[i[COL[pick]]]||0)),0);
      const g=el('div','grid');
      [['원장 채택 RWA',base,''],
       ['선택 방법 RWA',alt,alt>base?'bad':alt<base?'good':''],
       ['차이',alt-base,Math.abs(alt-base)<1?'':'warn']].forEach(([k,v,t])=>{
        const cc=el('div','card kpi');
        cc.appendChild(el('div','lab',k));
        cc.appendChild(el('div','val '+t,fmtMoney(v)));
        cc.appendChild(el('div','sub',base?((v/base-1)*100).toFixed(1)+'% (채택 대비)':''));
        g.appendChild(cc)});
      pane.appendChild(g);
      pane.appendChild(table({table:'rwa_fund_result',
        columns:['fund_id','fund_name','adopted_method','rw_lta','rw_mba','rw_fallback','adopted_rwa'],
        labels:['펀드','펀드명','채택 방법','LTA RW','MBA RW','Fallback RW','채택 RWA'],
        rows:fr.rows.map(r=>[r[i.fund_id],r[i.fund_name],r[i.adopted_method],
          r[i.rw_lta],r[i.rw_mba],r[i.rw_fallback],r[i.adopted_rwa]]),
        total:fr.total,shown:fr.rows.length}));
      pane.appendChild(el('div','meta',
        'LTA 는 편입자산을 직접 보유한 것처럼, MBA 는 운용지침 한도까지 투자했다고 '+
        '가정한다. 정보가 부족하면 Fallback 1250%.'));
    }
    sel.onchange=draw;draw();
    root.appendChild(c);
  }

  /* --- 유동화 --- */
  const sr=D.data['rwa_sec_result'];
  if(sr){
    const i=frameIdx(sr);
    const c=el('div','card set-method-sec');
    c.appendChild(el('h3',null,'유동화 (SEC-IRBA · ERBA · SA, CRE40.41 계층)'));
    const bar=el('div','toolbar');
    const sel=el('select','sel');
    [['as_is','원장 채택값 (CRE40.41 계층)'],
     ['irba','전건 SEC-IRBA (가능한 건만)'],
     ['erba','전건 SEC-ERBA (등급 있는 건만)'],
     ['sa','전건 SEC-SA']].forEach(([v,t])=>{
      const o=el('option');o.value=v;o.textContent=t;sel.appendChild(o)});
    bar.appendChild(sel);c.appendChild(bar);
    const pane=el('div');c.appendChild(pane);
    const COL={irba:'rwa_irba',erba:'rwa_erba',sa:'rwa_sa'};
    function draw2(){
      pane.innerHTML='';
      const base=sr.rows.reduce((a,r)=>a+(r[i.adopted_rwa]||0),0);
      let alt=0,skipped=0;
      sr.rows.forEach(r=>{
        if(sel.value==='as_is'){alt+=r[i.adopted_rwa]||0;return}
        const v=r[i[COL[sel.value]]];
        /* 산출 불가(등급 없음 등)를 0으로 채우지 않는다. 채우면 자본이
           사라지고 그 사실이 화면 어디에도 안 남는다. */
        if(v==null||Number.isNaN(v)){skipped++;alt+=r[i.adopted_rwa]||0}
        else alt+=v;
      });
      const g=el('div','grid');
      [['원장 채택 RWA',base,''],['선택 방법 RWA',alt,alt>base?'bad':alt<base?'good':''],
       ['차이',alt-base,Math.abs(alt-base)<1?'':'warn']].forEach(([k,v,t])=>{
        const cc=el('div','card kpi');
        cc.appendChild(el('div','lab',k));
        cc.appendChild(el('div','val '+t,fmtMoney(v)));
        g.appendChild(cc)});
      pane.appendChild(g);
      if(skipped)pane.appendChild(el('div','note',
        `산출 불가 ${skipped}건은 채택값을 유지했다.`));
      pane.appendChild(table({table:'rwa_sec_result',
        columns:['tranche_id','tranche_name','adopted_method','rw_sa','rw_erba','rw_irba','adopted_rw','floor_applied'],
        labels:['트렌치','트렌치명','채택','SA RW','ERBA RW','IRBA RW','채택 RW','하한 적용'],
        rows:sr.rows.map(r=>[r[i.tranche_id],r[i.tranche_name],r[i.adopted_method],
          r[i.rw_sa],r[i.rw_erba],r[i.rw_irba],r[i.adopted_rw],r[i.floor_applied]]),
        total:sr.total,shown:sr.rows.length}));
      pane.appendChild(el('div','meta',
        '계층은 IRBA → ERBA → SA 순이다(CRE40.41). 위험가중 하한은 15%, '+
        'STC 선순위는 10%(CRE44.5).'));
    }
    sel.onchange=draw2;draw2();
    root.appendChild(c);
  }

  /* --- 제안 --- */
  const c3=el('div','card set-method-proposal');
  c3.appendChild(el('h3',null,'방법론 변경 제안'));
  const bar=el('div','toolbar');
  const dom=el('select','sel');
  ['집합투자증권','유동화','파생(SA-CCR)'].forEach(x=>{
    const o=el('option');o.value=x;o.textContent=x;dom.appendChild(o)});
  const why=el('input','input');why.type='text';
  why.placeholder='변경 사유 (필수, 정보 가용성 변화·감독 지적·정책 결정 등)';
  bar.appendChild(dom);bar.appendChild(why);c3.appendChild(bar);
  const gen=el('button','btn primary','제안 생성');c3.appendChild(gen);
  const err=el('div','note bad');err.hidden=true;c3.appendChild(err);
  const out=el('pre','mono');out.style.whiteSpace='pre-wrap';c3.appendChild(out);
  gen.onclick=()=>{
    err.hidden=true;out.textContent='';
    if(STATE.killed&&STATE.killScope==='전사'){
      err.textContent='비상정지 중. 제안을 만들지 않는다.';err.hidden=false;return}
    if(!why.value.trim()){err.textContent='사유는 필수다.';err.hidden=false;return}
    const path={'집합투자증권':'risk_lib/datamodel/funds.py (approach 결정 규칙)',
      '유동화':'risk_lib/datamodel/securitisation.py (CRE40.41 계층)',
      '파생(SA-CCR)':'risk_lib/ccr.py (SF·α·담보 인식)'}[dom.value];
    out.textContent=JSON.stringify({
      proposal:'산출 방법론 변경',domain:dom.value,reason:why.value.trim(),
      asof:D.meta.asof,run_id:D.meta.run_id,apply_path:path,
      procedure:['방법론 코드 반영','파이프라인 재실행','자체검증(2선) FAIL 0',
                 '독립검증(3선) 재요청 (방법론 변경은 지문을 바꾼다)',
                 '게이트 통과 후 결재'],
      note:'화면은 원장에 이미 있는 대안 값을 보여줄 뿐 산출을 바꾸지 않는다.'},null,2);
  };
  root.appendChild(c3);
}

function settings(root){
  root.appendChild(el('p','lead',
    '표시명·기준일 전환은 세션 안에서 즉시 적용된다(산출값 무관). 서식번호 '+
    '매핑과 시나리오 파라미터는 산출물의 정체를 바꾸므로 화면에서 적용하지 '+
    '않는다. 변경 제안서를 만들고, 적용은 코드 반영 + 파이프라인 재실행 + '+
    '검증 두 층(자체검증·독립검증)을 다시 거친다.'));
  runRegistry(root);
  labelSettings(root);
  formMapSettings(root);
  /* 시나리오 설정은 별도 화면(위기상황 > 시나리오 설정)으로 옮겼다 */
}

/* ---- 범위형 비상정지 (PLT-016) (부문 단위로 조회를 세운다) ---- */
function killedFor(domain){
  return STATE.killed&&(STATE.killScope==='전사'||domain===STATE.killScope);
}

/* ---- 도메인 세부화면 (원장 나열 + 부문 차트. 전 값이 payload 원장이다) ---- */
/* ---- 코드 마스터 정렬. rdm_code_master 가 정본이다 ----
   등급·건전성 분류는 선언 순서가 업무 순서다. 가나다순은 틀린 정렬이다. */
let _CODE_ORDER=null;
function codeRank(tableName,col){
  if(!_CODE_ORDER){
    _CODE_ORDER={};
    const f=D.data['rdm_code_master'];
    if(f){const i=frameIdx(f);
      f.rows.forEach(r=>{
        (_CODE_ORDER[r[i.code_set]]=_CODE_ORDER[r[i.code_set]]||{})
          [r[i.code]]=r[i.sort_order]})}
  }
  return _CODE_ORDER[tableName+'.'+col]||_CODE_ORDER[col]||null;
}
function sortByCode(values,tableName,col){
  const rank=codeRank(tableName,col);
  const out=[...values];
  if(rank)out.sort((a,b)=>(rank[a]??1e9)-(rank[b]??1e9));
  return out;
}

/* 전이행렬 피봇 (세그먼트 선택, 행·열은 코드 마스터 순서, 대각선 강조) */
function migrationPivot(root){
  const f=D.data['crm_rating_migration'];
  if(!f)return;
  const i=frameIdx(f);
  const c=el('div','card');
  c.appendChild(el('h3',null,'등급 전이행렬 (피봇)'));
  const bar=el('div','toolbar');
  const sel=el('select','sel');
  sortByCode([...new Set(f.rows.map(r=>r[i.segment]))],
             'crm_rating_migration','segment')
    .forEach(sg=>{const o=el('option');o.value=sg;
      o.textContent='세그먼트 · '+sg;sel.appendChild(o)});
  bar.appendChild(sel);c.appendChild(bar);
  const pane=el('div');c.appendChild(pane);
  function draw(){
    pane.innerHTML='';
    const rows=f.rows.filter(r=>r[i.segment]===sel.value);
    const grades=sortByCode(
      [...new Set(rows.flatMap(r=>[r[i.from_grade],r[i.to_grade]]))],
      'crm_rating_migration','from_grade');
    const cell={};let mx=0;
    rows.forEach(r=>{
      const k=r[i.from_grade]+'>'+r[i.to_grade];
      cell[k]=(cell[k]||0)+r[i.share];mx=Math.max(mx,cell[k])});
    const w=el('div','tw'),t=el('table'),th=el('thead'),tr=el('tr');
    tr.appendChild(el('th',null,'시작 \\ 도착'));
    grades.forEach(g=>tr.appendChild(el('th','num',g)));
    th.appendChild(tr);t.appendChild(th);
    const tb=el('tbody');
    grades.forEach(fr=>{
      const x=el('tr');
      const h=el('td',null,fr);h.style.fontWeight='700';x.appendChild(h);
      grades.forEach(to=>{
        const v=cell[fr+'>'+to];
        const td=el('td','num',v==null?'-':(v*100).toFixed(1)+'%');
        if(v!=null){
          td.style.background=`rgba(66,169,255,${(0.06+0.5*v/mx).toFixed(3)})`;
          td.title=`${fr} → ${to} · ${(v*100).toFixed(2)}%`;
        }
        if(fr===to)td.style.boxShadow='inset 0 0 0 1px var(--lineage)';
        x.appendChild(td)});
      tb.appendChild(x)});
    t.appendChild(tb);w.appendChild(t);pane.appendChild(w);
    pane.appendChild(el('div','meta',
      `세그먼트 ${sel.value} · 전이 ${rows.length}건. 행·열은 코드 마스터 `+
      `순서(등급 사다리), 대각선 테두리는 등급 유지`));
    pane.appendChild(srcMeta(f));
  }
  sel.onchange=draw;draw();
  root.appendChild(c);
}

function autoCharts(root,specs){
  (specs||[]).forEach(([title,tab,labCols,valCol,opt])=>{
    const f=D.data[tab];if(!f)return;
    const i=frameIdx(f);
    const g=new Map();
    f.rows.forEach(r=>{
      const k=labCols.map(c=>r[i[c]]).join(' · ');
      g.set(k,(g.get(k)||0)+(valCol?(r[i[valCol]]||0):1))});
    const items=[...g.entries()].map(([k,v])=>({label:k,value:v}))
      .sort((a,b)=>b.value-a.value).slice(0,10);
    root.appendChild(hbars(items,{title,money:opt?.money!==false,
      src:srcMeta(f)}))});
}
function screenOf(defs){
  return root=>{
    root.appendChild(el('p','lead',defs.lead));
    if(defs.charts)defs.charts(root);
    autoCharts(root,defs.autochart);
    (defs.forms||[]).forEach(fid=>{
      const f=D.forms.find(x=>x.form_id===fid);
      if(f){const pane=el('div');renderForm(pane,f);root.appendChild(pane)}
    });
    defs.tables.forEach(([title,key])=>{
      const f=D.data[key];
      const c=el('div','card');c.appendChild(el('h3',null,title));
      if(f){c.appendChild(table(f));c.appendChild(srcMeta(f))}
      else c.appendChild(el('div','note','원장 '+key+' 이 payload에 없다'));
      root.appendChild(c)});
  };
}

function exceptionQueue(root){
  const f=D.data['gov_exception_action'];
  if(!f)return;
  const i=frameIdx(f);
  const g=groupSum(f,'status','due_days');
  root.appendChild(hbars(g.map(x=>({label:'상태 '+x.key,value:x.n,
    sub:null,tone:x.key==='접수'?'warn':x.key==='조치중'?'bad':undefined})),
    {title:'예외 상태 분포 (자동상계 금지, 종결은 사람 승인 후)',
     money:false,src:srcMeta(f)}));
}

function commercial(root){
  const C=D.commercial;
  root.appendChild(el('p','lead',
    '사업성 산출. 규제 산출물이 아니다. 제출 지문·독립검증 대상에 넣지 않으며 '+
    '모든 금액은 가정 원장에서 계산으로만 나온다. 전부 합성 가정이며 실제 '+
    '견적은 계약 가정으로 교체된다.'));
  const dc=C.double_counting;
  const note=el('div','note'+(dc.length?' bad':''));
  note.textContent=dc.length
    ? 'ROI 이중계상 '+dc.length+'건 ('+dc.join(' · ')+')'
    : 'ROI 이중계상 검증 통과. 편익 항목마다 출처 가정이 하나씩이다 (COM-007)';
  root.appendChild(note);
  [['패키지 견적 (COM-002·003·004·005)','quotes'],
   ['ROI 편익 (항목별 1회 계상, COM-007)','roi'],
   ['가정 원장 (COM-001·006)','assumptions'],
   ['GTM Funnel 단계 정의 (COM-008)','funnel']].forEach(([t,k])=>{
    const c=el('div','card');c.appendChild(el('h3',null,t));
    c.appendChild(table(C[k]));root.appendChild(c)});
}

const DETAIL_SCREENS=[
  ['원천·계약','A · 원천 인터페이스 (계약·스냅샷·표준 매핑)',screenOf({
    lead:'원천 시스템과의 인터페이스 계약, 수신 스냅샷, 표준코드 매핑을 원장으로 통제한다. 계약 위반은 적재 전에 차단된다.',
    autochart:[['원천 시스템별 수신 행수','rdm_source_contract',
                ['source_system'],'actual_rows',{money:false}]],
    tables:[['원천 인터페이스 계약','rdm_source_contract'],
            ['수신 스냅샷 원장','rdm_snapshot'],
            ['표준코드 매핑','rdm_canonical_map']]})],
  ['DQ·대사','A · 데이터품질 (규칙·판정·대사)',screenOf({
    lead:'DQ 규칙과 판정, 원천–산출 대사를 한 화면에서 본다. 실패는 예외·조치 큐로 넘어간다.',
    autochart:[['판정 심각도별 건수','rdm_dq_result',['severity'],null,{money:false}],
               ['DQ 규칙 유형 분포','rdm_dq_rule',['rule_type'],null,{money:false}]],
    tables:[['DQ 규칙 원장','rdm_dq_rule'],['DQ 판정 결과','rdm_dq_result'],
            ['집계·대사','rdm_reconciliation']]})],
  ['예외·조치','A · 예외·조치 워크플로 (접수→조치→종결)',screenOf({
    lead:'대사·DQ·IPV 세 원장의 미해소 예외가 표준 조치·담당·기한이 붙은 하나의 큐로 모인다. 종결은 사람 승인 후에만 한다.',
    charts:exceptionQueue,
    tables:[['예외·조치 큐','gov_exception_action'],
            ['경보·조치 정책 바인딩','gov_alert_policy']]})],
  ['담보·보증','A · 담보·보증·재무 원장',screenOf({
    lead:'담보·보증·차주 재무 원장. 신용위험경감과 LGD의 원천이다.',
    autochart:[['담보유형별 평가액','rdm_collateral',['collateral_type'],'market_value'],
               ['보증유형별 보증액','rdm_guarantee',['protection_type'],'guaranteed_amount']],
    tables:[['담보 원장','rdm_collateral'],['보증 원장','rdm_guarantee'],
            ['차주 재무','rdm_obligor_financial']]})],
  ['등급 전이','MDL · 등급 전이행렬 (세그먼트별 피봇)',screenOf({
    lead:'등급 이동행렬과 그 재료가 되는 원장들이다. 전이행렬 피봇의 행·열은 코드 마스터(등급 사다리) 순서다. 모형 인벤토리는 모형 > 모형 인벤토리 화면에 있다.',
    charts:migrationPivot,
    tables:[['PD 보정','crm_pd_calibration'],
            ['모형 성능','crm_performance'],['등급 이동행렬','crm_rating_migration'],
            ['LGD 구성요소','crm_lgd_component']]})],
  ['조기경보','B · 조기경보(EWS) (신호·단계·조치)',screenOf({
    lead:'차주 단위 조기경보 신호와 단계, 권고 조치. 에이전트가 순위를 제안하고 사람이 결정한다.',
    charts:root=>{if(DOMAIN_CHARTS['PRD-CRM'])DOMAIN_CHARTS['PRD-CRM'](root)},
    tables:[['조기경보 신호','crm_ews_signal']]})],
  ['가격검증·IPV','C · 독립가격검증 (거래·위험요소·IPV)',screenOf({
    lead:'거래 원장, 위험요소 매핑, 독립가격검증 결과. 미해소 5일 초과는 상위보고 대상이다.',
    charts:root=>{if(DOMAIN_CHARTS['PRD-MKT'])
      {const ipv=D.data['mkt_ipv'];if(ipv){const i=frameIdx(ipv);
        const open=ipv.rows.filter(r=>r[i.is_break]);
        root.appendChild(hbars(open.sort((a,b)=>b[i.days_open]-a[i.days_open])
          .slice(0,8).map(r=>({label:`${r[i.trade_id]} · ${r[i.source]}`,
            value:r[i.days_open],sub:`차이 ${fmtMoney(r[i.diff])}`,
            tone:r[i.days_open]>=5?'bad':'warn'})),
          {title:'미해소 경과일 상위',money:false,
           src:srcMeta(ipv,TP('미해소',TC(open.length,'건')))}))}}},
    tables:[['거래 원장','mkt_trade'],['위험요소','mkt_risk_factor'],
            ['독립가격검증','mkt_ipv']]})],
  ['백테스팅','C · VaR 백테스팅 (예외 달력·손익 대 경계)',screenOf({
    lead:'일별 손익과 VaR 경계의 실측 대조. 예외는 신호등 구간 판정으로 이어진다.',
    charts:root=>{const bt=D.data['mkt_backtest_exception'];
      if(bt){root.appendChild(pnlChart(bt));root.appendChild(calheat(bt))}},
    tables:[['백테스팅 관측 원장','mkt_backtest_exception']]})],
  ['VaR·ES','C · VaR·기대손실(ES) 원장',screenOf({
    lead:'과거시뮬레이션 VaR·ES 산출 원장. 백테스팅·소요자기자본의 원천이다.',
    autochart:[['측정치별 금액','mkt_var_es',['measure','confidence'],'value']],
    tables:[['VaR·ES','mkt_var_es']]})],
  ['손실·회수','D · 운영손실 (사건·회수·자본)',screenOf({
    lead:'내·외부 손실사건, 회수, 운영리스크 소요자본. 총손실 → 적격회수 → 순손실 순서로 읽는다.',
    charts:root=>{if(DOMAIN_CHARTS['PRD-OPR'])DOMAIN_CHARTS['PRD-OPR'](root)},
    tables:[['손실사건 원장','opr_loss_event'],['회수 원장','opr_recovery'],
            ['운영리스크 자본','opr_capital']]})],
  ['KRI·통제','D · KRI·통제 (지표·통제·경보정책)',screenOf({
    lead:'핵심리스크지표와 통제 원장, 그리고 경보가 떴을 때 무엇을 해야 하는지의 정책 바인딩.',
    autochart:[['통제 증빙 상태','opr_control',['evidence_status'],null,{money:false}]],
    tables:[['핵심리스크지표','opr_kri'],['통제 원장','opr_control'],
            ['경보·조치 정책','gov_alert_policy']]})],
  ['NCR·건전성','S · 증권 건전성 (NCR·재무·적기시정조치)',screenOf({
    lead:'순자본비율(NCR) 구성과 증권 건전성 원장. 은행 BIS 비율과 분모·분자·규정 근거가 다르다.',
    autochart:[['NCR 구성요소별 금액','ncr_component',['category','component'],'amount']],
    tables:[['NCR 구성','ncr_component'],['재무상태','pru_balance_sheet'],
            ['유동성 비율','pru_liquidity_ratio'],['경영실태평가(CAMEL)','pru_camel'],
            ['적기시정조치','pru_prompt_action']]})],
  ['시장 RWA','C · 시장리스크 위험가중자산 (소요자기자본 서식·VaR/ES 원장)',screenOf({
    lead:'시장리스크 소요자기자본 서식(B2326)과 그 원천인 VaR·ES 원장. 서식 라인마다 산식·규정 근거가 붙어 있다.',
    forms:['BR-05'],
    tables:[['VaR·ES 원장','mkt_var_es']]})],
  ['운영 RWA','D · 운영리스크 위험가중자산 (소요자기자본 서식·산출방법)',screenOf({
    lead:'운영리스크 소요자기자본 서식(BA2325-1)과 산출방법별 자본·위험가중자산 원장.',
    charts:root=>{const f=D.data['opr_capital'];
      if(!f)return;const i=frameIdx(f);
      root.appendChild(hbars(f.rows.map(r=>({
        label:'산출방법 '+r[i.method],value:r[i.rwa],
        sub:'소요자본 '+fmtMoney(r[i.capital])})),
        {title:'산출방법별 위험가중자산',src:srcMeta(f)}))},
    forms:['BR-06'],
    tables:[['운영리스크 자본 원장','opr_capital']]})],
  ['집합투자증권','CIU · 집합투자증권 (모펀드·편입자산·운용지침, CRE60)',screenOf({
    lead:'모펀드 마스터와 편입자산·운용지침을 분리해 LTA·MBA 를 둘 다 산출한다. LTA 는 편입자산을 직접 보유한 것처럼, MBA 는 운용지침 한도까지 투자했다고 가정하며, 정보가 부족하면 1250% fallback 이다.',
    autochart:[['펀드별 채택 위험가중자산','rwa_fund_result',['fund_name'],'adopted_rwa'],
               ['자산군별 편입 시가','rdm_fund_holding',['asset_class'],'market_value']],
    tables:[['펀드 마스터','rdm_fund_master'],['편입자산 (LTA 입력)','rdm_fund_holding'],
            ['운용지침 한도 (MBA 입력)','rdm_fund_mandate'],
            ['위험가중자산 (세 방법·채택값)','rwa_fund_result']]})],
  ['파생상품','DRV · 파생 마스터·기초자산·넷팅집합 (CRE52 SA-CCR)',screenOf({
    lead:'거래 마스터와 기초자산(다리)을 분리해 SA-CCR EAD 와 시장리스크 민감도를 둘 다 낸다. EAD 는 risk_lib/ccr.py 산출이며 기초자산 자산군이 감독계수 키가 된다.',
    autochart:[['거래상대방별 명목','rdm_derivative_master',['counterparty'],'notional'],
               ['자산군별 명목','rdm_derivative_underlying',['asset_class'],'notional']],
    tables:[['파생 마스터','rdm_derivative_master'],['기초자산 (다리)','rdm_derivative_underlying'],
            ['넷팅집합','rdm_netting_set'],['FRTB 위험군별 민감도','mkt_derivative_sensitivity']]})],
  ['유동화','SEC · 유동화 딜·트렌치·풀 (CRE40~45 SA·ERBA·IRBA)',screenOf({
    lead:'딜 마스터와 트렌치·기초자산 풀을 분리해 SEC-SA·ERBA·IRBA 를 모두 산출하고 CRE40.41 계층(IRBA→ERBA→SA)으로 채택한다. 위험가중 하한은 15%, STC 선순위는 10%다.',
    autochart:[['딜별 보유 위험가중자산','rwa_sec_result',['deal_name'],'adopted_rwa'],
               ['트렌치별 보유액','rdm_sec_tranche',['tranche_name'],'holding_amount']],
    tables:[['유동화 딜 마스터','rdm_sec_master'],['트렌치','rdm_sec_tranche'],
            ['기초자산 풀','rdm_sec_pool'],['위험가중자산 (세 방법·채택값)','rwa_sec_result']]})],
  ['집계 원장','AGG · 도메인별 익스포저 집계',screenOf({
    lead:'도메인마다 집계 축과 필요 컬럼이 다르므로 집계 결과를 원장으로 고정했다. 신용·ALM 집계의 EAD 합은 익스포저 원장 총계와 일치한다.',
    autochart:[['자산군별 익스포저(신용 축)','agg_credit_exposure',['asset_class'],'ead'],
               ['리프라이싱 구간별 익스포저(ALM 축)','agg_alm_exposure',['repricing_bucket'],'ead']],
    tables:[['신용 집계','agg_credit_exposure'],['시장 집계','agg_market_exposure'],
            ['운영손실 집계','agg_operational_loss'],['ALM 집계','agg_alm_exposure'],
            ['위기상황 집계','agg_stress_exposure']]})],
  ['상업성','$ · 사업성 (견적·ROI·Funnel, 규제 산출물 아님)',commercial],
  ['시뮬레이션','SIM · 자본비율 영향도 (설명용 산술, 승인·제출값 아님)',simulation],
  ['한도관리','LIM · 다차원 한도·소진율',limitsScreen],
  ['오버레이','OVR · 수동조정(오버레이) (사유·증빙·승인·만료)',overlay],
  ['거시지표 모니터링','E · 거시·금융지표 모니터링 (시나리오 심도의 근거)',macroMonitor],
  ['역스트레스','RST · 역방향 위기상황 (자본 임계를 뚫는 심도)',reverseStress],
  ['시나리오 설정','SET · 위기상황 시나리오 설정 (축·심도·신규 제안)',scenarioScreen],
  ['코드 마스터','SET · 코드 마스터 관리 (정렬 정본)',codeMasterAdmin],
  ['코드 매핑','SET · 계정·상품 코드 × 리스크 대상·특성 매핑',codeScope],
  ['모형 인벤토리','MDL · 모형 인벤토리 (전 도메인, 신용·시장·ALM·위기·기후·전사)',modelInventory],
  ['검증 일정','MDL · 모형 검증 일정 (주기·경과·의존·한계)',modelValidationSchedule],
  ['모형리스크','MDL · 모형리스크 관리 (등급별 거버넌스·운영 상태)',modelRiskGovernance],
  ['변별력·안정성','MDL · 신용모형 성능 (Gini·KS·PSI)',modelPerformance],
  ['등급 보정','MDL · 등급 보정 (예측 PD 대 실측 부도율, O/E)',modelCalibration],
  ['산출 방법론','SET · 산출 방법론 (LTA/MBA · SEC 계층 선택)',methodology],
  ['금리리스크','E · 은행계정 금리리스크(IRRBB) (충격 ΔEVE·ΔNII·버킷 현재가치)',
   almIrrbbScreen],
  ['현금흐름 원장','E · ALM 현금흐름 (계약 대 행동조정)',almCashflowScreen],
  ['유동성 사다리','E · 만기 사다리 (유입·유출·누적갭·반대매매가능자산)',
   almLadderScreen],
  ['유동성리스크','E · 유동성비율 상세 (LCR·NSFR 항목별 잔액×계수=가중액)',
   almLiquidityScreen],
  ['생존기간','E · 생존기간 (스트레스별 소진 경로)',almSurvivalScreen],
  ['ALM 계수 원장','E · ALM 계수·수기입력 모수 (승인·근거 상태)',almParamScreen],
  ['국내 금리리스크','E · [별표 9-1] 국내 금리리스크 (ΔEVE·ΔNII·아웃라이어·공시)',
   krIrrbbScreen],
  ['행동모형 추정','E · 고객행동모형 추정 (조기상환·중도해지)',bhvModelScreen],
  ['비만기성예금 코어','E · 비만기성예금 코어 (세 추정방법·<표3> 상한)',nmdCoreScreen],
  ['행동모형 백테스트','E · 고객행동모형 백테스트 (표본외 실적 대비)',
   bhvBacktestScreen],
  ['PD 추정','IRB · PD 추정 (장기평균 부도율·하한·MoC)',pdEstimateScreen],
  ['LGD 추정','IRB · LGD 추정 (회수곡선·경기침체·관측중단)',lgdEstimateScreen],
  ['CCF 추정','IRB · CCF 추정 (관측설계·상관·보수화)',ccfEstimateScreen],
  ['부도자산 LGD','IRB · 부도자산 LGD (ELBE·충당금 비교)',defaultedLgdScreen],
  ['회수 할인율','IRB · 회수 할인율 (CAPM 관측·추정·승인·적용)',
   capmDiscountScreen],
  ['BEEL·PLGD','IRB · 부도자산 LGD (BEEL 곡선·PLGD·신뢰수준 민감도)',
   beelPlgdScreen],
  ['모형 거버넌스','IRB · 모형 거버넌스·사후검증 (적용·실측·허용범위)',
   irbGovernanceScreen],
  ['LGD·EAD 실측검증','B · LGD·EAD 실측 검증 (추정 대 실현)',lgdEadBacktestScreen],
  ['거액 설정','LEX · 거액익스포져 설정 (한도율·보고기준·면제정책)',lexSettingScreen],
  ['거액 분석','LEX · 거액익스포져 분석 (순위·대체·연결그룹·총액한도)',
   lexAnalysisScreen],
];

/* 메뉴 트리. 그룹은 시각적 계층이고, 리프 순서가 화면 목록의 순서를 정한다.
   앞 4개 리프(콕핏·정형·비정형·A RDM) 순서는 바꾸지 않는다. */
/* 항목은 리프 라벨(문자열) 또는 [하위그룹, [...]]. 트리는 재귀로 그린다. */
/* 부문 마커(A/B/C…·Δ)는 메뉴에서 뺀다. 트리 들여쓰기가 이미 부문을
   말한다. 부문 개요는 2레벨 리프-부모, 마커 없던 세부화면은 3레벨이다. */
const NAVGROUPS=[
  /* 보고서가 통제센터 위다. 경영진이 먼저 보는 것이 위에 있어야 한다.
     콕핏은 실무 운영 화면이고 이쪽은 결재선·이사회로 나가는 산출물이다. */
  ['보고서',['종합보고서']],
  ['통제센터',['콕핏','시뮬레이션','한도관리']],
  ['조회·컴포저',['정형 조회','비정형 UI']],
  /* 모형은 신용에만 있지 않다. 도메인 축으로 따로 세운다(사용자 지적).
     원장이 crm_ 스키마에 산다는 것과 신용 모형이라는 것은 다른 말이다. */
  ['모형',[
    ['모형 인벤토리',['검증 일정','모형리스크']],
    ['신용모형',['변별력·안정성','등급 보정','등급 전이']],
    /* 내부등급법 추정은 신용모형 성능과 다른 것을 본다. 성능은 변별력이고
       추정은 값 자체와 하한·MoC·관측기간이다. 그래서 하위그룹을 따로 둔다. */
    ['내부등급법 추정',['PD 추정','LGD 추정','CCF 추정','회수 할인율',
                        '부도자산 LGD','BEEL·PLGD',
                        '모형 거버넌스','LGD·EAD 실측검증']],
    ['고객행동모형',['행동모형 추정','비만기성예금 코어','행동모형 백테스트']],
  ]],
  ['리스크데이터',[
    ['RDM',['원천·계약','DQ·대사','예외·조치','담보·보증','집계 원장']],
    ['선행 원장',['집합투자증권','파생상품','유동화']],
  ]],
  ['위험가중자산(RWA)',[
    ['신용',['조기경보','신용 RWA','ECL']],
    ['거액익스포져',['거액 설정','거액 분석']],
    ['시장',['가격검증·IPV','백테스팅','VaR·ES','시장 RWA']],
    ['운영',['손실·회수','KRI·통제','운영 RWA']],
  ]],
  ['ALM·위기상황',[
    /* 국내 감독기준 화면과 BCBS 계정 화면은 나란히 두되 섞지 않는다.
       적용 계정이 다르므로 두 화면의 수치를 한 문장에서 비교하지 않는다. */
    ['ALM',['금리리스크','국내 금리리스크','현금흐름 원장','유동성 사다리',
            '유동성리스크','생존기간','ALM 계수 원장']],
    ['위기상황',['거시지표 모니터링','시나리오 설정','역스트레스']],
  ]],
  ['증권 건전성',['NCR·건전성']],
  ['보고',['감독보고']],
  ['검증·거버넌스',[
    ['검증',['요건 추적']],
    '에이전트','변경','오버레이',
  ]],
  ['데이터·설정',[
    '데이터모델',
    ['⚙ 설정',['코드 마스터','코드 매핑','산출 방법론']],
  ]],
  /* 사업성은 규제 산출물이 아니다. 제출 지문·독립검증 대상이 아니므로
     메뉴에서도 맨 끝에 두고 이름으로 성격을 밝힌다. */
  ['(참고)',['상업성']],
];

const TABS=[
  ['종합보고서','종합보고서 (자본·유동성·KRI·CRO 액션)',executiveReport],
  ['콕핏','00 전사 리스크 콕핏',cockpit],
  ['정형 조회','정형 조회 스튜디오 · Governed Query',structured],
  ['비정형 UI','비정형 Adaptive UI Composer',adaptive],
  /* 위험데이터마트 화면은 합성데이터 고지와 소관 부서를 맨 위에 둔다.
     이 화면의 수치가 원장 그대로라서, 실적 수치로 오인될 여지가 가장 크다. */
  ['RDM','A · 리스크데이터 (유연집계·가공·정합성·계보)',
   r=>{reviewNotice(r,'RDM');
       domain(r,'PRD-RDM',null,'원천계약부터 표준 매핑, 버전형 가공, 다차원 집계, DQ·대사, 승인 스냅샷까지 통제한다.')}],
  ['신용','B · 신용리스크 (모형·파라미터·회수·경보)',
   r=>domain(r,'PRD-CRM',null,'등급·PD/LGD/EAD·부도/회수 품질·담보배분·조기경보를 연결한다.')],
  ['신용 RWA','B · 신용리스크 위험가중자산',
   r=>domain(r,'PRD-RWA',null,'표준방법 구간별·내부등급법 PD 구간별로 분해해 업무보고서 라인과 같은 입도로 둔다.')],
  ['ECL','B · 기대신용손실',
   r=>domain(r,'PRD-ECL',null,'Stage 전이·SICR 트리거·충당금 증감 브리지를 분해한다.')],
  ['시장','C · 시장리스크 (가격평가·위험요소·ES·백테스팅)',
   r=>domain(r,'PRD-MKT',null,'벤치마크 가격·시장데이터 계보·위험요소·ES·백테스팅을 연결한다.')],
  ['운영','D · 운영리스크 (손실데이터·PSMOR)',
   r=>domain(r,'PRD-OPR',null,'내·외부 사건·회수·KRI·PSMOR 원칙 매핑을 연결한다. 매핑이며 준수 인증이 아니다.')],
  ['ALM','E · ALM (IRRBB·LCR·NSFR)',
   r=>domain(r,'PRD-ALM',null,'항목별 잔액·적용률·가중 후 금액까지 분해해 규제 비율의 원인을 추적한다.')],
  ['위기상황','E · 통합위기상황분석 (심각도별 전 단계 산출과정)',stressDeepDive],
  ['감독보고','R · 금감원 업무보고서',regulatory],
  ['검증','F · 검증 두 층, 자체검증(2선)과 상시 독립검증(3선)',validation],
  ['에이전트','G · 에이전트 운영 · 권한 · Kill Switch',agents],
  ['변경','Δ · 리스크 변경 팩토리',changes],
  ['데이터모델','정규 데이터모델 카탈로그',catalogView],
  ['요건 추적','REQ · v9.6.0 업무요건 추적 (131건 대비 구현 재고조사)',reqTrace],
  ...DETAIL_SCREENS.map(([lab,title,fn])=>[lab,title,fn]),
  ['⚙ 설정','⚙ · 설정 (기준일 · 표시명 · 코드 매핑 · 시나리오)',settings],
];

let repaintAll=()=>{};                   /* boot에서 실체가 채워진다 */

function setRun(a){
  /* 승인·이력은 **실행에 속한다**. proposal_id는 (view, 프롬프트)의 해시라
     실행이 바뀌어도 같으므로, 그대로 두면 이전 기준일 데이터로 받은 승인이
     새 기준일 화면에 "승인 적용"으로 뜬다. 다른 산출물에 승인 도장이
     옮겨 찍히는 것이다. 실행별로 보관하고 전환 시 맞바꾼다. */
  STATE.byRun=STATE.byRun||{};
  STATE.byRun[D.meta.asof]={approved:STATE.approved,history:STATE.history};
  const kept=STATE.byRun[a]||{approved:{},history:{}};
  STATE.approved=kept.approved;STATE.history=kept.history;

  D=RUNS[a];
  paintChips();
  const fa=$('#foot-asof');if(fa)fa.textContent=a;
  const fs=$('#foot-seed');if(fs)fs.textContent=String(D.meta.seed);
  repaintAll();
}

/* 머리말 칩은 라벨(카탈로그)과 원장 값(실행 메타)이 붙어 있다. 라벨만
   옮기고 값은 그대로 둔다. 기준일 전환과 언어 전환 두 곳에서 같은 함수를
   쓴다. 두 벌로 적으면 한쪽만 고쳐져 화면이 어긋난다. */
function paintChips(){
  const set=(sel,txt)=>{const e=$(sel);if(e)e.textContent=txt};
  set('#chip-run',D.meta.run_id);
  set('#chip-digest',TP('지문',D.meta.digest.slice(0,12)));
  set('#chip-seed',TP('시드',String(D.meta.seed)));
  set('#chip-rows',LANG==='ko'
    ? `테이블 ${D.meta.n_tables}장 · ${D.meta.n_rows.toLocaleString()}행`
    : `${D.meta.n_tables} tables · ${D.meta.n_rows.toLocaleString()} rows`);
  document.title='RYNTA '+T('에이전틱 UI 스튜디오')+' · '+D.meta.asof;
}

/* 화면 언어. 초기값은 영어이고, 사용자가 고르면 그 선택이 이긴다. 선택은
   localStorage 에 남아 다음 열람에도 유지된다. 전환은 새로고침 없이 즉시
   다시 그린다(원장은 그대로이고 표시 문자열만 바뀐다). */
const LANG_KEY=I18N.storage_key||'rynta-lang';
function storedLang(){
  try{const v=localStorage.getItem(LANG_KEY);
    return (I18N.langs||['en','ko']).indexOf(v)>=0?v:null}catch(e){return null}
}
/* 마크업에 직접 적힌 문자열(머리말·꼬리말·비상정지 막대)은 el() 을 거치지
   않는다. 원문을 dataset 에 한 번 담아 두고 그 원문으로 다시 옮긴다.
   화면에 이미 그려진 영문을 다시 찾으면 두 번째 전환에서 원문을 잃는다. */
function paintStatic(){
  document.documentElement.lang=LANG;
  [...document.querySelectorAll('[data-i18n]')].forEach(e=>{
    if(e.dataset.ko===undefined)e.dataset.ko=e.textContent.trim();
    e.textContent=T(e.dataset.ko)});
  const rin=$('#killreason');
  if(rin){if(rin.dataset.ko===undefined)rin.dataset.ko=rin.value;
    if(!rin.dataset.touched)rin.value=T(rin.dataset.ko)}
  const nv=$('nav');if(nv)nv.setAttribute('aria-label',T('메뉴'));
  const tb=$('#themebtn');if(tb)paintThemeButton(tb);
  const lb=$('#langbtn');
  if(lb){lb.textContent=(LANG==='en'?T('한국어'):'English');
    lb.title=T('화면 언어를 전환한다. 원장에서 오는 값(차주명·등급·서식 항목명·컬럼명)은 원문 그대로 둔다.');
    lb.setAttribute('aria-label',lb.title)}
  paintChips();
}
/* 메뉴 버튼은 boot() 에서 한 번 만들어지고 화면 다시 그리기의 대상이 아니다.
   원문을 dataset 에 담아 두고 언어 전환 때 이름만 갈아 끼운다. */
function relabelNav(){
  const nav=$('nav');if(!nav)return;
  [...nav.children].forEach(e=>{
    if(e.dataset.ko!==undefined)e.textContent=T(e.dataset.ko)});
}
function setLang(next){
  LANG=next;
  try{localStorage.setItem(LANG_KEY,next)}catch(e){}
  paintStatic();relabelNav();repaintAll();
}
function wireLang(){
  const stored=storedLang();
  if(stored)LANG=stored;
  const b=$('#langbtn');
  if(b)b.onclick=()=>setLang(LANG==='en'?'ko':'en');
}
/* 번역 누락을 사람이 눈으로 세면 빠뜨린다. 브라우저 검사가 화면을 전부
   돌면서 이 목록으로 화면별 번역률을 잰다(tests/test_i18n.py). */
window.__I18N__={miss:I18N_MISS,hit:I18N_HIT,T:s=>T(s),lang:()=>LANG,
                 set:l=>setLang(l)};

/* 화면 밝기. 초기값은 시스템 설정(prefers-color-scheme)을 따르고, 한 번
   고르면 그 선택이 이긴다. 선택은 localStorage 에 남아 다음 열람에도 유지된다.
   외부 리소스를 부르지 않으므로 폐쇄망·아티팩트에서도 그대로 동작한다. */
const THEME_KEY='rynta-theme';
function systemTheme(){
  return (window.matchMedia&&
    window.matchMedia('(prefers-color-scheme: light)').matches)?'light':'dark'}
function currentTheme(){
  return document.documentElement.getAttribute('data-theme')||systemTheme()}
function paintThemeButton(btn){
  const t=currentTheme();
  btn.textContent=T(t==='dark'?'밝은 화면으로':'어두운 화면으로');
  btn.setAttribute('aria-pressed',t==='dark'?'true':'false');
  let stored=null;
  try{stored=localStorage.getItem(THEME_KEY)}catch(e){}
  btn.title=T(stored?'선택한 화면 밝기':'시스템 설정을 따르는 중')+
    ' ('+t+'). '+T('누르면 전환한다.');
}
function wireTheme(){
  const btn=$('#themebtn');
  if(!btn)return;
  btn.onclick=()=>{
    const next=currentTheme()==='dark'?'light':'dark';
    document.documentElement.setAttribute('data-theme',next);
    try{localStorage.setItem(THEME_KEY,next)}catch(e){}
    paintThemeButton(btn)};
  /* 사용자가 아직 고르지 않았으면 시스템 설정 변경을 따라간다. */
  if(window.matchMedia){
    const mq=window.matchMedia('(prefers-color-scheme: light)');
    const onChange=()=>{
      let stored=null;
      try{stored=localStorage.getItem(THEME_KEY)}catch(e){}
      if(!stored)paintThemeButton(btn)};
    if(mq.addEventListener)mq.addEventListener('change',onChange);
    else if(mq.addListener)mq.addListener(onChange);
  }
  paintThemeButton(btn);
}

function boot(){
  const nav=$('nav'),main=$('main');
  wireLang();
  wireTheme();
  const byLabel={};TABS.forEach(t=>{byLabel[t[0]]=t});
  let first=null,idx=0;
  function addLeaf(label,depth,collect){
    const t=byLabel[label];
    if(!t)return;
    const [,title,fn]=t;
    const b=el('button','lvl'+depth,label);
    b.dataset.ko=label;                  /* 언어 전환 때 원문으로 되돌아간다 */
    const s=el('section');s.id='tab'+(idx++);
    b.onclick=()=>{
      [...nav.querySelectorAll('button')].forEach(x=>x.classList.remove('on'));
      [...main.children].forEach(x=>x.classList.remove('on'));
      b.classList.add('on');s.classList.add('on');
      if(!s.dataset.done){const h=el('h2',null,title);s.appendChild(h);fn(s);
        insertSummary(label,s);
        s.dataset.done='1'}
      window.scrollTo({top:0});
    };
    collect.push(b);nav.appendChild(b);main.appendChild(s);
    if(!first)first=b;
  }
  function addGroup(gname,items,depth){
    const gh=el('div','navgroup'+(depth?' sub lvl'+depth:''),gname);
    gh.dataset.ko=gname;
    const under=[];                      /* 이 그룹 아래 전부 (접기 대상) */
    gh.onclick=()=>{gh.classList.toggle('closed');
      const closed=gh.classList.contains('closed');
      under.forEach(x=>{x.hidden=closed;
        if(x.classList&&x.classList.contains('navgroup'))
          x.classList.toggle('closed',closed)})};
    nav.appendChild(gh);
    items.forEach(item=>{
      if(typeof item==='string'){addLeaf(item,depth+1,under)}
      else{const [sub,subItems]=item;
        if(byLabel[sub]){
          /* 리프-부모 (화면을 여는 항목이면서 자식(3레벨)을 거느린다) */
          addLeaf(sub,depth+1,under);
          subItems.forEach(ch=>addLeaf(ch,depth+2,under));
        } else {
          const before=nav.children.length;
          addGroup(sub,subItems,depth+1);
          for(let k=before;k<nav.children.length;k++)under.push(nav.children[k]);
        }}
    });
  }
  NAVGROUPS.forEach(([gname,items])=>addGroup(gname,items,0));
  if(first)first.onclick();
  /* 사유 입력은 **화면 안**에서 받는다. prompt()는 샌드박스 iframe(임베드·
     아티팩트)에서 차단되어 null을 돌려주고, 그러면 통제가 아무 반응 없이
     죽는다. 통제가 있는 것처럼 보이면서 실제로는 작동하지 않는 상태가 된다. */
  const kb=$('.kill'), bar=$('.killbar'), rin=$('#killreason');
  const ksc=$('#killscope');
  /* 범위 값은 실행 원장의 도메인 코드다. 값은 그대로 두고 표시만 옮긴다.
     값을 옮기면 정지 사유 기록에 화면 언어가 섞여 들어간다. */
  ['전사'].concat([...new Set(Object.values(D.view_meta).map(v=>v.domain))].sort())
    .forEach(d=>{const o=el('option');o.value=d;o.dataset.ko=d;
      o.textContent=T(d);ksc.appendChild(o)});
  const repaint=()=>{
    [...main.children].forEach(x=>{x.dataset.done='';x.innerHTML=''});
    [...nav.querySelectorAll('button')].forEach(b=>{
      if(b.classList.contains('on'))b.onclick()});
  };
  repaintAll=repaint;

  /* 기준일 전환. 실은 실행 사이의 전환이다. 옵션은 실행 목록에서 나온다. */
  const asel=$('#asofsel');
  Object.keys(RUNS).sort().forEach(a=>{
    const o=el('option');o.value=a;o.textContent=a;asel.appendChild(o)});
  asel.value=D.meta.asof;
  asel.onchange=()=>setRun(asel.value);

  const engage=()=>{
    const reason=(rin.value||'').trim();
    if(!reason){rin.focus();return;}        /* 사유 없는 정지는 없다 */
    STATE.killed=true;STATE.killReason=reason;
    STATE.killScope=ksc.value||'전사';       /* 범위형 정지 (PLT-016) */
    kb.textContent=T('Kill Switch 해제')+(STATE.killScope==='전사'?''
      :' · '+T(STATE.killScope));
    kb.classList.add('on');
    bar.hidden=true;repaint();
  };
  kb.onclick=()=>{
    if(STATE.killed){
      STATE.killed=false;kb.textContent='Kill Switch';
      kb.classList.remove('on');
      bar.hidden=true;repaint();return;
    }
    bar.hidden=!bar.hidden;
    if(!bar.hidden){rin.focus();rin.select();}
  };
  $('.killgo').onclick=engage;
  $('.killno').onclick=()=>{bar.hidden=true;kb.focus();};
  rin.onkeydown=e=>{
    if(e.key==='Enter')engage();
    if(e.key==='Escape'){bar.hidden=true;kb.focus();}
  };
  /* 사용자가 사유를 직접 적었으면 언어를 바꿔도 그 문장을 덮지 않는다.
     사람이 쓴 정지 사유를 화면이 갈아 치우면 기록이 사라진다. */
  rin.oninput=()=>{rin.dataset.touched='1'};
  paintStatic();
}
boot();
"""


def render(studios: Studio | list[Studio]) -> str:
    """한 개 이상의 실행 스냅샷을 한 화면으로 그린다.

    기준일 전환은 **미리 산출해 실은 실행 사이의 전환**이다. 화면은 계산기가
    아니므로 새 기준일을 즉석에서 만들 수 없다. 만들 수 있는 것처럼 보이면
    검증 안 된 수치가 화면에 생긴다. 실행마다 자기 run_id·지문·검증 상태를
    갖고, 전환하면 그 실행의 것으로 전부 바뀐다.
    """
    ss = [studios] if isinstance(studios, Studio) else sorted(
        studios, key=lambda x: x.asof)
    runs = {s.asof: _payload(s) for s in ss}
    primary = ss[-1].asof                    # 최신 기준일이 기본 화면
    m = runs[primary]["meta"]
    return f"""<!doctype html>
<html lang="{_i18n.DEFAULT_LANG}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>RYNTA 에이전틱 UI 스튜디오 · {html.escape(primary)}</title>
<style>{_CSS}</style></head><body>
<script>/* 저장된 선택을 그리기 전에 적용한다. 뒤에서 적용하면 첫 페인트가
  시스템 설정으로 나갔다가 바뀌어 화면이 한 번 번쩍인다. 외부 리소스를 부르지
  않고 인라인으로만 둔다(폐쇄망·아티팩트 CSP). */
(function(){{try{{var t=localStorage.getItem('rynta-theme');
if(t==='light'||t==='dark')document.documentElement.setAttribute('data-theme',t);
}}catch(e){{}}}})();</script>
<div class="topbar">
<header>
  <div class="brand">RYNTA <span>·</span> <b data-i18n>에이전틱 UI 스튜디오</b></div>
  <label class="hchip" for="asofsel"><span data-i18n>기준일</span>
    <select id="asofsel" class="sel asofsel"></select></label>
  <span class="hchip" id="chip-run">{html.escape(m['run_id'])}</span>
  <span class="hchip" id="chip-digest">지문 {html.escape(m['digest'][:12])}</span>
  <span class="hchip" id="chip-seed">시드 {m['seed']}</span>
  <span class="hchip" id="chip-rows">테이블 {m['n_tables']}장 · {m['n_rows']:,}행</span>
  <span class="hchip">Read-only · PII Mask</span>
  <button class="theme" id="langbtn" type="button">English</button>
  <button class="theme" id="themebtn" type="button" aria-pressed="false"
          title="밝은 화면과 어두운 화면을 전환한다">화면 밝기</button>
  <button class="kill" data-i18n>Kill Switch</button>
</header>
<div class="killbar" hidden>
  <label for="killscope" data-i18n>범위</label>
  <select id="killscope" class="sel"></select>
  <label for="killreason" data-i18n>비상정지 사유 (필수)</label>
  <input id="killreason" type="text"
         value="시장데이터 지연 확인 중 신규 재계산 보류">
  <button class="killgo" data-i18n>정지</button>
  <button class="killno" data-i18n>취소</button>
  <span class="killnote" data-i18n>중요 범위는 운영에서 독립된 2차 확인이 추가로 필요하다.</span>
</div>
</div>
<div class="layout">
<nav aria-label="메뉴"></nav>
<main></main>
</div>
<footer>
  <span data-i18n>엔진 산출은 결정론적이며, 에이전트는 제안만 하고 승인은 사람이 한다.</span>
  <span data-i18n>화면의 모든 값은 합성 포트폴리오에서</span> <code>run_pipeline(seed=<span
  id="foot-seed">{m['seed']}</span>,
  asof='<span id="foot-asof">{html.escape(primary)}</span>')</code><span
  data-i18n>로 산출한 것이며 실제 기관 수치가 아니다.</span>
  <span data-i18n>에이전트는 신용등급·여신승인, PD·LGD·EAD 등 핵심 위험파라미터, ECL·충당금, RWA·BIS 비율, 감독제출·공시, 경영조치를 자동확정하지 않는다.</span>
  <br><span data-i18n>약어</span>: <span data-i18n>RDM(리스크데이터관리) · RWA(위험가중자산) · ECL(기대신용손실) · ALM(자산부채관리) · IRRBB(은행계정 금리리스크) · LCR(유동성커버리지비율) · NSFR(순안정자금조달비율) · IPV(독립가격검증) · SICR(신용위험 유의적 증가) · DQ(데이터품질) · AST(구문트리) · PSMOR(운영리스크 건전관리 원칙).</span>
</footer>
<script>window.__RYNTA_RUNS__={json.dumps(runs, ensure_ascii=False, default=str,
                                          separators=(",", ":"))};
window.__RYNTA__=window.__RYNTA_RUNS__[{json.dumps(primary)}];
window.__RYNTA_I18N__={json.dumps(_i18n.payload(), ensure_ascii=False,
                                  separators=(",", ":"))};</script>
<script>{_ENGINE_JS}</script>
<script>{_JS}</script>
</body></html>"""


def write_app(s: Studio | list[Studio], path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render(s), encoding="utf-8")
    return p
