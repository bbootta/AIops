"""Next-generation UI shell in Chromium: what only a browser can prove.

Design spec section 8: A6, A7, A8, A9, A13, A14, A17, A18, A23, A25. The
criteria that need no browser are in tests/test_ui_next.py.

Every expected value comes from the fixture frames, the registry or the
catalogue. A count such as "89 screens" or "294 approvals" is read from
payload_ext.SCREEN_REGISTRY or from studio.tables at test time, never typed in,
so a different fixture asof cannot leave a pin stale while it still looks
like a control.
"""

from __future__ import annotations

import dataclasses
import os
import re
from pathlib import Path

import pytest

from risk_lib.datamodel import catalog as cat
from risk_lib.ui_studio.next import i18n_next, payload_ext
from risk_lib.ui_studio.next import render as R

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright  # noqa: E402

_CHROME = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")) / "chromium"
pytestmark = pytest.mark.skipif(not _CHROME.exists(), reason="chromium not installed")

REGISTRY = payload_ext.SCREEN_REGISTRY
IDS = [e["id"] for e in REGISTRY]
BY_ID = {e["id"]: e for e in REGISTRY}
GROUPS = sorted(R.load_registry_files()[0]["groups"], key=lambda g: g["order"])
# A7: the screen must name where its numbers come from. The shell prints the
# catalogued English of these keys in English, so both sides are accepted.
_MARKER_KEYS = ("연결 원장", "기준값의 출처", "한도 정의")
_CATALOGUE = i18n_next.merged_map()
LEDGER_MARKERS = tuple(dict.fromkeys(
    list(_MARKER_KEYS) + [_CATALOGUE[k] for k in _MARKER_KEYS if k in _CATALOGUE]))


def _screen_tables(entry: dict) -> set[str]:
    """A8 expansion: the named tables plus every catalogue table of a product."""
    names = set(entry.get("tables", []))
    for p in entry.get("products", []):
        names |= {sp.name for sp in cat.by_product(p)}
    return names


def _label(entry: dict) -> str:
    return (entry["legacy"] or [entry["title_ko"]])[0]


# ---------------------------------------------------------------- fixtures

@pytest.fixture(scope="module")
def studio(result, portfolio):
    from risk_lib.ui_studio.studio import build_studio
    return build_studio(result, portfolio)


@pytest.fixture(scope="module")
def app_path(studio, tmp_path_factory):
    out = tmp_path_factory.mktemp("uinextb") / "studio_next.html"
    return R.write_app_next(studio, out)


@pytest.fixture(scope="module")
def multi_path(studio, tmp_path_factory):
    """A17: a second run that differs in asof, run_id and digest.

    The digest is what makes the switch visible; with asof and run_id alone a
    test cannot tell a repaint from a no-op.
    """
    older = dataclasses.replace(studio, asof="2026-03-31",
                                run_id="RUN-20260331", digest="f" * 64)
    out = tmp_path_factory.mktemp("uinextm") / "studio_next_two.html"
    return R.write_app_next([studio, older], out)


@pytest.fixture(scope="module")
def ext(studio):
    return payload_ext.build_ext(studio)


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=str(_CHROME))
        yield b
        b.close()


def _open(browser, path, lang=None, width=1400, height=1000):
    pg = browser.new_page(viewport={"width": width, "height": height})
    pg.errors, pg.console_errors = [], []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.on("console", lambda m: pg.console_errors.append(m.text)
          if m.type == "error" else None)
    if lang:
        pg.add_init_script(f"localStorage.setItem('rynta-lang','{lang}')")
    pg.goto(f"file://{path}")
    pg.wait_for_function("window.NG!==undefined && window.__I18N__!==undefined")
    pg.wait_for_timeout(300)
    return pg


@pytest.fixture(scope="module")
def pages(browser, app_path):
    """One read only page per language, shared by the sweeps."""
    out = {"en": _open(browser, app_path), "ko": _open(browser, app_path, "ko")}
    yield out
    for pg in out.values():
        pg.close()


@pytest.fixture
def page(browser, app_path):
    pg = _open(browser, app_path)
    yield pg
    pg.close()


