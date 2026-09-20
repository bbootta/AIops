"""차세대 UI 셸 렌더러. 자체 완결 단일 HTML (설계 사양 3장, A1..A3, A16).

app.py 는 건드리지 않고 그 `_payload` 를 기본 payload 로 재사용한다.
payload_ext 가 x_ 키를 더하고, 정적 파일(tokens.css, base.css, engine.js,
core.js, charts.js, shared.js, screens/*.js)은 groups.json 순서로 인라인한다.
브라우저는 payload 만 읽는다: 외부 리소스·fetch·CDN 이 없다.
"""

from __future__ import annotations

import html
import json
import re
import warnings
from pathlib import Path

from risk_lib import data_gen_intl as _intl
from risk_lib.ui_studio import app as _app
from risk_lib.ui_studio import i18n as _i18n
from risk_lib.ui_studio.studio import Studio

NEXT_DIR = Path(__file__).parent
STATIC = NEXT_DIR / "static"
REGISTRY_DIR = NEXT_DIR / "registry"
HEAD_CSS = ("tokens.css", "base.css")
BODY_JS = ("core.js", "charts.js", "shared.js")
# 정적 JS+CSS 예산 (shared_contracts.budgets). 상한은 올리지 않는다.
STATIC_HARD = 600_000
STATIC_WARN = 540_000
DEPLOY_SIZE_LIMIT = _app.DEPLOY_SIZE_LIMIT

_SIZE: dict[str, int] = {}
_DASHES = ("\u2014", "\u2013")
_COMMENT_ONLY = re.compile(r"^\s*(//.*|/\*(?:(?!\*/).)*\*/\s*)$")


def size_report() -> dict[str, int]:
    """마지막 렌더에서 실제로 실은 정적 파일별 바이트 (strip_static 이후)."""
    return dict(_SIZE)


def strip_static(text: str) -> str:
    """빈 줄과 주석만 있는 줄(// 또는 /* ... */ 한 줄)을 결정론적으로 뺀다.

    다른 토큰이 하나라도 있는 줄은 건드리지 않는다. 멱등이다.
    """
    keep = [ln for ln in text.split("\n")
            if ln.strip() and not _COMMENT_ONLY.match(ln)]
    return "\n".join(keep) + "\n"


def _guard(name: str, text: str) -> None:
    for c in _DASHES:
        if c in text:
            raise ValueError(f"{name}: 긴 대시 U+{ord(c):04X} 가 정적 파일에 있다")


def _esc(text: str) -> str:
    """스크립트 본문의 긴 대시를 JS/JSON 이스케이프로 바꾼다. 값은 유지된다."""
    return text.replace("\u2014", "\\u2014").replace("\u2013", "\\u2013")


def _static(name: str) -> str:
    p = STATIC / name
    if not p.exists():
        warnings.warn(f"정적 파일이 없다: {p}", stacklevel=3)
        _SIZE[name] = 0
        return ""
    text = p.read_text(encoding="utf-8")
    _guard(name, text)
    out = strip_static(text)
    _SIZE[name] = len(out.encode("utf-8"))
    return out


def _js(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str, sort_keys=True,
                      separators=(",", ":"))


# ── 화면 레지스트리 (data, registry/*.json) ─────────────────────────────

def load_registry_files() -> tuple[dict, list[dict]]:
    """groups.json 과 <slug>.json 을 groups 순서로 읽는다. 검증은 payload_ext."""
    gdoc = json.loads((REGISTRY_DIR / "groups.json").read_text(encoding="utf-8"))
    groups = sorted(gdoc["groups"], key=lambda g: g["order"])
    screens: list[dict] = []
    for g in groups:
        for e in json.loads((REGISTRY_DIR / f"{g['slug']}.json")
                            .read_text(encoding="utf-8")):
            screens.append({**e, "group": g["label_ko"], "slug": g["slug"],
                            "module": g["module"]})
    return gdoc, screens


def _label(e: dict) -> str:
    """nav button 의 dataset.ko: 흡수한 기존 화면의 라벨, 새 화면은 title_ko."""
    return e["legacy"][0] if e.get("legacy") else e["title_ko"]


def _lit(v) -> str:
    """단일 인용 Python repr 의 중첩 리스트 리터럴 (json.dumps 가 아니다)."""
    if isinstance(v, list):
        return "[" + ",".join(_lit(x) for x in v) + "]"
    r = repr(str(v))
    if r[0] != "'":
        raise ValueError(f"작은따옴표 리터럴로 적을 수 없다: {v!r}")
    return r


