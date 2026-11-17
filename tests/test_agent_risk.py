"""Agent 위험도 등급(risk_lib.aig.agent_tier)과 등급별 위험 관리(risk_lib.aig.agent_risk).

고정하는 것:
  1) 등급 산식은 요건정의서 4.9 의 예시 6건과 전수 점검(단조성 위반 0건, 균등 조합
     분포)을 그대로 재현한다. 고정 조건은 하향을 막고, 불허는 접수 반려, 입력 결손은
     미확정이다.
  2) 위험 관리 수치(위험가중 사용량, 감내수준 지표 상태, 차단장치 시작 단계)는
     요건정의서 4.13 의 예시 산술과 같다.
  3) 원장 18장은 카탈로그 사양과 같고, 자체검증 12종과 독립 재계산 대상 4종에
     연결되어 있다.
  4) 화면(기존·새 UI)과 영문 빌드가 새 원장을 빠짐없이 싣는다.

수치는 전부 예시 설정값이다. 골든은 "맞는 값"이 아니라 "바뀌면 알아채야 하는 값"이다.
"""

from __future__ import annotations

import re

import pandas as pd
import pytest

from risk_lib.aig import agent_risk as ar
from risk_lib.aig import agent_tier as at
from risk_lib.datamodel import catalog as cat
from risk_lib.ui_studio import export_en
from risk_lib.ui_studio.next import payload_ext
from risk_lib.validation import independent

OK3 = (True, True, True)
HANGUL = re.compile(r"[가-힣]")

# 요건정의서 4.9 예시 1~6: (A1~A4, B1~B4, 고정, 불허, 통제 증거와 승인) ->
# (영향, 점수, 노출, 고유, 잔여)
PRD_EXAMPLES = [
    ((1, 1, 1, 1), (1, 2, 1, 2), (), (), False, (1, 7, 1, "저", "저")),
    ((2, 1, 2, 2), (2, 2, 1, 2), (), (), True, (2, 9, 2, "중", "저")),
    ((2, 1, 2, 1), (3, 3, 2, 2), (), (), True, (2, 13, 3, "고", "중")),
    ((3, 3, 3, 2), (2, 3, 2, 2), ("F2",), (), True, (3, 11, 2, "고", "고")),
    ((3, 3, 3, 2), (2, 3, 3, 2), ("F2",), (), False, (3, 12, 3, "고", "고")),
]

AGENT_CHECKS = {
    "agent_tier_recompute_matches": "PASS", "agent_tier_monotone": "PASS",
    "agent_tier_fixed_banned_rules": "PASS", "agent_tier_downgrade_evidence": "PASS",
    "agent_limit_hierarchy": "WARN", "agent_weighted_usage_reconciles": "PASS",
    "agent_appetite_status": "WARN", "agent_contagion_traces_to_stress": "PASS",
    "agent_addon_separation": "PASS", "agent_param_evidence": "PASS",
    "agent_backcheck_small_sample": "WARN", "agent_control_link_reconciles": "PASS",
}
AGENT_TARGETS = ("agent_high_tier_share", "agent_weighted_limit_usage",
                 "agent_internal_rwa_addon", "agent_op_internal_capital_addon")
SCREENS = ("Agent 위험도 등급", "Agent 위험 관리", "실행 통제 연계")


def _t(result, name):
    return result.ledger_tables[name]


# ---------------------------------------------------------------- 등급 산식

@pytest.mark.parametrize("a, b, fixed, banned, evidenced, want", PRD_EXAMPLES)
def test_tier_formula_reproduces_the_requirement_examples(a, b, fixed, banned,
                                                          evidenced, want):
    out = at.assess(a, b, fixed=fixed, banned=banned,
                    controls=OK3 if evidenced else (False,) * 3, approved=evidenced)
    assert (out.impact, out.score, out.exposure, out.inherent, out.residual) == want


