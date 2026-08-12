"""회수 할인율(CAPM)·부도자산 LGD(BEEL·PLGD) 배선과 화면 두 장.

여기서 고정하는 것은 넷이다.

1. **잠정 준용이 지어낸 값이 아니다.** 파이프라인이 '전체' 회수유형에 넣는
   할인율은 원장의 참고치 칸에서 그대로 온다. 소스에 숫자가 없어야 하고,
   참고치를 지우면 값도 들어가지 않아야 한다.
2. **승인 미완이 원장·화면 양쪽에 남는다.** 승인자 칸이 미승인이라고 말하고,
   화면이 그 칸을 그대로 싣는다.
3. **할인율이 실제로 LGD를 연다.** 승인 전에는 전건 산출불가였다. 준용 뒤에는
   LGD 원시추정과 BEEL 곡선·PLGD 민감도가 산출된다.
4. **정합성 검사가 통제다.** 검사마다 위반을 주입해 실제로 FAIL이 뜨는지 본다.
   주입해도 PASS가 유지되는 검사는 통제가 아니라 장식이다.
"""

from __future__ import annotations

import os
import re
import warnings
from pathlib import Path

import pandas as pd
import pytest

from risk_lib.datamodel import catalog as cat
from risk_lib.ui_studio import app as uiapp
from risk_lib.ui_studio import i18n

_APP = Path(uiapp.__file__).read_text(encoding="utf-8")
_JS = re.search(r'^_JS = r"""(.*?)^"""', _APP, re.S | re.M).group(1)

ASOF = "2026-06-11"

#: 두 화면의 리프 라벨. NAVGROUPS·DETAIL_SCREENS 두 곳에서 같은 문자열이어야
#: 하므로 여기 한 번만 적는다.
SCREENS = ("회수 할인율", "BEEL·PLGD")

#: 두 화면이 읽는 신규 원장.
LEDGERS = ("crm_capm_observation", "crm_capm_estimate", "crm_beel_curve",
           "crm_plgd", "crm_plgd_sensitivity")


# ---------------------------------------------------------------- 원장 배선

def test_new_estimation_specs_are_registered_in_the_catalog():
    """카탈로그에 없으면 검증·DQ·화면 어디에도 나타나지 않는다."""
    names = {sp.name for sp in cat.ALL_TABLES}
    missing = [n for n in LEDGERS if n not in names]
    assert missing == [], f"카탈로그에 등재되지 않은 원장: {missing}"


def test_pipeline_materialises_the_new_estimation_ledgers(result):
    """등재만 하고 실체화하지 않으면 화면에 빈 원장이 남는다."""
    empty = [n for n in LEDGERS
             if not isinstance(result.ledger_tables.get(n), pd.DataFrame)]
    assert empty == [], f"파이프라인이 만들지 않은 원장: {empty}"
    for n in ("crm_capm_observation", "crm_capm_estimate", "crm_beel_curve",
              "crm_plgd", "crm_plgd_sensitivity"):
        assert len(result.ledger_tables[n]), f"{n} 이 비어 있다"


# ---------------------------------------------------------------- 잠정 준용

def _rates():
    from risk_lib.pipeline import _provisional_discount_rates
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return _provisional_discount_rates(ASOF)


def test_provisional_rate_comes_from_the_ledger_reference_value():
    """준용 값은 원장의 참고치다. 소스에 숫자를 적으면 두 벌이 된다."""
    rates, _ = _rates()
    total = rates[rates["recovery_scope"] == "전체"]
    assert len(total), "'전체' 회수유형 행이 없다"
    for _, r in total.iterrows():
        assert r["discount_rate"] == pytest.approx(float(r["reference_value"]))


def test_pipeline_source_carries_no_discount_rate_literal():
    """할인율 수치가 파이프라인 소스에 박혀 있으면 원장이 바뀌어도 안 따라온다."""
    from risk_lib import pipeline
    src = Path(pipeline.__file__).read_text(encoding="utf-8")
    fn = src[src.index("def _provisional_discount_rates"):
             src.index("def _stage_ledgers")]
    assert not re.search(r"0\.\d{3,}", fn), (
        "잠정 준용 함수에 소수 리터럴이 있다. 값은 원장에서 읽어야 한다")


