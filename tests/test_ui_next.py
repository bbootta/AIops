"""Next-generation UI shell: everything testable without a browser.

Design spec section 8: A1..A5, A10..A12, A15, A16, A19..A25. Browser-bound
criteria (A6..A9, A13, A14, A17, A18) live in tests/test_ui_next_browser.py.

Every expected value is derived from the fixture frames, the catalogue, the
registry or the i18n catalogue. No fixture literal (a row count, a table count,
a screen count) is written down here: a stale pin is worse than no pin, because
it reads like a control while it only records what the data happened to be.
"""

from __future__ import annotations

import ast
import dataclasses
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from risk_lib import institutions as _inst
from risk_lib.datamodel import catalog as cat
from risk_lib.ui_studio import app as uiapp
from risk_lib.ui_studio import governance as gov
from risk_lib.ui_studio.next import i18n_next, payload_ext
from risk_lib.ui_studio.next import render as R
from risk_lib.validation import independent

STATIC = Path(R.__file__).parent / "static"
SCREEN_DIR = STATIC / "screens"

# A16 byte budgets, copied from module_plan.json shared_contracts.budgets
# (design lead hand-off). Unit: bytes of each static file as emitted, that is
# after render.strip_static, as reported by render.size_report(). The hard and
# warning totals live in render.py (STATIC_HARD, STATIC_WARN) and are read from
# there so there is one copy of them.
BUDGETS = {
    "shell": 120_000,            # tokens.css + base.css + core.js + shared.js
    "charts.js": 60_000,
    "screens/reports.js": 42_000,
    # 48,000 -> 50,000 (설계 리드 서면 변경, 2026-09-02). 이 모듈이 가진 화면
    # 일곱 장 가운데 콕핏과 한도관리가 가장 복잡하고, 검수에서 나온 결함
    # 세 가지(헤드라인 라벨 영문화, 마감 보드 반응형, 문구 구분자)를 고치며
    # 87바이트를 넘었다. 총계는 438KB 로 경고선 540KB 와 상한 600KB 에서
    # 각각 19% · 27% 남아 있어 상한은 건드리지 않는다.
    "screens/control.js": 50_000,
    "screens/query.js": 26_000,
    "screens/models.js": 52_000,
    "screens/riskdata.js": 28_000,
    "screens/capital.js": 30_000,
    "screens/alm.js": 38_000,
    "screens/stress.js": 28_000,
    "screens/governance.js": 33_000,
    "screens/settings.js": 16_000,
    "screens/reference.js": 4_000,
    "engine.js": 12_000,
}
BUDGET_SUM = 525_000             # shared_contracts.budgets.sum
SHELL_FILES = ("tokens.css", "base.css", "core.js", "shared.js")

# NG.shared helpers (A21). shared.js owns these five names; no screens file may
# define one of them, because two definitions of the same helper drift apart.
SHARED_HELPERS = ("renderForm", "domainBrowser", "almEvidence", "almSources",
                  "judgeGlyph")

# The two banned characters, written as escapes so this file carries neither.
EM_DASH, EN_DASH = "\u2014", "\u2013"


# ---------------------------------------------------------------- fixtures

@pytest.fixture(scope="module")
def studio(result, portfolio):
    from risk_lib.ui_studio.studio import build_studio
    return build_studio(result, portfolio)


@pytest.fixture(scope="module")
def rendered(studio):
    """One render for the whole module, with the size report of that render.

    render.size_report() is global state of the last render, so it is captured
    here and never read from a test that rendered something else in between.
    """
    html = R.render_next(studio)
    return html, R.size_report()


@pytest.fixture(scope="module")
def html(rendered):
    return rendered[0]


@pytest.fixture(scope="module")
def sizes(rendered):
    return rendered[1]


@pytest.fixture(scope="module")
def app_path(studio, tmp_path_factory):
    out = tmp_path_factory.mktemp("uinext") / "studio_next.html"
    return R.write_app_next(studio, out)


@pytest.fixture(scope="module")
def ext(studio):
    return payload_ext.build_ext(studio)


# ---------------------------------------------------------------- helpers

def _runs(h: str) -> dict:
    m = re.search(r"window\.__RYNTA_RUNS__=(\{.*\});\nwindow\.__RYNTA__", h, re.S)
    assert m, "run payload not found"
    return json.loads(m.group(1))


def _primary_asof(h: str) -> str:
    m = re.search(r'window\.__RYNTA__=window\.__RYNTA_RUNS__\[("[^"]+")\];', h)
    assert m, "primary run reference not found"
    return json.loads(m.group(1))


def _payload(h: str) -> dict:
    return _runs(h)[_primary_asof(h)]


def _nav_literal(h: str, name: str):
    m = re.search(r"const %s=(\[.*?\]);\n" % name, h, re.S)
    assert m, f"const {name}= literal not found"
    return ast.literal_eval(m.group(1))


def _static_js() -> list[Path]:
    return sorted(STATIC.rglob("*.js"))


def _static_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------- A1 payload script

def test_document_starts_with_the_doctype(html):
    assert html.startswith("<!doctype html>")