def test_banned_design_gets_no_tier():
    """예시 6. 불허 조건은 등급을 매기지 않고 접수에서 돌려보낸다."""
    out = at.assess((3, 3, 3, 3), (3, 2, 2, 2), banned=("X1",), controls=OK3,
                    approved=True)
    assert (out.inherent, out.residual, out.impact, out.score) == (at.BANNED, at.BANNED,
                                                                   None, None)


def test_missing_input_is_unconfirmed_not_low():
    """입력이 비면 낮은 등급으로 떨어지지 않고 미확정으로 남는다."""
    out = at.assess((1, None, 1, 1), (1, 1, 1, 1))
    assert out.inherent == out.residual == at.HOLD
    assert out.hold and out.hold.startswith("H1")


@pytest.mark.parametrize("score, level", [(5, 1), (7, 1), (8, 2), (11, 2), (12, 3), (15, 3)])
def test_exposure_band_boundaries(score, level):
    b1 = {5: 1, 7: 2, 8: 2, 11: 3, 12: 3, 15: 3}[score]
    rest = score - 2 * b1                       # B2 + B3 + B4
    b = (b1,) + {3: (1, 1, 1), 4: (2, 1, 1), 5: (2, 2, 1), 6: (2, 2, 2),
                 9: (3, 3, 3)}[rest]
    out = at.assess((1, 1, 1, 1), b)
    assert (out.score, out.exposure) == (score, level)


def test_data_sensitivity_alone_caps_impact_at_two():
    """A3 는 단독으로 영향 2 까지만 올린다. 규모 가산은 기본 수준 2 이상에서만 붙는다."""
    assert at.assess((1, 1, 3, 1), (1, 1, 1, 1)).impact == 2
    assert at.assess((1, 1, 1, 3), (1, 1, 1, 1)).impact == 1
    assert at.assess((2, 1, 1, 3), (1, 1, 1, 1)).impact == 3


def test_downgrade_needs_all_evidence_and_approval_and_is_one_step():
    a, b = (2, 1, 2, 1), (3, 3, 2, 2)           # 행렬 등급 고
    assert at.assess(a, b, controls=OK3, approved=True).residual == "중"
    assert at.assess(a, b, controls=OK3, approved=False).residual == "고"
    assert at.assess(a, b, controls=(True, True, False), approved=True).residual == "고"


def test_fixed_condition_blocks_downgrade():
    a, b = (3, 3, 3, 2), (2, 3, 2, 2)
    assert at.rule_of_two(a, b)
    out = at.assess(a, b, fixed=at.fixed_flags(a, b), controls=OK3, approved=True)
    assert (out.inherent, out.residual, out.downgraded) == ("고", "고", False)


def test_formula_is_monotone_over_every_combination():
    assert at.monotonicity_violations() == 0


def test_uniform_distribution_matches_the_requirement_figures():
    dist = at.uniform_distribution()
    assert {t: round(v * 100, 1) for t, v in dist.items()} == {
        "저": 6.4, "중": 26.8, "고": 66.8}


def test_agent_system_is_the_union_of_its_members():
    """예시 5. 따로 보면 저·중·중인 구성원이 시스템으로는 세 조건이 함께 성립해 고다."""
    members = [((1, 1, 1, 1), (1, 3, 1, 2)), ((2, 1, 3, 2), (1, 1, 1, 2)),
               ((3, 3, 1, 2), (1, 1, 1, 2))]
    a, b = at.union_levels(members)
    assert (a, b) == ((3, 3, 3, 2), (1, 3, 3, 2))
    out = at.assess(a, b, fixed=at.fixed_flags(a, b))
    assert out.fixed == ("F2",) and out.inherent == "고"
    assert not any(at.rule_of_two(*m) for m in members)


def test_breaker_start_stage_adds_the_tier_and_caps_at_five():
    assert [at.breaker_start(1, t) for t in at.TIERS] == [1, 2, 3]
    assert at.breaker_start(1, at.HOLD) == 3
    assert at.breaker_start(4, "고") == 5


# ---------------------------------------------------------------- 위험 관리 산술

