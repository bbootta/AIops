"""브라우저에서 실제로 시연되는지 — Playwright로 화면을 몰아본다.

"프롬프트를 바꾸면 레이아웃이 바뀐다"는 주장은 렌더된 DOM으로만 증명된다.
JSON 페이로드를 검사하는 것으로는 부족하다 — 데이터가 실려 있어도 화면이
반응하지 않을 수 있기 때문이다.

Playwright·Chromium이 없으면 건너뛴다(엔진 로직 자체는 test_ui_engine_parity가
node로 고정한다).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright  # noqa: E402

_CHROME = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")) / "chromium"
pytestmark = pytest.mark.skipif(not _CHROME.exists(), reason="chromium 미설치")


@pytest.fixture(scope="module")
def page_path(result, portfolio, tmp_path_factory):
    from risk_lib.ui_studio.app import write_app
    from risk_lib.ui_studio.studio import build_studio
    out = tmp_path_factory.mktemp("ui") / "studio.html"
    return write_app(build_studio(result, portfolio), out)


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=str(_CHROME))
        yield b
        b.close()


@pytest.fixture
def page(browser, page_path):
    pg = browser.new_page(viewport={"width": 1400, "height": 1000})
    errors: list[str] = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(f"file://{page_path}")
    pg.wait_for_timeout(500)
    pg.errors = errors           # type: ignore[attr-defined]
    yield pg
    pg.close()


def _tab(pg, index: int) -> None:
    pg.eval_on_selector_all("nav button", f"els => els[{index}].click()")
    pg.wait_for_timeout(250)


def _text(pg) -> str:
    return pg.inner_text("section.on")


# ----- 로딩 -------------------------------------------------------------------

def test_page_loads_every_tab_without_script_errors(page):
    n = page.eval_on_selector_all("nav button", "els => els.length")
    assert n >= 14
    for i in range(n):
        _tab(page, i)
        assert page.inner_text("section.on h2")
    assert page.errors == []


# ----- 정형 조회: 입력에 따라 계획과 결과가 바뀐다 ------------------------------

def test_typing_recompiles_the_plan_and_changes_results(page):
    _tab(page, 1)
    page.select_option("section.on select.sel", "V_RDM_ASSET_QUALITY")
    page.wait_for_timeout(200)

    page.fill("section.on input.input", "연체일수 1 이상")
    page.wait_for_timeout(250)
    loose = _text(page)
    assert "AST: (dpd >= 1.0)" in loose

    page.fill("section.on input.input", "연체일수 100 이상")
    page.wait_for_timeout(250)
    tight = _text(page)
    assert "AST: (dpd >= 100.0)" in tight

    def pop(txt: str) -> int:
        import re
        m = re.search(r"모집단 ([\d,]+)건", txt)
        assert m, txt[:400]
        return int(m.group(1).replace(",", ""))

    # 조건을 좁혔는데 건수가 줄지 않으면 필터가 실제로 돌지 않은 것이다.
    assert pop(tight) < pop(loose)


def test_query_hash_changes_with_the_sentence(page):
    _tab(page, 1)
    page.fill("section.on input.input", "연체일수 10 이상")
    page.wait_for_timeout(250)
    h1 = page.inner_text("section.on .card .meta")
    page.fill("section.on input.input", "연체일수 20 이상")
    page.wait_for_timeout(250)
    h2 = page.inner_text("section.on .card .meta")
    assert h1 != h2


def test_masked_field_condition_is_blocked_on_screen(page):
    _tab(page, 1)
    page.select_option("section.on select.sel", "V_CRM_EWS_SIGNAL")
    page.wait_for_timeout(200)
    page.fill("section.on input.input", "차주 식별자 OBL_CORP_00001")
    page.wait_for_timeout(250)
    txt = _text(page)
    assert "차단" in txt and "집계 최소단위" in txt
    assert "고정 컬럼 결과" not in txt          # 결과를 그리지 않는다


def test_a_blocking_demo_chip_is_offered(page):
    """차단이 실제로 걸리는 걸 클릭 한 번으로 보여줄 수 있어야 시연이 된다."""
    _tab(page, 1)
    chips = page.eval_on_selector_all("section.on .chip",
                                      "els => els.map(e => e.textContent)")
    assert any("차단 시연" in c for c in chips)


# ----- 비정형 UI: 프롬프트에 따라 레이아웃이 바뀐다 -----------------------------

def _blocks(pg) -> str:
    import re
    m = re.search(r"제안 레이아웃 — (\[.*?\])", _text(pg))
    assert m, _text(pg)[:400]
    return m.group(1)


def test_prompt_changes_the_layout_blocks(page):
    _tab(page, 2)
    page.select_option("section.on select.sel", "V_RWA_SA_BUCKET")
    page.wait_for_timeout(200)

    page.fill("section.on textarea.input", "자산군 기여도를 막대차트로 보여줘")
    page.wait_for_timeout(250)
    assert "bar" in _blocks(page)

    page.fill("section.on textarea.input", "위험가중자산 추이를 보여줘")
    page.wait_for_timeout(250)
    line = _blocks(page)
    assert "line" in line and "bar" not in line

    page.fill("section.on textarea.input", "자산군과 위험가중자산을 카드로 보여줘")
    page.wait_for_timeout(250)
    assert "kpi" in _blocks(page)


def test_prompt_changes_the_selected_columns(page):
    _tab(page, 2)
    page.select_option("section.on select.sel", "V_RWA_SA_BUCKET")
    page.wait_for_timeout(200)
    page.fill("section.on textarea.input", "위험가중자산을 표로")
    page.wait_for_timeout(250)
    one = _text(page)
    page.fill("section.on textarea.input", "위험가중자산과 소요자기자본을 표로")
    page.wait_for_timeout(250)
    two = _text(page)
    assert "cols=(rwa)" in one
    assert "capital_required" in two


def test_top_n_in_the_prompt_caps_the_preview(page):
    _tab(page, 2)
    page.select_option("section.on select.sel", "V_RDM_ASSET_QUALITY")
    page.wait_for_timeout(200)
    page.fill("section.on textarea.input", "잔액 상위 3건을 표로")
    page.wait_for_timeout(250)
    assert "limit=3" in _text(page)


def test_rejected_prompt_shows_the_reason_and_blocks_approval(page):
    _tab(page, 2)
    page.select_option("section.on select.sel", "V_CRM_EWS_SIGNAL")
    page.wait_for_timeout(200)
    page.fill("section.on textarea.input", "차주 식별자와 신호 강도를 행 단위 표로")
    page.wait_for_timeout(250)
    txt = _text(page)
    assert "집계 최소단위 위반" in txt
    assert page.eval_on_selector("section.on .btn.primary", "b => b.disabled")


def test_approve_then_rollback_round_trip(page):
    _tab(page, 2)
    page.select_option("section.on select.sel", "V_RWA_SA_BUCKET")
    page.wait_for_timeout(200)
    page.fill("section.on textarea.input", "자산군 기여도를 막대차트로 보여줘")
    page.wait_for_timeout(250)
    assert not page.eval_on_selector("section.on .btn.primary", "b => b.disabled")

    page.click("section.on .btn.primary")
    page.wait_for_timeout(300)
    assert "승인 적용 화면" in _text(page)

    page.eval_on_selector_all(
        "section.on .btn", "els => els.find(e => e.textContent === 'Rollback').click()")
    page.wait_for_timeout(300)
    assert "승인 적용 화면" not in _text(page)


# ----- Kill Switch ------------------------------------------------------------

def test_kill_switch_stops_new_queries(page):
    page.on("dialog", lambda d: d.accept("통제 점검"))
    page.click(".kill")
    page.wait_for_timeout(400)
    _tab(page, 1)
    # select 옵션 목록에도 "비상정지"라는 테이블명이 있으므로 카드 안만 본다.
    card = page.inner_text("section.on .card")
    assert "비상정지 — 실행 차단" in card
    assert "고정 컬럼 결과" not in card


def test_kill_switch_requires_a_reason(page):
    page.on("dialog", lambda d: d.dismiss())     # 사유 입력 취소
    page.click(".kill")
    page.wait_for_timeout(300)
    assert "Kill Switch 해제" not in page.inner_text(".kill")
    _tab(page, 1)
    assert "비상정지 — 실행 차단" not in page.inner_text("section.on .card")