def _tree(groups: list[dict], screens: list[dict]) -> list:
    """[group_ko, [leaf | [sub_or_leaf_parent, [leaves]]]] 중첩 구조."""
    out = []
    for g in groups:
        nodes: list = []
        subs: dict[str, list] = {}
        for e in (x for x in screens if x["slug"] == g["slug"]):
            lab = _label(e)
            if e["sub"] is None:
                node = [lab, []] if e["leaf_parent"] else lab
                nodes.append(node)
                if e["leaf_parent"]:
                    subs[e["title_ko"]] = node
                    subs[lab] = node
                continue
            if e["sub"] not in subs:
                node = [lab, []] if e["leaf_parent"] else [e["sub"], []]
                nodes.append(node)
                subs[e["sub"]] = node
                if e["leaf_parent"]:
                    continue
            subs[e["sub"]][1].append(lab)
        out.append([g["label_ko"], nodes])
    return out


def nav_literals(gdoc: dict, screens: list[dict]) -> str:
    """core.js 스크립트 블록 맨 위에 붙는 const NAVGROUPS / TABS / NAV_DISPLAY."""
    groups = sorted(gdoc["groups"], key=lambda g: g["order"])
    tabs = [[_label(e), e["title_en"], e["id"]] for e in screens]
    disp = ",".join(f"{_lit(k)}:{_lit(v)}"
                    for k, v in sorted(gdoc.get("NAV_DISPLAY", {}).items()))
    return (f"const NAVGROUPS={_lit(_tree(groups, screens))};\n"
            f"const TABS={_lit(tabs)};\n"
            f"const NAV_DISPLAY={{{disp}}};\n")


def nav_payload(gdoc: dict, screens: list[dict]) -> dict:
    groups = sorted(gdoc["groups"], key=lambda g: g["order"])
    return {
        "groups": groups,
        "screens": screens,
        "tree": _tree(groups, screens),
        "nav_display": gdoc.get("NAV_DISPLAY", {}),
        "aliases": {lab: e["id"] for e in screens for lab in e["legacy"]},
        "labels": {_label(e): e["id"] for e in screens},
    }


# ── payload ────────────────────────────────────────────────────────────

def _payload_ext():
    try:
        from risk_lib.ui_studio.next import payload_ext
    except ImportError as exc:                      # 병렬 작성 중
        warnings.warn(f"payload_ext 를 불러오지 못해 x_ 키 없이 그린다: {exc}",
                      stacklevel=3)
        return None
    return payload_ext


def _run_payload(s: Studio, ledger_path, pe) -> dict:
    p = _app._payload(s)
    if pe is not None:
        r = pe.strip_base(p)
        p = r if isinstance(r, dict) else p
        ext = pe.build_ext(s, ledger_path=ledger_path)
        p.update({k: v for k, v in ext.items() if k.startswith("x_")})
    return p


def _i18n_payload() -> dict:
    try:
        from risk_lib.ui_studio.next import i18n_next
    except ImportError as exc:                      # 병렬 작성 중
        warnings.warn(f"i18n_next 를 불러오지 못해 기존 카탈로그만 싣는다: {exc}",
                      stacklevel=3)
        return _i18n.payload()
    return i18n_next.payload()


def _write_allowed(s: Studio) -> str:
    ar = s.tables.get("agent_registry")
    if ar is None or "write_allowed" not in ar.columns:
        return "-"
    # 참인 건수 / 전체. 전 에이전트가 거짓이면 0/N 이다 (A19).
    return f'{int(ar["write_allowed"].astype(bool).sum())}/{len(ar)}'


# ── HTML ───────────────────────────────────────────────────────────────

_PREPAINT = """<script>(function(){try{var t=localStorage.getItem('rynta-theme');
if(t==='light'||t==='dark')document.documentElement.setAttribute('data-theme',t);
}catch(e){}})();</script>"""

_AIMS = ("에이전트는 신용등급·여신승인, 가격·거래, PD·LGD·EAD 등 핵심 위험파라미터, "
         "ECL·충당금·회계전표, RWA·NCR·BIS 비율, 감독제출·공시, 경영조치, "
         "운영코드·모형 배포를 자동확정하지 않는다.")
_KILLNOTE = ("화면 전용 가드다. 이 페이지 안의 조회·제안 실행만 막고 운영 런타임에는 "
             "영향이 없으며 agent_killswitch 원장에는 쓰지 않는다.")