def test_no_reference_value_means_no_rate_and_a_stated_reason(monkeypatch):
    """근거가 없으면 값을 넣지 않는다. 조용히 건너뛰지도 않는다."""
    import risk_lib.models.estimation as est
    from risk_lib import pipeline

    blank = est.build_crm_lgd_discount_rate(ASOF)
    blank["reference_value"] = float("nan")
    monkeypatch.setattr(est, "build_crm_lgd_discount_rate",
                        lambda asof, *a, **k: blank)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        rates, warns = pipeline._provisional_discount_rates(ASOF)

    assert rates["discount_rate"].isna().all(), "참고치가 없는데 값이 들어갔다"
    assert warns and all("참고치가 없어" in w for w in warns), warns


def test_provisional_rate_is_recorded_as_unapproved():
    """승인기구 의결이 없다는 사실이 원장 칸에 남아야 한다."""
    from risk_lib.pipeline import PROVISIONAL_RATE_APPROVER
    rates, _ = _rates()
    total = rates[rates["recovery_scope"] == "전체"]
    assert (total["approved_by"] == PROVISIONAL_RATE_APPROVER).all()
    assert "미승인" in PROVISIONAL_RATE_APPROVER
    # 값이 들어간 행에 승인일이 함께 있어야 한다. 값만 있는 행은 만들지 않는다.
    filled = rates[rates["discount_rate"].notna()]
    assert filled["approval_date"].notna().all()
    assert (filled["basis"] != "미정").all()


# ---------------------------------------------------------------- 산출 개시

@pytest.fixture(scope="module")
def ledgers():
    from risk_lib.models.estimation import build_irb_estimation_ledgers
    rates, _ = _rates()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return build_irb_estimation_ledgers(asof=ASOF, seed=42, rates=rates)


def test_lgd_is_calculated_once_the_discount_rate_is_applied(ledgers):
    """할인율이 없던 상태에서는 전건 산출불가였다.

    승인 전 상태(할인율 원장을 넘기지 않음)와 준용 후를 같은 자리에서 비교한다.
    비교하지 않으면 '원래부터 산출됐다'와 구분되지 않는다.
    """
    from risk_lib.models.estimation import build_irb_estimation_ledgers

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        before = build_irb_estimation_ledgers(asof=ASOF, seed=42)
    assert set(before["crm_lgd_estimate"]["status"]) == {"산출불가"}
    assert before["crm_lgd_estimate"]["raw_estimate"].isna().all()

    after = ledgers["crm_lgd_estimate"]
    assert set(after["status"]) == {"산출완료"}
    assert after["raw_estimate"].notna().all()
    assert after["discount_rate"].notna().all()


def test_beel_curve_and_plgd_sensitivity_follow_the_discount_rate(ledgers):
    """곡선·민감도도 할인율에 걸려 있다. 하나가 열리면 셋이 함께 열린다."""
    curve = ledgers["crm_beel_curve"]
    assert set(curve["status"]) == {"산출완료"}
    # 두 분모를 모두 산출하고 적용 표시만 다르다.
    assert set(curve["beel_denominator"]) == {"부도시익스포저", "잔여익스포저"}
    applied = set(curve.loc[curve["is_applied_denominator"], "beel_denominator"])
    assert len(applied) == 1, f"적용 분모가 하나로 정해지지 않았다: {applied}"
    assert len(ledgers["crm_plgd_sensitivity"]), "q 민감도 격자가 비었다"


def test_plgd_value_stays_empty_until_the_confidence_level_is_approved(ledgers):
    """q 는 시뮬레이션이 정해 주는 값이 아니다. 승인 전에는 비어 있어야 한다."""
    plgd = ledgers["crm_plgd"]
    assert plgd["plgd"].isna().all()
    assert plgd["confidence_q"].isna().all()
    assert (plgd["confidence_q_status"] == "미승인").all()
    # ELBE 는 q 와 무관하므로 산출된다.
    assert plgd["elbe"].notna().all()