@pytest.fixture
def ko_page(browser, app_path):
    pg = _open(browser, app_path, "ko")
    yield pg
    pg.close()


@pytest.fixture
def multi_page(browser, multi_path):
    pg = _open(browser, multi_path)
    yield pg
    pg.close()


def _go(pg, sid: str) -> None:
    pg.evaluate("id=>{window.NG.go(id)}", sid)
    pg.wait_for_timeout(140)


def _text(pg) -> str:
    return pg.inner_text("section.on")


def _screen(pg, sid: str) -> dict:
    _go(pg, sid)
    return pg.evaluate("""() => {
        const s = document.querySelector('section.on');
        if (!s) return null;
        return {id: s.dataset.screen,
                text: s.innerText,
                th: Array.from(s.querySelectorAll('th')).map(e => e.title).join(' '),
                svg: s.querySelectorAll('svg[role=img]').length,
                h2: (s.querySelector('h2') || {}).textContent || ''};
    }""")


def _num_forms(n: int) -> tuple[str, ...]:
    """The screen may print a count plain or with thousands separators."""
    return (str(n), f"{n:,}")


def _has_count(text: str, prefix: str, n: int) -> bool:
    return any(f"{prefix}{form}" in text for form in _num_forms(n))


# ---------------------------------------------------------------- A6 nav

def test_registry_and_registrations_are_the_same_set(pages):
    registered = pages["en"].evaluate("()=>Array.from(NG.registry.keys())")
    assert sorted(registered) == sorted(IDS), {
        "missing": sorted(set(IDS) - set(registered)),
        "unknown": sorted(set(registered) - set(IDS))}


def test_every_nav_button_is_a_screen(pages):
    pg = pages["en"]
    assert pg.eval_on_selector_all("nav button:not([data-ko])", "e=>e.length") == 0
    assert pg.eval_on_selector_all("nav button.navgroup", "e=>e.length") == 0
    kos = pg.eval_on_selector_all("nav button", "els=>els.map(e=>e.dataset.ko)")
    assert len(kos) == len(set(kos)) == len(IDS)
    assert set(kos) == {_label(e) for e in REGISTRY}
    ids = pg.eval_on_selector_all("nav button", "els=>els.map(e=>e.dataset.id)")
    assert sorted(ids) == sorted(IDS)


def test_every_absorbed_legacy_label_has_exactly_one_button(pages):
    kos = pages["en"].eval_on_selector_all("nav button", "els=>els.map(e=>e.dataset.ko)")
    for label in payload_ext.legacy_labels():
        assert kos.count(label) == 1, label
    assert len(set(kos)) >= 60


def test_group_headers_are_divs_in_registry_order(pages):
    heads = pages["en"].eval_on_selector_all(
        "nav .navgroup", "els=>els.map(e=>({ko:e.dataset.ko, cls:e.className, "
        "role:e.getAttribute('role'), tab:e.tabIndex, "
        "exp:e.getAttribute('aria-expanded'), tag:e.tagName}))")
    tops = [h for h in heads if h["cls"] == "navgroup"]
    assert [h["ko"] for h in tops] == [g["label_ko"] for g in GROUPS]
    for h in heads:
        assert h["tag"] == "DIV" and h["role"] == "button"
        assert h["tab"] == 0 and h["exp"] in ("true", "false")


def test_subgroup_head_and_leaves_carry_the_level_classes(pages):
    """A6: a leaf_parent screen is a button; a plain subgroup is a header div."""
    pg = pages["en"]
    inventory = next(e for e in REGISTRY
                     if e["slug"] == "models" and e["leaf_parent"] and e["sub"] is None)
    cls = pg.eval_on_selector_all(
        "nav button", "(els,ko)=>{const b=els.find(e=>e.dataset.ko===ko);"
        "return b?b.className:null}", _label(inventory))
    assert cls == "lvl1", cls
    # The credit model subgroup: registry decides how many leaves it has. The
    # design spec text says five, the committed models.json lists the leaves
    # below; the shell contract records that deviation for the registry owner.
    heads = {e["title_ko"] for e in REGISTRY if e["leaf_parent"]}
    sub = next(e["sub"] for e in REGISTRY
               if e["slug"] == "models" and e["sub"] and e["sub"] not in heads)
    leaves = [e for e in REGISTRY if e["sub"] == sub]
    head = pg.eval_on_selector_all(
        "nav .navgroup", "(els,ko)=>{const h=els.find(e=>e.dataset.ko===ko);"
        "return h?h.className:null}", sub)
    assert head == "navgroup sub lvl1", (sub, head)
    for leaf in leaves:
        cls = pg.eval_on_selector_all(
            "nav button", "(els,ko)=>{const b=els.find(e=>e.dataset.ko===ko);"
            "return b?b.className:null}", _label(leaf))
        assert cls == "lvl2", (leaf["id"], cls)


