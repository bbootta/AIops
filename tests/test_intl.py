"""권역별 가상 기관 원장·생성기·다기관 실행부 시험 (INST-002).

이 시험이 지키려는 것은 셋이다.

1. **익명화가 지켜지는가.** 합성 기관 행은 전부 `data_origin='합성'` 이고
   실존 기관명이 들어갈 자리가 없다. 국내 표본과 화면에서 갈린다.
2. **원장이 값의 유일한 출처인가.** 생성기·엔진 본문에 계수가 없고, 원장을
   바꾸면 산출이 따라 바뀐다.
3. **기관 축이 실제로 산출을 가르는가.** 기관마다 파이프라인을 돌려 서로 다른
   RWA·자본비율·ECL 이 나오고, 각자의 자체검증을 통과한다.

파이프라인 실행은 기관 1곳당 15~30초다. 전 기관을 이 파일에서 돌리면 시험
전체가 4분 이상 길어지므로, 실행이 필요한 시험은 **은행 1곳 + 증권 1곳**
표본으로 좁힌다(`_SAMPLE`). 전 기관 실행은 시험이 아니라 실행 스크립트에서
확인하며, 이 파일은 그 사실을 숨기지 않기 위해 여기 적어 둔다.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

from risk_lib import data_gen_intl as gi
from risk_lib import institutions as inst
from risk_lib.data_gen import generate_portfolio
from risk_lib.datamodel.spec import validate

# 실행 시험이 도는 표본. 은행 1곳과 증권 1곳이면 업권 분기를 다 지난다.
_SAMPLE = ("EU_BANK_01", "NA_SEC_01")
_ASOF = "2025-12-31"
_SEED = 42


# ---------------------------------------------------------------- 원장

@pytest.fixture(scope="module")
def ledgers():
    return gi.build_all()


def test_ledgers_validate_against_specs(ledgers):
    assert gi.validate_ledgers(ledgers) == []


def test_master_has_at_least_eight_institutions_across_regions(ledgers):
    m = ledgers[inst.AXIS_MASTER]
    assert len(m) >= 9                       # 국내 1 + 권역별 8
    regions = set(m["region"])
    assert {"국내", "아시아태평양", "북미", "유럽", "중동아프리카",
            "중남미"} <= regions
    # 요구된 업권 구성: 권역별 은행 1 + 증권 1(아태·북미·유럽), 그 밖 은행 1
    per_region = m.groupby(["region", "institution_type"]).size()
    for r in ("아시아태평양", "북미", "유럽"):
        assert per_region[(r, "은행")] == 1
        assert per_region[(r, "증권")] == 1
    for r in ("중동아프리카", "중남미"):
        assert per_region[(r, "은행")] == 1


def test_domestic_row_is_untouched(ledgers):
    """국내 표본 행은 기관 축 원장이 만든 그대로여야 한다."""
    base = inst.build_inst_master()
    got = ledgers[inst.AXIS_MASTER]
    got = got[got["institution_code"] == inst.PRIMARY_INSTITUTION]
    # dtype 은 비교하지 않는다. 국외 행이 붙으면서 name_ko 가 object 로 넓어지는
    # 것은 값의 변화가 아니다. 값이 하나라도 다르면 여기서 걸린다.
    pd.testing.assert_frame_equal(base.reset_index(drop=True),
                                  got.reset_index(drop=True),
                                  check_dtype=False)


def test_synthetic_rows_are_marked_synthetic(ledgers):
    m = ledgers[inst.AXIS_MASTER]
    synth = m[m["institution_code"] != inst.PRIMARY_INSTITUTION]
    assert (synth["data_origin"] == gi.SYNTHETIC_ORIGIN).all()
    assert (synth["evidence_status"] == gi.SYNTHETIC_EVIDENCE).all()
    for name in (gi.INST_PORTFOLIO_MIX.name, gi.INST_COUNTRY_MIX.name,
                 gi.INST_PROFILE.name):
        t = ledgers[name]
        s = t[t["institution_code"] != inst.PRIMARY_INSTITUTION]
        assert (s["data_origin"] == gi.SYNTHETIC_ORIGIN).all(), name
        assert (s["evidence_status"] == gi.SYNTHETIC_EVIDENCE).all(), name


def test_names_follow_domestic_foreign_rule(ledgers):
    assert inst.check_names(ledgers[inst.AXIS_MASTER]) == []
    m = ledgers[inst.AXIS_MASTER]
    foreign = m[~m["is_domestic"].astype(bool)]
    assert foreign["name_en"].notna().all()
    # 국외 기관명은 영문만 쓴다. 한글이 섞이면 감독 제출본과 대조가 되지 않는다.
    assert not foreign["name_en"].str.contains(r"[가-힣]").any()


def test_seed_offsets_are_unique_and_domestic_stays_zero(ledgers):
    offsets = inst.seed_offsets(ledgers[inst.AXIS_MASTER])
    assert offsets[inst.PRIMARY_INSTITUTION] == 0
    assert len(set(offsets.values())) == len(offsets)


def test_country_mix_weights_sum_to_one_and_regions_do_not_overlap(ledgers):
    cm = ledgers[gi.INST_COUNTRY_MIX.name]
    m = ledgers[inst.AXIS_MASTER].set_index("institution_code")
    for code, sub in cm.groupby("institution_code"):
        assert abs(float(sub["weight"].sum()) - 1.0) < 1e-9, code
    # 권역이 다르면 국가군이 겹치지 않는다.
    by_region: dict[str, set[str]] = {}
    for code, sub in cm.groupby("institution_code"):
        by_region.setdefault(str(m.loc[code, "region"]), set()).update(sub["country"])
    regions = sorted(by_region)
    for i, a in enumerate(regions):
        for b in regions[i + 1:]:
            assert not (by_region[a] & by_region[b]), (a, b)


def test_domestic_has_no_country_mix_rows(ledgers):
    """국내 표본에 국가 재배정을 걸면 기존 (asof, seed) 산출이 바뀐다."""
    cm = ledgers[gi.INST_COUNTRY_MIX.name]
    assert (cm["institution_code"] != inst.PRIMARY_INSTITUTION).all()


def test_lexicon_covers_every_generated_code(ledgers):
    lex = ledgers[gi.INTL_LABEL_LEXICON.name]
    base = generate_portfolio(seed=_SEED)
    for lang in gi.LANGUAGES:
        sectors = set(lex[(lex.language == lang)
                          & (lex.label_kind == "sector")]["label_code"])
        assert set(base["sector"]) <= sectors, lang
        for kind in ("product", "obligor_affix"):
            codes = set(lex[(lex.language == lang)
                            & (lex.label_kind == kind)]["label_code"])
            assert set(base["asset_class"]) <= codes, (lang, kind)


def test_lexicon_is_not_institution_scoped():
    """어휘는 언어에 딸린다. 기관마다 복제하면 같은 낱말이 갈라진다."""
    assert "institution_code" not in gi.INTL_LABEL_LEXICON.column_names


# ---------------------------------------------------------------- 생성기

def test_domestic_portfolio_is_numerically_unchanged():
    """국내 표본은 라벨만 붙고 숫자는 그대로여야 한다."""
    got = gi.generate_institution_portfolio(inst.PRIMARY_INSTITUTION,
                                            seed=_SEED)
    base = generate_portfolio(seed=_SEED)
    assert len(got) == len(base)
    for col in base.columns:
        a, b = got[col], base[col]
        if pd.api.types.is_numeric_dtype(b):
            assert np.allclose(a.astype(float), b.astype(float),
                               equal_nan=True), col
        else:
            assert (a.fillna("∅").values == b.fillna("∅").values).all(), col


def test_every_generated_exposure_is_marked_synthetic():
    """익스포저 표기는 그 행을 만든 경로를 가리켜야 한다.

    국내 표본의 익스포저도 `data_gen.generate_portfolio` 가 만든 합성 행이다.
    프로파일 원장의 등록 경로('수기등록')를 그대로 옮기면 배포되는 유일한
    기관의 전 포트폴리오가 사람이 등록한 실데이터로 표시되고, 합성 행을
    거르는 쪽은 그 전건을 놓친다.
    """
    for code in (inst.PRIMARY_INSTITUTION, "EU_BANK_01"):
        p = gi.generate_institution_portfolio(code, seed=_SEED)
        assert (p["data_origin"] == gi.SYNTHETIC_ORIGIN).all(), code
        assert (p["evidence_status"] == gi.SYNTHETIC_EVIDENCE).all(), code
        assert not p.empty, code
    # 프로파일 원장의 국내 표본 행은 별개다. 그 값은 사람이 옮겨 적은 상수이며
    # 그 사실이 바뀌면 이 시험이 아니라 원장 쪽을 다시 봐야 한다.
    prow = gi.profile_row(inst.PRIMARY_INSTITUTION)
    assert str(prow["data_origin"]) == "수기등록"


def test_domestic_labels_are_korean_and_foreign_labels_are_english():
    dom = gi.generate_institution_portfolio(inst.PRIMARY_INSTITUTION,
                                            seed=_SEED)
    fgn = gi.generate_institution_portfolio("EU_BANK_01", seed=_SEED)
    hangul = r"[가-힣]"
    for col in ("sector_label", "product_label", "obligor_name"):
        assert dom[col].str.contains(hangul).all(), col
        assert not fgn[col].str.contains(hangul).any(), col


def test_foreign_countries_come_from_the_country_ledger():
    led = gi.build_all()
    cm = led[gi.INST_COUNTRY_MIX.name]
    for code in ("APAC_BANK_01", "LATAM_BANK_01"):
        p = gi.generate_institution_portfolio(code, seed=_SEED)
        allowed = set(cm[cm["institution_code"] == code]["country"])
        assert set(p["country"]) <= allowed, code


def test_generator_is_deterministic_for_fixed_seed():
    a = gi.generate_institution_portfolio("MEA_BANK_01", seed=_SEED)
    b = gi.generate_institution_portfolio("MEA_BANK_01", seed=_SEED)
    pd.testing.assert_frame_equal(a, b)


def test_different_institutions_get_different_streams():
    a = gi.generate_institution_portfolio("APAC_BANK_01", seed=_SEED)
    b = gi.generate_institution_portfolio("NA_BANK_01", seed=_SEED)
    assert len(a) == len(b)                      # 같은 유형, 같은 건수
    assert not np.allclose(a["ead"].to_numpy(), b["ead"].to_numpy())


def test_ledger_counts_and_scales_drive_the_generator():
    """원장을 바꾸면 산출이 따라 바뀐다. 생성기 본문에 수가 없다는 증거다."""
    led = gi.build_all()
    code = "MEA_BANK_01"
    base = gi.generate_institution_portfolio(code, seed=_SEED, **_kw(led))
    mix = led[gi.INST_PORTFOLIO_MIX.name].copy()
    row = (mix["institution_code"] == code) & (mix["asset_class"] == "corporate")
    mix.loc[row, "n_exposures"] = int(mix.loc[row, "n_exposures"].iloc[0]) + 100
    mix.loc[row, "ead_scale"] = float(mix.loc[row, "ead_scale"].iloc[0]) * 2.0
    led2 = dict(led, **{gi.INST_PORTFOLIO_MIX.name: mix})
    got = gi.generate_institution_portfolio(code, seed=_SEED, **_kw(led2))
    assert len(got) == len(base) + 100
    corp_base = base[base.asset_class == "corporate"]["ead"].mean()
    corp_got = got[got.asset_class == "corporate"]["ead"].mean()
    assert corp_got > corp_base * 1.5


def _kw(led):
    return {"master": led[inst.AXIS_MASTER],
            "profile": led[gi.INST_PROFILE.name],
            "mix": led[gi.INST_PORTFOLIO_MIX.name],
            "country_mix": led[gi.INST_COUNTRY_MIX.name],
            "lexicon": led[gi.INTL_LABEL_LEXICON.name]}


def test_unknown_institution_is_refused():
    with pytest.raises(ValueError):
        gi.generate_institution_portfolio("NOWHERE_01", seed=_SEED)


# ---------------------------------------------------------------- 엔진 배선

def test_market_op_params_come_from_the_profile_ledger():
    from risk_lib.pipeline import _stage_market_op_rwa
    p_bank = gi.market_op_params("EU_BANK_01")
    p_sec = gi.market_op_params("EU_SEC_01")
    assert p_sec["share_equity"] > p_bank["share_equity"]
    mkt_b, op_b, _pos, _bi, _n = _stage_market_op_rwa(_SEED, p_bank)
    mkt_s, op_s, _pos, _bi, _n = _stage_market_op_rwa(_SEED, p_sec)
    # 모수가 다르면 산출이 다르다. 같으면 엔진이 원장을 안 읽은 것이다.
    assert mkt_b.rwa != mkt_s.rwa
    assert op_b.rwa != op_s.rwa


def test_domestic_profile_reproduces_the_incumbent_market_op_numbers():
    """국내 표본 모수는 기관 축을 붙이기 전 엔진이 쓰던 값과 같아야 한다."""
    from risk_lib.pipeline import _stage_market_op_rwa
    p = gi.market_op_params(gi.BASE_INSTITUTION)
    mkt, op, pos, bi, notional = _stage_market_op_rwa(_SEED, p)
    rng = np.random.default_rng(_SEED + 7100)
    expected = 1.0e13 * float(rng.uniform(0.95, 1.05))
    assert notional == pytest.approx(expected)
    assert float(pos["net_position"].iloc[0]) == pytest.approx(expected * 0.02)
    assert bi.fc == pytest.approx(expected * 0.005)


def test_capital_ledger_comes_from_the_profile_ledger():
    """자본은 산출물이 아니라 입력이다. 합성 기관은 원장이 자본을 준다."""
    ead = 1.0e13
    stack = gi.capital_ledger_for("EU_BANK_01", ead)
    row = gi.profile_row("EU_BANK_01")
    assert stack is not None
    assert stack.cet1 == pytest.approx(float(row["cet1_to_ead"]) * ead)
    assert stack.tier2 == pytest.approx(float(row["tier2_to_ead"]) * ead)


def test_domestic_sample_keeps_the_profitability_fallback():
    """국내 표본에 자본 비율을 채우면 기존 산출이 재현되지 않는다."""
    assert gi.capital_ledger_for(gi.BASE_INSTITUTION, 1.0e13) is None


def _capital_source_check(stack, basis):
    from risk_lib.validation.consistency import (
        ValidationReport, _check_capital_source)
    rep = ValidationReport()
    _check_capital_source("ledger", stack, 1.0e13, rep, basis)
    hit = [c for c in rep.checks if c.name == "capital_source"]
    assert len(hit) == 1, basis
    return hit[0]


def test_ratio_built_capital_is_not_recorded_as_an_observed_ledger():
    """원장에서 왔다는 것만으로 capital_source 가 PASS 로 꺼지면 안 된다.

    이 원장의 자본은 `cet1_to_ead` × 총익스포저라 규모 비례분이 100% 다.
    독립검증 F-201·F-202 가 가리키는 상태가 가장 강할 때 검사가 PASS 로
    꺼지면 그 검사는 그 상태를 한 번도 드러내지 못한다. 산출근거를 아예 안
    넘긴 실행도 마찬가지다. 통과시키면 근거를 생략하는 것이 검사를 끄는
    가장 쉬운 길이 된다.
    """
    from risk_lib.validation.consistency import RATIO_TO_EAD_BASIS
    assert gi.CAPITAL_BASIS == RATIO_TO_EAD_BASIS
    stack = gi.capital_ledger_for("EU_BANK_01", 1.0e13)

    by_ratio = _capital_source_check(stack, gi.CAPITAL_BASIS)
    assert by_ratio.status == "WARN"
    assert "규모 비례분 100%" in by_ratio.detail

    blank = _capital_source_check(stack, None)
    assert blank.status == "WARN"
    for phrase in ("합성기 미사용", "실제 자본 원장"):
        assert phrase not in blank.detail
        assert phrase not in by_ratio.detail

    # 근거를 댈 수 있는 주입만 통과하고, 통과할 때도 그 근거를 적는다.
    named = _capital_source_check(stack, "감독제출_자본원장")
    assert named.status == "PASS"
    assert "감독제출_자본원장" in named.detail


def test_pipeline_defaults_read_the_ledger_not_a_literal():
    """`run_pipeline` 기본 완충자본은 원장의 국내 표본 행과 같아야 한다."""
    import inspect
    from risk_lib import pipeline
    src = inspect.getsource(pipeline.run_pipeline)
    assert "capital_conservation\": 0.025" not in src
    assert gi.buffers_for(gi.BASE_INSTITUTION) == {
        "capital_conservation": 0.025, "countercyclical": 0.0, "dsib": 0.01}


# ---------------------------------------------------------------- 다기관 실행

@pytest.fixture(scope="module")
def multi():
    from risk_lib.pipeline import run_multi_institution
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return run_multi_institution(codes=_SAMPLE, seed=_SEED, asof=_ASOF)


# PD 모형 변별력 계열. 합성 생성기의 기업 부도율이 1% 미만이라 표본 부도건수가
# 적고, 표본외 Gini 추정치의 산포가 하한(0.2) 근처를 덮는다. 기업 건수를
# 800에서 20,000까지 올려 9개 기관 × 3개 세그먼트를 재보니 어느 크기에서도
# 27쌍 전부가 하한을 넘지는 않았다. 검사를 통과시키려고 시드 오프셋이나 표본
# 크기를 고르는 것은 검사에 데이터를 맞추는 일이라 하지 않았다. 그래서 이
# 계열은 실패를 **드러내고** 나머지 계열에만 무실패를 요구한다.
_MODEL_DISCRIMINATION = ("pd_gini_", "pd_backtest_zones")


def _failed(run) -> list[str]:
    fr = run.result.validation.to_frame()
    return list(fr[fr["status"] == "FAIL"]["name"])


def test_no_institution_fails_outside_the_model_discrimination_family(multi):
    """자본·유동성·한도·정합성 계열은 기관마다 전부 통과해야 한다."""
    leftover = {c: [n for n in _failed(r)
                    if not n.startswith(_MODEL_DISCRIMINATION)]
                for c, r in multi.runs.items()}
    assert not any(leftover.values()), leftover
    assert (multi.validation["n_checks"] > 50).all()


def test_model_discrimination_failures_are_surfaced_not_swallowed(multi):
    """변별력 실패가 있으면 집계표의 FAIL 수에 그대로 잡혀야 한다."""
    v = multi.validation.set_index("institution_code")
    for code, run in multi.runs.items():
        assert int(v.loc[code, "FAIL"]) == len(_failed(run))
        assert bool(v.loc[code, "passes"]) == (len(_failed(run)) == 0)


def test_headline_is_one_row_per_institution_with_no_total(multi):
    """규제자본은 기관 단위 지표다. 통화가 다른 기관을 더한 수는 뜻이 없다."""
    h = multi.headline
    assert list(h["institution_code"]) == list(_SAMPLE)
    assert len(h) == len(multi.runs) == len(_SAMPLE)
    # 각 행의 금액은 그 기관 포트폴리오만으로 설명돼야 한다. 기관이 섞이면
    # 여기서 갈린다.
    for r in h.itertuples():
        run = multi.runs[r.institution_code]
        assert float(r.total_ead) == pytest.approx(
            float(run.portfolio["ead"].sum()))
        assert float(r.ecl_total) == pytest.approx(
            float(run.result.ecl["total"]))


def test_institutions_produce_different_capital_outcomes(multi):
    h = multi.headline.set_index("institution_code")
    a, b = _SAMPLE
    for col in ("rwa_final", "cet1_ratio", "ecl_total", "market_op_share"):
        assert h.loc[a, col] != h.loc[b, col], col


def test_securities_carries_a_larger_market_and_op_share(multi):
    h = multi.headline.set_index("institution_code")
    bank = h[h["institution_type"] == "은행"]["market_op_share"].max()
    sec = h[h["institution_type"] == "증권"]["market_op_share"].min()
    assert sec > bank


def test_capital_source_is_disclosed_per_institution(multi):
    """어느 기관이 원장 자본을 썼고 어느 기관이 합성기를 썼는지 결과가 말한다."""
    for code, run in multi.runs.items():
        fr = run.result.validation.to_frame()
        hit = fr[fr["name"] == "capital_source"]
        assert len(hit) == 1, code
        # 표본은 전부 합성 기관이므로 원장 자본을 쓴다.
        assert "원장" in str(hit.iloc[0]["detail"]), code


def test_result_meta_names_its_institution(multi):
    for code, run in multi.runs.items():
        assert run.result.meta["institution_code"] == code
        assert run.result.meta["asof"] == _ASOF
        assert run.result.meta["asof_source"] == "explicit"


def test_ledgers_carry_the_institution_code(multi):
    from risk_lib.pipeline import institution_ledgers
    code = _SAMPLE[0]
    stamped = institution_ledgers(multi.runs[code])
    assert stamped
    scoped = [n for n in stamped if inst.is_institution_scoped(n)]
    assert scoped
    for name in scoped:
        df = stamped[name]
        if df.empty:
            continue
        assert inst.INSTITUTION_COLUMN in df.columns, name
        assert set(df[inst.INSTITUTION_COLUMN]) == {code}, name


def test_stamped_ledgers_match_the_institution_axis_spec(multi):
    """축을 적용한 파생 스펙에 대조한다. 컬럼이 빠지면 여기서 걸린다."""
    from risk_lib.datamodel import catalog as cat
    from risk_lib.pipeline import institution_ledgers
    axis = {s.name: s for s in cat.inst_axis_tables()}
    stamped = institution_ledgers(multi.runs[_SAMPLE[0]])
    checked = 0
    violations = []
    for name, df in stamped.items():
        spec = axis.get(name)
        if spec is None or df.empty:
            continue
        checked += 1
        violations += [v for v in validate(df, spec)
                       if v.rule in ("missing_column", "null_in_not_null")
                       and v.column == inst.INSTITUTION_COLUMN]
    assert checked > 50
    assert violations == []


def test_foreign_output_labels_stay_english(multi):
    sec = [c for c in _SAMPLE if c.endswith("SEC_01")][0]
    port = multi.runs[sec].portfolio
    assert not port["obligor_name"].str.contains(r"[가-힣]").any()
    assert not port["sector_label"].str.contains(r"[가-힣]").any()


def test_timing_is_measured_and_reported(multi):
    t = multi.timing
    assert set(t["institution_code"]) == set(_SAMPLE)
    assert (t["elapsed_sec"] > 0).all()


def test_rerunning_one_institution_reproduces_the_headline(multi):
    """(asof, seed) 가 같으면 같은 값이다. 벽시계가 섞이면 여기서 갈린다."""
    from risk_lib.pipeline import run_multi_institution
    code = _SAMPLE[1]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        again = run_multi_institution(codes=(code,), seed=_SEED, asof=_ASOF)
    a = multi.headline.set_index("institution_code").loc[code]
    b = again.headline.set_index("institution_code").loc[code]
    for col in ("rwa_final", "cet1_ratio", "leverage_ratio", "ecl_total"):
        assert float(a[col]) == pytest.approx(float(b[col]), rel=0, abs=0), col


def test_shared_reference_macro_indicator_does_not_split_by_institution(multi):
    """공유 참조 판정은 "기관이 달라도 값이 같다" 는 주장이다. 확인한다.

    `macro_indicator` 에는 기관코드가 없고 기본키가 (indicator_id, period) 다.
    산출 경로가 기관 시드를 타면 같은 기본키에 기관마다 다른 값이 생기고 두
    기관 원장을 합칠 때 한쪽이 조용히 덮인다. 그래서 계열은 기관 오프셋을
    더하기 전 시드로 만든다. 그 배선이 끊기면 여기서 실패한다.
    """
    from risk_lib.datamodel.materialize_detail import materialize_stress_trace
    by_inst = {
        code: {"macro_indicator": materialize_stress_trace(
            run.result, run.portfolio, {})["macro_indicator"]}
        for code, run in multi.runs.items()}
    assert inst.check_shared_reference_agreement(by_inst) == []
    a, b = (by_inst[c]["macro_indicator"] for c in _SAMPLE)
    assert len(a) == len(b) > 0
    assert list(a["value"]) == list(b["value"])
    # 판정이 성립하는 이유는 산출 경로가 기관 오프셋 전 시드를 넘기기 때문이다.
    # 기관 시드는 기관마다 다르다는 사실은 그대로다.
    for code, run in multi.runs.items():
        assert int(run.result.meta["base_seed"]) == _SEED, code
        assert int(run.result.meta["seed"]) != _SEED, code


# ----------------------------------------------- 적용범위 판정을 값으로 확인
#
# 판정 검사가 문서 대조(`docs/기관축_적용범위.md`)에만 걸리면, 문서는
# `scope_markdown()` 의 출력이라 코드를 고치고 문서를 다시 생성하는 것만으로
# 통과한다. 기관 종속 표를 공유 참조로 옮겨도 그 상태에서는 아무 검사도
# 걸리지 않았다. 여기서는 두 기관을 실제로 돌린 원장을 맞대고, 공유 참조로
# 분류된 표에서 값이 갈리면 실패한다.

@pytest.fixture(scope="module")
def by_institution(multi):
    """기관별 실체화 원장 한 벌. 실행은 `multi` 것을 쓰고 실체화만 더한다."""
    from risk_lib.datamodel.materialize import materialize_all
    from risk_lib.datamodel.materialize_detail import materialize_detail

    out: dict[str, dict] = {}
    for code, run in multi.runs.items():
        t: dict = {}
        t.update(run.result.rdm_base)
        t.update(run.result.alm_tables)
        t.update(run.result.ledger_tables)
        if run.result.structured is not None:
            t.update(run.result.structured.tables)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            t.update(materialize_all(run.result, run.portfolio))
            t.update(materialize_detail(run.result, run.portfolio, dict(t)))
        out[code] = t
    return out


def test_no_shared_reference_ledger_splits_by_institution(by_institution):
    """공유 참조로 분류된 표는 두 기관의 값이 실제로 같아야 한다."""
    assert inst.check_shared_reference_agreement(by_institution) == []


def test_the_comparison_reaches_the_headline_output_ledgers(by_institution):
    """대조 범위가 줄면 오분류를 잡을 수 없다. 어디까지 닿는지 적어 둔다."""
    common = set.intersection(*(set(t) for t in by_institution.values()))
    for name in ("rwa_result", "ecl_result", "cap_stack", "val_check",
                 "rdm_exposure", "alm_irrbb_result", "lex_position",
                 "macro_indicator"):
        assert name in common, f"{name} 이 대조 범위 밖이다"
    split = [n for n in sorted(common) if inst.is_institution_scoped(n)
             and not _same(by_institution, n)]
    assert len(split) >= 100, (
        f"기관마다 값이 갈리는 표가 {len(split)}장뿐이다. 대조 범위가 줄었거나 "
        "산출이 기관을 타지 않는다")


def _same(by_institution, name: str) -> bool:
    frames = [t[name].reset_index(drop=True) for t in by_institution.values()]
    return all(f.equals(frames[0]) for f in frames[1:])


@pytest.mark.parametrize("name", ["rwa_result", "ecl_result", "cap_stack",
                                  "rdm_exposure"])
def test_a_misclassified_output_ledger_is_caught_by_the_data(
        by_institution, monkeypatch, name):
    """산출 원장을 공유 참조로 옮기면 여기서 걸린다. 통과가 상시면 통제가 아니다.

    이 검사가 없던 때는 `rwa_result` 를 공유 참조 목록에 넣어도 판정 검사
    일곱 중 하나(문서 대조)만 걸렸고, 문서를 다시 생성하면 그마저 통과했다.
    """
    monkeypatch.setitem(inst.SHARED_REFERENCE_TABLES, name,
                        "시험이 일부러 넣은 오분류다. 값으로 걸려야 한다.")
    v = inst.check_shared_reference_agreement(by_institution)
    assert [x.table for x in v] == [name], v


# ------------------------------------------------- 기관 배선 회귀 (적대적 검증)
#
# 아래 네 묶음은 "기관 축은 세웠는데 산출 경로가 그 원장을 읽지 않는다" 는
# 지적에 대응한다. 지적이 되살아나면 여기서 실패한다.
#
#   구조화   `_stage_structured` 가 (asof, seed) 만 받아 최종 RWA 의 19~31%가
#            기관과 무관하게 국내 표본 규모감으로 붙었다.
#   시장운영 케이스 스터디 3사가 국내 표본 행(명목 10조)을 공유했다.
#   완충     `bis_deep` 호출부에 DSIB 등급 2 와 P2R·P2G 가 박혀 있어 같은
#            기관에 요구 CET1 이 두 벌 나왔다. 국가별 익스포저도 고정이었다.
#   업권     업권이 산출 분기에도 경고에도 닿지 않아 증권 기관 결과가 은행
#            건전성 지표로 공시됐다.


def test_structured_stage_cannot_run_without_the_ledger_scale():
    """(asof, seed) 만으로 돌던 서명으로 되돌아가면 여기서 걸린다."""
    import inspect
    from datetime import date as _date
    from risk_lib.pipeline import _stage_structured
    assert list(inspect.signature(_stage_structured).parameters) == [
        "asof", "seed", "scale"]
    with pytest.raises(TypeError):
        _stage_structured(_date(2025, 12, 31), _SEED)


def test_structured_rwa_scales_with_the_profile_ledger():
    """같은 시드라도 원장 배수가 다르면 구조화 RWA 가 그만큼 달라야 한다."""
    from datetime import date as _date
    from risk_lib.pipeline import _stage_structured
    asof = _date.fromisoformat(_ASOF)
    base = _stage_structured(asof, _SEED, {"fund_scale": 1.0, "sec_scale": 1.0})
    twice = _stage_structured(asof, _SEED, {"fund_scale": 2.0, "sec_scale": 2.0})
    assert twice.rwa_internal == pytest.approx(2.0 * base.rwa_internal)
    # 국내 표본 배수는 1.0 이므로 기관 축을 붙이기 전 값과 같아야 한다.
    assert gi.structured_scale_for(gi.BASE_INSTITUTION) == {
        "fund_scale": 1.0, "sec_scale": 1.0}
    # 재고정: 기업 B등급 RW 100% -> 150% (CRE20.34). 펀드 look-through 의 기업
    # B등급 지분이 움직여 4,128.3십억 -> 4,137.9십억. 총 RWA 증분 9.54십억이
    # 전부 여기서 나왔다 (직접 보유 기업 익스포저에는 B등급이 없다).
    assert base.rwa_internal == pytest.approx(4137877287710.5225, rel=0, abs=1.0)


def test_structured_rwa_in_the_headline_comes_from_the_institution_scale(
        multi, ledgers):
    """헤드라인의 구조화 RWA 를 원장 배수로 **독립하게** 세워 대조한다.

    이전 판은 헤드라인을 같은 `_stage_structured` 에 같은 배수를 넣어 다시
    돌린 값과 맞대었다. 그러면 `_stage_structured` 가 배수를 통째로 버려도
    양변이 함께 무너져 통과한다. 재검증이 그 변조를 주입해 통과를 확인했다.
    재계산 대조는 통제가 아니다.

    여기서는 배수 1.0 의 값만 엔진에서 받고, 기대값은 **원장 컬럼에서 직접
    읽은 배수**로 시험이 세운다.

        기대 = fund_scale × (배수 1.0 의 fund_rwa)
             + sec_scale  × (배수 1.0 의 sec_rwa_internal)

    배수를 버리는 변조가 들어오면 헤드라인은 배수 1.0 값이 되고 기대값과
    어긋난다(EU_BANK_01 은 6,399,895,242,737 대 4,204,717,131,288).
    엔진 안의 배수 적용이 선형이라는 사실 자체는
    `test_structured_rwa_scales_with_the_profile_ledger` 가 따로 고정한다.
    """
    from datetime import date as _date
    from risk_lib.pipeline import _stage_structured
    master = ledgers[inst.AXIS_MASTER]
    profile = ledgers[gi.INST_PROFILE.name].set_index("institution_code")
    unit = {"fund_scale": 1.0, "sec_scale": 1.0}
    h = multi.headline.set_index("institution_code")
    for code in _SAMPLE:
        fund_scale = float(profile.loc[code, "fund_scale"])
        sec_scale = float(profile.loc[code, "sec_scale"])
        # 배수가 1.0 이면 "배수를 버린 값" 과 기대값이 같아져 대조가 성립하지
        # 않는다. 표본 기관이 그런 배수를 갖게 되면 여기서 먼저 걸린다.
        assert fund_scale != 1.0 and sec_scale != 1.0, code
        # 헤드라인이 읽는 인자 생성기도 원장 그대로여야 한다.
        assert gi.structured_scale_for(code, ledgers[gi.INST_PROFILE.name]) == {
            "fund_scale": fund_scale, "sec_scale": sec_scale}, code
        base = _stage_structured(
            _date.fromisoformat(_ASOF),
            inst.institution_seed(_SEED, code, master), unit)
        expected = fund_scale * base.fund_rwa + sec_scale * base.sec_rwa_internal
        got = float(h.loc[code, "rwa_structured"])
        assert got == pytest.approx(expected, rel=1e-12), code
        # 배수를 버린 값(= 배수 1.0 값)과는 반드시 달라야 한다.
        assert got != pytest.approx(base.rwa_internal, rel=1e-9), code
    # 배수가 다른 두 기관이면 값도 갈린다.
    a, b = _SAMPLE
    assert (float(profile.loc[a, "fund_scale"]),
            float(profile.loc[a, "sec_scale"])) != (
        float(profile.loc[b, "fund_scale"]), float(profile.loc[b, "sec_scale"]))
    assert h.loc[a, "rwa_structured"] != h.loc[b, "rwa_structured"]


def test_case_study_banks_do_not_borrow_the_domestic_market_op_row(monkeypatch):
    """케이스 스터디 3사가 각자의 공시 총여신으로 시장·운영 명목을 받는가.

    이전에는 `market_op` 를 안 넘겨 파이프라인이 국내 표본 행(명목 10조)을
    읽었고, 총여신 46.9조·18.4조·15.35조인 세 은행이 같은 시장 RWA 를 받았다.
    """
    from risk_lib import case_studies as cs
    seen: list[dict] = []

    def _capture(portfolio, **kw):
        seen.append(kw)
        return object()

    monkeypatch.setattr("risk_lib.pipeline.run_pipeline", _capture)
    for p in cs.BANKS:
        cs.run_bank_stress(p, seed=_SEED)
    assert len(seen) == len(cs.BANKS)
    notionals = [kw["market_op"]["mkt_notional_base"] for kw in seen]
    assert notionals == [p.total_loans_krw for p in cs.BANKS]
    assert len(set(notionals)) == len(notionals)
    # 업권도 함께 넘어가야 자체검증이 어느 체계 기준인지 적을 수 있다.
    assert {kw["institution_type"] for kw in seen} == {cs.INSTITUTION_TYPE}
    assert cs.INSTITUTION_TYPE in inst.INSTITUTION_TYPES


def test_case_study_market_op_rwa_differs_across_the_three_banks():
    """모수가 다르면 산출도 달라야 한다. 같으면 원장을 안 읽은 것이다."""
    from risk_lib import case_studies as cs
    from risk_lib.pipeline import _stage_market_op_rwa
    out = []
    for p in cs.BANKS:
        mkt, op, _pos, _bi, _n = _stage_market_op_rwa(
            _SEED, cs.market_op_for(p))
        out.append((mkt.rwa, op.rwa))
    assert len(set(out)) == len(out)
    # 총여신이 큰 은행이 더 큰 시장 RWA 를 받는다.
    order = sorted(range(len(cs.BANKS)),
                   key=lambda i: cs.BANKS[i].total_loans_krw)
    assert [out[i][0] for i in order] == sorted(out[i][0] for i in order)


def test_buffer_layering_and_capital_ratio_share_one_requirement(multi):
    """한 기관에 요구 CET1 이 두 벌 나오면 안 된다.

    `compute_bis_ratios` 의 required 와 `bis_deep` 의 계층(P1+CBR)은 같은
    완충 원장에서 나와야 한다. 이전에는 계층 쪽에 DSIB 등급 2(1.5%)가 박혀
    있어 완충 원장이 0 인 증권 기관에서 1.5%p 어긋났다.
    """
    for code, run in multi.runs.items():
        lay = run.result.bis_deep.layering
        buf = run.result.meta["buffers"]
        assert lay.dsib == pytest.approx(buf["dsib"]), code
        assert lay.countercyclical == pytest.approx(buf["countercyclical"]), code
        assert lay.capital_conservation == pytest.approx(
            buf["capital_conservation"]), code
        cbr = lay.capital_conservation + lay.countercyclical + lay.dsib
        assert lay.p1_cet1 + cbr == pytest.approx(
            float(run.result.bis.required["cet1"])), code


def test_pillar2_layers_come_from_the_ledger_not_the_source(multi):
    """P2R·P2G 는 원장에서 온다. 원장에 없으면 0 이고 그 사실이 검증에 남는다."""
    import inspect
    from risk_lib import pipeline
    src = inspect.getsource(pipeline.run_pipeline)
    assert "dsib_bucket=2" not in src
    assert "p2r=0.015" not in src
    assert "p2g=0.010" not in src
    for code, run in multi.runs.items():
        p2 = run.result.meta["pillar2"]
        lay = run.result.bis_deep.layering
        assert lay.p2r == pytest.approx(0.0 if p2.get("p2r") is None
                                        else float(p2["p2r"])), code
        assert lay.p2g == pytest.approx(0.0 if p2.get("p2g") is None
                                        else float(p2["p2g"])), code
        fr = run.result.validation.to_frame()
        assert len(fr[fr["name"] == "pillar2_requirement_evidence"]) == 1, code


def test_country_ccyb_reads_the_institution_portfolio(multi):
    """국가가중 CCyB 의 국가 배분이 그 기관의 포트폴리오와 같아야 한다.

    이전에는 KR 80%/US 8%/JP 5%/CN 5%/VN 2% 로 고정한 배분을 넘겼고, 그 배분은
    어느 기관의 원장과도 대조되지 않았다.
    """
    for code, run in multi.runs.items():
        by = run.result.bis_deep.country_ccyb["by_country"]
        assert not by.empty, code
        assert set(by["country"]) == set(run.portfolio["country"].unique()), code
        for row in by.itertuples():
            assert float(row.exposure) == pytest.approx(float(
                run.portfolio[run.portfolio["country"] == row.country]
                ["ead"].sum()), rel=1e-9), (code, row.country)


def test_headline_says_which_prudential_regime_applies(multi):
    """증권 기관의 은행 기준 비율이 그 기관의 건전성 지표로 읽히면 안 된다."""
    h = multi.headline.set_index("institution_code")
    for code in _SAMPLE:
        itype = str(h.loc[code, "institution_type"])
        assert h.loc[code, "prudential_regime"] == inst.prudential_regime(itype)
        assert bool(h.loc[code, "ratio_applicable"]) == inst.regime_applies(itype)
        if not inst.regime_applies(itype):
            assert "참고치" in str(h.loc[code, "ratio_basis"])
            assert inst.prudential_regime(itype) in str(h.loc[code, "ratio_basis"])
    # 표본에 은행과 증권이 하나씩 있어야 이 시험이 뜻을 갖는다.
    assert set(h["institution_type"]) == {"은행", "증권"}


def test_every_run_records_the_regime_gap_in_its_own_validation(multi):
    """업권이 산출에 반영되지 않았다는 사실을 산출물이 스스로 들고 있어야 한다."""
    h = multi.headline.set_index("institution_code")
    for code, run in multi.runs.items():
        fr = run.result.validation.to_frame()
        hit = fr[fr["name"] == "prudential_regime_applies"]
        assert len(hit) == 1, code
        itype = str(h.loc[code, "institution_type"])
        assert str(hit.iloc[0]["status"]) == (
            "PASS" if inst.regime_applies(itype) else "WARN"), code
        if not inst.regime_applies(itype):
            assert inst.prudential_regime(itype) in str(hit.iloc[0]["detail"])