def test_weighted_usage_example_and_its_threshold_status():
    """4.13 예시. 300 × 1.0 + 120 × 1.5 + 30 × 2.5 = 555, 중 50 이 고로 오르면 605."""
    p = ar.DEFAULT_RISK_PARAMS
    usage = lambda g: sum(v * p.weight(t) for t, v in g.items())
    before = usage({"저": 300.0, "중": 120.0, "고": 30.0})
    after = usage({"저": 300.0, "중": 70.0, "고": 80.0})
    assert (before, after) == (555.0, 605.0)
    thr = p.thresholds["K2"]
    assert ar.appetite_status(before / 20000, thr) == (ar.STATUS_LEVELS[0], 1)
    assert ar.appetite_status(after / 20000, thr) == (ar.STATUS_LEVELS[1], 2)


def test_unset_threshold_is_reported_as_unset_not_within_range():
    assert ar.appetite_status(0.9, None) == (ar.STATUS_UNSET, None)
    assert ar.appetite_status(0.9, (0.5, None, 1.0)) == (ar.STATUS_UNSET, None)
    assert ar.appetite_status(None, (0.1, 0.2, 0.3)) == (ar.STATUS_UNSET, None)
    assert ar.appetite_status(0.1, (0.1, 0.2, 0.3)) == (ar.STATUS_OK, 0)


def test_missing_tier_weight_falls_back_to_the_highest():
    p = ar.RiskParams(risk_weight={"저": 1.0, "중": None, "고": 2.5})
    assert p.weight("중") == 2.5
    assert p.weight(at.HOLD) == 2.5


# ---------------------------------------------------------------- 원장

def test_ledgers_are_in_the_catalog_and_materialised(result):
    names = {sp.name for sp in cat.ALL_TABLES}
    assert len(ar.SPECS) == 18
    for sp in ar.SPECS:
        assert sp.name in names, f"{sp.name} 이 카탈로그에 없다"
        df = _t(result, sp.name)
        assert len(df), f"{sp.name} 이 비었다"
        assert list(df.columns) == [c.name for c in sp.columns], sp.name


def test_reference_portfolio_reproduces_the_requirement_tiers(result):
    """참조 포트폴리오의 운영 등급이 예시와 같다 (고유, 잔여)."""
    a = _t(result, "aig_tier_assessment")
    op = a[a["stage"] == "운영"].set_index("unit_id")
    got = {u: (op.at[u, "inherent_tier"], op.at[u, "residual_tier"])
           for u in ("AGT-0102", "AGT-0233", "AGT-0305", "AGT-0417", "SYS-0009")}
    assert got == {"AGT-0102": ("저", "저"), "AGT-0233": ("중", "저"),
                   "AGT-0305": ("고", "중"), "AGT-0417": ("고", "고"),
                   "SYS-0009": ("고", "고")}
    members = op.loc[["AGT-0911", "AGT-0912", "AGT-0913"], "residual_tier"].tolist()
    assert members == ["저", "중", "중"]
    banned = a[a["unit_id"] == "INT-2026-0027"]
    assert set(banned["residual_tier"]) == {at.BANNED}


def test_unconfirmed_tier_counts_as_high_for_risk_quantities(result):
    a = _t(result, "aig_tier_assessment")
    hold = a[a["residual_tier"] == at.HOLD]
    assert len(hold) and set(hold["quantity_tier"]) == {"고"}


def test_tier_parameters_are_marked_as_example_settings(result):
    """기관이 승인한 값처럼 보이는 수치가 하나도 없다."""
    p = _t(result, "aig_tier_param")
    assert set(p["setting_status"]) <= {ar.SET_EXAMPLE, ar.SET_STRUCT, ar.SET_UNSET}
    assert (p["setting_status"] == ar.SET_EXAMPLE).sum() > 0
    unset = p[p["setting_status"] == ar.SET_UNSET]
    assert len(unset) and unset["value"].isna().all()
    assert p["basis"].notna().all() and p["unset_handling"].notna().all()


