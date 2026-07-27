"""문서에 적힌 수치를 코드 사실과 대조한다 — 손으로 옮겨 적은 값을 기계가 잡는다.

문서–산출 불일치가 네 번 재발했다 (F-103 역스트레스 심도 · F-201 자본의 파생
성격 · F-401 · F-501 라인 수·실측 비중). F-501은 `asof=2026-06-11`(테스트
고정일) 실행의 출력을 `asof=2026-06-30` 제출본의 설명으로 옮겨 적은 것이다 —
산출값 오류가 아니라 **문서가 다른 실행을 설명한** 것이며, 문서를 2차 인용하는
검토자·결재선이 잘못된 근거로 판단하게 된다. 매번 "다음엔 확인하겠다"로
끝났으므로 사람의 주의력이 아니라 체크가 막아야 한다.

## 왜 '표시된 구간만' 대조하는가

문서의 모든 숫자를 훑어 산출과 대조하면 **거짓 경보가 쏟아진다**. 시정 문서는
회차별 절이 누적되는 기록이고 1~5차 절의 숫자는 그 시점에 옳았다. 과거 기록을
현재 산출과 대조하면 전부 불일치로 나오며, 그렇게 시끄러운 체크는 몇 주 만에
무시된다 — 무시되는 체크는 없는 체크와 같다.

그래서 대조 대상을 문서가 **명시적으로 표시**한다.

    <!-- generated: provenance -->
    (이 구간은 코드가 만든 정본이다 — 손으로 고치지 않는다)
    <!-- /generated -->

체크는 표시된 구간만 재생성해 글자 단위로 비교하고 표시 밖은 읽지도 않는다.
과거 회차 기록에는 거짓 경보가 원리적으로 생기지 않고, 표시된 구간은 손으로
고칠 수 없다 — 고치면 다음 실행에서 FAIL이다.

이 규약 자체를 **설명하는** 코드 표기(``` 펜스 · `인라인`) 안의 표시자는 예시일
뿐이므로 세지 않는다. 시정 문서는 통제를 서술하는 문서라 예시가 실릴 수밖에
없고, 그것을 실제 구간으로 오인하면 정본이 최신인데도 FAIL이 풀리지 않는다.

표시를 지워 침묵시킬 수도 없다. 정본이 있는 이름이 문서에 없으면 FAIL이고
(검사 대상이 사라진 것과 일치하는 것은 다르다), 닫히지 않은 표시자와 정본이
없는 이름도 FAIL이다.

`fill_blocks`가 정본을 문서에 써 넣는다. 대조만 있고 갱신 수단이 없으면 사람이
FAIL 메시지를 보고 값을 다시 손으로 옮겨 적게 되는데, 그것이 애초의 원인이다.

## 자체검증(2선) 통합

`consistency.run_consistency_checks`에 서식 빌드 결과와 기준일을 넘겨 호출한다.

    from risk_lib.validation.doc_figures import REMEDIATION_DOC, check_doc_figures
    for c in check_doc_figures(REMEDIATION_DOC, built_forms, asof):
        rep.add(c)

서식을 빌드하지 않은 실행에서는 `built_forms`가 없으므로 빈 목록이 되어 체크가
붙지 않는다 (입력이 없으면 관련 체크를 건너뛰는 이 모듈의 규약과 같다).
"""

from __future__ import annotations

import re
from pathlib import Path

from risk_lib.regulatory.provenance import (
    provenance_report_md, provenance_sentence, provenance_stats,
)
from risk_lib.validation.consistency import ConsistencyCheck

# 대조 대상 문서. 회차별 절이 누적되므로 표시된 구간만 본다.
REMEDIATION_DOC = Path("docs/independent_validation/RUN-20260630-42.remediation.md")

_BLOCK_RE = re.compile(
    r"<!--\s*generated:\s*(?P<name>[A-Za-z0-9_]+)\s*-->"
    r"(?P<body>.*?)"
    r"<!--\s*/generated\s*-->",
    re.DOTALL,
)
_OPEN_RE = re.compile(r"<!--\s*generated:")

# 문서가 이 표시자 규약을 **설명**할 때 쓰는 코드 표기(``` 펜스 · `인라인`)는
# 대조 대상이 아니다. 시정 문서는 통제를 서술하는 문서이므로 표시자 문구가
# 예시로 실릴 수밖에 없는데, 그 예시를 실제 구간으로 오인하면 정본이 최신인데도
# 영구 FAIL이 난다 — 그런 체크는 곧 꺼지고, 꺼진 체크는 없는 체크와 같다.
# 가림은 길이를 보존하므로 본문은 원문에서 그대로 잘라 쓴다. 가림이 할 수 있는
# 일은 구간을 **덜 찾는** 것뿐이고, 정본이 있는 이름이 안 보이면 FAIL이므로
# 이 완화로 침묵이 생기지는 않는다 (코드 표기 안에 진짜 구간을 숨기면 FAIL이다).
_CODE_RE = re.compile(r"^```.*?^```|`[^`\n]*`", re.DOTALL | re.MULTILINE)


# 대조 대상 문서. 생성 구간을 가진 문서는 전부 여기 등록한다 — 등록하지 않으면
# 아무도 대조하지 않고, 그게 F-501이 살아남은 방식이다.
DOC_TARGETS: tuple[str, ...] = (
    "docs/independent_validation/RUN-20260630-42.remediation.md",
)


def _mask_code(text: str) -> str:
    return _CODE_RE.sub(
        lambda m: m.group(0).replace("<", "\x00").replace(">", "\x01"), text)