def test_headers_toggle_on_click_enter_and_space(page):
    sel = "nav .navgroup"
    state = lambda: page.eval_on_selector_all(
        sel, "els=>els[0].getAttribute('aria-expanded')")
    first = state()
    page.eval_on_selector_all(sel, "els=>els[0].click()")
    page.wait_for_timeout(80)
    assert state() != first
    for key in ("Enter", " "):
        before = state()
        page.eval_on_selector_all(sel, "els=>els[0].focus()")
        page.keyboard.press(key)
        page.wait_for_timeout(80)
        assert state() != before, key


def test_the_settings_leaf_keeps_its_original_label_as_the_key(pages):
    entry = next(e for e in REGISTRY if e["slug"] == "settings" and e["sub"] is None)
    got = pages["ko"].eval_on_selector_all(
        "nav button", "(els,ko)=>{const b=els.find(e=>e.dataset.ko===ko);"
        "return b?b.textContent:null}", _label(entry))
    nav_display = R.load_registry_files()[0].get("NAV_DISPLAY", {})
    assert got == nav_display.get(_label(entry), _label(entry))


# ---------------------------------------------------------------- A7 every screen

@pytest.mark.parametrize("lang", ("en", "ko"))
@pytest.mark.parametrize("sid", IDS)
def test_every_screen_renders_without_a_script_error(pages, sid, lang):
    pg = pages[lang]
    before = (len(pg.errors), len(pg.console_errors))
    info = _screen(pg, sid)
    assert info and info["id"] == sid, info
    assert (len(pg.errors), len(pg.console_errors)) == before, (
        pg.errors[before[0]:] + pg.console_errors[before[1]:])
    assert info["h2"].strip(), "the screen has no title"
    assert len(info["text"]) > 400, f"{len(info['text'])} characters only"
    assert any(m in info["text"] for m in LEDGER_MARKERS), (
        "the screen does not name where its numbers come from")


# ---------------------------------------------------------------- A8 census

@pytest.mark.parametrize("sid", IDS)
def test_every_screen_names_its_ledgers_and_draws_its_charts(pages, sid):
    entry = BY_ID[sid]
    info = _screen(pages["en"], sid)
    hay = info["text"] + " " + info["th"]
    missing = sorted(t for t in _screen_tables(entry) if t not in hay)
    assert missing == [], missing
    assert info["svg"] >= entry["min_svg"], (
        f"{info['svg']} charts, {entry['min_svg']} required")


def test_the_census_covers_the_whole_catalogue():
    """A8 dead control: if the union shrinks, the census stops meaning anything."""
    names = {sp.name for sp in cat.ALL_TABLES}
    union: set[str] = set()
    for e in REGISTRY:
        union |= _screen_tables(e) & names
    assert union == names, sorted(names - union)
    assert all(isinstance(e.get("min_svg"), int) for e in REGISTRY)


# ---------------------------------------------------------------- A9 and A25 gate strip

def _gate_expectation(studio, ext) -> tuple[str, str]:
    """Status verbatim from the ledger row; tone from the built gate (A9, 3.2).

    The tone rule itself is pinned against the status in tests/test_ui_next.py,
    so it is stated once and read here.
    """
    status = str(studio.tables["val_independent_request"].iloc[0]["status"])
    return status, ext["x_gate"]["overall"]["tone"]


