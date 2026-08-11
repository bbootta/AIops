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
    pd.testing.assert_frame_equal(base.reset_index(drop=True),
                                  got.reset_index(drop=True))


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


def test_each_institution_passes_its_own_consistency_checks(multi):
    assert multi.failing() == [], multi.validation.to_string()
    assert (multi.validation["FAIL"] == 0).all()
    assert (multi.validation["n_checks"] > 50).all()


def test_headline_is_one_row_per_institution_with_no_total(multi):
    h = multi.headline
    assert list(h["institution_code"]) == list(_SAMPLE)
    assert h["institution_code"].is_unique
    # 합계 행을 만들면 통화가 다른 기관을 더한 수가 화면에 오른다.
    assert not h["institution_code"].astype(str).str.contains(
        "합계|TOTAL|total", case=False).any()


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