def test_payload_script_layout_is_the_agreed_one(html, studio):
    """A1: one JSON object per global, in the agreed order, one script block."""
    m = re.search(
        r"<script>window\.__RYNTA_RUNS__=(\{.*\});\n"
        r"window\.__RYNTA__=window\.__RYNTA_RUNS__\[\"([^\"]+)\"\];\n"
        r"window\.__RYNTA_INSTS__=(\{.*\});\n"
        r"window\.__RYNTA_I18N__=(\{.*\});\n"
        r"window\.__RYNTA_NAV__=(\{.*\})</script>", html, re.S)
    assert m, "the payload script does not follow the A1 layout"
    runs = json.loads(m.group(1))
    assert m.group(2) == studio.asof and m.group(2) in runs
    assert json.loads(m.group(4))["map"], "i18n map is empty"
    assert json.loads(m.group(5))["screens"], "nav payload carries no screens"


def test_primary_institution_reuses_the_runs_object(html):
    """A1: the primary institution is a reference, never a second copy."""
    code = _inst.PRIMARY_INSTITUTION
    assert f'{json.dumps(code)}:window.__RYNTA_RUNS__' in html
    payload = _payload(html)
    assert payload["meta"]["institution_code"] == code


# ---------------------------------------------------------------- A2 self contained

def test_page_pulls_nothing_from_the_network(html):
    """A2: no external script, style, fetch or socket. The page is one file."""
    assert "<script src=" not in html
    assert "@import url(" not in html
    assert not re.search(r"\bfetch\s*\(", html)
    assert "XMLHttpRequest" not in html
    assert "new WebSocket" not in html
    assert "cdn." not in html
    for url in set(re.findall(r"https?://[^\s\"'`)]+", html)):
        assert url.startswith("http://www.w3.org/"), url


def test_engine_is_inlined_and_never_linked(html):
    """A2: engine.js is inlined. The name may appear in catalogued prose only.

    The shell has no <script src=> at all, so the check is that no src or href
    attribute anywhere names a .js file.
    """
    linked = re.findall(r'(?:src|href)\s*=\s*"[^"]*\.js[^"]*"', html)
    assert linked == [], linked


def test_query_engine_literals_survive_the_inline(html):
    """A2: the query engine the structured screen calls is really on the page."""
    assert "RY.compileQuery" in html
    assert "function sha256Hex" in html


# ---------------------------------------------------------------- A3 bytes

def test_rendered_bytes_carry_no_long_dash(html):
    assert EM_DASH not in html and EN_DASH not in html


def test_two_renders_are_byte_identical(studio, html):
    assert R.render_next(studio) == html


def test_payload_json_is_sorted(html):
    """A3: sort_keys, so a re-render never reshuffles the file."""
    raw = re.search(r"window\.__RYNTA_RUNS__=(\{.*\});\nwindow\.__RYNTA__",
                    html, re.S).group(1)
    keys = re.findall(r'"([a-z_0-9]+)":', raw[:4000])
    top = json.loads(raw)[_primary_asof(html)]
    order = [k for k in keys if k in top]
    assert order == sorted(dict.fromkeys(order)), order[:20]


def test_em_dash_sentinel_of_the_ledger_survives_the_escape(html, studio):
    """A3: the renderer escapes U+2014 as \\u2014; the ledger value is intact.

    crm_code_scope uses U+2014 as the "not mapped" sentinel. Escaping it keeps
    the rendered bytes free of long dashes without rewriting the ledger.
    """
    src = studio.tables["crm_code_scope"]
    assert (src["ccf_type"].astype(str) == EM_DASH).any(), (
        "the fixture no longer carries the sentinel; this test is now dead")
    frame = _payload(html)["data"]["crm_code_scope"]
    assert any(str(v) == EM_DASH for row in frame["rows"] for v in row), \
        frame["columns"]


# ---------------------------------------------------------------- A4 payload invariants

def test_payload_carries_every_catalogue_table(html, studio):
    d = _payload(html)
    assert d["meta"]["n_tables"] == len(cat.ALL_TABLES)
    assert len(d["catalog"]) == len(cat.ALL_TABLES)
    assert all(r["materialised"] for r in d["catalog"])
    assert len(d["forms"]) == len(studio.built_forms)


def test_capital_kpi_matches_the_engine_and_the_binding_tier(html, studio):
    d = _payload(html)
    cap = d["kpis"][0]
    assert "CET1" in cap["label"]
    assert cap["value"] == f"{studio.result.bis.cet1_ratio:.2%}"
    short = {k: v for k, v in studio.result.bis.surplus_shortfall.items() if v < 0}
    if short:
        worst = min(studio.result.bis.surplus_shortfall,
                    key=studio.result.bis.surplus_shortfall.get)
        assert cap["tone"] == "bad"
        assert f"{studio.result.bis.surplus_shortfall[worst]*100:+.2f}%p" in cap["sub"]
    else:
        assert cap["tone"] == "good"


def test_every_frame_column_carries_a_catalogue_label(html):
    d = _payload(html)
    missing: list[str] = []
    checked = [0]

    def walk(o, path):
        if isinstance(o, dict):
            if isinstance(o.get("columns"), list) and isinstance(o.get("rows"), list):
                checked[0] += 1
                labs = o.get("labels") or [None] * len(o["columns"])
                missing.extend(f"{o.get('table') or path}/{c}"
                               for c, l in zip(o["columns"], labs) if l is None)
            else:
                for k, v in o.items():
                    walk(v, f"{path}.{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{path}[{i}]")

    walk(d, "$")
    assert not missing, missing[:20]
    assert checked[0] >= 80, f"only {checked[0]} frames inspected; detection broke"


