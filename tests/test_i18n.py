"""화면 언어 전환 (기본 영어) 검사.

두 가지를 나눠 본다.

1. **카탈로그 자체의 무결성.** 모든 항목이 ko·en 두 값을 갖고, 같은 한국어에
   서로 다른 영문이 붙지 않는다. 이건 브라우저 없이도 본다.
2. **화면에서 실제로 옮겨지는가.** 영문으로 전환한 뒤 남은 한국어를 센다.
   소스를 눈으로 훑는 방식은 빠뜨리므로, 70개 화면을 전부 열어 T() 가 못 찾은
   문자열을 런타임에서 걷는다(`window.__I18N__.miss`).

**원장에서 오는 값은 옮기지 않는 것이 정답이다.** 차주명·지표명·요건 레지스터
비고·조문 인용은 원장과 레지스터가 정본이라, 화면이 옮기면 화면의 이름과 원장의
이름이 갈라져 감사 추적이 끊긴다. 아래 `test_ledger_values_stay_korean` 이 그
값들이 영문 화면에서도 원문 그대로인지 고정한다.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from risk_lib.ui_studio import i18n

# ════════════════════════════════════════════════════════════════════════
# 1. 카탈로그 무결성 (브라우저 없이)
# ════════════════════════════════════════════════════════════════════════


def test_every_entry_has_both_languages():
    assert i18n.MESSAGES, "카탈로그가 비어 있다"
    for key, v in i18n.MESSAGES.items():
        assert set(v) == {"ko", "en"}, f"{key} 에 ko·en 이 아닌 키가 있다"
        assert v["ko"].strip(), f"{key} 의 한국어가 비었다"
        assert v["en"].strip(), f"{key} 의 영문이 비었다"


def test_lookup_table_has_no_conflicting_translation():
    """같은 한국어에 영문이 둘이면 ko_to_en() 이 예외를 던진다."""
    m = i18n.ko_to_en()
    assert len(m) > 1000, f"조회 사전이 {len(m)}건뿐이다"


def test_default_language_is_english():
    assert i18n.DEFAULT_LANG == "en"
    assert i18n.payload()["default"] == "en"


def test_payload_carries_storage_key_and_langs():
    p = i18n.payload()
    assert p["storage_key"] == "rynta-lang"
    assert set(p["langs"]) == {"en", "ko"}


def test_english_side_has_no_em_dash():
    """긴 대시는 화면·문서에서 빼기로 했다. 영문에도 쓰지 않는다."""
    bad = [k for k, v in i18n.MESSAGES.items() if "—" in v["en"]]
    assert not bad, f"영문에 긴 대시가 남았다: {bad}"


def test_english_side_is_not_left_in_korean():
    """영문 자리에 한국어가 그대로 남은 항목을 잡는다.

    조문 인용(`[별표 9-1]`, `은행업감독규정 제26조`)과 원장 라벨은 원문 표기를
    유지하는 것이 맞으므로, 문장 전체가 한국어인 경우만 걸러낸다.
    """
    import re
    hangul = re.compile(r"[가-힣]")
    latin = re.compile(r"[A-Za-z]")
    bad = []
    for k, v in i18n.MESSAGES.items():
        en = v["en"]
        if hangul.search(en) and not latin.search(en):
            bad.append((k, en))
    # 언어 전환 버튼의 '한국어' 는 어느 언어에서나 그대로 보여야 한다.
    bad = [b for b in bad if b[1] != "한국어"]
    assert not bad, f"영문이 번역되지 않았다: {bad}"


# ════════════════════════════════════════════════════════════════════════
# 2. 화면 배선 (소스 수준)
# ════════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="module")
def app_src():
    return Path("risk_lib/ui_studio/app.py").read_text(encoding="utf-8")


def test_language_button_exists_and_uses_storage(app_src):
    assert 'id="langbtn"' in app_src, "헤더에 언어 전환 버튼이 없다"
    assert "I18N.storage_key" in app_src, "localStorage 키를 페이로드에서 읽지 않는다"
    assert "localStorage.setItem(LANG_KEY" in app_src, "선택이 저장되지 않는다"


def test_switch_repaints_without_reload(app_src):
    """전환은 새로고침 없이 즉시 다시 그려야 한다."""
    assert "function setLang(" in app_src
    assert "repaintAll()" in app_src
    assert "location.reload" not in app_src, "언어 전환이 새로고침에 기대고 있다"


def test_missing_key_is_visible_in_debug_mode(app_src):
    """조용히 한국어로 떨어지면 누락을 못 본다. 개발 모드에서 표시를 감싼다."""
    assert "I18N_DEBUG" in app_src
    assert "I18N_MISS" in app_src


# ════════════════════════════════════════════════════════════════════════
# 3. 브라우저에서 실제 전환 (Playwright)
# ════════════════════════════════════════════════════════════════════════

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright  # noqa: E402

_CHROME = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")) / "chromium"
_needs_chrome = pytest.mark.skipif(not _CHROME.exists(), reason="chromium 미설치")


@pytest.fixture(scope="module")
def page_path(result, portfolio, tmp_path_factory):
    from risk_lib.ui_studio.studio import build_studio
    from risk_lib.ui_studio.app import write_app
    st = build_studio(result, portfolio)
    return write_app(st, tmp_path_factory.mktemp("i18n") / "studio.html")


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=str(_CHROME))
        yield b
        b.close()


@pytest.fixture
def page(browser, page_path):
    pg = browser.new_page(viewport={"width": 1400, "height": 1000})
    pg.goto(f"file://{page_path}")
    pg.wait_for_function("window.__I18N__!==undefined")
    return pg


@_needs_chrome
def test_opens_in_english(page):
    """고른 적이 없으면 영어로 연다."""
    assert page.evaluate("window.__I18N__.lang()") == "en"
    nav = page.evaluate("[...document.querySelectorAll('nav button')].map(b=>b.textContent)")
    assert "Cockpit" in nav, f"네비게이션이 영문이 아니다: {nav[:5]}"
    assert "콕핏" not in nav


@_needs_chrome
def test_toggle_switches_and_persists(page):
    """전환은 즉시 반영되고 localStorage 에 남는다."""
    page.click("#langbtn")
    assert page.evaluate("window.__I18N__.lang()") == "ko"
    nav = page.evaluate("[...document.querySelectorAll('nav button')].map(b=>b.textContent)")
    assert "콕핏" in nav
    assert page.evaluate("localStorage.getItem('rynta-lang')") == "ko"
    page.click("#langbtn")
    assert page.evaluate("window.__I18N__.lang()") == "en"
    assert page.evaluate("localStorage.getItem('rynta-lang')") == "en"


@_needs_chrome
def test_stored_choice_wins_over_english_default(browser, page_path):
    pg = browser.new_page(viewport={"width": 1200, "height": 900})
    pg.goto(f"file://{page_path}")
    pg.evaluate("localStorage.setItem('rynta-lang','ko')")
    pg.reload()
    pg.wait_for_function("window.__I18N__!==undefined")
    assert pg.evaluate("window.__I18N__.lang()") == "ko"
    pg.close()


@_needs_chrome
def test_ledger_values_stay_korean(page):
    """원장·레지스터에서 오는 값은 영문 화면에서도 원문 그대로다.

    옮기면 화면의 이름과 원장의 이름이 갈라져 감사 추적이 끊긴다. 지표
    마스터(macro_monitor.py)의 지표명과 "움직이는 축" 으로 확인한다.
    """
    page.evaluate("""()=>{const b=[...document.querySelectorAll('nav button')]
        .find(x=>x.dataset.ko==='거시지표 모니터링'); b.click()}""")
    page.wait_for_timeout(200)
    txt = page.inner_text("main")
    assert "실질 GDP 성장률" in txt, "지표명이 원장과 다르게 옮겨졌다"
    assert "PD 시스템요인" in txt, "움직이는 축이 원장과 다르게 옮겨졌다"


@_needs_chrome
def test_numbers_are_unchanged_between_languages(page):
    """언어를 바꿔도 원장 수치는 그대로다."""
    import re

    def digits_of(screen: str) -> list[str]:
        page.evaluate(
            """(lab)=>{const b=[...document.querySelectorAll('nav button')]
                 .find(x=>x.dataset.ko===lab); if(b)b.click()}""", screen)
        page.wait_for_timeout(200)
        # 첫 표는 지금 켜진 화면의 것이어야 한다. 부트 화면(종합보고서)에도
        # 표가 있으므로 main 전체에서 첫 표를 잡으면 다른 화면의 표를 읽는다.
        return re.findall(r"\d[\d,]*\.?\d*", page.inner_text("section.on table"))

    en = digits_of("신용 RWA")
    page.click("#langbtn")
    ko = digits_of("신용 RWA")
    assert en == ko, "언어 전환이 표의 수치를 바꿨다"


@_needs_chrome
def test_translation_coverage_does_not_regress(page):
    """70개 화면을 전부 열어 옮기지 못한 문자열을 센다.

    남은 것은 대부분 원장 수치가 박힌 합성 문자열(`기준 1.03tn` 처럼 값이
    실행마다 달라 통째로 키가 될 수 없는 것)이다. 이 상한은 내려가기만 해야
    한다. 올라갔다면 새 화면 문자열이 카탈로그를 거치지 않은 것이다.
    """
    labels = page.evaluate(
        "[...document.querySelectorAll('nav button')].map(b=>b.dataset.ko)")
    assert len(labels) >= 60, f"화면이 {len(labels)}개뿐이다"
    page.evaluate("window.__I18N__.miss.length=0")
    for lab in labels:
        page.evaluate(
            """(lab)=>{const b=[...document.querySelectorAll('nav button')]
                 .find(x=>x.dataset.ko===lab); if(b)b.click()}""", lab)
        page.wait_for_timeout(60)
    miss = page.evaluate("window.__I18N__.miss.slice()")
    assert len(miss) <= 60, (
        f"카탈로그를 거치지 않은 화면 문자열이 {len(miss)}건으로 늘었다. "
        f"예: {miss[:8]}")