def test_weighted_usage_and_indicator_reconcile(result):
    r = result.agent_risk
    lim = _t(result, "aig_agent_limit")
    k = _t(result, "aig_risk_appetite").set_index(["indicator_id", "measure_seq"])
    assert k.at[("K2", 1), "value"] == pytest.approx(
        lim["weighted_granted"].sum() / r.capital_total)
    assert r.headline["agent_weighted_limit_usage"] == pytest.approx(0.03025, abs=1e-9)
    assert k.at[("K2", 1), "status"] == ar.STATUS_LEVELS[1]
    assert k.at[("K1", 1), "value"] == pytest.approx(5 / 15)
    unset = k[k["status"] == ar.STATUS_UNSET]
    assert set(unset.index.get_level_values(0)) == {"K8"}
    assert unset["breach_level"].isna().all()


def test_internal_addon_never_changes_regulatory_rwa(result):
    r = result.agent_risk
    add = _t(result, "aig_internal_addon").set_index("addon_kind")
    total = add.loc[ar.ADDON_TOTAL]
    assert total["rwa_regulatory"] == pytest.approx(r.rwa_regulatory)
    assert total["rwa_internal"] == pytest.approx(r.rwa_regulatory + total["addon_rwa"])
    # 같은 익스포저에는 (a)·(b) 가운데 큰 값만 반영한다 (익스포저 단위 최댓값의 합).
    f = _t(result, "aig_internal_addon")
    for scope, g in f[f["scope_id"].str.startswith("AGT-")].groupby("scope_id"):
        by = g.set_index("addon_kind")["addon_rwa"]
        assert by[ar.ADDON_APPLIED] >= max(by[ar.ADDON_A], by[ar.ADDON_B]) - 1e-6, scope
        assert by[ar.ADDON_APPLIED] <= by[ar.ADDON_A] + by[ar.ADDON_B] + 1e-6, scope
    applied = f[(f["addon_kind"] == ar.ADDON_APPLIED)]["addon_rwa"].sum()
    assert total["addon_rwa"] == pytest.approx(applied)
    assert r.headline["agent_internal_rwa_addon"] == pytest.approx(total["addon_rwa"])


def test_contagion_sizes_come_from_the_ai_incident_stress(result):
    c = _t(result, "aig_contagion")
    imp = _t(result, "st_ai_impact")
    assert set(c["scenario_id"]) <= set(imp["scenario_id"])
    assert set(c["depth"]) <= set(ar.DEPTH.values())
    cap = _t(result, "aig_internal_addon").set_index("addon_kind").loc[ar.ADDON_C]
    applied = c[c["applied"].astype(bool)]
    assert cap["addon_capital"] == pytest.approx(applied["loss_first_order"].max())


def test_control_links_run_both_ways_and_feed_the_breaker(result):
    link = _t(result, "aig_control_link")
    assert set(link["direction"]) == {ar.TO_HEIMDALL, ar.TO_BIFROST}
    assert link["source_table"].isin({sp.name for sp in cat.ALL_TABLES}).all()
    lim = _t(result, "aig_agent_limit")
    hot = lim[lim["t2_triggered"].astype(bool)]
    assert len(hot) and (hot["utilisation"] > ar.DEFAULT_RISK_PARAMS.t2_utilisation).all()
    assert (lim["breaker_start_stage"].dropna() <= 5).all()
    assert (lim["t10_start_stage"].dropna() <= ar.T10_MAX_STAGE).all()
    k = _t(result, "aig_risk_appetite")
    worst = k[k["indicator_id"].isin(ar.T10_INDICATORS)]["breach_level"].max()
    if worst and worst > 0:
        assert lim["t10_start_stage"].notna().any()


# ---------------------------------------------------------------- 검증 연결

def test_self_validation_carries_the_twelve_agent_checks(result):
    got = {c.name: c for c in result.validation.checks if c.name.startswith("agent_")}
    assert {n: c.status for n, c in got.items()} == AGENT_CHECKS
    assert not any(c.blocks_approval for c in got.values())


