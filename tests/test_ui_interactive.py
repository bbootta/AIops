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
def studio(result, portfolio):
    from risk_lib.ui_studio.studio import build_studio
    return build_studio(result, portfolio)


@pytest.fixture(scope="module")
def page_path(studio, tmp_path_factory):
    from risk_lib.ui_studio.app import write_app
    out = tmp_path_factory.mktemp("ui") / "studio.html"
    return write_app(studio, out)


@pytest.fixture(scope="module")
def multi_page_path(studio, tmp_path_factory):
    """실행 2개를 실은 화면 — 기준일 전환을 실제 DOM에서 검증하기 위한 판.

    두 번째 실행은 같은 스냅샷의 얕은 복제다(파이프라인을 두 번 돌리면 이
    모듈이 배로 느려진다). 전환 대상 식별·칩 갱신·재렌더는 payload 내용과
    무관하게 실행 전환 경로 그 자체이므로 이것으로 충분하다.
    """
    import dataclasses
    from risk_lib.ui_studio.app import write_app
    # digest 를 바꿔 둔다 — asof·run_id 만 바꾸면 화면 어디에도 두 실행을
    # 구별할 신호가 없어, 전환이 실제로 일어났는지 단언할 수 없다 (검토 지적:
    # repaintAll 을 지워도 통과하는 테스트였다).
    older = dataclasses.replace(studio, asof="2026-03-31",
                                run_id="RUN-20260331", digest="f" * 64)
    out = tmp_path_factory.mktemp("ui2") / "studio2.html"
    return write_app([studio, older], out)


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


# ----- 컬럼 표시명 — 물리명이 아니라 업무 명칭이 보인다 -------------------------

def test_table_headers_show_catalog_labels_not_physical_names(page):
    """A RDM 첫 테이블(차주 원장)의 머리글이 한글 업무 명칭이다.

    물리명은 버리지 않는다 — th.title 로 남아, 감사자가 어느 원장 컬럼인지
    추적할 수 있다. 표시명의 정본은 카탈로그(ColumnSpec.korean)다.
    """
    _tab(page, 3)                              # A RDM
    ths = page.eval_on_selector_all(
        "section.on .card th",
        "els => els.map(e => [e.textContent, e.title])")
    texts = [t for t, _ in ths]
    assert "차주 식별자" in texts, texts[:10]
    assert "obligor_id" not in texts           # 물리명이 머리글로 나오면 실패
    title = dict((t, ti) for t, ti in ths).get("차주 식별자")
    assert title == "obligor_id"               # 물리명은 툴팁으로 남는다


# ----- ⚙ 설정 ------------------------------------------------------------------

def _tab_named(pg, label: str) -> None:
    """탭을 라벨로 찾는다 — 인덱스 하드코딩은 탭 순서가 바뀌는 순간 다른 탭을
    누르고, 특히 `~ not in` 류 부정 단언을 조용히 항상-참으로 만든다."""
    pg.eval_on_selector_all(
        "nav button",
        "(els, t) => els.find(e => e.textContent.includes(t)).click()", label)
    pg.wait_for_timeout(300)


def test_settings_run_registry_lists_the_runs(page):
    _tab_named(page, '설정')
    txt = page.inner_text("section.on .set-runs")
    assert "RUN-" in txt and "기준일" in txt


def test_settings_label_override_applies_to_the_screen(page):
    """표시명 재정의 → 세션 적용 → 다른 탭의 머리글이 바뀐다."""
    _tab_named(page, '설정')
    page.select_option("section.on .set-labels select.sel", "rdm_obligor")
    page.wait_for_timeout(200)
    page.fill("section.on .set-labels tbody tr:first-child input", "차주 ID")
    page.click("section.on .set-labels .btn.primary")
    page.wait_for_timeout(500)
    _tab(page, 3)                              # A RDM — 재정의가 보인다
    ths = page.eval_on_selector_all(
        "section.on .card th", "els => els.map(e => e.textContent)")
    assert "차주 ID" in ths
    assert page.errors == []


