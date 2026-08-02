"""코드 마스터 — 카탈로그 `allowed` 선언에서 생성한다 (rdm_code_master).

등급(AAA→UNRATED)·건전성 분류(정상→추정손실)·조기경보 단계(관찰→경보) 같은
코드는 **선언 순서가 곧 업무 순서**다. 화면이 가나다순으로 정렬하면 등급
사다리가 뒤섞인다 — 실제로 그렇게 표시된 것이 지적됐다.

손으로 적지 않는다. 카탈로그 스펙의 allowed 튜플을 그대로 옮기므로, 스펙이
바뀌면 마스터도 따라온다. 같은 컬럼명이 테이블마다 다른 코드셋을 가지면
(status·severity 등 9종) `table.column`으로 한정해 서로 섞이지 않게 한다.
"""

from __future__ import annotations

import pandas as pd

from risk_lib.datamodel import catalog as cat


def build_code_master() -> pd.DataFrame:
    # 컬럼명별 allowed 집합 — 충돌 여부 판정
    by_name: dict[str, set[tuple]] = {}
    for sp in cat.ALL_TABLES:
        for c in sp.columns:
            if c.allowed:
                by_name.setdefault(c.name, set()).add(tuple(c.allowed))
    conflicted = {k for k, v in by_name.items() if len(v) > 1}

    rows, seen = [], set()
    for sp in cat.ALL_TABLES:
        for c in sp.columns:
            if not c.allowed:
                continue
            key = f"{sp.name}.{c.name}" if c.name in conflicted else c.name
            if key in seen:
                continue
            seen.add(key)
            for i, code in enumerate(c.allowed):
                rows.append({"code_set": key, "code": str(code),
                             "sort_order": i, "source_table": sp.name})
    return pd.DataFrame(rows, columns=[
        "code_set", "code", "sort_order", "source_table"])