def test_labels_resolve_per_table_not_globally(html):
    d = _payload(html)
    by_col: dict[str, set] = {}
    for f in d["previews"].values():
        for c, l in zip(f["columns"], f["labels"]):
            by_col.setdefault(c, set()).add(l)
    diverging = {c: ls for c, ls in by_col.items() if len(ls) > 1}
    assert len(diverging) >= 5, sorted(diverging)[:5]


def test_multi_run_render_carries_every_run(studio):
    older = dataclasses.replace(studio, asof="2026-03-31",
                                run_id="RUN-20260331", digest="f" * 64)
    h = R.render_next([studio, older])
    runs = _runs(h)
    assert set(runs) == {studio.asof, older.asof}
    assert _primary_asof(h) == max(studio.asof, older.asof)
    assert 'id="asofsel"' in h
    for a, d in runs.items():
        assert d["meta"]["asof"] == a


# ---------------------------------------------------------------- A5 literals

def test_navgroups_literal_follows_the_registry_order(html):
    groups = R.load_registry_files()[0]["groups"]
    order = [g["label_ko"] for g in sorted(groups, key=lambda g: g["order"])]
    tree = _nav_literal(html, "NAVGROUPS")
    assert [g[0] for g in tree] == order
    raw = re.search(r"const NAVGROUPS=(\[.*?\]);\n", html, re.S).group(1)
    first, second = order[0], order[1]
    lead = payload_ext.SCREEN_REGISTRY[0]
    lead_label = (lead["legacy"] or [lead["title_ko"]])[0]
    assert raw.index(repr(first)) < raw.index(repr(lead_label)) < raw.index(repr(second))


def test_tabs_literal_is_label_english_id_triples(html):
    tabs = _nav_literal(html, "TABS")
    reg = payload_ext.SCREEN_REGISTRY
    ids = [e["id"] for e in reg]
    assert [t[2] for t in tabs] == ids
    assert [t[1] for t in tabs] == [e["title_en"] for e in reg]
    assert [t[0] for t in tabs] == [(e["legacy"] or [e["title_ko"]])[0] for e in reg]
    raw = re.search(r"const TABS=(\[.*?\]);\n", html, re.S).group(1)
    triples = re.findall(r"\['([^']*)','([^']*)','([^']*)'\]", raw)
    assert len(triples) == len(reg), "a TABS element is not a three string literal"
    assert [t[2] for t in triples] == ids, "a TABS id is a bare identifier"
    lead = reg[0]
    assert (f"[{(lead['legacy'] or [lead['title_ko']])[0]!r},"
            f"{lead['title_en']!r},{lead['id']!r}]") in raw


def test_screen_and_chart_functions_are_on_the_page(html):
    for token in ("function executiveReport(root)", "function autoChart(",
                  "const PREF=[", "원장 전량", "function treemap("):
        assert token in html, token
    assert "function donut(" not in html


def test_node_check_passes_on_every_static_file():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed")
    for f in _static_js():
        r = subprocess.run([node, "--check", str(f)], capture_output=True, text=True)
        assert r.returncode == 0, f"{f.name}: {r.stderr[:400]}"


# ---------------------------------------------------------------- A10 gate arithmetic

def test_self_tally_partitions_val_check_exactly_once(ext, studio):
    s = ext["x_gate"]["self"]
    vc = studio.tables["val_check"]
    assert s["total"] == len(vc)
    assert (s["pass"] + s["warn"] + s["fail"] + s["not_run"]
            + s["identity_excluded"]) == len(vc)
    assert s["identity_excluded"] == int(vc["is_identity"].astype(bool).sum())
    live = vc[~vc["is_identity"].astype(bool)]
    assert s["not_run"] == int(live["check_name"].astype(str)
                               .str.endswith("_not_run").sum())
    assert s["blocks"] == int(live["blocks_approval"].astype(bool).sum())


def test_an_unknown_status_stops_the_build_and_names_the_row(studio):
    """A10: the tally may never fall through silently on a new status value."""
    vc = studio.tables["val_check"].copy()
    live = vc[~vc["is_identity"].astype(bool)
              & ~vc["check_name"].astype(str).str.endswith("_not_run")]
    assert len(live), "no live check row to mutate"
    i = live.index[0]
    vc.loc[i, "status"] = "OK"
    broken = dataclasses.replace(studio, tables={**studio.tables, "val_check": vc})
    with pytest.raises(ValueError) as exc:
        payload_ext.build_ext(broken)
    assert str(vc.loc[i, "check_name"]) in str(exc.value)
    assert "OK" in str(exc.value)


def test_approvals_total_is_the_whole_ledger_not_the_frame(ext, studio):
    ga = studio.tables["gov_approval"]
    a = ext["x_gate"]["approvals"]
    assert a["total"] == len(ga)
    for decision in ("대기", "승인", "반려"):
        assert a[decision] == int((ga["decision"] == decision).sum())
    assert sum(a[k] for k in ("대기", "승인", "반려")) == len(ga)