def test_settings_form_map_rejects_duplicate_and_bad_format(page):
    """서식번호 매핑 — 형식 위반·중복은 제안이 되기 전에 걸린다."""
    _tab_named(page, '설정')
    rows = "section.on .set-formmap tbody tr"
    # 2행에 1행의 현행 번호(B2101)를 넣는다 → 중복
    page.fill(f"{rows}:nth-child(2) input", "B2101")
    page.click("section.on .set-formmap .btn.primary")
    page.wait_for_timeout(300)
    err = page.inner_text("section.on .set-formmap .note.bad")
    assert "이미 사용" in err
    # 형식 위반
    page.fill(f"{rows}:nth-child(2) input", "X99")
    page.click("section.on .set-formmap .btn.primary")
    page.wait_for_timeout(300)
    assert "형식 위반" in page.inner_text("section.on .set-formmap .note.bad")


def test_settings_form_map_produces_a_proposal_not_an_edit(page):
    """유효한 변경은 제안서 JSON이 된다 — 화면의 서식번호는 바뀌지 않는다.

    서식번호는 제출 지문이 걸린 값이다. 화면이 즉석에서 바꾸면 제출본과 다른
    화면이 생기고, 그것은 F-501(문서가 다른 실행을 설명) 유형의 화면판이 된다.
    """
    _tab_named(page, '설정')
    page.fill("section.on .set-formmap tbody tr:nth-child(2) input", "B9999")
    page.click("section.on .set-formmap .btn.primary")
    page.wait_for_timeout(300)
    out = page.inner_text("section.on .set-formmap pre")
    assert "form_ids.py" in out and "재실행" in out
    # 감독보고 탭의 서식번호는 그대로다
    _tab_named(page, '감독보고')
    assert "B9999" not in page.inner_text("section.on .list")


def test_settings_scenario_produces_a_proposal_and_never_recomputes(page):
    _tab_named(page, '설정')
    page.fill("section.on .set-scenario tbody tr:first-child input", "0.05")
    page.click("section.on .set-scenario .btn.primary")
    page.wait_for_timeout(300)
    out = page.inner_text("section.on .set-scenario pre")
    assert "위기상황 시나리오" in out and "재계산하지 않는다" in out
    # 숫자가 아니면 거부
    page.fill("section.on .set-scenario tbody tr:first-child input", "많이")
    page.click("section.on .set-scenario .btn.primary")
    page.wait_for_timeout(300)
    assert "숫자가 아니다" in page.inner_text("section.on .set-scenario .note.bad")


def test_settings_proposals_are_blocked_while_killed(page):
    _tab_named(page, '설정')
    page.click("header .kill")
    page.fill("#killreason", "통제 점검")
    page.click(".killbar .killgo")
    page.wait_for_timeout(400)
    _tab_named(page, '설정')
    page.fill("section.on .set-scenario tbody tr:first-child input", "0.05")
    page.click("section.on .set-scenario .btn.primary")
    page.wait_for_timeout(300)
    assert "비상정지" in page.inner_text("section.on .set-scenario .note.bad")


# ----- 기준일 전환 --------------------------------------------------------------

def test_asof_switch_changes_the_active_run(browser, multi_page_path):
    """헤더의 기준일 선택이 실행을 통째로 바꾼다 — 칩·화면이 함께 간다."""
    pg = browser.new_page(viewport={"width": 1400, "height": 1000})
    errors: list[str] = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(f"file://{multi_page_path}")
    pg.wait_for_timeout(600)
    opts = pg.eval_on_selector_all("#asofsel option", "els => els.map(e=>e.value)")
    assert len(opts) == 2
    assert pg.input_value("#asofsel") == max(opts)   # 최신 기준일이 기본
    run_before = pg.inner_text("#chip-run")

    # 재렌더 증명 — 활성 섹션 안에 탐침을 심는다. repaintAll 이 실제로 돌면
    # innerHTML 이 비워지며 탐침이 사라진다. `h2 가 있다` 같은 단언은 전환
    # 전 DOM에도 참이라 repaintAll 을 지워도 통과했다 (검토 실측 지적).
    pg.evaluate("const s=document.querySelector('section.on');"
                "const d=document.createElement('div');d.id='repaint-probe';"
                "s.appendChild(d)")
    assert pg.query_selector("#repaint-probe")

    pg.select_option("#asofsel", min(opts))
    pg.wait_for_timeout(800)
    assert pg.inner_text("#chip-run") != run_before
    assert "RUN-20260331" in pg.inner_text("#chip-run")
    assert "ffffffffffff" in pg.inner_text("#chip-digest")  # 그 실행의 지문
    assert pg.query_selector("#repaint-probe") is None      # 본문이 재렌더됐다
    assert errors == []
    pg.close()


