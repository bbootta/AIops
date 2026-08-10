"""화면 규약 고정 검사.

사용자가 직접 지적한 네 가지를 되돌아오지 않게 못 박는다.

  1) 화면 문자열에 긴 대시가 없다.
  2) 경구·대조 수사 문장이 없다.
  3) 화면 밝기 토글이 실재하고 루트의 data-theme 을 실제로 바꾼다.
  4) 신규 화면이 실재하는 원장(카탈로그 테이블)만 참조하고, 규제 수치를
     문자열에 박아 두지 않는다.

브라우저가 없는 환경에서도 3)의 앞부분(마크업·핸들러 존재)은 소스로 고정하고,
실제 토글 동작은 Chromium 이 있을 때만 확인한다.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from risk_lib.datamodel import catalog as cat
from risk_lib.ui_studio import app as uiapp

SRC = Path(uiapp.__file__).read_text(encoding="utf-8")
_JS = re.search(r'^_JS = r"""(.*?)^"""', SRC, re.S | re.M).group(1)

# 신규 화면 구간. 이 구간만 따로 검사하는 이유는 앞선 회차의 화면에도 같은
# 규약을 소급 적용하면 이 검사가 무엇을 지키는지 흐려지기 때문이다.
_NEW_START = _JS.index("공통 헬퍼 (신규 화면)")
_NEW_END = _JS.index("function scenarioScreen(root){")
_NEW = _JS[_NEW_START:_NEW_END]


def _korean_literals(text: str) -> list[str]:
    out = []
    for pat in (r"'((?:[^'\\\n]|\\.)*)'", r"`((?:[^`\\]|\\.)*)`"):
        for m in re.finditer(pat, text, re.S):
            t = m.group(1)
            if re.search(r"[가-힣]", t):
                out.append(t)
    return out


# ---------------------------------------------------------------- 1) 긴 대시

def test_screen_source_has_no_em_dash():
    assert "—" not in SRC, (
        "화면 소스에 긴 대시가 남아 있다. 쉼표·마침표·괄호로 문장을 끊는다.")


# ---------------------------------------------------------------- 2) 경구 문장

# 사용자가 화면 캡처로 지적한 문장과 같은 계열(대조 수사·단정 경구).
_APHORISMS = (
    "서식만 다르고",
    "사람의 적은",
    "없는 것만 못하다",
    "제일 나쁘다",
    "제일 위험하다",
    "데인 유형",
    "경보가 죽는다",
    "거짓이 된다",
    "화면의 정체",
    "부문이 이긴다",
    "사실은 하나다",
    "조건부는 적합이 아니다",
    "아무에게도 안 읽힌다",
)


@pytest.mark.parametrize("phrase", _APHORISMS)
def test_no_aphorism_survives(phrase):
    assert phrase not in SRC, f"경구 문장이 남아 있다: {phrase}"


def test_screen_leads_do_not_use_contrastive_rhetoric():
    """'A가 아니라 B다' 대조는 범위 고지에만 남기고 수사로 쓰지 않는다."""
    bad = [t for t in _korean_literals(_NEW) if "가 아니라" in t]
    assert bad == [], bad


# ---------------------------------------------------------------- 3) 화면 밝기

def test_theme_toggle_markup_and_handler_exist():
    html = uiapp.render.__doc__ or ""
    assert html is not None
    # 헤더 버튼
    assert 'id="themebtn"' in SRC
    assert ".theme{" in uiapp._CSS
    # 두 방향 모두 이기도록 팔레트가 세 자리에 선언돼 있다
    assert ':root[data-theme="light"]' in uiapp._PALETTE
    assert ':root[data-theme="dark"]' in uiapp._PALETTE
    assert "@media (prefers-color-scheme:light)" in uiapp._PALETTE
    # 초기값은 시스템 설정, 선택은 localStorage 로 유지
    assert "prefers-color-scheme: light" in _JS
    assert "localStorage.setItem(THEME_KEY" in _JS
    assert "setAttribute('data-theme'" in _JS
    assert "wireTheme()" in _JS


def test_theme_bootstrap_script_is_inline_and_runs_before_paint():
    """외부 리소스를 부르면 아티팩트 CSP 가 막는다. 인라인이어야 한다."""
    assert "localStorage.getItem('rynta-theme')" in SRC
    body = SRC[SRC.index("</style></head><body>"):]
    assert body.index("rynta-theme") < body.index('<div class="topbar">')
    assert "src=" not in body[:body.index('<div class="topbar">')]


# ---------------------------------------------------------------- 4) 원장 참조

_TABLE_NAMES = {sp.name for sp in cat.ALL_TABLES}


# 아직 만들어지지 않은 원장. [별표 9-1] 제25항 라가 한도 초과 시 원인분석과
# 대응책 수립·운영을 요구하므로 화면이 자리를 잡아 두되, 원장이 없다는 사실을
# 화면에 적는다. 원장이 생기면 이 목록에서 빠진다.
_PENDING_LEDGERS = {"lim_breach_action"}


def test_every_ledger_reference_names_a_real_table():
    refs = set(re.findall(r"almF\('([a-z0-9_]+)'\)", _JS))
    refs |= set(re.findall(r"D\.data\['([a-z0-9_]+)'\]", _JS))
    assert refs, "원장 참조를 하나도 찾지 못했다. 정규식이 낡았다."
    unknown = sorted(r for r in refs
                     if r not in _TABLE_NAMES and r not in _PENDING_LEDGERS)
    assert unknown == [], f"카탈로그에 없는 원장을 참조한다: {unknown}"


def test_pending_ledger_absence_is_stated_on_the_screen():
    """없는 원장을 조용히 건너뛰면 화면이 '해당 없음'으로 읽힌다."""
    for name in _PENDING_LEDGERS:
        assert name in _JS
        assert f"{name})이 없다" in _JS or f"{name})가 없다" in _JS, (
            f"{name} 이 없다는 사실을 화면에 적지 않았다")
        assert name not in _TABLE_NAMES, (
            f"{name} 이 카탈로그에 생겼다. _PENDING_LEDGERS 에서 뺀다.")


def test_new_screens_are_registered_in_menu_and_tab_list():
    labels = ["국내 금리리스크", "행동모형 추정", "비만기성예금 코어",
              "행동모형 백테스트", "PD 추정", "LGD 추정", "CCF 추정",
              "부도자산 LGD", "모형 거버넌스", "LGD·EAD 실측검증",
              "거액 설정", "거액 분석"]
    detail = _JS[_JS.index("const DETAIL_SCREENS=["):_JS.index("const NAVGROUPS=[")]
    nav = _JS[_JS.index("const NAVGROUPS=["):_JS.index("const TABS=[")]
    for lab in labels:
        assert f"'{lab}'" in detail, f"{lab} 이 화면 목록에 없다"
        assert f"'{lab}'" in nav, f"{lab} 이 메뉴 트리에 없다"


def test_new_screens_reference_the_full_load_budget_tables():
    """집계해서 그리는 원장은 전량 실려야 한다. 표본으로 그리면 축이 잘린다."""
    for name in ("alm_repricing_gap", "crm_pd_estimate", "lex_setting",
                 "alm_nmd_core_method_compare", "crm_backtest_result"):
        assert name in uiapp.NEW_SCREEN_FULL_TABLES


# ---------------------------------------------------------------- 5) 리터럴 수치

_NUMERIC = re.compile(r"\d[\d,.]*\s*(bp|%|조원|억원|배)")


def test_new_screen_strings_carry_no_literal_figures():
    """규제 수치·산출값은 원장에서 온다. 화면 문자열에 박으면 두 벌이 된다."""
    bad = [t for t in _korean_literals(_NEW)
           if _NUMERIC.search(t) and "${" not in t]
    assert bad == [], bad


@pytest.mark.parametrize("figure", ["225bp", "350bp", "기본자본의 15",
                                    "자기자본의 20", "25%", "500%", "0.03%"])
def test_regulatory_figures_are_not_hardcoded_in_screen_text(figure):
    assert figure not in _JS, (
        f"규제 수치 {figure} 가 화면 소스에 박혀 있다. 원장에서 읽어야 한다.")


# ---------------------------------------------------------------- 브라우저 확인

_CHROME = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH",
                              "/opt/pw-browsers")) / "chromium"


@pytest.fixture(scope="module")
def rendered(result, portfolio, tmp_path_factory):
    from risk_lib.ui_studio.studio import build_studio
    out = tmp_path_factory.mktemp("uiscreens") / "studio.html"
    return uiapp.write_app(build_studio(result, portfolio), out)


@pytest.mark.skipif(not _CHROME.exists(), reason="chromium 미설치")
def test_theme_toggle_actually_flips_data_theme(rendered):
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=str(_CHROME))
        pg = b.new_page()
        errors: list[str] = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(f"file://{rendered}")
        pg.wait_for_timeout(300)
        first = pg.eval_on_selector("html", "e=>e.getAttribute('data-theme')")
        pg.click("#themebtn")
        pg.wait_for_timeout(120)
        second = pg.eval_on_selector("html", "e=>e.getAttribute('data-theme')")
        assert second in ("light", "dark")
        assert second != first
        pg.click("#themebtn")
        pg.wait_for_timeout(120)
        third = pg.eval_on_selector("html", "e=>e.getAttribute('data-theme')")
        assert third != second
        # 선택은 유지된다
        assert pg.evaluate("localStorage.getItem('rynta-theme')") == third
        assert errors == []
        b.close()


@pytest.mark.skipif(not _CHROME.exists(), reason="chromium 미설치")
def test_every_new_screen_renders_with_content(rendered):
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright
    labels = ["국내 금리리스크", "행동모형 추정", "비만기성예금 코어",
              "행동모형 백테스트", "PD 추정", "LGD 추정", "CCF 추정",
              "부도자산 LGD", "모형 거버넌스", "LGD·EAD 실측검증",
              "거액 설정", "거액 분석", "시뮬레이션", "한도관리"]
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=str(_CHROME))
        pg = b.new_page(viewport={"width": 1400, "height": 1000})
        errors: list[str] = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(f"file://{rendered}")
        pg.wait_for_timeout(400)
        for lab in labels:
            found = pg.eval_on_selector_all(
                "nav button",
                "(els,l)=>{const b=els.find(x=>x.textContent===l);"
                "if(b){b.click();return true}return false}", lab)
            assert found, f"{lab} 메뉴가 없다"
            pg.wait_for_timeout(220)
            text = pg.inner_text("section.on")
            assert len(text) > 400, f"{lab} 화면이 비어 있다"
            # 연결 원장 카드가 없으면 어디서 온 수치인지 화면에서 알 수 없다
            assert ("연결 원장" in text or "기준값의 출처" in text
                    or "한도 정의" in text), f"{lab} 에 원장 표기가 없다"
        assert errors == []
        b.close()


@pytest.mark.skipif(not _CHROME.exists(), reason="chromium 미설치")
def test_rdm_screen_opens_with_the_review_notice(rendered):
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=str(_CHROME))
        pg = b.new_page(viewport={"width": 1400, "height": 1000})
        pg.goto(f"file://{rendered}")
        pg.wait_for_timeout(400)
        pg.eval_on_selector_all(
            "nav button",
            "els=>{const b=els.find(x=>x.textContent==='RDM');b.click()}")
        pg.wait_for_timeout(250)
        text = pg.inner_text("section.on")
        head = text[:600]
        assert "합성데이터" in head
        assert "소관 부서" in head
        assert "검토" in head
        b.close()


@pytest.mark.skipif(not _CHROME.exists(), reason="chromium 미설치")
def test_simulation_amount_input_moves_the_ratio(rendered):
    """금액 입력이 비율과 같은 값을 가리키는지 (사용자 지적 사항)."""
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=str(_CHROME))
        pg = b.new_page(viewport={"width": 1400, "height": 1200})
        pg.goto(f"file://{rendered}")
        pg.wait_for_timeout(400)
        pg.eval_on_selector_all(
            "nav button",
            "els=>{const b=els.find(x=>x.textContent==='시뮬레이션');b.click()}")
        pg.wait_for_timeout(300)
        before = pg.inner_text("section.on .kpi .val")
        # 위험가중자산 합계의 금액 칸 (첫 입력 쌍의 두 번째 input)
        pg.eval_on_selector_all(
            "section.on input[type=number]",
            "els=>{els[1].value='-100000';"
            "els[1].dispatchEvent(new Event('input',{bubbles:true}))}")
        pg.wait_for_timeout(250)
        after = pg.inner_text("section.on .kpi .val")
        assert after != before, "금액 입력이 비율을 움직이지 않았다"
        # 비율 칸이 같은 조정을 가리키도록 따라 갱신된다
        pct = pg.eval_on_selector_all(
            "section.on input[type=number]", "els=>els[0].value")
        assert float(pct) < 0
        b.close()
