"""업무보고서 서식의 공용 자료구조 — 라인·검증·유틸.

빌더 모듈(`forms_*.py`)이 `forms.py`를 import하면 순환이 된다(서식 등록이
forms.py에 있으므로). 자료구조만 여기 두어 어느 쪽에서든 안전하게 쓴다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

from risk_lib.regulatory.form_ids import FormId, form_id, section_of


# ---------------------------------------------------------------- 자료 구조

@dataclass(frozen=True)
class FormLine:
    line_code: str
    line_name: str
    level: int = 0
    unit: str = "KRW"          # KRW · ratio · count · text
    value: float | None = None
    text_value: str | None = None
    formula: str | None = None
    citation: str | None = None
    source_module: str | None = None
    is_subtotal: bool = False
    # 산출 근거를 라인이 스스로 밝힐 때 쓴다. 비워 두면 provenance가 formula·
    # text_value에서 규칙으로 추론한다 — 추론이 애매한 라인만 명시하면 된다.
    basis: str | None = None


@dataclass(frozen=True)
class FormCheck:
    check_name: str
    expected: float
    actual: float
    tolerance: float = 1.0     # KRW 단위 서식은 원 단위 반올림 오차를 허용

    @property
    def diff(self) -> float:
        return self.actual - self.expected

    @property
    def status(self) -> str:
        return "PASS" if abs(self.diff) <= self.tolerance else "FAIL"


@dataclass(frozen=True)
class FormSpec:
    form_id: str
    form_name: str
    frequency: str             # 월 · 분기 · 반기 · 연
    citation: str
    sheet_order: int
    source_domain: str
    builder: Callable

    @property
    def form_no(self) -> "FormId":
        """업무보고서 서식번호 — 공식 번호가 없으면 내부 코드를 쓴다."""
        return form_id(self.form_id)

    @property
    def form_no_display(self) -> str:
        return self.form_no.display()

    @property
    def section(self) -> str:
        """감독규정 편제 — 목차·UI가 이 순서로 묶는다."""
        return section_of(self.form_id)


@dataclass
class BuiltForm:
    spec: FormSpec
    lines: list[FormLine]
    checks: list[FormCheck] = field(default_factory=list)

    @property
    def n_failed(self) -> int:
        return sum(1 for c in self.checks if c.status == "FAIL")


# ---------------------------------------------------------------- 유틸

def _val(lines: list[FormLine], code: str) -> float:
    for ln in lines:
        if ln.line_code == code:
            return float(ln.value or 0.0)
    raise KeyError(f"라인 없음: {code}")


def _sum_check(name: str, lines: list[FormLine], parent: str,
               children: tuple[str, ...], tol: float = 1.0) -> FormCheck:
    """소계 = 구성요소 합. 서식이 스스로 대사하지 못하면 제출 전에 틀린 걸 못 찾는다."""
    return FormCheck(name, _val(lines, parent),
                     sum(_val(lines, c) for c in children), tol)


def _ratio_check(name: str, lines: list[FormLine], ratio: str,
                 num: str, den: str, tol: float = 1e-9) -> FormCheck:
    d = _val(lines, den)
    expected = _val(lines, num) / d if d else 0.0
    return FormCheck(name, expected, _val(lines, ratio), tol)