# ----- 검토(3렌즈 워크플로)가 찾은 결함의 고정 --------------------------------

def test_five_digit_official_form_numbers_are_accepted(page):
    """B10101 등 5자리 숫자부 배포 코드 9종이 실재한다 — 형식 검사가 거부하면
    실코드를 쓰는 정당한 제안이 만들어지지 않는다."""
    _tab_named(page, '설정')
    page.fill("section.on .set-formmap tbody tr:nth-child(2) input", "B99901")
    page.click("section.on .set-formmap .btn.primary")
    page.wait_for_timeout(300)
    out = page.inner_text("section.on .set-formmap pre")
    assert '"to": "B99901"' in out.replace("'", '"')


def test_internal_form_number_duplicate_is_caught(page):
    """내부관리 서식의 form_no는 'RM-#### (내부관리)' 표시문자열이다 — 중복
    검사가 표시문자열을 키로 쓰면 'RM-####' 입력이 그대로 지나간다."""
    _tab_named(page, '설정')
    rm = page.evaluate(
        "window.__RYNTA__.forms.find(f=>f.form_no.startsWith('RM-'))"
        ".form_no.split(' ')[0]")
    page.fill("section.on .set-formmap tbody tr:nth-child(2) input", rm)
    page.click("section.on .set-formmap .btn.primary")
    page.wait_for_timeout(300)
    assert "이미 사용" in page.inner_text("section.on .set-formmap .note.bad")


def test_kill_switch_blocks_adaptive_preview_and_approval(page):
    """비상정지는 비정형 UI에도 미친다 — 정형 조회만 막으면 절반짜리 통제다."""
    page.click("header .kill")
    page.fill("#killreason", "통제 점검")
    page.click(".killbar .killgo")
    page.wait_for_timeout(400)
    _tab(page, 2)
    page.select_option("section.on select.sel", "V_RWA_SA_BUCKET")
    page.wait_for_timeout(200)
    page.fill("section.on textarea.input", "자산군 기여도를 막대차트로 보여줘")
    page.wait_for_timeout(300)
    assert page.eval_on_selector("section.on .btn.primary", "b => b.disabled")
    assert "Kill Switch가 걸려 있어" in _text(page)


def test_asof_switch_does_not_carry_approvals_across_runs(browser, multi_page_path):
    """승인은 실행에 속한다 — proposal_id 가 (view, 프롬프트) 해시라 실행이
    바뀌어도 같으므로, 전환 시 승인을 실행별로 갈라 두지 않으면 이전 기준일
    데이터로 받은 승인이 새 기준일 화면에 '승인 적용'으로 뜬다."""
    pg = browser.new_page(viewport={"width": 1400, "height": 1000})
    errors: list[str] = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(f"file://{multi_page_path}")
    pg.wait_for_timeout(600)

    _tab(pg, 2)                                    # 비정형 UI에서 승인
    pg.select_option("section.on select.sel", "V_RWA_SA_BUCKET")
    pg.wait_for_timeout(200)
    pg.fill("section.on textarea.input", "자산군 기여도를 막대차트로 보여줘")
    pg.wait_for_timeout(300)
    pg.click("section.on .btn.primary")
    pg.wait_for_timeout(300)
    assert "승인 적용 화면" in pg.inner_text("section.on")

    opts = pg.eval_on_selector_all("#asofsel option", "els => els.map(e=>e.value)")
    pg.select_option("#asofsel", min(opts))        # 다른 실행으로 전환
    pg.wait_for_timeout(800)
    pg.select_option("section.on select.sel", "V_RWA_SA_BUCKET")
    pg.wait_for_timeout(200)
    pg.fill("section.on textarea.input", "자산군 기여도를 막대차트로 보여줘")
    pg.wait_for_timeout(300)
    txt = pg.inner_text("section.on")
    assert "승인 적용 화면" not in txt             # 승인이 따라오면 안 된다

    pg.select_option("#asofsel", max(opts))        # 돌아오면 승인이 살아 있다
    pg.wait_for_timeout(800)
    pg.select_option("section.on select.sel", "V_RWA_SA_BUCKET")
    pg.wait_for_timeout(200)
    pg.fill("section.on textarea.input", "자산군 기여도를 막대차트로 보여줘")
    pg.wait_for_timeout(300)
    assert "승인 적용 화면" in pg.inner_text("section.on")
    assert errors == []
    pg.close()
