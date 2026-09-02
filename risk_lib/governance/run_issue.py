"""실행 통제 단계가 낸 이슈 원장 (검수 2단계).

마감 워크플로의 차단·순서위반, 감사체인의 수집 기록, 보존의 폐기 건너뜀,
통합 실행의 문제 목록은 각 빌더가 두 번째 반환값으로 돌려주는데,
`materialize_run_control` 이 전부 `_issues` 처럼 버렸다. 계산은 됐고 어디에도
실리지 않았다. 순서위반이 나도 산출물에 흔적이 없었다.

이 원장이 그 네 목록을 싣는다. 비어 있으면 "이슈 없음" 이고, 원장이 없으면
"수집하지 않았다" 다. 둘은 다른 뜻이라 원장 자체는 항상 만든다.
"""

from __future__ import annotations

import pandas as pd

from risk_lib.datamodel.spec import ColumnSpec as C, TableSpec

STAGES = ("마감", "감사체인", "보존", "통합실행")
KINDS = ("차단", "순서위반", "기록", "건너뜀", "문제")

RUN_ISSUE = TableSpec(
    name="gov_run_issue", korean="실행 통제 이슈", product="PRD-VAL",
    grain="기준일 × 단계 × 일련번호 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("run_id", "string", "실행 식별자", nullable=False),
        C("stage", "string", "단계", nullable=False, allowed=STAGES),
        C("seq", "int", "일련번호", nullable=False, unit="count", min_value=1),
        C("kind", "string", "성격", nullable=False, allowed=KINDS),
        C("detail", "text", "내용", nullable=False),
    ),
    primary_key=("asof", "stage", "seq"),
    note="각 단계 빌더의 두 번째 반환값. 버려지던 목록이라 비어 있어도 원장은 만든다.",
)
SPECS: tuple[TableSpec, ...] = (RUN_ISSUE,)


def _kind_of(stage: str, text: str) -> str:
    if stage == "마감":
        return "순서위반" if "순서위반" in text else "차단"
    if stage == "감사체인":
        return "기록"
    if stage == "보존":
        return "건너뜀"
    return "문제"


def build_run_issue(*, asof: str, run_id: str,
                    close_issues: list[str], chain_notes: list[str],
                    retention_skipped: list[str], run_problems: list[str]
                    ) -> pd.DataFrame:
    rows = []
    for stage, items in (("마감", close_issues), ("감사체인", chain_notes),
                         ("보존", retention_skipped), ("통합실행", run_problems)):
        for i, text in enumerate(items or [], start=1):
            rows.append({"asof": asof, "run_id": run_id, "stage": stage,
                         "seq": i, "kind": _kind_of(stage, str(text)),
                         "detail": str(text)})
    return pd.DataFrame(rows, columns=[c.name for c in RUN_ISSUE.columns])
