"""원장·화면 계보 추출기 (DAT-001 계보).

흐름도를 손으로 그리면 코드가 바뀐 뒤 문서와 코드가 갈라진다. 이 모듈은
계보를 **소스에서 뽑는다**. 뽑는 대상은 네 갈래다.

  원장 → 화면   `ui_studio/app.py` 의 화면 선언(TABS·DETAIL_SCREENS)에서
                 참조하는 원장. `D.data['x']` 직접 참조, `screenOf({tables:…})`
                 선언, `domain(r,'PRD-x')` 부문 전개, 파이썬 `_payload` 가
                 만든 payload 키를 화면이 읽는 경로까지 따라간다.
  원장 → 서식   `regulatory/*.py` 의 `ctx.tables["x"]`.
  원장 → 원장   TableSpec 의 FK 선언 + 같은 함수(또는 모듈 상수)가 A를 읽고
                 B를 쓰는 관계.
  산출 → 원장   테이블명을 키로 대입하는 함수(`tables["x"] = …`,
                 `{"x": df}`)가 생산자다. TableSpec 을 선언한 모듈이 소유자다.

정적 분석만으로는 실체화 여부를 모른다. `build_lineage(tables=…)` 에 실행
결과(`Studio.tables`)를 주면 행수가 붙는다. 주지 않으면 행수 칸이 비고,
비었다는 사실이 그대로 남는다.

재생성:

    python -m risk_lib.datamodel.lineage            # docs/DATA_FLOW.md 갱신
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from risk_lib.datamodel import catalog as cat
from risk_lib.datamodel.spec import TableSpec

_ROOT = Path(__file__).resolve().parents[2]
_APP = _ROOT / "risk_lib" / "ui_studio" / "app.py"
_PIPELINE = _ROOT / "risk_lib" / "pipeline.py"
_REGULATORY = _ROOT / "risk_lib" / "regulatory"
_LIB = _ROOT / "risk_lib"

# 카탈로그는 스펙 **선언**이고 요건추적은 증빙 **주장**이다. 둘을 참조로 세면
# 모든 테이블이 자기 자신을 참조하는 것으로 잡혀 계보가 무의미해진다.
# 이 모듈 자신도 뺀다. 판정 대장의 키가 원장을 만드는 것으로 잡힌다.
_SCAN_SKIP = ("risk_lib/datamodel/catalog.py", "risk_lib/ui_studio/req_trace.py",
              "risk_lib/datamodel/lineage.py")

# 여러 빌더를 모아 부르는 함수. 이 함수의 읽기·쓰기는 실행 순서를 뜻한다.
# 원장 간 의존으로 세면 한 함수가 수십 건의 없는 간선을 만든다.
_ORCHESTRATORS = ("_stage_", "materialize", "run_pipeline", "build_studio")

# 화면이지만 특정 원장을 그리지 않는 것. 정형 조회·비정형 UI 는 승인 View
# 전량을 대상으로 하는 범용 조회기이고, 데이터모델은 스펙 열람기다. 이 넷을
# "그린다"로 세면 카탈로그의 모든 테이블이 화면에 연결돼 고아가 사라진다.
GENERIC_SCREENS = ("정형 조회", "비정형 UI", "데이터모델", "⚙ 설정")

# 부문 코드 → 조감도 블록. 블록 이름은 사용자가 요청한 8구획이다.
DOMAIN_BLOCK: dict[str, str] = {
    "PRD-RDM": "원천·리스크데이터",
    "PRD-CRM": "신용", "PRD-RWA": "신용", "PRD-ECL": "신용",
    "PRD-MKT": "시장", "PRD-NCR": "시장",
    "PRD-OPR": "운영",
    "PRD-ALM": "ALM",
    "PRD-ST": "위기상황", "PRD-CAP": "위기상황", "PRD-ICP": "위기상황",
    "PRD-REG": "규제서식", "PRD-PRU": "규제서식",
    "PRD-VAL": "거버넌스·통제", "PRD-AIG": "거버넌스·통제",
    "PRD-UIX": "거버넌스·통제", "PRD-LIMIT": "거버넌스·통제",
}
BLOCK_ORDER = ("원천·리스크데이터", "신용", "시장", "운영", "ALM",
               "위기상황", "규제서식", "거버넌스·통제")


def block_of(spec: TableSpec) -> str:
    return DOMAIN_BLOCK.get(spec.product, "미분류")


# ---------------------------------------------------------------- 자료구조

@dataclass(frozen=True)
class Edge:
    src: str
    dst: str
    kind: str          # produces · feeds · fk · renders · reports
    via: str = ""      # 근거 (모듈::함수 · 화면 라벨 · FK 컬럼)


@dataclass
class Lineage:
    specs: tuple[TableSpec, ...]
    edges: tuple[Edge, ...]
    screens: dict[str, dict]          # 라벨 → {title, generic, tables}
    forms: dict[str, set[str]]        # 서식 모듈 → 읽는 원장
    owners: dict[str, str]            # 원장 → TableSpec 선언 모듈
    producers: dict[str, set[str]]    # 원장 → 생산 함수 (모듈::함수)
    rows: dict[str, int] = field(default_factory=dict)   # 실행 시 행수

    # ---- 조회 --------------------------------------------------------
    @property
    def spec_by_name(self) -> dict[str, TableSpec]:
        return {s.name: s for s in self.specs}

    def edges_of(self, kind: str) -> list[Edge]:
        return [e for e in self.edges if e.kind == kind]

    def rendered(self) -> set[str]:
        """전용 화면이 그리는 원장. 범용 조회기는 세지 않는다."""
        out: set[str] = set()
        for lab, s in self.screens.items():
            if s["generic"]:
                continue
            out |= s["tables"]
        return out

    def reported(self) -> set[str]:
        """감독서식이 읽는 원장."""
        return set().union(*self.forms.values()) if self.forms else set()

    def downstream(self) -> dict[str, set[str]]:
        """원장 → 이 원장을 재료로 쓰는 원장."""
        out: dict[str, set[str]] = {}
        for e in self.edges:
            if e.kind in ("feeds", "fk"):
                out.setdefault(e.src, set()).add(e.dst)
        return out

    def unwired(self) -> list[str]:
        """전용 화면도 서식도 쓰지 않는 원장. 고아 판정의 모집단이다."""
        used = self.rendered() | self.reported()
        return sorted(s.name for s in self.specs if s.name not in used)

    def orphans(self) -> list[str]:
        """지시받은 정의 그대로. 화면·서식·하류원장 셋 다 없는 원장."""
        down = self.downstream()
        return [n for n in self.unwired() if not down.get(n)]


# ---------------------------------------------------------------- 공통 유틸

def _names() -> set[str]:
    return {s.name for s in cat.ALL_TABLES}


def _py_files() -> list[Path]:
    skip = {(_ROOT / p) for p in _SCAN_SKIP}
    return sorted(p for p in _LIB.rglob("*.py") if p not in skip)


def _rel(p: Path) -> str:
    return str(p.relative_to(_ROOT))


def _scope_tables(node: ast.AST, names: set[str]) -> tuple[set[str], set[str]]:
    """이 노드의 **직속 범위**에서 쓰는 테이블과 참조하는 테이블.

    하위 함수는 제외한다. 함수마다 따로 세지 않으면 한 모듈이 쓰는 것과 읽는
    것이 전부 교차곱으로 이어져 없는 의존이 생긴다.
    """
    written: set[str] = set()
    written_ids: set[int] = set()
    refs: set[str] = set()

    def walk(n: ast.AST, collect_write: bool):
        for child in ast.iter_child_nodes(n):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if collect_write:
                if (isinstance(child, ast.Subscript)
                        and isinstance(child.slice, ast.Constant)
                        and child.slice.value in names
                        and isinstance(child.ctx, ast.Store)):
                    written.add(child.slice.value)
                    written_ids.add(id(child.slice))
                if isinstance(child, ast.Dict):
                    for k in child.keys:
                        if (isinstance(k, ast.Constant) and k.value in names):
                            written.add(k.value)
                            written_ids.add(id(k))
            elif (isinstance(child, ast.Constant)
                  and isinstance(child.value, str)
                  and child.value in names and id(child) not in written_ids):
                refs.add(child.value)
            walk(child, collect_write)

    walk(node, True)
    walk(node, False)
    return written, refs


# ---------------------------------------------------------------- 산출 계보

def scan_owners(names: set[str] | None = None) -> dict[str, str]:
    """원장 → TableSpec 을 선언한 모듈. 스펙이 없는 원장은 나오지 않는다."""
    names = names or _names()
    out: dict[str, str] = {}
    # 소유자는 카탈로그에서도 찾는다. 스펙 선언은 참조가 아니므로 계보 스캔이
    # 카탈로그를 건너뛰는 것과 별개다. 건너뛰면 108장이 소유자 없이 남는다.
    for p in sorted(_LIB.rglob("*.py")):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            if not (isinstance(n, ast.Call)
                    and getattr(n.func, "id", "") == "TableSpec"):
                continue
            for kw in n.keywords:
                if (kw.arg == "name" and isinstance(kw.value, ast.Constant)
                        and kw.value.value in names):
                    out[kw.value.value] = _rel(p)
    return out


def scan_dataflow(names: set[str] | None = None
                  ) -> tuple[dict[str, set[str]], list[Edge]]:
    """(원장 → 생산 함수, 원장→원장 feeds 간선).

    생산자는 테이블명을 키로 값을 대입하는 함수다. feeds 는 같은 함수가 A를
    읽고 B를 쓰면 A→B로 본다. 함수가 테이블명을 안 읽고 모듈 상수 목록으로
    받는 경우(감사사슬의 수집 원장 목록 등)를 위해 모듈 상수도 본다.
    """
    names = names or _names()
    producers: dict[str, set[str]] = {}
    edges: list[Edge] = []
    owners = scan_owners(names)

    for p in _py_files():
        rel = _rel(p)
        tree = ast.parse(p.read_text(encoding="utf-8"))
        mod_w, mod_r = _scope_tables(tree, names)
        # 모듈이 스펙을 선언한 원장도 그 모듈의 산출로 본다. 스펙과 빌더가
        # 같은 모듈에 있는데 대입은 실체화 단계에서 일어나는 구성이 흔하다.
        mod_out = mod_w | {t for t, m in owners.items() if m == rel}

        for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
            w, r = _scope_tables(fn, names)
            if not w:
                continue
            via = f"{rel}::{fn.name}"
            for t in w:
                producers.setdefault(t, set()).add(via)
            # 오케스트레이터는 여러 빌더를 한 자리에서 부른다. 읽는 원장과
            # 쓰는 원장을 교차곱으로 이으면 없는 의존이 수십 건 생긴다.
            # (`_stage_ledgers` 하나가 ALM→거버넌스 48건을 만들었다)
            kind = "orchestrates" if fn.name.startswith(_ORCHESTRATORS) else "feeds"
            for src in sorted((r or mod_r) - w):
                for dst in sorted(w):
                    edges.append(Edge(src, dst, kind, via))

        for t in sorted(mod_w):
            producers.setdefault(t, set()).add(f"{rel}::<module>")
        for src in sorted(mod_r - mod_out):
            for dst in sorted(mod_out):
                edges.append(Edge(src, dst, "feeds", f"{rel}::<module>"))
    return producers, edges


def fk_edges(specs: tuple[TableSpec, ...] | None = None) -> list[Edge]:
    """FK 선언에서 나오는 원장 간 의존. 참조되는 쪽이 상류다."""
    specs = specs or cat.ALL_TABLES
    return sorted(
        (Edge(fk.ref_table, s.name, "fk", "+".join(fk.columns))
         for s in specs for fk in s.foreign_keys),
        key=lambda e: (e.src, e.dst, e.via))


def stage_io(names: set[str] | None = None) -> dict[str, dict[str, set[str]]]:
    """pipeline.py 의 `_stage_*` · `run_pipeline` 이 읽고 쓰는 원장."""
    names = names or _names()
    tree = ast.parse(_PIPELINE.read_text(encoding="utf-8"))
    out: dict[str, dict[str, set[str]]] = {}
    for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        if not (fn.name.startswith("_stage_") or fn.name == "run_pipeline"):
            continue
        w, r = _scope_tables(fn, names)
        if w or r:
            out[fn.name] = {"writes": w, "reads": r - w}
    return out


# ---------------------------------------------------------------- 서식 계보

def scan_forms(names: set[str] | None = None) -> dict[str, set[str]]:
    """감독서식 모듈 → 읽는 원장 (`ctx.tables["x"]`)."""
    names = names or _names()
    pat = re.compile(r'ctx\.tables\["(\w+)"\]')
    out: dict[str, set[str]] = {}
    for p in sorted(_REGULATORY.glob("*.py")):
        hit = {t for t in pat.findall(p.read_text(encoding="utf-8"))
               if t in names}
        if hit:
            out[p.name] = hit
    return out


# ---------------------------------------------------------------- 화면 계보

def _js_block(src: str, start: int) -> tuple[str, int]:
    """`start` 의 여는 괄호가 닫히는 곳까지. 문자열·주석 안의 괄호는 센다."""
    depth = 0
    i, n = start, len(src)
    quote = None
    while i < n:
        ch = src[i]
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "'\"`":
            quote = ch
        elif ch == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            i = (j + 2) if j > 0 else n
            continue
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
            if depth == 0:
                return src[start:i + 1], i + 1
        i += 1
    return src[start:], n


def _strip_js_comments(src: str) -> str:
    """자바스크립트 주석을 지운다. 문자열 안의 `//` 는 남긴다.

    주석을 남기면 설명문에 적힌 식별자가 참조로 잡힌다. 실제로 `wireExecLinks`
    의 주석에 적힌 `TABS` 때문에 종합보고서 화면이 전 화면의 원장을 그리는
    것으로 나왔다.
    """
    out = []
    i, n = 0, len(src)
    quote = None
    while i < n:
        ch = src[i]
        if quote:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(src[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "'\"`":
            quote = ch
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            i = (j + 2) if j > 0 else n
            continue
        if ch == "/" and i + 1 < n and src[i + 1] == "/":
            j = src.find("\n", i + 2)
            i = j if j > 0 else n
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def js_source() -> str:
    """app.py 의 `_JS` 블록만 뽑아 주석을 지운 자바스크립트 원문.

    파일 전체를 그대로 훑으면 파이썬 문자열 규칙(삼중따옴표·파이썬 주석)과
    자바스크립트 문자열 규칙이 섞여 따옴표 추적이 어긋난다. 어긋나면 주석이
    안 지워지고, 주석에 적힌 식별자가 참조로 잡힌다.
    """
    src = _APP.read_text(encoding="utf-8")
    m = re.search(r'^_JS = r"""\n(.*?)\n"""\s*$', src, re.S | re.M)
    if not m:
        raise RuntimeError("app.py 에서 _JS 블록을 찾지 못했다. "
                           "화면 계보를 뽑을 수 없다")
    return _strip_js_comments(m.group(1))


def _js_statement(src: str, start: int) -> str:
    """`start` 부터 최상위 깊이의 `;` 또는 줄바꿈까지. 괄호 안은 넘어간다.

    `const x=screenOf({…})` 처럼 여는 괄호가 첫 글자가 아닌 정의를 첫 줄만
    잘라 받으면 그 화면의 원장 선언이 통째로 사라진다.
    """
    depth = 0
    i, n = start, len(src)
    quote = None
    while i < n:
        ch = src[i]
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "'\"`":
            quote = ch
        elif ch == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            i = (j + 2) if j > 0 else n
            continue
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
            if depth < 0:
                break
        elif depth == 0 and ch in ";\n":
            break
        i += 1
    return src[start:i]


def _js_definitions(src: str) -> dict[str, tuple[str, str]]:
    """app.py 안 자바스크립트의 최상위 정의 이름 → (종류, 본문).

    종류가 'object' 인 것만 키 단위로 편다. 함수 본문도 `{` 로 시작하므로
    종류를 같이 들고 다니지 않으면 모든 함수가 객체로 취급된다.
    """
    out: dict[str, tuple[str, str]] = {}
    for m in re.finditer(r"^(function|const|let)\s+([A-Za-z_$][\w$]*)", src, re.M):
        kw, name = m.group(1), m.group(2)
        if kw == "function":
            brace = src.find("{", m.end())
            if brace < 0:
                continue
            body, _ = _js_block(src, brace)
            out[name] = ("function", body)
        else:
            eq = src.find("=", m.end())
            if eq < 0:
                continue
            body = _js_statement(src, eq + 1)
            kind = "object" if body.lstrip().startswith("{") else "expr"
            out[name] = (kind, body)
    return out


def _js_object_value(block: str, key: str) -> str:
    """객체 리터럴에서 키 하나의 값만 뽑는다.

    `DOMAIN_CHARTS` 처럼 부문별 차트를 한 객체에 모아 둔 정의를 통째로 펼치면
    'PRD-CRM' 하나를 부른 화면이 전 부문 원장을 그리는 것으로 잡힌다.
    """
    body = block.lstrip()
    if not body.startswith("{"):
        return ""
    pat = re.compile(rf"['\"]?{re.escape(key)}['\"]?\s*:")
    depth = 0
    i, n = 0, len(body)
    quote = None
    while i < n:
        ch = body[i]
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "'\"`":
            quote = ch
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif depth == 1:
            m = pat.match(body, i)
            if m:
                j, d2, q2 = m.end(), 0, None
                while j < n:
                    c = body[j]
                    if q2:
                        if c == "\\":
                            j += 2
                            continue
                        if c == q2:
                            q2 = None
                    elif c in "'\"`":
                        q2 = c
                    elif c in "([{":
                        d2 += 1
                    elif c in ")]}":
                        if d2 == 0:
                            break
                        d2 -= 1
                    elif c == "," and d2 == 0:
                        break
                    j += 1
                return body[m.end():j]
        i += 1
    return ""


def _js_array_entries(src: str, array_name: str) -> list[str]:
    """`const NAME=[ [..], [..] ]` 의 최상위 항목 원문."""
    m = re.search(rf"^const {array_name}=\[", src, re.M)
    if not m:
        return []
    arr, _ = _js_block(src, src.index("[", m.start()))
    out, i, n = [], 1, len(arr) - 1
    while i < n:
        if arr[i] == "[":
            blk, i = _js_block(arr, i)
            out.append(blk)
        else:
            i += 1
    return out


def payload_keys(names: set[str] | None = None) -> dict[str, set[str]]:
    """app.py `_payload` 의 payload 키 → 그 키가 담는 원장.

    화면이 `D.data['x']` 로 원장을 직접 읽기도 하지만 `D.agents` 처럼 파이썬
    쪽에서 미리 뽑아 둔 키를 읽기도 한다. 그 경로를 빼면 에이전트·검증·증빙
    화면이 전부 원장 없는 화면으로 잡힌다.
    """
    names = names or _names()
    tree = ast.parse(_APP.read_text(encoding="utf-8"))
    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}

    def consts(node: ast.AST) -> set[str]:
        return {c.value for c in ast.walk(node)
                if isinstance(c, ast.Constant) and isinstance(c.value, str)
                and c.value in names}

    def called(node: ast.AST) -> set[str]:
        return {c.func.id for c in ast.walk(node)
                if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}

    per_func = {k: consts(v) for k, v in funcs.items()}
    for k in per_func:                       # 한 단계 전개면 충분한 구조다
        for c in called(funcs[k]):
            if c in per_func and c != k:
                per_func[k] = per_func[k] | per_func[c]

    ret = [n for n in ast.walk(funcs["_payload"]) if isinstance(n, ast.Return)][-1]
    out: dict[str, set[str]] = {}
    for k, v in zip(ret.value.keys, ret.value.values):
        if not isinstance(k, ast.Constant):
            continue
        tabs = consts(v)
        for c in called(v):
            tabs |= per_func.get(c, set())
        out[k.value] = tabs
    return out


def ops_page_ledgers(names: set[str] | None = None) -> tuple[int, set[str]]:
    """보고서 페이지 세트(`page_registry.PAGES`)가 이름으로 부르는 원장.

    이 세트는 `PipelineResult` 객체를 직접 읽어 그린다. 원장을 거치지 않으므로
    화면 계보에 거의 잡히지 않고, 같은 수치를 원장에서 조회할 수 없다.
    """
    names = names or _names()
    from risk_lib.page_registry import PAGES
    refs: set[str] = set()
    for p in sorted((_LIB / "ops_pages").rglob("*.py")):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        refs |= {n.value for n in ast.walk(tree)
                 if isinstance(n, ast.Constant) and isinstance(n.value, str)
                 and n.value in names}
    return len(PAGES), refs


def scan_screens(names: set[str] | None = None) -> dict[str, dict]:
    """화면 라벨 → {title, generic, tables}."""
    names = names or _names()
    src = js_source()
    defs = _js_definitions(src)
    pkeys = payload_keys(names)
    by_product: dict[str, set[str]] = {}
    for s in cat.ALL_TABLES:
        by_product.setdefault(s.product, set()).add(s.name)

    ident = re.compile(r"[A-Za-z_$][\w$]*")
    out: dict[str, dict] = {}
    for array_name in ("TABS", "DETAIL_SCREENS"):
        for entry in _js_array_entries(src, array_name):
            head = re.match(r"\['([^']*)','([^']*)'", entry)
            label = re.match(r"\['([^']*)'", entry)
            if not label:
                continue
            label = label.group(1)
            title = head.group(2) if head else ""

            # 화면 본문 = 항목 원문 + 그 안에서 부르는 최상위 정의의 전개.
            # 객체 리터럴은 실제로 인덱싱한 키만 편다.
            seen: set[tuple[str, str]] = set()
            stack, blob = [entry], [entry]
            while stack:
                cur = stack.pop()
                for name in sorted(set(ident.findall(cur))):
                    if name not in defs:
                        continue
                    kind, body = defs[name]
                    if kind == "object":
                        keys = (re.findall(rf"{re.escape(name)}\[['\"]([\w\-]+)['\"]\]", cur)
                                + re.findall(rf"{re.escape(name)}\.([A-Za-z_]\w*)", cur))
                        for k in sorted(set(keys)):
                            if (name, k) in seen:
                                continue
                            seen.add((name, k))
                            val = _js_object_value(body, k)
                            if val:
                                stack.append(val)
                                blob.append(val)
                        continue
                    if (name, "") in seen:
                        continue
                    seen.add((name, ""))
                    stack.append(body)
                    blob.append(body)
            text = "".join(blob)

            tabs = {lit for lit in re.findall(r"['\"]([A-Za-z][\w\-]*)['\"]", text)
                    if lit in names}
            # 부문 전개는 `domain(root,'PRD-x')` 호출에만 적용한다. 부문 코드가
            # 문자열로 있다는 것만으로 전개하면 부문 차트 하나를 부른 화면이
            # 그 부문 원장 전량을 그리는 것으로 잡힌다.
            for prod in re.findall(r"domain\(\s*\w+\s*,\s*['\"](PRD-[A-Z]+)['\"]", text):
                tabs |= by_product.get(prod, set())
            for key in re.findall(r"D\.([A-Za-z_]\w*)", text):
                tabs |= pkeys.get(key, set())
            for key in re.findall(r"D\[['\"](\w+)['\"]\]", text):
                tabs |= pkeys.get(key, set())

            rec = out.setdefault(label, {"title": title,
                                         "generic": label in GENERIC_SCREENS,
                                         "tables": set()})
            rec["tables"] |= tabs
    return out


# ---------------------------------------------------------------- 조립

def build_lineage(tables: dict[str, pd.DataFrame] | None = None) -> Lineage:
    """소스에서 계보를 뽑는다. `tables` 를 주면 실행 행수가 붙는다."""
    specs = cat.ALL_TABLES
    names = {s.name for s in specs}
    owners = scan_owners(names)
    producers, feeds = scan_dataflow(names)
    screens = scan_screens(names)
    forms = scan_forms(names)

    edges: list[Edge] = list(feeds) + fk_edges(specs)
    for table, funcs in sorted(producers.items()):
        for fn in sorted(funcs):
            edges.append(Edge(fn, table, "produces", fn))
    for label, rec in sorted(screens.items()):
        for t in sorted(rec["tables"]):
            edges.append(Edge(t, label, "renders", label))
    for module, tabs in sorted(forms.items()):
        for t in sorted(tabs):
            edges.append(Edge(t, module, "reports", module))

    rows = ({n: int(len(df)) for n, df in tables.items()
             if isinstance(df, pd.DataFrame)} if tables else {})
    return Lineage(specs=specs, edges=tuple(edges), screens=screens,
                   forms=forms, owners=owners, producers=producers, rows=rows)


# ---------------------------------------------------------------- 고아 판정

VERDICTS = ("편입 대상", "중간산출", "참조용 마스터", "불필요")


@dataclass(frozen=True)
class Judgement:
    verdict: str
    reason: str
    action: str = ""     # '편입 대상' 이면 어디에 어떻게 잇는지


# 전용 화면도 감독서식도 쓰지 않는 원장의 판정 대장.
#
# 새 원장이 배선 없이 늘면 `check_orphans` 가 미등재로 잡는다. 반대로 여기
# 남아 있는데 화면·서식이 생기면 낡은 항목으로 잡는다. 사유 없이 목록만
# 늘리면 통제 기능을 잃고 면제 목록이 된다.
ORPHAN_REGISTRY: dict[str, Judgement] = {
    # 비어 있다. 면제 목록이라서가 아니라 **다 소진해서** 비었다.
    #
    # 여기 있던 31장은 전부 산출은 되는데 전용 화면이 없던 원장이었고, 각
    # 항목이 편입 방법까지 적어 두고 있었다. app.py 에 여덟 화면을 붙여
    # 그대로 실행했다 (변경통제·모형 수명주기·접근통제·AI 거버넌스·
    # 실행감사추적·ICAAP 인벤토리·경영조치제출·조회 거버넌스).
    #
    # 다시 채워야 할 때가 온다. 새 원장을 화면 없이 만들면 check_orphans 가
    # 미등재로 잡고, 그때 사유와 편입 방법을 적어 여기 넣는다. 사유 없이
    # 이름만 넣으면 통제가 아니라 면제가 된다.
}

MAX_UNWIRED = len(ORPHAN_REGISTRY)

# 연결 원장 없이 그리는 화면. 이 저장소의 규약은 화면마다 연결 원장을 두는
# 것이므로 예외는 사유와 함께 여기 적는다.
SCREENS_WITHOUT_LEDGER: dict[str, str] = {
    "상업성": "사업성 산출. 규제 산출물이 아니고 원장 카탈로그에 넣지 않았다. "
              "수치는 risk_lib/commercial.py 의 가정 프레임에서 온다",
    "역스트레스": "역스트레스 결과를 원장으로 만들지 않았다. 화면은 "
                  "PipelineResult.reverse_stress 객체를 payload 로 받아 그린다. "
                  "원장이 없어 정형 조회·감독서식에서 이 결과를 쓸 수 없다",
    "요건 추적": "요건 추적표는 원장이 아니라 코드 선언(req_trace.TRACE)이다. "
                 "증빙 실재는 tests/test_req_trace.py 가 검증한다",
    "기관 설정": "연결 원장은 있다. inst_master·inst_profile·"
                 "inst_portfolio_mix·inst_country_mix·intl_label_lexicon 이며 "
                 "data_gen_intl.build_all() 이 만든다. 다만 그 다섯 장이 아직 "
                 "ALL_TABLES 밖이라 이 계보 그래프의 원장 집합에 없다. "
                 "카탈로그에 등재되면 이 줄을 뺀다",
}


def classify(lin: Lineage) -> pd.DataFrame:
    """미배선 원장에 판정을 붙여 돌려준다. 판정이 없으면 '미분류'."""
    down = lin.downstream()
    spec = lin.spec_by_name
    rows = []
    for name in lin.unwired():
        j = ORPHAN_REGISTRY.get(name)
        s = spec[name]
        rows.append({
            "table": name,
            "korean": s.korean,
            "product": s.product,
            "block": block_of(s),
            "owner": lin.owners.get(name, ""),
            "rows": lin.rows.get(name, None),
            "downstream": ", ".join(sorted(down.get(name, []))) or "",
            "verdict": j.verdict if j else "미분류",
            "reason": j.reason if j else "판정 미기재",
            "action": j.action if j else "",
        })
    return pd.DataFrame(rows)


def check_orphans(lin: Lineage) -> list[str]:
    """배선 통제. 위반 문장 목록을 돌려준다 (빈 목록이면 통과)."""
    v: list[str] = []
    unwired = set(lin.unwired())
    for name in sorted(unwired - set(ORPHAN_REGISTRY)):
        v.append(f"미배선 원장 {name} 이 판정 대장에 없다. "
                 f"ORPHAN_REGISTRY 에 판정과 사유를 적어라")
    for name in sorted(set(ORPHAN_REGISTRY) - unwired):
        v.append(f"판정 대장의 {name} 이 이제 화면·서식에 배선됐다. "
                 f"ORPHAN_REGISTRY 에서 빼라")
    if len(unwired) > MAX_UNWIRED:
        v.append(f"미배선 원장이 {len(unwired)}건으로 상한 {MAX_UNWIRED}건을 넘었다")
    for name, j in sorted(ORPHAN_REGISTRY.items()):
        if j.verdict not in VERDICTS:
            v.append(f"{name}: 알 수 없는 판정 {j.verdict!r}")
        if not j.reason.strip():
            v.append(f"{name}: 사유가 비었다")
        if j.verdict == "편입 대상" and not j.action.strip():
            v.append(f"{name}: 편입 대상인데 편입 방법이 비었다")
    return v


def screens_without_ledger(lin: Lineage) -> list[str]:
    """연결 원장이 없는 전용 화면."""
    return sorted(label for label, rec in lin.screens.items()
                  if not rec["generic"] and not rec["tables"])


def check_screens(lin: Lineage) -> list[str]:
    """화면 배선 통제. 연결 원장 없는 화면은 사유가 있어야 한다."""
    v: list[str] = []
    bare = set(screens_without_ledger(lin))
    for label in sorted(bare - set(SCREENS_WITHOUT_LEDGER)):
        v.append(f"화면 '{label}' 에 연결 원장이 없다. 원장을 잇거나 "
                 f"SCREENS_WITHOUT_LEDGER 에 사유를 적어라")
    for label in sorted(set(SCREENS_WITHOUT_LEDGER) - bare):
        if label not in lin.screens:
            v.append(f"SCREENS_WITHOUT_LEDGER 의 '{label}' 화면이 없어졌다")
        else:
            v.append(f"SCREENS_WITHOUT_LEDGER 의 '{label}' 이 이제 원장에 "
                     f"연결됐다. 목록에서 빼라")
    return v


# ---------------------------------------------------------------- 도표 생성

def _mid(prefix: str, text: str) -> str:
    """mermaid 노드 id. 한글·기호를 쓰면 파서가 깨진다.

    치환문자를 하나로 뭉개면 '신용'과 '시장'이 같은 id가 되어 서로 다른 블록이
    한 노드로 합쳐진다. 코드포인트로 적어 충돌을 없앤다.
    """
    body = "".join(ch if (ch.isascii() and (ch.isalnum() or ch == "_"))
                   else f"x{ord(ch):x}" for ch in text)
    return prefix + body


def _bid(block: str) -> str:
    """블록 노드 id. 순서 색인이라 짧고 안정적이다."""
    return f"B{BLOCK_ORDER.index(block) + 1}" if block in BLOCK_ORDER else "B0"


def _lbl(text: str) -> str:
    return '"' + text.replace('"', "'") + '"'


def mermaid_overview(lin: Lineage) -> str:
    """조감도. 도메인 블록 사이의 흐름만 그린다."""
    spec = lin.spec_by_name
    blocks = {b: 0 for b in BLOCK_ORDER}
    for s in lin.specs:
        blocks[block_of(s)] = blocks.get(block_of(s), 0) + 1

    flow: dict[tuple[str, str], int] = {}
    for e in lin.edges:
        if e.kind not in ("feeds", "fk"):
            continue
        a, b = spec.get(e.src), spec.get(e.dst)
        if a is None or b is None:
            continue
        ba, bb = block_of(a), block_of(b)
        if ba != bb:
            flow[(ba, bb)] = flow.get((ba, bb), 0) + 1

    L = ["flowchart LR"]
    for b in BLOCK_ORDER:
        L.append(f"  {_bid(b)}[{_lbl(f'{b} · 원장 {blocks.get(b, 0)}장')}]")
    for (a, b), n in sorted(flow.items()):
        L.append(f"  {_bid(a)} -->|{n}| {_bid(b)}")
    return "\n".join(L)


def _dedup(lines: list[str]) -> str:
    """같은 간선이 여러 근거로 나온다. 한 번만 그린다."""
    seen, out = set(), []
    for line in lines:
        if "-->" in line or "-.->" in line:
            if line in seen:
                continue
            seen.add(line)
        out.append(line)
    return "\n".join(out)


def domain_tables(lin: Lineage, block: str) -> list[str]:
    return sorted(s.name for s in lin.specs if block_of(s) == block)


def _table_node(lin: Lineage, name: str) -> str:
    n = lin.rows.get(name)
    cap = name if n is None else f"{name} ({n:,}행)"
    return f"    {_mid('T', name)}[{_lbl(cap)}]"


def mermaid_domain_build(lin: Lineage, block: str) -> str:
    """도메인 상세 (1) 산출 모듈에서 원장으로, 그리고 원장 간 의존.

    산출 노드는 모듈 단위로 묶는다. 한 도메인의 생산 함수는 20개가 넘는데
    대부분 같은 모듈에 있어, 함수 단위로 그리면 도표가 읽히지 않는다.
    """
    tabs = domain_tables(lin, block)
    tabset = set(tabs)
    mods: dict[str, set[str]] = {}
    for t in tabs:
        for fn in sorted(lin.producers.get(t, [])):
            mods.setdefault(fn.split("::")[0], set()).add(t)

    L = ["flowchart LR", f"  subgraph S[{_lbl('산출 모듈')}]", "  direction TB"]
    for m in sorted(mods):
        L.append(f"    {_mid('P', m)}[{_lbl(m)}]")
    L.append("  end")
    L.append(f"  subgraph G[{_lbl(block + ' 원장 ' + str(len(tabs)) + '장')}]")
    L.append("  direction TB")
    for t in tabs:
        L.append(_table_node(lin, t))
    L.append("  end")
    for m, outs in sorted(mods.items()):
        for t in sorted(outs):
            L.append(f"  {_mid('P', m)} --> {_mid('T', t)}")
    for e in lin.edges:
        if e.kind in ("feeds", "fk") and e.src in tabset and e.dst in tabset:
            L.append(f"  {_mid('T', e.src)} -.-> {_mid('T', e.dst)}")
    return _dedup(L)


def mermaid_domain_use(lin: Lineage, block: str) -> str:
    """도메인 상세 (2) 원장 → 화면·서식. 쓰이는 원장만 그린다."""
    tabs = domain_tables(lin, block)
    tabset = set(tabs)
    screens = {label: rec["tables"] & tabset
               for label, rec in sorted(lin.screens.items())
               if not rec["generic"] and rec["tables"] & tabset}
    form_mods = sorted(m for m, used in lin.forms.items() if used & tabset)
    used_by_form = (set().union(*(lin.forms[m] for m in form_mods)) & tabset
                    if form_mods else set())
    drawn = sorted(set().union(*screens.values()) | used_by_form) if (
        screens or used_by_form) else []

    L = ["flowchart LR", f"  subgraph G[{_lbl(block + ' 원장')}]", "  direction TB"]
    for t in drawn:
        L.append(_table_node(lin, t))
    L.append("  end")
    L.append(f"  subgraph V[{_lbl('화면·서식')}]")
    L.append("  direction TB")
    for label in sorted(screens):
        L.append(f"    {_mid('V', label)}[{_lbl(label)}]")
    if used_by_form:
        L.append(f"    FORMS[{_lbl(f'감독서식 {len(form_mods)}개 모듈')}]")
    L.append("  end")
    for label, hit in sorted(screens.items()):
        for t in sorted(hit):
            L.append(f"  {_mid('T', t)} --> {_mid('V', label)}")
    for t in sorted(used_by_form):
        L.append(f"  {_mid('T', t)} --> FORMS")
    return _dedup(L)


def mermaid_screens(lin: Lineage) -> str:
    """화면 기준 역방향. 각 화면이 어느 도메인 블록에서 오는지."""
    spec = lin.spec_by_name
    L = ["flowchart RL"]
    for b in BLOCK_ORDER:
        L.append(f"  {_bid(b)}[{_lbl(b)}]")
    pairs: dict[tuple[str, str], int] = {}
    for label, rec in sorted(lin.screens.items()):
        if rec["generic"] or not rec["tables"]:
            continue
        L.append(f"  {_mid('V', label)}({_lbl(label)})")
        for t in sorted(rec["tables"]):
            s = spec.get(t)
            if s is None:
                continue
            key = (label, block_of(s))
            pairs[key] = pairs.get(key, 0) + 1
    for (label, b), n in sorted(pairs.items()):
        L.append(f"  {_mid('V', label)} -.->|{n}| {_bid(b)}")
    return "\n".join(L)


# ---------------------------------------------------------------- 문서 생성

_DOC_HEADER = """# 원장·화면 계보와 산출 흐름도

