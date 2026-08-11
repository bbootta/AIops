"""기관 선택기와 기관 설정 화면.

핵심 명제:
  1) 화면은 기관 산출을 만들지 않는다. 실행을 (기관, 기준일)로 갈라 미리
     싣고 그 사이를 오갈 뿐이다.
  2) 기관 선택기는 기준일 선택기 **왼쪽**에 있다 (사용자가 위치를 지정했다).
  3) 기관 설정 화면의 모든 값은 기관 축 원장에서 온다. 화면에 리터럴이 없다.
  4) 파일 크기 상한을 넘으면 조용히 줄이지 않고 경고로 드러낸다.

기관 2곳을 실제로 돌리면 이 모듈만 3분 더 걸린다. 전환 경로 자체는 payload
내용과 무관하므로 두 번째 기관은 같은 스냅샷의 얕은 복제로 만든다. 권역별
합성 기관을 실제로 돌린 결과는 tests/test_intl.py 가 고정한다.
"""

from __future__ import annotations

import dataclasses
import json
import os
import re
import warnings
from pathlib import Path

import pytest

from risk_lib import data_gen_intl as intl
from risk_lib.ui_studio import app as uiapp
from risk_lib.ui_studio import i18n
from risk_lib.ui_studio.app import render, write_app
from risk_lib.ui_studio.studio import build_studio

_OTHER = "EU_BANK_01"


@pytest.fixture(scope="module")
def studio(result, portfolio):
    return build_studio(result, portfolio)


@pytest.fixture(scope="module")
def two(studio):
    """기관 2곳을 실은 판. 두 번째는 얕은 복제이고 지문을 갈라 둔다."""
    other = dataclasses.replace(
        studio, institution_code=_OTHER, run_id="RUN-EU", digest="f" * 64)
    return [studio, other]


def _runs(h: str) -> dict:
    m = re.search(r"window\.__RYNTA_RUNS__=(\{.*\});\nwindow\.__RYNTA__", h, re.S)
    assert m, "실행 payload 를 찾지 못했다"
    return json.loads(m.group(1))


def _insts_src(h: str) -> str:
    m = re.search(r"window\.__RYNTA_INSTS__=(.*);\nwindow\.__RYNTA_I18N__",
                  h, re.S)
    assert m, "기관 payload 를 찾지 못했다"
    return m.group(1)


# ----- payload ----------------------------------------------------------------

def test_studio_carries_the_institution_of_its_run(studio):
    """실행은 자기 기관을 안다. 모르면 화면이 어느 기관의 수치인지 못 적는다."""
    assert studio.institution_code == intl.BASE_INSTITUTION


def test_institution_ledgers_are_built_but_kept_out_of_the_run_tables(studio):
    """축 마스터는 실행 산출물이 아니다. 실행 원장에 섞으면 기관귀속·DQ 판정이
    전 기관이 든 원장까지 세게 된다."""
    for name in uiapp._INST_TABLES:
        assert name in studio.inst_tables, f"{name} 원장이 없다"
        assert len(studio.inst_tables[name]) > 0, f"{name} 원장이 비었다"
        assert name not in studio.tables, f"{name} 이 실행 원장에 섞였다"


def test_payload_carries_the_axis_and_the_selected_row(studio):
    d = _runs(render(studio))[studio.asof]
    assert d["meta"]["institution_code"] == intl.BASE_INSTITUTION
    inst = d["institution"]
    assert inst["code"] == intl.BASE_INSTITUTION
    assert set(inst["tables"]) == set(uiapp._INST_TABLES)
    assert inst["master_row"]["institution_code"] == intl.BASE_INSTITUTION
    assert inst["profile_row"]["institution_code"] == intl.BASE_INSTITUTION


def test_column_labels_come_from_the_spec_not_the_screen(studio):
    """기관 원장은 ALL_TABLES 밖이라, 표시명을 따로 이어 두지 않으면 화면의
    열 머리가 전부 물리명으로 떨어진다."""
    f = _runs(render(studio))[studio.asof]["institution"]["tables"]["inst_master"]
    labels = dict(zip(f["columns"], f["labels"]))
    spec = {c.name: c.korean for c in intl.INST_MASTER_INTL.columns}
    assert labels["institution_code"] == spec["institution_code"]
    assert all(v for v in labels.values()), "표시명이 빈 컬럼이 있다"


# ----- 선택기 위치 ------------------------------------------------------------

def test_institution_selector_sits_left_of_the_asof_selector(studio):
    h = render(studio)
    assert 'id="instsel"' in h
    assert h.index('id="instsel"') < h.index('id="asofsel"'), (
        "기관 선택기가 기준일 선택기 오른쪽에 있다")


# ----- 기관 축 전환 -----------------------------------------------------------

def test_render_splits_runs_by_institution(two, studio):
    h = render(two)
    src = _insts_src(h)
    assert f'"{intl.BASE_INSTITUTION}":' in src
    assert f'"{_OTHER}":' in src
    # 기본 화면은 기관 원장 순서의 첫 기관이다.
    assert _runs(h)[studio.asof]["meta"]["institution_code"] == \
        intl.BASE_INSTITUTION


def test_primary_institution_payload_is_not_duplicated(two):
    """같은 payload 를 두 벌 실으면 파일이 그만큼 커지고 한쪽만 고쳐질 수 있다."""
    src = _insts_src(render(two))
    assert f'"{intl.BASE_INSTITUTION}":window.__RYNTA_RUNS__' in src


def test_switching_run_keys_state_by_institution_and_asof():
    """승인 도장이 다른 기관 화면으로 옮겨 찍히면 안 된다."""
    js = uiapp._JS
    assert "function runKey(d)" in js
    assert "d.meta.institution_code" in js
    assert "function setInst(" in js


