"""도전 대상 가정이 약속한 것이 실재하는가.

시정이 만든 **새 주장**이 사실과 어긋난 것이 세 번 반복됐다.

    F-B01  "요청서에 공시한다"고 적고 공시하지 않음
    F-C01  그 공시가 요청 식별자의 재현성을 깨뜨림
    F-D01  "산출물 Pack에 남긴다"고 적고 남기지 않음 (호출부 0건)

세 번 모두 값이 아니라 **약속**이 틀렸다. 값은 생성으로 옮겨 막았는데(F-501),
약속은 여전히 산문이라 아무도 대조하지 않았다.

이 검사는 가정 문장에서 **파일 경로**를 뽑아 그 파일이 산출물 Pack에 실제로
만들어지는지 본다. 좁은 검사다 — 문장이 약속하는 모든 것을 검증할 수는 없다.
그러나 세 번 중 두 번(F-B01·F-D01)이 "어디에 무엇이 있다"는 형태였으므로,
그 형태만이라도 기계가 묻게 한다.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

import pytest

from risk_lib.validation.independent import build_request

# 가정 문장에 나오는 산출물 경로. `05_regulatory/이름.csv` 꼴만 본다.
_ARTEFACT = re.compile(r"`?(\d\d_[\w가-힣]+)/([\w가-힣_]+\.(?:csv|xlsx|md|html))`?")


@pytest.fixture(scope="module")
def pack(result, portfolio):
    from risk_lib.deliverables import build_deliverables
    with tempfile.TemporaryDirectory() as d:
        root = Path(d) / "pack"
        build_deliverables(result, portfolio, root)
        yield {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}


def test_assumptions_do_not_promise_missing_artefacts(result, portfolio, pack):
    """가정이 "여기 있다"고 적은 파일은 실제로 있어야 한다."""
    from risk_lib.ui_studio.studio import build_studio
    studio = build_studio(result, portfolio)
    promised: list[str] = []
    for a in studio.iv_request.known_assumptions:
        for d, name in _ARTEFACT.findall(a):
            promised.append(f"{d}/{name}")
    assert promised, "가정이 산출물 경로를 하나도 약속하지 않는다 — 검사가 헛돈다"
    missing = sorted({p for p in promised if p not in pack})
    assert not missing, (
        f"가정이 약속한 산출물 {len(missing)}건이 Pack에 없다 — 지적 F-D01과 "
        f"같은 유형이다:\n  " + "\n  ".join(missing))


def test_every_generated_sentence_helper_is_wired(result, portfolio):
    """`coverage_*` 생성 함수가 정의만 되고 아무도 부르지 않는 상태를 막는다.

    F-D01의 실제 원인이 그것이었다 — `coverage_report()`가 정의만 있고 호출부가
    저장소 전체에 0건이었다. 정의는 통제가 아니다.
    """
    import subprocess
    out = subprocess.run(
        ["grep", "-rn", "coverage_report\\|coverage_sentence",
         "--include=*.py", "risk_lib", "tests"],
        capture_output=True, text=True).stdout
    for fn in ("coverage_report", "coverage_sentence"):
        defs = [l for l in out.splitlines() if f"def {fn}" in l]
        uses = [l for l in out.splitlines()
                if fn in l and f"def {fn}" not in l and "import" not in l]
        assert defs, f"{fn} 정의를 찾지 못했다 — 검사가 헛돈다"
        assert uses, f"{fn}이 정의만 있고 호출부가 없다 (지적 F-D01)"