_MASK_TITLE = ("마스킹은 조회 조건에는 엔진이, 출력 컬럼에는 화면만 적용한다. "
               "화면 밖 데이터는 이 가드가 지키지 않는다.")


def _header(m: dict, inst: dict) -> str:
    mr = inst.get("master_row") or {}
    e = html.escape
    chip_inst = " · ".join(str(mr.get(k) or "-")
                           for k in ("region", "institution_type", "data_origin"))
    return f"""<div class="topbar">
<header>
  <div class="brand">RYNTA <span>·</span> <b data-i18n>게이트하우스</b></div>
  <label class="hchip" for="instsel"><span data-i18n>기관</span>
    <select id="instsel" class="sel instsel"></select></label>
  <label class="hchip" for="asofsel"><span data-i18n>기준일</span>
    <select id="asofsel" class="sel asofsel"></select></label>
  <span class="hchip" id="chip-inst">{e(chip_inst)}</span>
  <span class="hchip" id="chip-run">{e(m['run_id'])}</span>
  <span class="hchip" id="chip-digest"><span data-i18n>지문</span> {e(m['digest'][:12])}</span>
  <span class="hchip" id="chip-seed"><span data-i18n>시드</span> {m['seed']}</span>
  <span class="hchip" id="chip-rows">테이블 {m['n_tables']}장 · {m['n_rows']:,}행</span>
  <span class="hchip" title="{e(_MASK_TITLE)}" data-i18n>Read-only · 조건·출력 마스킹</span>
  <button id="langbtn" class="theme" type="button">한국어</button>
  <button id="themebtn" class="theme" type="button" aria-pressed="false"
          title="밝은 화면과 어두운 화면을 전환한다" data-i18n>화면 밝기</button>
  <button class="kill" type="button" data-i18n>Kill Switch (화면 가드)</button>
</header>
<div id="gatestrip" role="status" aria-live="polite" data-gate-status="" data-tone=""></div>
<div class="killbar" hidden>
  <label for="killscope" data-i18n>범위</label>
  <select id="killscope" class="sel"></select>
  <label for="killreason" data-i18n>비상정지 사유 (필수)</label>
  <input id="killreason" type="text" value="">
  <label for="killconfirm" data-i18n>2차 확인자 (필수)</label>
  <input id="killconfirm" type="text" value="">
  <button class="killgo" type="button" disabled data-i18n>정지</button>
  <button class="killno" type="button" data-i18n>취소</button>
  <span class="killnote" data-i18n>{e(_KILLNOTE)}</span>
</div>
</div>"""


def _footer(m: dict, asof: str, write_allowed: str) -> str:
    return f"""<footer>
  <span data-i18n>화면의 모든 값은 합성 포트폴리오에서</span> <code>run_pipeline(seed=<span
  id="foot-seed">{m['seed']}</span>,
  asof='<span id="foot-asof">{html.escape(asof)}</span>')</code><span
  data-i18n>로 산출한 것이며 실제 기관 수치가 아니다.</span>
  <span data-i18n>{_AIMS}</span>
  <span id="foot-write"><span data-i18n>운영 반영 권한(write_allowed)은 전 에이전트가 거짓이다:</span> {write_allowed}</span>
</footer>"""