# ---------------------------------------------------------------- 정본 생성

def generated_blocks(built: list, asof: str) -> dict[str, str]:
    """문서에 실릴 정본 — 코드 사실에서만 만든다.

    렌더는 소유하지 않는다. 문서를 채우는 함수와 대조하는 함수가 각자 표를
    그리면 숫자가 같아도 서식 차이만으로 영구 FAIL이 나고, 그런 체크는 곧
    무시된다. 그래서 산출 모듈의 렌더러(`provenance_report_md`)를 그대로 쓴다 —
    이 모듈이 하는 일은 "같은 함수의 출력과 문서가 같은가"뿐이다.

    이름은 문서의 표시자와 같아야 한다. 새 생성 구간을 늘리려면 여기에 항목을
    더한다 — 문서에만 표시를 달면 '정본 없는 이름'으로 FAIL이 난다.
    """
    stats = provenance_stats(built)
    return {
        "provenance": provenance_report_md(stats, asof),
        # F-501이 실제로 틀렸던 것은 표가 아니라 **산문 문장**이었다. 표만
        # 대조하면 같은 통계의 문장 형태가 그대로 낡는다 — 정본 렌더러가 이미
        # 있는데 등록하지 않으면 통제 밖이다.
        "provenance_sentence": provenance_sentence(stats),
    }


# ---------------------------------------------------------------- 대조

def _first_diff(actual: str, expected: str) -> str:
    a, e = actual.strip().splitlines(), expected.strip().splitlines()
    for i in range(max(len(a), len(e))):
        av = a[i].strip() if i < len(a) else "(없음)"
        ev = e[i].strip() if i < len(e) else "(없음)"
        if av != ev:
            return f"{i + 1}행 — 문서 「{av}」 ≠ 코드 「{ev}」"
    return "행 구성은 같으나 공백이 다르다"


def check_blocks(doc_path: str | Path,
                 blocks: dict[str, str]) -> list[ConsistencyCheck]:
    """표시된 생성 구간을 정본과 대조한다."""
    path = Path(doc_path)
    if not path.exists():
        return [ConsistencyCheck("doc_figures_target", "FAIL",
                                 f"대조할 문서가 없다: {path}")]
    text = path.read_text(encoding="utf-8")
    masked = _mask_code(text)

    found: dict[str, list[str]] = {}
    for m in _BLOCK_RE.finditer(masked):
        found.setdefault(m.group("name"), []).append(
            text[m.start("body"):m.end("body")])

    out: list[ConsistencyCheck] = []
    n_open = len(_OPEN_RE.findall(masked))
    n_closed = sum(len(v) for v in found.values())
    if n_open != n_closed:
        # 이름을 둘로 나눈 이유는 _check_ead_positive와 같다 — 같은 이름으로 두 번
        # 등록하면 이름으로 조회할 때 한쪽이 조용히 가려진다.
        out.append(ConsistencyCheck(
            "doc_figures_marker_closed", "FAIL",
            f"닫히지 않은 생성 구간 {n_open - n_closed}개 — "
            f"표시자가 깨지면 그 구간이 대조에서 조용히 빠진다",
            metric=float(n_open - n_closed)))
    unknown = sorted(set(found) - set(blocks))
    if unknown:
        out.append(ConsistencyCheck(
            "doc_figures_marker_known", "FAIL",
            f"정본이 없는 생성 구간: {', '.join(unknown)} — "
            f"generated_blocks에 없으면 아무도 대조하지 않는다",
            metric=float(len(unknown))))

    for name, canonical in sorted(blocks.items()):
        check = f"doc_figures_{name}"
        bodies = found.get(name, [])
        if not bodies:
            out.append(ConsistencyCheck(
                check, "FAIL",
                f"{path.name}에 '{name}' 생성 구간이 없다 — "
                f"검사 대상이 사라진 것은 일치가 아니다"))
            continue
        stale = [b for b in bodies if b.strip() != canonical.strip()]
        if stale:
            out.append(ConsistencyCheck(
                check, "FAIL",
                f"문서의 '{name}' 구간이 산출과 다르다 ({len(stale)}/{len(bodies)}곳) "
                f"— {_first_diff(stale[0], canonical)}",
                metric=float(len(stale))))
        else:
            out.append(ConsistencyCheck(
                check, "PASS",
                f"문서의 '{name}' 구간이 현재 산출과 일치 ({len(bodies)}곳)"))
    return out


def check_doc_figures(doc_path: str | Path, built: list | None,
                      asof: str) -> list[ConsistencyCheck]:
    """자체검증에서 부르는 진입점 — 서식을 빌드한 실행에서만 붙는다."""
    if not built:
        return []
    return check_blocks(doc_path, generated_blocks(built, asof))


# ---------------------------------------------------------------- 갱신

def fill_blocks(text: str, blocks: dict[str, str]) -> str:
    """표시된 구간의 내용을 정본으로 바꾼다 — 표시 밖은 건드리지 않는다.

    대조와 같은 눈으로 읽는다. 규약을 설명하는 코드 표기 안의 예시를 갱신이
    정본으로 덮어써 버리면 설명이 망가지고, 대조가 보지 않는 곳을 갱신만
    건드리게 된다.
    """
    out, end = [], 0
    for m in _BLOCK_RE.finditer(_mask_code(text)):
        name = m.group("name")
        if name not in blocks:
            continue
        out.append(text[end:m.start()])
        out.append(f"<!-- generated: {name} -->\n{blocks[name].strip()}\n"
                   f"<!-- /generated -->")
        end = m.end()
    out.append(text[end:])
    return "".join(out)
