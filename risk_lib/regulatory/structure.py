"""서식 구조 키 — 라인이 조용히 사라지는 것을 잡기 위한 표현.

`tests/test_form_structure.py`가 쓰던 것을 여기로 옮겼다. 테스트 안에만 두면
**통제의 한계를 요청서에 실을 수 없다** — 실제로 그랬다. docstring에 "요청서에
공시한다"고 적어 놓고 요청 패키지의 가정은 직전 회차와 집합이 완전히 동일했다
(독립검증 지적 F-B01). 산출 쪽에서 부를 수 있어야 생성해서 실을 수 있다.

## 왜 이런 키인가

라인명이 날짜를 담는 서식(B2316 일별 트레이딩·B2602-2 일별 LCR 등)은 기준일이
바뀌면 이름도 개수도 달라진다. 시험 고정일에서 만든 기준선을 제출 실행에 돌리면
어떤 기준일에서도 실패해, 통제가 제출물을 덮지 못한다 (지적 F-A01).

그래서 날짜를 `<date>`로 바꾸고 그 결과 같아진 연속 라인을 하나로 접는다. 월별
영업일 수가 달라 개수까지 맞출 수는 없기 때문이다.

**그 절충의 값이 곧 사각이다** — 접힌 계열 안에서 라인 하나가 사라져도 키 집합은
그대로라 통과한다. `coverage()`가 그 크기를 재고 `coverage_sentence()`가 문장을
만든다. 한계를 아는 사람과 모르는 사람이 갈리지 않게 하려는 것이다.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# 라인명에 박힌 날짜·분기 표기.
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}|\d{1,2}월\s*\d{1,2}일|\d{4}Q[1-4]")

BASELINE_PATH = (Path(__file__).resolve().parents[2]
                 / "tests" / "form_structure_baseline.json")


def structure_keys(built: list) -> dict[str, list[str]]:
    """서식 → 라인 키 목록. 값은 담지 않고 기준일에 독립이다."""
    out: dict[str, list[str]] = {}
    for b in built:
        keys: list[str] = []
        for ln in b.lines:
            k = _DATE.sub("<date>", f"{ln.line_code}|{ln.line_name}")
            name = k.split("|", 1)[1] if "|" in k else k
            if "<date>" in name:
                # 코드에도 연번이 붙으므로 이름만으로 접는다.
                k = f"<daily>|{name}"
            if keys and keys[-1] == k:
                continue
            keys.append(k)
        out[b.spec.form_id] = keys
    return out


def coverage(built: list, baseline_path: Path | None = None) -> dict:
    """구조 통제가 실제로 덮는 범위 — 접힌 계열이 만드는 사각을 잰다."""
    path = Path(baseline_path or BASELINE_PATH)
    now = structure_keys(built)
    n_now = sum(len(v) for v in now.values())
    n_lines = sum(len(b.lines) for b in built)
    folded = n_lines - n_now          # 접혀서 개별로는 안 보이는 라인 수
    if not path.exists():
        return {"n_lines": n_lines, "n_keys": n_now, "n_folded": folded,
                "n_baseline_keys": 0, "key_gap": 0}
    base = json.loads(path.read_text(encoding="utf-8"))
    n_base = sum(len(v) for v in base.values())
    return {
        "n_lines": n_lines,
        "n_keys": n_now,
        "n_folded": folded,
        "n_baseline_keys": n_base,
        "key_gap": n_now - n_base,
    }


def coverage_sentence(built: list, baseline_path: Path | None = None) -> str:
    """요청서에 실을 한 문장 — 손으로 적지 않는다 (지적 F-501·F-603·F-B01)."""
    c = coverage(built, baseline_path)
    return (
        f"서식 구조 회귀 통제는 라인 {c['n_lines']:,}건을 키 {c['n_keys']:,}종으로 "
        f"보며, 라인명에 날짜가 박힌 일별 계열을 접느라 {c['n_folded']:,}건이 "
        f"개별로 보이지 않는다. 기준선은 시험 고정일에서 만들어 "
        f"{c['n_baseline_keys']:,}키이고 제출 실행과 {c['key_gap']:+,}키 차이가 "
        f"나는데, 판정이 **집합 포함**이라 이 차이가 흡수된다 — 즉 **접힌 계열 "
        f"안에서 라인이 사라져도 통과한다**. 월별 영업일 수가 달라 개수를 고정할 "
        f"수 없어 택한 절충이며, 손으로 쓴 라인 소실(지적 F-901의 실제 양상)은 "
        f"잡는다 (지적 F-A01 · F-B01)."
    )