def test_every_pending_approval_is_covered_by_a_hold_reason(ext, studio):
    """A10: a pending form approval always says why it is held.

    Manual adjustment rows are the other subject type; they are pending because
    their own ledger row is still in review, and their evidence_ref is that
    ledger reference, so they are covered by the adjustment ledger instead.
    """
    ga = studio.tables["gov_approval"]
    pending = ga[ga["decision"] == "대기"]
    forms = pending[pending["subject_type"] == "업무보고서 서식"]
    uncovered = forms[~forms["evidence_ref"].astype(str).str.contains("보류: ")]
    assert len(uncovered) == 0, uncovered["approval_id"].tolist()[:5]
    adj = studio.tables["aig_adjustment"]
    rest = pending[pending["subject_type"] != "업무보고서 서식"]
    assert set(rest["subject_type"]) <= {"수동조정"}, sorted(set(rest["subject_type"]))
    assert set(rest["subject_id"]) <= set(adj["adjustment_id"].astype(str))
    holds = ext["x_gate"]["approvals"]["holds"]
    assert holds, "pending rows exist but no hold was parsed"
    assert max(h["n"] for h in holds) <= len(forms)


def test_hold_reason_format_is_pinned(studio):
    """A10: the join and the evidence_ref prefix are a format contract."""
    reasons = gov.approval_hold_reasons(studio.tables, studio.iv_gate)
    ga = studio.tables["gov_approval"]
    forms = ga[ga["subject_type"] == "업무보고서 서식"]
    assert len(forms), "no form approval rows"
    assert forms["evidence_ref"].astype(str).str.startswith("digest=").all()
    if reasons:
        joined = " / ".join(reasons)
        assert forms["evidence_ref"].astype(str).str.endswith(joined).all()


def test_limits_two_sources_match_the_check_detail(ext, studio):
    """The screen numbers and the 2nd line check text cannot disagree."""
    two = ext["x_limits"]["two_sources"]
    chk = two["check"]
    assert chk is not None and chk["check_name"] == "large_exposure_two_sources"
    detail = chk["detail"]
    assert two["law"] is not None
    assert f"위반 {two['law']['n_breach']}건" in detail
    n_engine = two["engine"]["n_breach"]
    if n_engine is None:
        assert "미산출" in detail
    else:
        assert f"위반 {n_engine}건" in detail


# ---------------------------------------------------------------- A11 lineage

def test_figure_map_covers_kpis_scope_and_facts(ext, html):
    figures = ext["x_lineage"]["figures"]
    assert set(ext["x_lineage"]["kpi_map"]) <= set(figures)
    assert len(ext["x_lineage"]["kpi_map"]) == len(_payload(html)["kpis"])
    targets = {f["recalc_target"] for f in figures.values()}
    assert {k for k, _, _ in independent.RECALC_SCOPE} <= targets
    facts = ext["x_lineage"]["facts_map"]
    assert set(facts) == set(payload_ext.FACTS_MAP)
    assert set(facts.values()) <= set(figures)


def test_every_lineage_entry_names_real_checks_and_a_real_table(ext, studio):
    names = {sp.name for sp in cat.ALL_TABLES}
    known = set(studio.tables["val_check"]["check_name"].astype(str))
    ids = {e["id"] for e in payload_ext.SCREEN_REGISTRY}
    bad_tables, bad_checks, bad_screens = [], [], []
    for fid, f in ext["x_lineage"]["figures"].items():
        if f["table"] not in names:
            bad_tables.append((fid, f["table"]))
        bad_checks += [(fid, c) for c in f["check_names"] if c not in known]
        if f["screen"] not in ids:
            bad_screens.append((fid, f["screen"]))
    assert bad_tables == [] and bad_checks == [] and bad_screens == []


def test_the_report_screen_reads_only_catalogued_fact_keys():
    """A11: exec-report may read no executive.facts key outside facts_map."""
    src = _static_text(SCREEN_DIR / "reports.js")
    used = set(re.findall(r"facts\.([A-Za-z_][A-Za-z_0-9]*)", src))
    used |= set(re.findall(r"facts\[\s*'([^']+)'\s*\]", src))
    assert used <= set(payload_ext.FACTS_MAP), sorted(used - set(payload_ext.FACTS_MAP))


# ---------------------------------------------------------------- A12 static JS grep

_RE_START = set("(,=:[!&|?{};+-*%~^<>")


def _scan(src: str):
    """Return (template spans, code mask).

    mask[i] is True when character i is ordinary code, that is not inside a
    string, template literal, comment or regular expression literal.
    """
    spans: list[tuple[int, int]] = []
    mask = [False] * len(src)
    i, n, prev = 0, len(src), ""
    while i < n:
        c = src[i]
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        if c in "'\"":
            j = i + 1
            while j < n and src[j] != c:
                j += 2 if src[j] == "\\" else 1
            i, prev = j + 1, c
            continue
        if c == "`":
            j, depth = i + 1, 0
            while j < n:
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == "$" and j + 1 < n and src[j + 1] == "{":
                    depth += 1
                    j += 2
                    continue
                if src[j] == "}" and depth:
                    depth -= 1
                    j += 1
                    continue
                if src[j] == "`" and not depth:
                    break
                j += 1
            spans.append((i, min(j + 1, n)))
            i, prev = j + 1, "`"
            continue
        if c == "/" and (prev == "" or prev in _RE_START):
            j, cls = i + 1, False
            while j < n:
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == "[":
                    cls = True
                elif src[j] == "]":
                    cls = False
                elif src[j] == "\n":
                    j = i
                    break
                elif src[j] == "/" and not cls:
                    break
                j += 1
            if j > i:
                i, prev = j + 1, "/"
                continue
        mask[i] = True
        if not c.isspace():
            prev = c
        i += 1
    return spans, mask