@pytest.mark.parametrize("sid", ("exec-report", "cockpit"))
def test_gate_strip_repeats_the_ledger_verdict(pages, studio, ext, sid):
    pg = pages["ko"]
    _go(pg, sid)
    strip = pg.evaluate("""() => {const g=document.querySelector('#gatestrip');
        return g ? {status:g.dataset.gateStatus, tone:g.dataset.tone,
                    text:g.innerText, segs:g.querySelectorAll('.gseg').length,
                    role:g.getAttribute('role')} : null}""")
    status, tone = _gate_expectation(studio, ext)
    assert strip is not None
    assert strip["role"] == "status"
    assert strip["status"] == status
    assert strip["tone"] == tone
    assert status in strip["text"], strip["text"]
    assert strip["segs"] >= 3, "the strip lost a segment"


@pytest.mark.parametrize("sid", ("exec-report", "cockpit"))
def test_gate_strip_counts_come_from_the_second_line_ledger(pages, studio, sid):
    """A9 and A25: the strip is not a static note; the numbers are the tally."""
    pg = pages["ko"]
    _go(pg, sid)
    text = pg.inner_text("#gatestrip")
    vc = studio.tables["val_check"]
    live = vc[~vc["is_identity"].astype(bool)]
    not_run = live["check_name"].astype(str).str.endswith("_not_run")
    n_pass = int(((live["status"] == "PASS") & ~not_run).sum())
    n_fail = int(((live["status"] == "FAIL") & ~not_run).sum())
    assert _has_count(text, "PASS ", n_pass), text
    assert _has_count(text, "FAIL ", n_fail), text
    assert _has_count(text, "미실행 ", int(not_run.sum())), text
    assert _has_count(text, "항등식 ", int(vc["is_identity"].astype(bool).sum())), text


def test_gate_strip_survives_print(pages):
    pg = pages["ko"]
    _go(pg, "exec-report")
    pg.emulate_media(media="print")
    try:
        visible = pg.eval_on_selector(
            "#gatestrip", "e=>getComputedStyle(e).display")
    finally:
        pg.emulate_media(media="screen")
    assert visible != "none", "the gate strip disappears on paper"


# ---------------------------------------------------------------- A13 kill guard

def _kill_state(pg) -> dict:
    return pg.evaluate("""() => ({
        bar: document.querySelector('.killbar').hidden,
        disabled: document.querySelector('.killgo').disabled,
        kill: document.querySelector('.kill').textContent,
        killed: !!NG.state.killed, scope: NG.state.killScope})""")


def test_kill_needs_a_reason_and_a_second_pair_of_eyes(page):
    page.click(".kill")
    page.wait_for_timeout(80)
    st = _kill_state(page)
    assert st["bar"] is False and st["disabled"] is True
    page.fill("#killreason", "   ")
    page.fill("#killconfirm", " ")
    page.wait_for_timeout(60)
    assert _kill_state(page)["disabled"] is True, "blank space passed as a reason"
    page.fill("#killreason", "reason only")
    page.wait_for_timeout(60)
    assert _kill_state(page)["disabled"] is True
    page.eval_on_selector(".killgo", "e=>e.click()")
    page.wait_for_timeout(80)
    assert "Kill Switch 해제" not in _kill_state(page)["kill"]
    page.press("#killreason", "Enter")
    page.wait_for_timeout(80)
    assert _kill_state(page)["killed"] is False, "Enter engaged with one field"
    page.fill("#killconfirm", "second reviewer")
    page.wait_for_timeout(60)
    assert _kill_state(page)["disabled"] is False
    page.click(".killgo")
    page.wait_for_timeout(150)
    st = _kill_state(page)
    assert st["killed"] is True and "Kill Switch 해제" in st["kill"]


def test_cancel_closes_the_bar_without_engaging(page):
    page.click(".kill")
    page.wait_for_timeout(60)
    page.click(".killno")
    page.wait_for_timeout(60)
    st = _kill_state(page)
    assert st["bar"] is True and st["killed"] is False


