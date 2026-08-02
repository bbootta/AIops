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
#
# 이 두 검사는 원래 `page.on("dialog", …)`로 prompt()에 답해 주고 통과했다.
# **테스트가 통제에 없는 도움을 주고 있었다** — 샌드박스 iframe(임베드·아티팩트)은
# prompt()를 차단하고 null을 돌려주므로, 실제 배포 화면에서는 비상정지 버튼을
# 눌러도 아무 일도 일어나지 않는다. 통과하는 검사가 죽은 통제를 덮은 것이다.
#
# 그래서 사유 입력을 화면 안으로 옮기고, 검사에서 dialog 핸들러를 **뺐다**.
# 이제 이 검사가 통과한다는 것은 대화상자 없이도 통제가 산다는 뜻이다.

def test_kill_switch_stops_new_queries_without_any_dialog(page):
    page.click(".kill")                          # 사유 입력줄이 화면 안에 열린다
    page.wait_for_timeout(200)
    assert not page.eval_on_selector(".killbar", "e => e.hidden")
    page.fill("#killreason", "통제 점검")
    page.click(".killbar .killgo")
    page.wait_for_timeout(400)
    assert "Kill Switch 해제" in page.inner_text(".kill")
    _tab(page, 1)
    # select 옵션 목록에도 "비상정지"라는 테이블명이 있으므로 카드 안만 본다.
    card = page.inner_text("section.on .card")
    assert "비상정지 — 실행 차단" in card
    assert "고정 컬럼 결과" not in card
    assert page.errors == []


def test_kill_switch_requires_a_reason(page):
    page.click(".kill")
    page.wait_for_timeout(200)
    page.fill("#killreason", "   ")               # 공백만 — 사유가 아니다
    page.click(".killbar .killgo")
    page.wait_for_timeout(300)
    assert "Kill Switch 해제" not in page.inner_text(".kill")
    _tab(page, 1)
    assert "비상정지 — 실행 차단" not in page.inner_text("section.on .card")


def test_kill_switch_can_be_cancelled(page):
    page.click(".kill")
    page.wait_for_timeout(200)
    page.click(".killbar .killno")
    page.wait_for_timeout(200)
    assert page.eval_on_selector(".killbar", "e => e.hidden")
    assert "Kill Switch 해제" not in page.inner_text(".kill")


def test_no_control_depends_on_a_blocked_modal_dialog(page_path):
    """화면이 prompt()·alert()·confirm()에 기대지 않는다.

    이 셋은 샌드박스 iframe에서 차단된다. 차단되면 예외가 아니라 **조용한
    무반응**이 되므로, 그 위에 올린 통제(비상정지 사유, 승인 거부 사유)는 있는
    것처럼 보이면서 작동하지 않는다. 배포 화면에서 제일 나쁜 실패 방식이다.
    """
    import re
    html = Path(page_path).read_text(encoding="utf-8")
    # 주석에서 이 셋을 **언급**하는 것은 정상이다 — 실제로 이 파일의 주석이
    # 왜 쓰지 않는지를 설명한다. 코드만 본다. 주석까지 잡으면 다음 사람이
    # 설명을 지우거나 검사를 끄게 되고, 그러면 통제가 아니라 방해가 된다.
    code = re.sub(r"/\*.*?\*/", " ", html, flags=re.S)
    code = re.sub(r"(?m)//.*$", " ", code)
    hits = re.findall(
        r"(?<![\w.])(?:window\.)?(?:prompt|alert|confirm)\s*\(", code)
    assert not hits, f"차단되는 대화상자 호출 {len(hits)}건 — 화면 안 입력으로 옮겨라"


# ----- E 위기상황: 심각도별 전 단계 산출과정 ------------------------------------

def _stress_tab(pg) -> None:
    labels = pg.eval_on_selector_all("nav button", "els => els.map(e => e.textContent)")
    _tab(pg, labels.index("E 위기상황"))
    pg.wait_for_timeout(400)


def test_stress_screen_shows_every_calculation_block(page):
    _stress_tab(page)
    txt = _text(page)
    for block in ("거시", "충격축", "신용파라미터", "신용RWA", "시장",
                  "은행계정금리", "운영", "유동성", "손익", "자본",
                  "RWA합계", "비율", "판정"):
        assert block in txt, block
    # 산식·투입값·근거가 화면에 있어야 "산출 과정"이다.
    assert "logit(PD)" in txt and "IFRS 9 5.5" in txt


def test_stress_screen_lists_every_shock_axis(page):
    """신용만 충격하는 화면은 통합위기상황분석이 아니다."""
    from risk_lib.stress.axes import AXES
    _stress_tab(page)
    txt = _text(page)
    for a in AXES:
        assert a.korean in txt, a.korean
    for risk_type in ("신용", "시장", "운영", "유동성", "수익"):
        assert f"({risk_type})" in txt, risk_type