_CALL = re.compile(r"(?<![\w$.])(?:T|TF)\s*\(|(?<![\w$])fmt\.(?:int|num)\s*\(")
_ASSIGN = re.compile(r"\.(?:textContent|innerText|title)\s*=(?!=)")


def _call_args(src, mask):
    for m in _CALL.finditer(src):
        if not mask[m.start()]:
            continue
        i, depth = m.end(), 1
        while i < len(src) and depth:
            if mask[i]:
                if src[i] == "(":
                    depth += 1
                elif src[i] == ")":
                    depth -= 1
            i += 1
        yield m.start(), src[m.end():i - 1]


def _assign_rhs(src, mask):
    for m in _ASSIGN.finditer(src):
        if not mask[m.start()]:
            continue
        i, depth = m.end(), 0
        while i < len(src):
            c = src[i]
            if mask[i]:
                if c in "([{":
                    depth += 1
                elif c in ")]}":
                    if depth == 0:
                        break
                    depth -= 1
                elif depth == 0 and c in ";,\n":
                    break
            i += 1
        yield m.start(), src[m.end():i]


def _length_offences(src: str) -> list[str]:
    spans, mask = _scan(src)
    out = []
    for a, b in spans:
        if ".length" in src[a:b]:
            out.append(f"line {src[:a].count(chr(10)) + 1} template {src[a:b][:60]}")
    for pos, arg in _call_args(src, mask):
        if ".length" in arg:
            out.append(f"line {src[:pos].count(chr(10)) + 1} call {arg[:60]}")
    for pos, rhs in _assign_rhs(src, mask):
        if ".length" in rhs:
            out.append(f"line {src[:pos].count(chr(10)) + 1} assign {rhs[:60]}")
    return out


_SAMPLE_BAD = """
const a = `rows ${x.length}`;
el.textContent = rows.length + ' rows';
n.title = items.length;
ap(root, T('모집단 ' + rows.length));
ap(root, TF('{n}건', {n: rows.length}));
ap(root, NG.fmt.int(rows.length));
"""
_SAMPLE_OK = """
for (let i = 0; i < rows.length; i++) { total += rows[i]; }
const head = rows.slice(0, rows.length - 1);
if (rows.length > 0 && cols.length !== rows.length) return null;
const n = frame.total;  // rows.length is not a total
el.textContent = String(frame.total);
"""


def test_the_length_tokeniser_is_not_a_dead_control():
    """The five flagged contexts are found, the safe ones are left alone."""
    bad = _length_offences(_SAMPLE_BAD)
    assert len(bad) == 6, bad
    assert _length_offences(_SAMPLE_OK) == []


@pytest.mark.parametrize("path", _static_js(), ids=lambda p: p.name)
def test_row_count_never_reaches_the_screen(path):
    """A12: a frame may be truncated, so rows.length is never a displayed total."""
    assert _length_offences(_static_text(path)) == []


@pytest.mark.parametrize("path", _static_js(), ids=lambda p: p.name)
def test_static_js_has_no_nondeterministic_or_modal_call(path):
    src = _static_text(path)
    for pat in (r"Date\.now", r"Math\.random", r"\bprompt\s*\(", r"\balert\s*\(",
                r"\bconfirm\s*\(", r"location\.reload", r"\.spark", r"\.trend\b",
                r"toLocaleString\(\s*[){]"):
        assert not re.search(pat, src), f"{path.name}: {pat}"


def test_no_template_literal_opens_a_comment_looking_line():
    """A16 fallback: strip_static removes comment only lines, so a template
    literal may not carry an inner line that starts with //."""
    for f in _static_js():
        src = _static_text(f)
        for a, b in _scan(src)[0]:
            for line in src[a:b].split("\n")[1:]:
                assert not line.lstrip().startswith("//"), f"{f.name}: {line[:60]}"


# ---------------------------------------------------------------- A15 tokens

_TOKEN_RE = re.compile(r"(--[a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{6})")
TEXT_TOKENS = ("--ink", "--muted", "--accent", "--good", "--warn", "--bad",
               "--blocked", "--not-run", "--synthetic", "--neutral")


def _palettes() -> dict[str, dict[str, str]]:
    css = (STATIC / "tokens.css").read_text(encoding="utf-8")

    def block(head: str) -> dict[str, str]:
        i = css.index(head)
        return dict(_TOKEN_RE.findall(css[i:css.index("}", i)]))

    return {"light": block(":root{"), "dark": block(':root[data-theme="dark"]{')}


def _ratio(a: str, b: str) -> float:
    def lum(h: str) -> float:
        ch = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        f = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in ch]
        return 0.2126 * f[0] + 0.7152 * f[1] + 0.0722 * f[2]

    la, lb = lum(a), lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