def test_release_needs_the_same_two_fields(page):
    page.click(".kill")
    page.fill("#killreason", "engage")
    page.fill("#killconfirm", "reviewer")
    page.click(".killgo")
    page.wait_for_timeout(150)
    assert _kill_state(page)["killed"] is True
    page.click(".kill")                       # opens the release form
    page.wait_for_timeout(60)
    assert _kill_state(page)["disabled"] is True
    page.fill("#killreason", "release")
    page.wait_for_timeout(60)
    assert _kill_state(page)["disabled"] is True, "release passed with one field"
    page.fill("#killconfirm", "reviewer")
    page.wait_for_timeout(60)
    page.click(".killgo")
    page.wait_for_timeout(150)
    st = _kill_state(page)
    assert st["killed"] is False and "Kill Switch 해제" not in st["kill"]


def test_a_global_kill_blocks_the_structured_query(ko_page):
    pg = ko_page
    _go(pg, "structured-query")
    before = _text(pg)
    assert "비상정지 (실행 차단)" not in before
    pg.click(".kill")
    pg.fill("#killreason", "screen guard drill")
    pg.fill("#killconfirm", "reviewer")
    pg.click(".killgo")
    pg.wait_for_timeout(250)
    after = _text(pg)
    assert "비상정지 (실행 차단)" in after
    assert "고정 컬럼 결과" not in after


def test_a_scoped_kill_blocks_only_its_own_domain(ko_page):
    pg = ko_page
    doms = pg.evaluate("""() => {const vm = NG.D.view_meta || {};
        return {crm: (vm['V_CRM_EWS_SIGNAL']||{}).domain,
                rdm: (vm['V_RDM_ASSET_QUALITY']||{}).domain}}""")
    assert doms["crm"] and doms["rdm"] and doms["crm"] != doms["rdm"]
    pg.click(".kill")
    pg.select_option("#killscope", doms["crm"])
    pg.fill("#killreason", "credit domain drill")
    pg.fill("#killconfirm", "reviewer")
    pg.click(".killgo")
    pg.wait_for_timeout(250)
    blocked = pg.evaluate("()=>NG.killedFor(NG.D.view_meta['V_CRM_EWS_SIGNAL'].domain)")
    spared = pg.evaluate("()=>NG.killedFor(NG.D.view_meta['V_RDM_ASSET_QUALITY'].domain)")
    assert blocked is True and spared is False
    _go(pg, "structured-query")
    pg.select_option("section.on select.sel", "V_CRM_EWS_SIGNAL")
    pg.wait_for_timeout(200)
    assert "비상정지 (실행 차단)" in _text(pg)
    pg.select_option("section.on select.sel", "V_RDM_ASSET_QUALITY")
    pg.wait_for_timeout(200)
    assert "비상정지 (실행 차단)" not in _text(pg)


def test_the_kill_screen_states_its_scope_and_its_requirement(ko_page):
    text = _screen(ko_page, "kill-guard")["text"]
    assert "화면" in text, text[:300]          # the guard is screen only
    assert "agent_killswitch" in text          # and writes to no ledger
    assert "AIG-009" in text


# ---------------------------------------------------------------- A14 language

def test_english_is_the_default_language(pages):
    pg = pages["en"]
    assert pg.evaluate("()=>__I18N__.lang()") == "en"
    cockpit = BY_ID["cockpit"]
    labels = pg.eval_on_selector_all("nav button", "els=>els.map(e=>e.textContent)")
    assert cockpit["title_en"] in labels
    assert cockpit["title_ko"] not in labels


def test_the_language_button_toggles_and_persists(page):
    page.click("#langbtn")
    page.wait_for_timeout(250)
    assert page.evaluate("()=>__I18N__.lang()") == "ko"
    assert page.evaluate("()=>localStorage.getItem('rynta-lang')") == "ko"
    page.reload()
    page.wait_for_function("window.__I18N__!==undefined")
    page.wait_for_timeout(250)
    assert page.evaluate("()=>__I18N__.lang()") == "ko", "the stored choice lost"
    labels = page.eval_on_selector_all("nav button", "els=>els.map(e=>e.textContent)")
    assert BY_ID["cockpit"]["title_ko"] in labels