def test_stress_screen_shows_non_credit_propagation(page):
    """시장·운영·유동성·수익이 실제로 움직이는 것이 화면에 보여야 한다."""
    _stress_tab(page)
    txt = _text(page)
    for step in ("트레이딩 손익 합계", "ΔEVE", "내부손실승수 (ILM)",
                 "유동성커버리지비율", "당기순이익", "산출하한 증가분"):
        assert step in txt, step


def test_stress_screen_compares_every_severity(page):
    _stress_tab(page)
    txt = _text(page)
    for sc in ("baseline", "adverse", "severely_adverse"):
        assert sc in txt, sc
    assert "심각도 비교" in txt


def test_changing_severity_changes_the_traced_values(page):
    _stress_tab(page)
    import re

    def pd_shock() -> float:
        m = re.search(r"PD \(충격 후\)\s+([\d.]+)%", _text(page))
        assert m, _text(page)[:600]
        return float(m.group(1))

    severe = pd_shock()
    page.eval_on_selector_all(
        "section.on .chips .chip",
        "els => els.find(e => e.textContent === 'baseline').click()")
    page.wait_for_timeout(400)
    base = pd_shock()
    assert base < severe, "심도를 낮췄는데 충격 PD가 줄지 않았다"


def test_changing_quarter_changes_the_trace(page):
    _stress_tab(page)
    first = _text(page)
    opts = page.eval_on_selector_all("section.on select.sel option",
                                     "els => els.map(e => e.value)")
    page.select_option("section.on select.sel", opts[0])
    page.wait_for_timeout(400)
    a = _text(page)
    page.select_option("section.on select.sel", opts[-1])
    page.wait_for_timeout(400)
    assert a != _text(page)


def test_trough_button_selects_the_worst_quarter(page):
    _stress_tab(page)
    page.eval_on_selector_all(
        "section.on .btn", "els => els.find(e => e.textContent === '저점 분기로').click()")
    page.wait_for_timeout(400)
    q = page.eval_on_selector("section.on select.sel", "s => s.value")
    assert q                                  # 저점 분기가 선택돼 있다
    assert "심각도 비교 · " + q in _text(page)


def test_blocks_collapse_and_expand(page):
    _stress_tab(page)
    assert "logit(PD)" in _text(page)
    page.eval_on_selector_all(
        "section.on .blockhead",
        "els => els.find(e => e.textContent.includes('신용파라미터')).click()")
    page.wait_for_timeout(300)
    assert "logit(PD)" not in _text(page)


# ----- R 감독보고: 편제 전 영역 -------------------------------------------------

def test_regulatory_tab_covers_every_regulation_section(page):
    """편제마다 최소 한 서식의 번호가 화면에 보여야 한다.

    이전에는 서식번호 8개를 손으로 박아 뒀는데, 금감원 FINES 마스터를 확보해
    번호를 전부 정정하자 테스트가 옛 코드를 찾다가 깨졌다. 번호는 마스터가
    정본이므로 여기서 다시 적지 않고 레지스트리에서 가져온다.
    """
    from risk_lib.regulatory.form_ids import SECTIONS, form_id
    labels = page.eval_on_selector_all("nav button", "els => els.map(e => e.textContent)")
    _tab(page, labels.index("R 감독보고"))
    txt = _text(page)
    for section, ids in SECTIONS:
        assert ids, section
        code = form_id(ids[0]).display().split(" ")[0]
        assert code in txt, (section, code)


# ----- F 검증: 두 층이 화면에서 구분되는가 --------------------------------------

def test_validation_tab_separates_self_and_independent(page):
    from risk_lib.validation.independent import VALIDATION_TEAM_BRANCH
    labels = page.eval_on_selector_all("nav button", "els => els.map(e => e.textContent)")
    _tab(page, labels.index("F 검증"))
    txt = _text(page)
    assert "자체검증 (2선)" in txt
    assert "상시 독립검증 (3선)" in txt
    assert VALIDATION_TEAM_BRANCH in txt
    assert "fail-closed" in txt


def test_validation_tab_shows_the_gate_is_pending(page):
    """2선이 전건 PASS여도 3선 게이트는 열리지 않는다."""
    labels = page.eval_on_selector_all("nav button", "els => els.map(e => e.textContent)")
    _tab(page, labels.index("F 검증"))
    txt = _text(page)
    assert "응답대기" in txt
    assert "독립 재계산 대상" in txt
    assert "3선이 도전해야 할 가정" in txt