# ---------------------------------------------------------------- 정합성 검사

def _report(led, asof=ASOF):
    from risk_lib.validation.consistency import (
        ValidationReport, _check_irb_estimation_ledgers,
    )
    rep = ValidationReport()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _check_irb_estimation_ledgers(led, asof, rep)
    return {c.name: c.status for c in rep.checks}


def test_consistency_runs_the_module_checks_and_passes_in_the_base_state(ledgers):
    got = _report(ledgers)
    assert got, "검사가 하나도 붙지 않았다"
    assert "CAPM 재계산" in got and "BEEL 곡선 단조성" in got
    assert [k for k, v in got.items() if v == "FAIL"] == []


def _mutate(base, fn):
    led = {k: (v.copy() if isinstance(v, pd.DataFrame) else v)
           for k, v in base.items()}
    fn(led)
    return _report(led)


def _beta_shift(led):
    led["crm_capm_estimate"].loc[:, "beta"] += 0.5


def _truncate_observations(led):
    led["crm_capm_observation"] = led["crm_capm_observation"].head(40)


def _swap_recovery_scopes(led):
    r = led["crm_lgd_discount_rate"]
    a, b = r["recovery_scope"] == "전체", r["recovery_scope"] == "무위험회수"
    va, vb = r.loc[a, "discount_rate"].to_numpy(), r.loc[b, "discount_rate"].to_numpy()
    r.loc[a, "discount_rate"], r.loc[b, "discount_rate"] = vb, va


def _drop_approver(led):
    r = led["crm_lgd_discount_rate"]
    r.loc[r["recovery_scope"] == "전체", "approved_by"] = None


def _mislabel_evidence(led):
    r = led["crm_lgd_discount_rate"]
    r.loc[r["recovery_scope"] == "무위험회수", "evidence_status"] = "2차자료"


def _flatten_recovery_timing(led):
    led["crm_recovery_history"].loc[:, "recovery_years"] = 0.0


def _break_monotonicity(led):
    c = led["crm_beel_curve"]
    c.loc[c["is_applied_denominator"], "monotonicity_verdict"] = "단조증가아님"


def _plgd_below_elbe(led):
    p = led["crm_plgd"]
    p.loc[:, "plgd"] = p["elbe"] - 0.05
    p.loc[:, "unexpected_loss_addon"] = -0.05


def _justification_missing(led):
    p = led["crm_plgd"]
    p.loc[:, "justification_required"] = True
    p.loc[:, "justification_ref"] = None


def _drop_capm_ledger(led):
    del led["crm_capm_estimate"]


def _drop_plgd_ledger(led):
    del led["crm_plgd"]


# (위반 주입, 발동해야 하는 검사, 기대 판정)
_VIOLATIONS = [
    (_beta_shift, "CAPM 재계산", "FAIL"),
    (_truncate_observations, "CAPM 재계산", "FAIL"),
    (_swap_recovery_scopes, "CAPM 회수유형 할인율 서열", "FAIL"),
    (_drop_approver, "CAPM 할인율 승인기록", "FAIL"),
    (_mislabel_evidence, "CAPM 근거 표시", "FAIL"),
    (_flatten_recovery_timing, "CAPM 할인율 LGD 민감도", "FAIL"),
    # 단조성은 데이터 품질 신호이므로 WARN 이다. FAIL 로 올리면 회수 데이터가
    # 얇은 세그먼트 하나가 결재를 막는다.
    (_break_monotonicity, "BEEL 곡선 단조성", "WARN"),
    (_plgd_below_elbe, "PLGD 예상외손실 추가분 부호", "FAIL"),
    (_justification_missing, "PLGD 부도자산 ELBE 대 충당금", "FAIL"),
    (_drop_capm_ledger, "irb_discount_rate_ledgers_present", "FAIL"),
    (_drop_plgd_ledger, "irb_plgd_ledgers_present", "FAIL"),
]