def test_ledger_values_stay_in_their_own_language(pages, studio):
    """A14: an indicator name is a ledger value, not a translatable string."""
    master = studio.tables["rdm_macro_indicator_master"]
    names = [str(v) for v in master["name"] if re.search(r"[가-힣]", str(v))]
    assert names, "the fixture has no Korean indicator name"
    text = _screen(pages["en"], "macro")["text"]
    assert any(n in text for n in names), names[:5]


def test_numbers_do_not_move_between_languages(pages):
    """A14: table cells go through one number format, not a per language one.

    Money KPIs are deliberately scaled per language (조 and 억 against tn, bn
    and m), so the comparison is over the table bodies.
    """
    def cells(pg):
        _go(pg, "credit-rwa")
        return pg.eval_on_selector_all(
            "section.on table td", "els=>els.map(e=>e.textContent)")

    en, ko = cells(pages["en"]), cells(pages["ko"])
    digits = lambda rows: [re.findall(r"\d[\d,.]*", c) for c in rows]
    assert digits(en) == digits(ko)


def test_opening_everything_in_english_leaves_no_missing_key(pages):
    """A14 and Q5: every authored string is catalogued, so miss stays empty."""
    pg = pages["en"]
    pg.evaluate("()=>{__I18N__.miss.length=0}")
    for sid in IDS:
        _go(pg, sid)
        keys = pg.evaluate("()=>{const d=NG.registry.get(NG.route().id);"
                           "return (d&&d.tabs||[]).map(t=>t.key)}")
        for k in keys:
            pg.evaluate("k=>{NG.go(NG.route().id,{tab:k})}", k)
            pg.wait_for_timeout(60)
    pg.evaluate("()=>NG.drawer.gate()")
    pg.wait_for_timeout(120)
    tabs = pg.eval_on_selector_all("#drawer .tabs button", "els=>els.length")
    for i in range(tabs):
        pg.eval_on_selector_all("#drawer .tabs button", f"els=>els[{i}].click()")
        pg.wait_for_timeout(60)
    pg.evaluate("()=>NG.drawer.shortcuts()")
    pg.wait_for_timeout(80)
    pg.evaluate("()=>NG.palette.open()")
    pg.wait_for_timeout(120)
    pg.evaluate("()=>NG.palette.close()")
    pg.evaluate("()=>NG.drawer.close()")
    miss = pg.evaluate("()=>Array.from(new Set(__I18N__.miss))")
    assert miss == [], miss


# ---------------------------------------------------------------- A17 runs

def test_the_selectors_are_in_reading_order(multi_page):
    order = multi_page.evaluate(
        "()=>{const i=document.querySelector('#instsel'),a=document.querySelector('#asofsel');"
        "return i.compareDocumentPosition(a)&Node.DOCUMENT_POSITION_FOLLOWING?1:-1}")
    assert order == 1, "the institution selector must come first"


def test_switching_the_run_repaints_and_leaves_the_source_payload_alone(multi_page, studio):
    pg = multi_page
    _go(pg, "exec-report")
    pg.evaluate("()=>{const s=document.querySelector('section.on');"
                "const d=document.createElement('div');d.id='probe';"
                "d.textContent='probe';s.appendChild(d)}")
    before = pg.evaluate("()=>({run:document.querySelector('#chip-run').textContent,"
                         "digest:document.querySelector('#chip-digest').textContent,"
                         "asof:window.__RYNTA__.meta.asof})")
    options = pg.eval_on_selector_all("#asofsel option", "els=>els.map(e=>e.value)")
    assert options == sorted(options)
    other = next(o for o in options if o != studio.asof)
    pg.select_option("#asofsel", other)
    pg.wait_for_timeout(600)
    after = pg.evaluate("()=>({run:document.querySelector('#chip-run').textContent,"
                        "digest:document.querySelector('#chip-digest').textContent,"
                        "asof:window.__RYNTA__.meta.asof,"
                        "probe:!!document.querySelector('#probe'),"
                        "active:NG.D.meta.asof})")
    assert after["run"] != before["run"]
    assert after["digest"] != before["digest"]
    assert after["probe"] is False, "the body was not rebuilt"
    assert after["asof"] == before["asof"], "__RYNTA__ must not move"
    assert after["active"] == other