@pytest.mark.parametrize("palette", ("light", "dark"))
def test_every_text_token_is_readable_on_both_grounds(palette):
    p = _palettes()[palette]
    missing = [t for t in TEXT_TOKENS + ("--bg", "--panel", "--on-bad", "--on-accent")
               if t not in p]
    assert missing == [], missing
    for token in TEXT_TOKENS:
        for ground in ("--bg", "--panel"):
            r = _ratio(p[token], p[ground])
            assert r >= 4.5, f"{palette} {token} on {ground} is {r:.2f}:1"
    assert _ratio(p["--on-bad"], p["--bad"]) >= 4.5
    assert _ratio(p["--on-accent"], p["--accent"]) >= 4.5


def test_theme_bootstrap_is_inline_and_runs_before_the_topbar(html):
    body = html[html.index("<body>"):]
    assert "rynta-theme" in body
    assert body.index("rynta-theme") < body.index('<div class="topbar">')
    assert "src=" not in body[:body.index('<div class="topbar">')]


# ---------------------------------------------------------------- A16 size

def test_every_static_file_stays_inside_its_budget(sizes):
    shell = sum(sizes[n] for n in SHELL_FILES)
    over = []
    if shell > BUDGETS["shell"]:
        over.append(f"shell {shell} > {BUDGETS['shell']}")
    for name, budget in BUDGETS.items():
        if name == "shell":
            continue
        assert name in sizes, f"{name} was not emitted"
        if sizes[name] > budget:
            over.append(f"{name} {sizes[name]} > {budget}")
    assert over == [], over
    assert set(sizes) == set(SHELL_FILES) | (set(BUDGETS) - {"shell"}), sorted(sizes)


def test_static_total_stays_under_the_warning_line(sizes):
    total = sum(sizes.values())
    assert total <= BUDGET_SUM, f"{total} over the planned sum {BUDGET_SUM}"
    assert total < R.STATIC_WARN, f"{total} over the warning line {R.STATIC_WARN}"
    assert total < R.STATIC_HARD


def test_written_file_is_complete_and_inside_the_deploy_limit(app_path, html):
    raw = app_path.read_bytes()
    assert len(raw) == len(html.encode("utf-8")), "the file is not the whole render"
    assert len(raw) <= uiapp.DEPLOY_SIZE_LIMIT
    assert raw.decode("utf-8").endswith("</body></html>")


def test_the_writer_warns_instead_of_truncating(studio, tmp_path):
    """A16: over the deploy limit the writer warns and still writes it whole.

    Two runs on one page cross the limit, which is exactly the case where a
    silent truncation would leave no trace on the screen.
    """
    older = dataclasses.replace(studio, asof="2026-03-31",
                                run_id="RUN-20260331", digest="f" * 64)
    out = tmp_path / "two_runs.html"
    with pytest.warns(UserWarning) as rec:
        R.write_app_next([studio, older], out)
    msg = " ".join(str(w.message) for w in rec)
    assert "배포 상한" in msg and "행 예산" in msg, msg
    raw = out.read_bytes()
    assert len(raw) > uiapp.DEPLOY_SIZE_LIMIT, "this run no longer crosses the limit"
    assert raw.decode("utf-8").endswith("</body></html>"), "the file was cut"


def test_strip_static_is_idempotent_and_keeps_code_lines():
    sample = "a = 1; // trailing\n// comment only\n\n/* block */\nb = 2;\n"
    once = R.strip_static(sample)
    assert once == R.strip_static(once)
    assert "a = 1; // trailing" in once
    assert "// comment only" not in once
    assert "/* block */" not in once
    for f in list(_static_js()) + [STATIC / "base.css", STATIC / "tokens.css"]:
        t = _static_text(f)
        assert R.strip_static(R.strip_static(t)) == R.strip_static(t), f.name


# ---------------------------------------------------------------- A19 footer

def test_footer_carries_the_no_autonomous_write_statement(html):
    foot = html[html.index("<footer>"):html.index("</footer>")]
    assert "자동확정하지 않는다" in foot
    assert "합성 포트폴리오" in foot
    items = R._AIMS.split("에이전트는 ", 1)[1]
    items = items.split("를 자동확정하지")[0].split(", ")
    assert len(items) == 8, items
    pos = -1
    for it in items:
        nxt = foot.find(it, pos + 1)
        assert nxt > pos, f"{it} missing or out of order"
        pos = nxt


def test_footer_write_allowed_line_is_computed(html, studio):
    reg = studio.tables["agent_registry"]
    expected = f'{int(reg["write_allowed"].astype(bool).sum())}/{len(reg)}'
    foot = html[html.index("<footer>"):html.index("</footer>")]
    assert expected in foot


# ---------------------------------------------------------------- A20 suite hygiene

def test_the_new_suites_render_through_write_app_next():
    here = Path(__file__)
    browser = here.with_name("test_ui_next_browser.py")
    assert browser.exists()
    old = "write_app" + "("          # never spelled out: this file greps itself
    for f in (here, browser):
        src = f.read_text(encoding="utf-8")
        assert "write_app_next" in src, f.name
        assert old not in src, (
            f"{f.name} renders the old app; the new suites use write_app_next")


# ---------------------------------------------------------------- A21 shared helpers