이 문서는 **생성물이다.** 손으로 고치지 마라. 계보는
`risk_lib/datamodel/lineage.py` 가 소스에서 뽑고, 아래 도표는 그 결과로
그려진다. 코드가 바뀌면 재생성해야 문서가 사실로 남는다.

```
python -m risk_lib.datamodel.lineage
```

행수는 `run_pipeline(generate_portfolio(seed=42), seed=42, asof=…)` 한 번의
실행 결과다. 재생성 시 실행을 붙이지 않으면 행수 칸이 빈다.

계보의 근거는 네 갈래다.

| 갈래 | 뽑는 곳 |
|---|---|
| 원장 → 화면 | `ui_studio/app.py` 의 `TABS`·`DETAIL_SCREENS` 선언, `screenOf({tables:…})`, `D.data['x']`, `domain(r,'PRD-x')` 부문 전개, `_payload` 키 |
| 원장 → 서식 | `regulatory/*.py` 의 `ctx.tables["x"]` |
| 원장 → 원장 | TableSpec 의 FK 선언, 같은 함수가 A를 읽고 B를 쓰는 관계 |
| 산출 → 원장 | 테이블명을 키로 대입하는 함수, TableSpec 을 선언한 모듈 |

정형 조회·비정형 UI·데이터모델·설정 네 화면은 승인 View 전량을 대상으로 하는
범용 조회기라서 "그린다"로 세지 않는다. 이 넷을 세면 모든 원장이 화면에
연결된 것으로 나와 미배선 원장이 사라진다.
"""


def render_doc(lin: Lineage) -> str:
    cls = classify(lin)
    parts = [_DOC_HEADER]

    n_screen = sum(1 for r in lin.screens.values() if not r["generic"])
    parts.append(f"""