def test_per_run_state_does_not_leak_between_runs(multi_page, studio):
    pg = multi_page
    options = pg.eval_on_selector_all("#asofsel option", "els=>els.map(e=>e.value)")
    other = next(o for o in options if o != studio.asof)
    pg.evaluate("()=>{NG.state.approved['probe-layout']=true}")
    pg.select_option("#asofsel", other)
    pg.wait_for_timeout(500)
    assert pg.evaluate("()=>Object.keys(NG.state.approved)") == []
    pg.select_option("#asofsel", studio.asof)
    pg.wait_for_timeout(500)
    assert pg.evaluate("()=>Object.keys(NG.state.approved)") == ["probe-layout"]


def test_the_settings_screen_lists_the_loaded_runs(multi_page):
    _go(multi_page, "settings")
    text = multi_page.inner_text("section.on .set-runs")
    assert "RUN-" in text
    asof = _CATALOGUE.get("기준일", "기준일")
    assert "기준일" in text or asof.lower() in text.lower(), text[:200]


# ---------------------------------------------------------------- A18 governance truth

def test_the_cockpit_evidence_node_counts_the_approval_ledger(ko_page, studio):
    ga = studio.tables["gov_approval"]
    text = _screen(ko_page, "cockpit")["text"]
    for decision in ("대기", "승인", "반려"):
        n = int((ga["decision"] == decision).sum())
        assert _has_count(text, f"{decision} ", n), (decision, n, text[:400])


def test_the_cockpit_reconciliation_meter_uses_the_whole_ledger(ko_page, studio):
    total = len(studio.tables["rdm_reconciliation"])
    text = _screen(ko_page, "cockpit")["text"]
    assert any(f in text for f in _num_forms(total)), total


def test_the_close_screen_states_the_structural_blocker(ko_page, ext):
    ext_tasks = ext["x_close"]["tasks"]
    cl12 = next(t for t in ext_tasks if t["task_id"] == "CL-12")
    text = _screen(ko_page, "close-workflow")["text"]
    assert "CL-12" in text
    assert cl12["task_name"] in text


def test_the_queue_names_every_hold_and_its_owner(ko_page, ext):
    q = ext["x_queue"]
    text = _screen(ko_page, "decision-queue")["text"]
    for h in q["holds"]:
        assert h["reason_text"] in text, h["reason_text"]
        if h["unblock"] is None:
            assert "소관 미확인" in text or "owner unknown" in text


def test_the_limit_screen_shows_both_sources_and_says_they_disagree(ko_page, ext):
    x = ext["x_limits"]
    text = _screen(ko_page, "limits")["text"]
    assert x["two_sources"]["state"] in text
    assert x["two_sources"]["law"]["basis"] in text
    engine = x["two_sources"]["engine"]
    if engine["basis"]:
        assert engine["basis"] in text
    assert _has_count(text, "", x["populations"]["limits_full"]["total"])


def test_the_liquidity_screen_states_the_reconciliation_state(ko_page, ext):
    state = ext["x_lcr"]["state"]
    assert state in ("reconciled", "not reconciled", "not computable")
    assert state in _screen(ko_page, "liquidity")["text"]


def test_the_trend_screen_states_how_many_periods_it_has(ko_page, ext):
    t = ext["x_trend"]
    text = _screen(ko_page, "headline-trend")["text"]
    assert any(f in text for f in _num_forms(t["n_periods"]))
    assert "지문" in text or "digest" in text.lower()


def test_the_validation_screen_labels_a_stale_response(ko_page, ext):
    rc = ext["x_gate"]["recalc"]
    text = _screen(ko_page, "validation")["text"]
    for state, n in rc["counts"].items():
        if n and state != "stale":
            assert state in text, state
    if rc["counts"]["stale"]:
        assert "이전 요청 응답" in text


