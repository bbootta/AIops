"""민감정보 패턴 탐지.

주민등록번호, 계좌번호, 전화번호, 이메일 등 식별·금융 민감정보 패턴을 텍스트 또는
DataFrame 컬럼에서 탐지한다. 탐지 시 호출자는 출력·저장을 즉시 중단해야 한다.
본 모듈은 자동으로 데이터를 수정하거나 삭제하지 않는다.
"""

from __future__ import annotations

import re
from typing import Iterable, List

import pandas as pd


_PATTERNS = {
    # 단순 패턴 (정밀 검증 아님). false positive 가능성을 가정한다.
    "rrn_kr": re.compile(r"\b\d{6}[-\s]?[1-4]\d{6}\b"),
    "phone_kr": re.compile(r"\b01[016789][-\s]?\d{3,4}[-\s]?\d{4}\b"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "card_number": re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
    "account_number": re.compile(r"\b\d{2,6}-\d{2,6}-\d{2,7}\b"),
}


def scan_text(text: str) -> List[dict]:
    """텍스트에서 민감정보 패턴을 탐지한다."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    findings: List[dict] = []
    for name, pat in _PATTERNS.items():
        for m in pat.finditer(text):
            findings.append({"category": name, "matched": m.group(0)})
    return findings


def scan_dataframe(
    df: pd.DataFrame, text_columns: Iterable[str] | None = None
) -> dict:
    """DataFrame에서 민감정보 패턴을 탐지한다.

    text_columns가 None이면 object dtype 컬럼만 대상으로 한다.
    반환 dict 키: clean, findings (행 인덱스, 컬럼명, 카테고리, 매치 일부)
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")
    if text_columns is None:
        text_columns = df.select_dtypes(include="object").columns.tolist()
    else:
        text_columns = list(text_columns)
        missing = [c for c in text_columns if c not in df.columns]
        if missing:
            raise KeyError(f"columns missing: {missing}")

    findings: List[dict] = []
    for col in text_columns:
        series = df[col].astype(str).fillna("")
        for idx, val in series.items():
            for name, pat in _PATTERNS.items():
                m = pat.search(val)
                if m:
                    findings.append(
                        {
                            "row": int(idx) if isinstance(idx, (int, float)) else idx,
                            "column": col,
                            "category": name,
                            "matched_sample": m.group(0)[:6] + "***",
                        }
                    )
    return {"clean": len(findings) == 0, "findings": findings}