@pytest.mark.parametrize("inject,check,expected",
                         _VIOLATIONS,
                         ids=[v[0].__name__ for v in _VIOLATIONS])
def test_injected_violation_is_caught(ledgers, inject, check, expected):
    """위반을 만들면 실제로 판정이 바뀌어야 통제다."""
    base = _report(ledgers)
    got = _mutate(ledgers, inject)
    assert got.get(check) == expected, (
        f"{inject.__name__} 를 주입했는데 '{check}' 가 {got.get(check)} 다 "
        f"(기준 상태 {base.get(check)})")


def test_missing_ledger_is_a_failure_not_a_skip(ledgers):
    """원장이 없으면 검사가 돌지 않는다. 안 돈 것을 통과로 적지 않는다."""
    got = _mutate(ledgers, _drop_capm_ledger)
    assert "CAPM 재계산" not in got, "원장이 없는데 재계산 검사가 돌았다"
    assert got["irb_discount_rate_ledgers_present"] == "FAIL"


def test_checks_reach_the_pipeline_validation_report(result):
    """파이프라인 산출물의 자체검증 보고서에 실제로 실려 나가는가."""
    names = {c.name for c in result.validation.checks}
    for n in ("CAPM 재계산", "CAPM 할인율 승인기록", "BEEL 곡선 단조성"):
        assert n in names, f"{n} 이 파이프라인 자체검증에 없다"


# ---------------------------------------------------------------- 화면 배선

def test_screens_are_registered_in_the_menu_and_the_screen_list():
    detail = _JS[_JS.index("const DETAIL_SCREENS=["):_JS.index("const NAVGROUPS=[")]
    nav = _JS[_JS.index("const NAVGROUPS=["):_JS.index("const TABS=[")]
    for lab in SCREENS:
        assert f"'{lab}'" in detail, f"{lab} 이 화면 목록에 없다"
        assert f"'{lab}'" in nav, f"{lab} 이 메뉴 트리에 없다"


def test_screen_ledgers_are_loaded_in_full():
    """산점·곡선은 축 전체가 있어야 한다. 잘리면 공백이 관측 없음으로 읽힌다."""
    for n in LEDGERS:
        assert n in uiapp.NEW_SCREEN_FULL_TABLES, f"{n} 이 전량 탑재 목록에 없다"


def test_screen_source_reads_the_ledgers_and_not_a_recomputation():
    """회귀선은 추정 원장의 절편·기울기를 그대로 쓴다."""
    fn = _JS[_JS.index("function capmDiscountScreen(root){"):
             _JS.index("function beelPlgdScreen(root){")]
    assert "fit:{slope:r[ei.beta],intercept:(r[ei.alpha]||0)*100}" in fn, (
        "화면이 원장의 회귀계수로 적합선을 긋지 않는다")
    for n in ("crm_capm_observation", "crm_capm_estimate",
              "crm_lgd_discount_rate"):
        assert f"almF('{n}')" in fn, f"{n} 을 읽지 않는다"


def test_both_screens_are_translated():
    """기본 언어가 영어다. 화면 제목·설명이 카탈로그를 거쳐야 한다."""
    m = i18n.ko_to_en()
    keys = [
        "회수 할인율", "BEEL·PLGD",
        "IRB · 회수 할인율 (CAPM 관측·추정·승인·적용)",
        "IRB · 부도자산 LGD (BEEL 곡선·PLGD·신뢰수준 민감도)",
        "베타 회귀 (초과수익률 산점과 적합선)",
        "회수유형별 할인율 (승인 기록 포함)",
        "타행 참고치와의 대비",
        "경과월별 BEEL 곡선 (적용 분모)",
        "분모 두 방식 대비",
        "신뢰수준 q 민감도",
        "PLGD 대 ELBE",
        "개별충당금 + 부분상각 비교",
    ]
    missing = [k for k in keys if k not in m]
    assert missing == [], f"i18n 카탈로그에 없는 화면 문자열: {missing}"


