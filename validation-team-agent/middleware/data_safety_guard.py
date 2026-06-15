"""민감정보 패턴 탐지.

주민등록번호, 계좌번호, 전화번호, 이메일 등 식별·금융 민감정보 패턴을 텍스트 또는
DataFrame 컬럼에서 탐지한다. 탐지 시 호출자는 출력·저장을 즉시 중단해야 한다.
본 모듈은 자동으로 데이터를 수정하거나 삭제하지 않는다.

PII 비유출 원칙:
- 매칭된 원문(raw substring) 또는 부분 마스킹된 원문은 절대 반환하지 않는다.
- ``scan_text``는 위치(span)·길이·카테고리만 반환한다.
- ``scan_dataframe``은 카테고리별 row/column 메타데이터와 per-run salt 가 적용된
  SHA-256 해시만 반환한다. salt 는 기본적으로 프로세스 시작 시 1회 생성되어
  로그·파일 간 교차 매칭을 방지한다. 동일 입력의 결정적 해시가 필요한 경우
  ``salt`` 인자를 명시적으로 전달한다.
"""

from __future__ import annotations

import hashlib
import os
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


# per-run salt: 프로세스 시작 시 한 번 생성된다. 동일 프로세스 내 호출 간에는
# 동일한 입력이 동일 해시를 갖지만, 프로세스/세션이 달라지면 해시가 달라져
# 로그/감사기록 간 PII cross-linking 위험을 줄인다.
_RUN_SALT: bytes = os.urandom(16)


def _hash_match(raw: str, salt: bytes | None = None) -> str:
    """매칭된 원문을 salted SHA-256 으로 해시한다. 원문은 반환·저장하지 않는다."""
    s = salt if salt is not None else _RUN_SALT
    h = hashlib.sha256()
    h.update(s)
    h.update(raw.encode("utf-8"))
    return h.hexdigest()


def scan_text(text: str) -> List[dict]:
    """텍스트에서 민감정보 패턴을 탐지한다.

    각 finding 은 {category, span, length} 만 포함한다. 원문 매칭값은
    어떠한 형태로도 반환하지 않는다(부분 마스킹 포함).
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    findings: List[dict] = []
    for name, pat in _PATTERNS.items():
        for m in pat.finditer(text):
            findings.append(
                {
                    "category": name,
                    "span": [m.start(), m.end()],
                    "length": m.end() - m.start(),
                }
            )
    return findings


def scan_dataframe(
    df: pd.DataFrame,
    text_columns: Iterable[str] | None = None,
    salt: bytes | None = None,
) -> dict:
    """DataFrame 에서 민감정보 패턴을 탐지한다.

    text_columns 가 None 이면 object dtype 컬럼만 대상으로 한다.
    반환 dict 키:
        clean (bool), findings (list of {row, column, category, length, hash})

    원문 또는 부분 마스킹된 매칭값은 절대 포함하지 않는다. ``hash`` 는
    per-run salt 가 적용된 SHA-256 hex digest 로, 동일 프로세스 내 중복
    탐지 식별에만 사용한다.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")
    if text_columns is None:
        text_columns = df.select_dtypes(include=["object", "string"]).columns.tolist()
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
                    raw = m.group(0)
                    findings.append(
                        {
                            "row": int(idx) if isinstance(idx, (int, float)) else idx,
                            "column": col,
                            "category": name,
                            "length": len(raw),
                            "hash": _hash_match(raw, salt=salt),
                        }
                    )
    return {"clean": len(findings) == 0, "findings": findings}