@pytest.mark.parametrize("name", SHARED_HELPERS)
def test_shared_helpers_live_only_in_shared_js(name):
    for f in sorted(SCREEN_DIR.glob("*.js")):
        src = _static_text(f)
        assert not re.search(r"function\s+%s\s*\(" % name, src), f.name
        assert not re.search(r"NG\.shared\.%s\s*=" % name, src), f.name
        assert not re.search(r"(?:const|let|var)\s+%s\s*=\s*function" % name, src), f.name
    assert re.search(r"\b%s\b" % name, _static_text(STATIC / "shared.js")), name


def _block_at(html: str, path: Path) -> int:
    """Where render.py inlined this static file (whole body, exact match)."""
    body = R._esc(R.strip_static(_static_text(path)))
    i = html.find(body)
    assert i > 0, f"{path.name} was not inlined verbatim"
    return i


def test_shared_js_is_emitted_after_charts_and_before_the_screens(html):
    order = [_block_at(html, STATIC / n) for n in ("core.js", "charts.js", "shared.js")]
    assert order == sorted(order), "core, charts, shared must load in that order"
    first_screen = min(_block_at(html, p) for p in sorted(SCREEN_DIR.glob("*.js")))
    assert order[-1] < first_screen


# ---------------------------------------------------------------- A22 registry

def test_registry_validates_on_the_committed_files():
    reg = payload_ext.load_registry()
    ids = [e["id"] for e in reg]
    assert len(set(ids)) == len(ids)
    assert len(payload_ext.legacy_labels(reg)) == payload_ext.LEGACY_LABEL_COUNT
    labels = payload_ext.legacy_labels(reg)
    assert len(set(labels)) == len(labels)
    for e in reg:
        for key in ("products", "domains", "min_svg", "checks", "recalc"):
            assert key in e, (e["id"], key)
        assert isinstance(e["min_svg"], int) and e["min_svg"] >= 0
        assert e["module"].endswith(f"screens/{e['slug']}.js"), e["id"]
        assert (Path(R.__file__).parent.parent.parent.parent / e["module"]).exists()


def test_the_registry_union_covers_the_whole_catalogue():
    """A8 dead control, checked without a browser as well."""
    names = {sp.name for sp in cat.ALL_TABLES}
    union: set[str] = set()
    for e in payload_ext.SCREEN_REGISTRY:
        union |= {t for t in e["tables"] if t in names}
        for p in e["products"]:
            union |= {sp.name for sp in cat.by_product(p)}
    assert union == names, sorted(names - union)


def test_groups_order_matches_the_rendered_nav(html):
    gdoc, screens = R.load_registry_files()
    order = [g["slug"] for g in sorted(gdoc["groups"], key=lambda g: g["order"])]
    assert [s["slug"] for s in screens] == sorted(
        (s["slug"] for s in screens), key=order.index)
    nav = json.loads(re.search(r"window\.__RYNTA_NAV__=(\{.*\})</script>",
                               html, re.S).group(1))
    assert [g["slug"] for g in nav["groups"]] == order
    assert [t[0] for t in nav["tree"]] == [
        g["label_ko"] for g in sorted(gdoc["groups"], key=lambda g: g["order"])]


# ---------------------------------------------------------------- A23 ownership

def test_ownership_is_marked_as_a_ui_assumption(ext, studio):
    own = ext["x_ownership"]
    assert own["source"] == payload_ext.OWNERSHIP_SOURCE
    assert own["ledger_has_domain_role_join"] is False
    domains = set(studio.tables["gov_run_domain"]["domain"].astype(str))
    assert set(own["by_domain"]) == domains
    for code, v in own["by_domain"].items():
        if v is None:
            assert code in own["unresolved"]
        else:
            assert v["source"] == payload_ext.OWNERSHIP_SOURCE
            assert v["role_id"] == payload_ext.DOMAIN_ROLE_MAP[code]


# ---------------------------------------------------------------- A24 gate kinds

def _gate_ext(studio, tmp_path):
    gate = independent.check_gate(studio.iv_request, directory=tmp_path)
    return payload_ext.build_ext(dataclasses.replace(studio, iv_gate=gate),
                                 iv_dir=tmp_path)["x_gate"]["independent"], gate


def test_pending_gate_is_reported_as_pending(studio, tmp_path):
    indep, gate = _gate_ext(studio, tmp_path)
    assert gate.status == "응답대기"
    assert indep["kind"] == "pending"
    assert indep["tone"] == "blocked"
    assert indep["response"] is None
    assert indep["dispatch_dir"] == Path(tmp_path).as_posix()


def test_a_foreign_response_is_procedural_not_substantive(studio, tmp_path):
    """A24: a 부적합 whose response belongs to another request is procedural."""
    req = studio.iv_request
    body = {
        "request_id": req.request_id + "-OTHER",
        "run_id": req.run_id,
        "verdict": "중부적합",
        "validated_by": independent.VALIDATION_TEAM,
        "validated_at": req.created_at,
        "findings": [],
        "recalc_matches": {},
    }
    req.response_path(tmp_path).write_text(
        json.dumps(body, ensure_ascii=False), encoding="utf-8")
    indep, gate = _gate_ext(studio, tmp_path)
    assert gate.status == "부적합"
    assert indep["kind"] == "procedural"
    assert indep["tone"] == "bad"
    assert indep["response"]["request_id"] == body["request_id"]