## 0. 재고

| 항목 | 수 |
|---|---|
| 카탈로그 원장 | {len(lin.specs)}장 |
| 실체화된 원장 | {len(lin.rows) or '(실행 미첨부)'} |
| 전용 화면 | {n_screen}장 (범용 조회기 {len(GENERIC_SCREENS)}장 별도) |
| 감독서식 모듈 | {len(lin.forms)}개 |
| 전용 화면이 그리는 원장 | {len(lin.rendered())}장 |
| 감독서식이 읽는 원장 | {len(lin.reported())}장 |
| 미배선 원장 (화면·서식 둘 다 없음) | {len(lin.unwired())}장 |
| 그중 하류 원장도 없는 것 | {len(lin.orphans())}장 |
""")

    parts.append("\n## 1. 전체 조감도\n\n"
                 "도메인 블록 사이의 원장 의존만 그린다. 화살표 위 숫자는 그 "
                 "방향으로 이어지는 원장 쌍의 수다.\n\n"
                 "```mermaid\n" + mermaid_overview(lin) + "\n```\n")

    parts.append("\n## 2. 도메인별 상세\n\n"
                 "블록마다 두 장이다. 앞장은 산출 모듈이 원장을 만드는 경로와 "
                 "원장 간 의존(점선), 뒷장은 그 원장을 쓰는 화면·서식이다. "
                 "한 장에 다 넣으면 한 블록이 100노드를 넘어 읽히지 않는다.\n")
    for b in BLOCK_ORDER:
        tabs = domain_tables(lin, b)
        used = sorted(set(tabs) - set(lin.unwired()))
        parts.append(f"\n### 2.{BLOCK_ORDER.index(b) + 1} {b} · 원장 {len(tabs)}장\n")
        parts.append(f"\n산출 모듈 → 원장 (미배선 {len(tabs) - len(used)}장 포함)\n\n")
        parts.append("```mermaid\n" + mermaid_domain_build(lin, b) + "\n```\n")
        parts.append(f"\n원장 → 화면·서식 (쓰이는 {len(used)}장만)\n\n")
        parts.append("```mermaid\n" + mermaid_domain_use(lin, b) + "\n```\n")

    parts.append("\n## 3. 화면 기준 역방향\n\n"
                 "각 전용 화면이 어느 도메인 블록의 원장에서 오는지. 점선 위 "
                 "숫자는 그 블록에서 가져오는 원장 수다.\n\n"
                 "```mermaid\n" + mermaid_screens(lin) + "\n```\n")

    parts.append("\n### 3.1 화면별 원장 목록\n\n| 화면 | 원장 수 | 원장 |\n|---|---|---|\n")
    for label in sorted(lin.screens):
        rec = lin.screens[label]
        if rec["generic"]:
            continue
        tabs = sorted(rec["tables"])
        parts.append(f"| {label} | {len(tabs)} | {', '.join(tabs) or '(없음)'} |\n")

    parts.append("\n## 4. 미배선 원장과 판정\n\n"
                 "전용 화면도 감독서식도 쓰지 않는 원장이다. 판정 대장은 "
                 "`lineage.ORPHAN_REGISTRY` 이고 `tests/test_lineage.py` 가 "
                 "미등재 원장이 생기면 실패시킨다.\n\n")
    if cls.empty:
        parts.append("현재 0장이다. 원장 전부가 전용 화면이나 감독서식에 "
                     "닿는다.\n")
    for verdict in (VERDICTS + ("미분류",)) if not cls.empty else ():
        sub = cls[cls["verdict"] == verdict]
        if sub.empty:
            continue
        parts.append(f"\n### {verdict} · {len(sub)}건\n\n"
                     "| 원장 | 한글명 | 부문 | 행 | 사유 | 편입 방법 |\n|---|---|---|---|---|---|\n")
        for _, r in sub.iterrows():
            n = "" if pd.isna(r["rows"]) else f"{int(r['rows']):,}"
            parts.append(f"| {r['table']} | {r['korean']} | {r['product']} | {n} | "
                         f"{r['reason']} | {r['action'] or '-'} |\n")

    parts.append("\n## 5. 산출 단계별 입출력\n\n"
                 "`pipeline.py` 의 스테이지 함수가 원장명을 문자열로 다루는 "
                 "부분만 나온다. 스테이지가 DataFrame 을 인자로 주고받는 구간은 "
                 "여기 잡히지 않는다.\n\n"
                 "| 스테이지 | 쓰는 원장 | 읽는 원장 |\n|---|---|---|\n")
    for fn, io in sorted(stage_io().items()):
        parts.append(f"| `{fn}` | {', '.join(sorted(io['writes'])) or '-'} | "
                     f"{', '.join(sorted(io['reads'])) or '-'} |\n")

    parts.append("\n## 6. 감독서식이 읽는 원장\n\n| 서식 모듈 | 원장 |\n|---|---|\n")
    for module in sorted(lin.forms):
        parts.append(f"| {module} | {', '.join(sorted(lin.forms[module]))} |\n")

    parts.append("\n## 7. 연결 원장이 없는 화면\n\n"
                 "이 저장소의 규약은 화면마다 연결 원장을 두는 것이다. 아래 "
                 "화면은 원장이 아니라 산출 객체나 코드 선언에서 값을 받는다. "
                 "`tests/test_lineage.py` 가 목록이 늘면 실패시킨다.\n\n"
                 "| 화면 | 사유 |\n|---|---|\n")
    for label in screens_without_ledger(lin):
        parts.append(f"| {label} | {SCREENS_WITHOUT_LEDGER.get(label, '사유 미기재')} |\n")

    n_pages, page_refs = ops_page_ledgers()
    parts.append(f"""