def test_headline_figures_are_recalculation_targets(result):
    scope = {row[0] for row in independent.RECALC_SCOPE}
    assert set(AGENT_TARGETS) <= scope
    head = independent._agent_headline(result.ledger_tables)
    assert head == pytest.approx(result.agent_risk.headline)
    assert all(head[k] is not None for k in AGENT_TARGETS)


def test_headline_is_none_without_the_ledgers():
    """원장이 없으면 값을 지어내지 않는다."""
    assert independent._agent_headline({}) == dict.fromkeys(AGENT_TARGETS)


def test_assumptions_disclose_the_synthetic_portfolio_and_example_settings():
    joined = " ".join(independent.KNOWN_ASSUMPTIONS)
    for phrase in ("합성 참조 자료", "예시 설정값", "합성 배정", "조건부 값"):
        assert phrase in joined, phrase


# ---------------------------------------------------------------- 레지스트리 규칙

def test_registry_tier_is_derived_from_the_agent_definition():
    from risk_lib.ui_studio import governance as gov
    a, b = gov.agent_tier_levels("rwa-calculator", "Bash, Read, Write")
    assert at.assess(a, b, fixed=at.fixed_flags(a, b)).inherent == "고"
    # 조회만 하는 에이전트도 내부 기밀 수준 정보와 다단계 수행 때문에 중이다.
    a, b = gov.agent_tier_levels("brand-designer", "Read, Glob")
    assert at.assess(a, b, fixed=at.fixed_flags(a, b)).inherent == "중"
    # 외부 웹 입력은 노출을 올린다.
    assert gov.agent_tier_levels("x", "Read, WebFetch")[1][1] == 3


# ---------------------------------------------------------------- 화면과 영문

@pytest.fixture(scope="module")
def studio(result, portfolio):
    from risk_lib.ui_studio.studio import build_studio
    return build_studio(result, portfolio)


def test_old_ui_carries_the_three_screens_and_full_ledgers(studio):
    from risk_lib.ui_studio.app import decode_payload, render
    html = render(studio)
    for label in SCREENS:
        assert f"'{label}'" in html, label
    data = decode_payload(html)["runs"][studio.asof]["data"]
    for sp in ar.SPECS:
        f = data[sp.name]
        assert f["shown"] == f["total"] == len(studio.tables[sp.name]), sp.name


def test_next_ui_registers_the_screen_with_every_ledger_and_target():
    entry = next(e for e in payload_ext.SCREEN_REGISTRY if e["id"] == "agent-risk")
    assert set(entry["tables"]) == {sp.name for sp in ar.SPECS}
    assert set(entry["recalc"]) == set(AGENT_TARGETS)
    assert set(entry["legacy"]) == set(SCREENS)
    tones = payload_ext.SEVERITY_MAP
    assert set(tones["agent.tier"]) == set(at.TIER_STATES)
    assert set(tones["agent_appetite.status"]) == {ar.STATUS_OK, ar.STATUS_UNSET,
                                                   *ar.STATUS_LEVELS}


def test_english_build_translates_every_new_ledger_string(result):
    """영문 화면(대외 데모의 기본 언어)에 새 원장의 한글이 남지 않는다."""
    tr = export_en.Translator()
    left = []
    for sp in ar.SPECS:
        for s in [sp.korean] + [c.korean for c in sp.columns]:
            if HANGUL.search(tr.text(s)):
                left.append((sp.name, s))
        df = _t(result, sp.name)
        for col in df.columns:
            for v in pd.unique(df[col].dropna()):
                if isinstance(v, str) and HANGUL.search(tr.text(v)):
                    left.append((sp.name, col, v))
    assert not left, left[:10]


def test_exact_only_dictionary_keys_do_not_leak_into_longer_words():
    """'=중' 은 값 전체가 '중' 일 때만 Medium 이다. 다른 낱말 속 '중' 은 건드리지 않는다."""
    tr = export_en.Translator()
    assert tr.text("중") == "Medium"
    assert tr.text("저 / 중 / 고") == "Low / Medium / High"
    assert "Medium" not in tr.text("모델 공급자 집중도")
    assert "Medium" not in tr.text("운영 중")