def test_screen_cannot_calculate_a_new_institution():
    """화면에 기관 산출 경로가 없다. 선택은 실린 실행 사이의 전환뿐이다."""
    js = uiapp._JS
    assert "INSTS[code]" in js
    assert "run_pipeline(" not in js.split("function setInst(")[1][:600]


# ----- 화면 등록 --------------------------------------------------------------

def test_screen_is_registered_in_the_settings_group_and_tabs():
    js = uiapp._JS
    nav = js[js.index("const NAVGROUPS=["):js.index("const TABS=[")]
    tabs = js[js.index("const TABS=["):]
    assert "['⚙ 설정',['기관 설정'" in nav, "설정 화면그룹에 없다"
    assert "'기관 설정'" in tabs and "institutions]" in tabs


def test_nav_label_and_header_label_are_registered():
    m = i18n.ko_to_en()
    assert m["기관 설정"] == "Institution setup"
    assert m["기관"] == "Institution"


def test_screen_reads_only_the_institution_axis_ledgers():
    """화면이 참조하는 원장 이름이 기관 축 원장 다섯 장뿐이다."""
    js = uiapp._JS
    body = js[js.index("function institutions(root){"):
              js.index("function settings(root){")]
    refs = set(re.findall(r"instFrame\('([a-z0-9_]+)'\)", body))
    refs |= set(re.findall(r"'([a-z0-9_]+)'\]", body))
    unknown = sorted(r for r in refs if r not in uiapp._INST_TABLES)
    assert unknown == [], f"기관 축 밖의 원장을 참조한다: {unknown}"


def test_synthetic_institutions_are_marked_on_the_screen():
    js = uiapp._JS
    body = js[js.index("function institutions(root){"):
              js.index("function settings(root){")]
    assert "'합성'" in body, "합성 기관 표기가 화면에 없다"
    assert "데이터 출처가 합성인 기관은" in body


# ----- 파일 크기 --------------------------------------------------------------

def test_deploy_limit_is_declared():
    assert uiapp.DEPLOY_SIZE_LIMIT == 16 * 1024 * 1024


def test_oversize_warns_and_writes_the_whole_file(studio, tmp_path, monkeypatch):
    """상한을 넘겨도 화면을 자르지 않는다. 조용히 잘린 원장은 흔적이 없다."""
    monkeypatch.setattr(uiapp, "DEPLOY_SIZE_LIMIT", 1024)
    out = tmp_path / "s.html"
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        write_app(studio, out)
    msgs = [str(x.message) for x in w if "UI 스튜디오 HTML" in str(x.message)]
    assert msgs, "상한을 넘겼는데 경고가 없다"
    assert "행 예산" in msgs[0], "무엇을 줄일지 경고가 말하지 않는다"
    assert out.read_text(encoding="utf-8").endswith("</body></html>")


def test_no_warning_below_the_limit(studio, tmp_path):
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        write_app(studio, tmp_path / "s.html")
    assert not [x for x in w if "배포 상한" in str(x.message)]


# ----- 브라우저 ---------------------------------------------------------------

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright  # noqa: E402

_CHROME = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH",
                              "/opt/pw-browsers")) / "chromium"
pytestmark = pytest.mark.skipif(not _CHROME.exists(), reason="chromium 미설치")


@pytest.fixture(scope="module")
def page_path(two, tmp_path_factory):
    return write_app(two, tmp_path_factory.mktemp("inst") / "studio.html")


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
    yield pg
    pg.close()


def test_selector_lists_loaded_institutions_in_ledger_order(page):
    opts = page.eval_on_selector_all("#instsel option", "e=>e.map(x=>x.value)")
    assert opts == [intl.BASE_INSTITUTION, _OTHER]
    assert page.input_value("#instsel") == intl.BASE_INSTITUTION


def test_switching_institution_repaints_the_whole_screen(page):
    before = page.inner_text("#chip-run")
    page.evaluate("const s=document.querySelector('section.on');"
                  "const d=document.createElement('div');d.id='probe';"
                  "s.appendChild(d)")
    assert page.query_selector("#probe")
    page.select_option("#instsel", _OTHER)
    page.wait_for_timeout(800)
    assert page.inner_text("#chip-run") != before
    assert "RUN-EU" in page.inner_text("#chip-run")
    assert "ffffffffffff" in page.inner_text("#chip-digest")
    assert page.query_selector("#probe") is None
    assert page.evaluate("window.__RYNTA__.meta.institution_code") == \
        intl.BASE_INSTITUTION      # 원본 payload 는 손대지 않는다


def test_header_chip_shows_region_type_and_origin(page):
    chip = page.inner_text("#chip-inst")
    assert "국내" in chip and "은행" in chip


def test_institution_screen_lists_every_ledger_row(page):
    page.evaluate("""()=>{const b=[...document.querySelectorAll('nav button')]
        .find(x=>x.dataset.ko==='기관 설정'); b.click()}""")
    page.wait_for_timeout(400)
    txt = page.inner_text("section.on")
    for code in intl.institution_codes():
        assert code in txt, f"{code} 이 기관 설정 화면에 없다"
    assert "합성" in txt
    # 산출이 실리지 않은 기관은 그렇게 적힌다.
    assert page.evaluate("window.__I18N__.T('산출 미적재')") in txt


def test_institution_screen_leaves_no_untranslated_string(page):
    page.evaluate("window.__I18N__.miss.length=0")
    page.evaluate("""()=>{const b=[...document.querySelectorAll('nav button')]
        .find(x=>x.dataset.ko==='기관 설정'); b.click()}""")
    page.wait_for_timeout(400)
    assert page.evaluate("window.__I18N__.miss.slice()") == []