def test_dispatch_dir_falls_back_to_the_module_default(ext):
    assert ext["x_gate"]["independent"]["dispatch_dir"] == \
        Path(independent.DEFAULT_DIR).as_posix()


def test_build_ext_never_reads_the_response_itself():
    """A24: only Studio.iv_gate decides; payload_ext does not open a file."""
    src = Path(payload_ext.__file__).read_text(encoding="utf-8")
    assert "ValidationResponse.read" not in src
    assert "check_gate" not in src


# ---------------------------------------------------------------- A25 stripped payload

def test_no_kri_carries_a_synthetic_history(html, studio):
    kris = _payload(html)["executive"]["kris"]
    assert kris, "the fixture has no KRI rows"
    for k in kris:
        assert "spark" not in k and "trend" not in k
    assert {"name", "grade", "category"} <= set(kris[0])


def test_gate_strip_status_comes_from_the_ledger(ext, studio):
    """A25: the strip repeats the ledger status verbatim; A9 tone rule."""
    row = studio.tables["val_independent_request"].iloc[0]
    indep = ext["x_gate"]["independent"]
    assert indep["status"] == str(row["status"])
    assert indep["request_id"] == str(row["request_id"])
    tone = ext["x_gate"]["overall"]["tone"]
    status = indep["status"]
    if status == "부적합":
        assert tone == "bad"
    elif status in ("응답대기", "요청됨"):
        assert tone == "blocked"
    elif status == "조건부":
        assert tone == "warn"
    assert ext["x_gate"]["overall"]["blocks_approval"] == (tone != "good")


# ---------------------------------------------------------------- x_lcr, x_trend

def test_lcr_reconciliation_reports_one_of_three_states(ext):
    lcr = ext["x_lcr"]
    assert lcr["state"] in ("reconciled", "not reconciled", "not computable")
    if lcr["state"] == "not computable":
        assert lcr["reason"], "an uncomputable LCR must say why"
    else:
        assert lcr["result"]["lcr"] is not None
        assert lcr["tolerance"]["method"] == "math.isclose"


def test_trend_says_it_has_no_history_without_a_ledger(ext):
    t = ext["x_trend"]
    assert t["ledger_path"] is None
    assert t["n_periods"] == 0 and t["single_period"] is True
    assert t["flags"] == [] and t["qoq_yoy"] == {}


def test_trend_reads_a_ledger_when_one_is_given(studio, tmp_path):
    from risk_lib.timeseries_ledger import HEADLINE_SPEC, PeriodSnapshot, TimeSeriesLedger
    digest = str(studio.tables["val_independent_request"].iloc[0]["headline_digest"])
    led = TimeSeriesLedger()
    for i, (period, asof, dg) in enumerate((("2026Q1", "2026-03-31", "0" * 64),
                                            ("2026Q2", studio.asof, digest))):
        led.add(PeriodSnapshot(
            period=period, asof=asof, seed=int(studio.tables["gov_unified_run"]
                                               .iloc[0]["seed"]),
            headline={m: 0.1 + i * 0.01 for m in HEADLINE_SPEC},
            headline_digest=dg, validation_summary={}))
    path = tmp_path / "headline_trend.json"
    led.save(path)
    t = payload_ext.build_ext(studio, ledger_path=path)["x_trend"]
    assert t["ledger_path"] == str(path)
    assert t["n_periods"] == 2 and t["single_period"] is False
    assert [p["asof"] for p in t["periods"]] == ["2026-03-31", studio.asof]
    assert {f["metric"] for f in t["flags"]} <= set(HEADLINE_SPEC)
    assert t["digest_matches_latest"] is True


def test_payload_ext_carries_no_regulatory_literal():
    """Numbers come from the ledgers; 0 and 1 are the only float literals."""
    src = Path(payload_ext.__file__).read_text(encoding="utf-8")
    floats = {m for m in re.findall(r"(?<![\w.])\d+\.\d+", src)}
    assert floats <= {"0.0", "1.0"}, sorted(floats)
    assert "1e-" not in src


# ---------------------------------------------------------------- i18n catalogue

def test_merged_catalogue_has_both_languages_and_no_conflict():
    merged = i18n_next.merged_map()
    assert merged
    for ko, en in merged.items():
        assert ko.strip() and str(en).strip()
        assert EM_DASH not in en and EN_DASH not in en, ko
        assert not (re.search(r"[가-힣]", en)
                    and not re.search(r"[A-Za-z]", en)) or en == "한국어", ko


def test_no_two_screen_modules_own_the_same_key():
    assert i18n_next.duplicate_keys_across_modules() == {}


def test_every_screen_module_has_a_catalogue_file():
    slugs = {g["slug"] for g in R.load_registry_files()[0]["groups"]}
    have = {n[len("ng_"):] for n in i18n_next._module_names()}
    assert slugs <= have, sorted(slugs - have)


@pytest.mark.parametrize("path", _static_js(), ids=lambda p: p.name)
def test_every_translated_literal_is_catalogued(path):
    merged = i18n_next.merged_map()
    src = _static_text(path)
    keys = re.findall(r"\bTF?\(\s*'((?:[^'\\]|\\.)*)'", src)
    miss = sorted({k.replace("\\'", "'") for k in keys
                   if re.search(r"[가-힣]", k)
                   and k.replace("\\'", "'") not in merged})
    assert miss == [], miss