def render_next(studios: Studio | list[Studio], ledger_path=None,
                fragment: bool = False) -> str:
    """하나 이상의 실행 스냅샷을 한 화면으로 그린다 (실린 실행 사이 전환만).

    `fragment` 는 아티팩트 배포용이다. 호스트가 문서 골격을 감싸므로 제목·
    스타일·본문만 내보낸다. 파일로 저장하는 경로(`write_app_next`)는 기본값
    그대로 완전한 문서를 쓴다.
    """
    ss = [studios] if isinstance(studios, Studio) else list(studios)
    order = {c: i for i, c in enumerate(_intl.institution_codes())}
    ss = sorted(ss, key=lambda x: (order.get(x.institution_code, len(order)),
                                   x.asof))
    pe = _payload_ext()
    insts: dict[str, dict[str, dict]] = {}
    for s in ss:
        insts.setdefault(s.institution_code, {})[s.asof] = \
            _run_payload(s, ledger_path, pe)
    primary_inst = ss[0].institution_code
    runs = insts[primary_inst]
    asof = sorted(runs)[-1]
    m = runs[asof]["meta"]
    # 기본 기관의 실행은 두 번 싣지 않는다 (참조).
    insts_js = "{" + ",".join(
        f"{json.dumps(code)}:" + ("window.__RYNTA_RUNS__" if code == primary_inst
                                 else _js(rr))
        for code, rr in insts.items()) + "}"
    gdoc, screens = load_registry_files()
    _SIZE.clear()
    css = "\n".join(_static(n) for n in HEAD_CSS)
    engine = strip_static(_app._ENGINE_JS)
    _SIZE["engine.js"] = len(engine.encode("utf-8"))
    order_js = list(BODY_JS) + [
        f"screens/{g['slug']}.js"
        for g in sorted(gdoc["groups"], key=lambda g: g["order"])]
    blocks = []
    for i, name in enumerate(order_js):
        body = _static(name)
        if i == 0:
            body = nav_literals(gdoc, screens) + body
        blocks.append(f"<script>{_esc(body)}</script>")
    total = sum(_SIZE.values())
    if total > STATIC_HARD:
        raise ValueError(f"정적 JS+CSS {total:,}B 가 상한 {STATIC_HARD:,}B 를 넘었다")
    if total > STATIC_WARN:
        warnings.warn(f"정적 JS+CSS {total:,}B 가 경고선 {STATIC_WARN:,}B 를 넘었다",
                      stacklevel=2)
    payload_js = (
        f"window.__RYNTA_RUNS__={_js(runs)};\n"
        f"window.__RYNTA__=window.__RYNTA_RUNS__[{json.dumps(asof)}];\n"
        f"window.__RYNTA_INSTS__={insts_js};\n"
        f"window.__RYNTA_I18N__={_js(_i18n_payload())};\n"
        f"window.__RYNTA_NAV__={_js(nav_payload(gdoc, screens))}")
    body = (
        f"{_PREPAINT}\n"
        f"{_header(m, runs[asof].get('institution') or {})}\n"
        f"<div class=\"layout\">\n<nav aria-label=\"메뉴\"></nav>\n<main></main>\n</div>\n"
        f"<aside id=\"drawer\" role=\"complementary\" aria-label=\"상세\" hidden></aside>\n"
        f"<div id=\"palette\" role=\"dialog\" aria-label=\"명령 팔레트\" hidden></div>\n"
        f"{_footer(m, asof, _write_allowed(ss[0]))}\n"
        f"<script>{_esc(payload_js)}</script>\n"
        f"<script>{_esc(engine)}</script>\n" + "\n".join(blocks))
    title = f"RYNTA 게이트하우스 · {html.escape(asof)}"
    if fragment:
        # 아티팩트 호스트가 doctype·html·head·body 를 자기 것으로 감싼다.
        # 그 안에 두 번 감싸면 문서가 중첩되므로 제목·스타일·본문만 낸다.
        # 문서 언어는 호스트가 정하므로 스크립트가 나중에 documentElement 에
        # 적는다 (setLang 이 이미 그렇게 한다).
        # 아티팩트 제목은 판마다 바뀌면 안 된다(같은 탭·같은 카드로 남아야
        # 한다). 기준일은 머리말 칩에 이미 있으므로 제목은 이름만 쓴다.
        return f"<title>RYNTA 게이트하우스</title>\n<style>{css}</style>\n{body}\n"
    return (
        f"<!doctype html>\n<html lang=\"{_i18n.DEFAULT_LANG}\"><head>"
        f"<meta charset=\"utf-8\">\n"
        f"<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\n"
        f"<title>{title}</title>\n"
        f"<style>{css}</style></head><body>\n{body}\n</body></html>")


def write_app_next(studios: Studio | list[Studio], path: str | Path,
                   ledger_path=None) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render_next(studios, ledger_path=ledger_path), encoding="utf-8")
    n = p.stat().st_size
    if n > DEPLOY_SIZE_LIMIT:
        # 자르지 않는다. 조용히 줄어든 원장은 화면 어디에도 흔적이 남지 않는다.
        n_runs = 1 if isinstance(studios, Studio) else len(list(studios))
        warnings.warn(
            f"UI 스튜디오 HTML 이 {n/1024/1024:.1f}MB 로 배포 상한 "
            f"{DEPLOY_SIZE_LIMIT/1024/1024:.0f}MB 를 넘었다. 실은 실행 "
            f"{n_runs}건. 싣는 실행 수를 줄이거나 행 예산"
            f"(INTERACTIVE_ROWS·INTERACTIVE_ROWS_DEMO)을 낮춰야 하며, "
            f"어느 쪽을 줄일지는 사람이 정한다.",
            stacklevel=2)
    return p