def test_stale_statement_about_the_beel_curve_is_gone():
    """원장이 곡선을 만들기 시작했으므로 '그리지 않는다'는 더 이상 사실이 아니다."""
    assert "경과월별 BEEL 곡선은 그리지 않는다" not in _APP
    assert "만들지 않은 화면',null,\n    'PLGD" not in _APP


# ---------------------------------------------------------------- 브라우저

_CHROME = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH",
                              "/opt/pw-browsers")) / "chromium"


@pytest.fixture(scope="module")
def rendered(result, portfolio, tmp_path_factory):
    from risk_lib.ui_studio.studio import build_studio
    out = tmp_path_factory.mktemp("capmplgd") / "studio.html"
    return uiapp.write_app(build_studio(result, portfolio), out)


def _open(pg, path, label):
    pg.add_init_script("localStorage.setItem('rynta-lang','ko')")
    pg.goto(f"file://{path}")
    pg.wait_for_timeout(400)
    found = pg.eval_on_selector_all(
        "nav button",
        "(els,l)=>{const b=els.find(x=>x.dataset.ko===l);"
        "if(b){b.click();return true}return false}", label)
    assert found, f"{label} 메뉴가 없다"
    pg.wait_for_timeout(350)
    return pg.inner_text("section.on")


@pytest.mark.skipif(not _CHROME.exists(), reason="chromium 미설치")
def test_capm_screen_shows_the_approval_state_of_the_rate(rendered):
    """승인 상태와 합성 관측이라는 사실이 화면에 있어야 한다."""
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright
    from risk_lib.pipeline import PROVISIONAL_RATE_APPROVER
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=str(_CHROME))
        pg = b.new_page(viewport={"width": 1400, "height": 1200})
        errors: list[str] = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        txt = _open(pg, rendered, "회수 할인율")
        assert PROVISIONAL_RATE_APPROVER in txt, "승인자 칸이 화면에 없다"
        assert "합성 관측" in txt, "합성 관측 기반이라는 사실이 화면에 없다"
        assert "추정불가" in txt, "자기자본비용 산출 상태가 화면에 없다"
        assert "crm_capm_observation" in txt, "연결 원장 카드가 없다"
        assert "참고치" in txt, "타행 참고치 대비가 없다"
        assert errors == []
        b.close()


@pytest.mark.skipif(not _CHROME.exists(), reason="chromium 미설치")
def test_beel_screen_shows_the_denominator_and_the_unapproved_confidence(rendered):
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=str(_CHROME))
        pg = b.new_page(viewport={"width": 1400, "height": 1400})
        errors: list[str] = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        txt = _open(pg, rendered, "BEEL·PLGD")
        assert "부도시익스포저" in txt and "잔여익스포저" in txt, "분모 대비가 없다"
        assert "미승인" in txt, "신뢰수준 승인 상태가 화면에 없다"
        assert "산출불가(신뢰수준미승인)" in txt, "PLGD 산출 상태가 화면에 없다"
        assert "185.바" in txt, "충당금 비교의 규정 근거가 없다"
        assert errors == []
        b.close()


@pytest.mark.skipif(not _CHROME.exists(), reason="chromium 미설치")
def test_capm_scatter_draws_a_point_per_observation(rendered):
    """산점이 표본이 아니라 관측 전량이어야 한다."""
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=str(_CHROME))
        pg = b.new_page(viewport={"width": 1400, "height": 1200})
        _open(pg, rendered, "회수 할인율")
        n_pts = pg.eval_on_selector_all("section.on svg circle", "e=>e.length")
        n_rows = pg.evaluate(
            "window.__RYNTA__.data['crm_capm_observation'].total")
        assert n_pts == n_rows, f"산점 {n_pts}개 대 관측 {n_rows}행"
        n_fit = pg.eval_on_selector_all(
            "section.on svg line[stroke-dasharray='5 4']", "e=>e.length")
        assert n_fit >= 1, "적합선이 그려지지 않았다"
        b.close()