def test_the_overlay_screen_names_the_manual_adjustment_ledger(ko_page):
    """A18: the overlay screen names the ledger and the senior approval column.

    The physical column name may live in the th title when the catalogue label
    differs, which is where the table card puts it, so both are read.
    """
    info = _screen(ko_page, "overlay")
    hay = info["text"] + " " + info["th"]
    assert "수동조정" in hay
    assert "senior_approval" in hay, info["text"][:300]


# ---------------------------------------------------------------- A23 ownership

@pytest.mark.parametrize("sid", IDS)
def test_every_screen_marks_who_owns_it(pages, sid):
    pg = pages["ko"]
    _go(pg, sid)
    own = pg.evaluate("""() => {const o=document.querySelector('section.on .prov .own');
        return o ? {text:o.textContent, title:o.title} : null}""")
    assert own is not None, "the provenance header has no ownership line"
    if "소관 미확인" in own["text"]:
        return
    assert "(UI 가정)" in own["text"], own
    assert "DOMAIN_ROLE_MAP" in own["title"], own


# ---------------------------------------------------------------- shell surfaces

def test_a_kpi_opens_the_lineage_drawer_with_five_tabs(pages):
    pg = pages["en"]
    _go(pg, "exec-report")
    fid = pg.evaluate("()=>NG.D.x_lineage.kpi_map[0]")
    pg.evaluate("f=>NG.drawer.lineage(f)", fid)
    pg.wait_for_timeout(150)
    tabs = pg.eval_on_selector_all("#drawer .tabs button", "els=>els.map(e=>e.textContent)")
    assert len(tabs) == 5, tabs
    assert pg.eval_on_selector("#drawer", "e=>e.hidden") is False
    pg.evaluate("()=>NG.drawer.close()")


def test_the_palette_opens_and_routes(page):
    page.keyboard.press("Control+k")
    page.wait_for_timeout(150)
    assert page.eval_on_selector("#palette", "e=>e.hidden") is False
    target = BY_ID["cockpit"]
    page.fill("#palette input", target["title_en"])
    page.wait_for_timeout(150)
    page.eval_on_selector_all("#palette li.pitem", "els=>els[0].click()")
    page.wait_for_timeout(200)
    assert page.evaluate("()=>NG.route().id") == "cockpit"
    assert page.eval_on_selector("#palette", "e=>e.hidden") is True


def test_hash_routing_goes_back_and_forward(page):
    _go(page, "cockpit")
    _go(page, "validation")
    assert "validation" in page.evaluate("()=>location.hash")
    page.go_back()
    page.wait_for_timeout(250)
    assert page.evaluate("()=>NG.route().id") == "cockpit"
    page.go_forward()
    page.wait_for_timeout(250)
    assert page.evaluate("()=>NG.route().id") == "validation"


def test_a_legacy_label_in_the_hash_still_resolves(page):
    label = payload_ext.legacy_labels()[0]
    target = next(e["id"] for e in REGISTRY if label in e["legacy"])
    page.evaluate("l=>{location.hash='#/control/'+encodeURIComponent(l)}", label)
    page.wait_for_timeout(300)
    assert page.evaluate("()=>NG.route().id") == target


@pytest.mark.parametrize("sid", IDS)
def test_every_chart_is_described(pages, sid):
    pg = pages["en"]
    _go(pg, sid)
    bad = pg.evaluate("""() => Array.from(
        document.querySelectorAll('section.on svg[role=img]'))
        .map((s,i) => ({i, title: !!s.querySelector('title'),
                        desc: !!s.querySelector('desc'),
                        label: !!s.getAttribute('aria-label')}))
        .filter(x => !x.title || !x.desc || !x.label)""")
    assert bad == [], bad


def test_the_committee_row_of_the_report_is_four_up(pages):
    entry = BY_ID["exec-report"]
    _go(pages["en"], "exec-report")
    cls = pages["en"].eval_on_selector_all(
        "section.on .kpis", "els=>els.length?els[0].className:null")
    assert cls is not None, "the report has no KPI row"
    assert ("c4" in cls) == (entry["density"] == "committee"), (cls, entry["density"])
    n = pages["en"].eval_on_selector_all(
        "section.on .kpis", "els=>els.length?els[0].querySelectorAll('.kpi').length:0")
    assert n >= 4, n