### 7.1 보고서 페이지 세트

`page_registry.PAGES` 의 보고서 페이지 {n_pages}장은 원장이 아니라
`PipelineResult` 객체를 직접 읽어 그린다. 페이지 모듈이 이름으로 부르는 원장은
{len(page_refs)}장({', '.join(sorted(page_refs)) or '없음'})뿐이라 위 계보에
거의 잡히지 않는다. 같은 수치를 정형 조회나 감독서식에서 원장으로 다시 집을 수
없다는 뜻이다.
""")
    return "".join(parts)


def write_doc(path: str | Path | None = None,
              tables: dict[str, pd.DataFrame] | None = None) -> Path:
    path = Path(path) if path else (_ROOT / "docs" / "DATA_FLOW.md")
    lin = build_lineage(tables)
    path.write_text(render_doc(lin), encoding="utf-8")
    return path


def _run_tables() -> dict[str, pd.DataFrame]:
    """행수를 붙이기 위한 기준 실행. 기준일·시드를 고정한다."""
    from risk_lib.data_gen import generate_portfolio
    from risk_lib.pipeline import run_pipeline
    from risk_lib.ui_studio.studio import build_studio
    p = generate_portfolio(seed=42)
    return build_studio(run_pipeline(p, seed=42, asof=DOC_ASOF), p).tables


# 문서에 실리는 행수의 기준일. 벽시계를 쓰면 재생성마다 문서가 바뀐다.
DOC_ASOF = "2026-06-11"


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="원장·화면 계보 문서 재생성")
    ap.add_argument("path", nargs="?", default=None)
    ap.add_argument("--no-run", action="store_true",
                    help="파이프라인을 돌리지 않는다 (행수 칸이 빈다)")
    a = ap.parse_args(argv)
    tables = None if a.no_run else _run_tables()
    lin = build_lineage(tables)
    out = write_doc(a.path, tables)
    print(f"{out} 생성. 원장 {len(lin.specs)}장 · 미배선 {len(lin.unwired())}장")
    for v in check_orphans(lin):
        print("  위반:", v)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
