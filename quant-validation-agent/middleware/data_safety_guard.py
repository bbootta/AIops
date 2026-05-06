"""Data safety guard for personal information patterns.

Detects (best-effort) common Korean PII formats. This is a heuristic guard,
not a comprehensive scanner. The agent must treat any detection as a hard stop.
"""
from __future__ import annotations

import re
from typing import List

import pandas as pd

PII_PATTERNS = {
    # Korean RRN (주민등록번호): 6 digits - 7 digits
    "rrn": r"\b\d{6}[-\s]?\d{7}\b",
    # Card number: 13-19 digits w/ optional separators
    "card_number": r"\b(?:\d[ -]?){13,19}\b",
    # Account number (loose): 10-16 digits, optional separators
    "account_number": r"\b\d{2,4}[- ]\d{2,6}[- ]\d{2,8}\b",
    # Korean phone: 010 / 02 / 0xx with separators
    "phone_kr": r"\b0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4}\b",
    # Email
    "email": r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b",
}


def detect_pii_in_text(text: str) -> List[dict]:
    """Return all PII pattern matches in `text`."""
    if text is None:
        return []
    out: List[dict] = []
    for name, pat in PII_PATTERNS.items():
        for m in re.finditer(pat, text):
            out.append({"type": name, "match": m.group(0), "span": list(m.span())})
    return out


def detect_pii_in_dataframe(df: pd.DataFrame, max_rows: int = 1000) -> List[dict]:
    """Scan up to `max_rows` of object/string columns for PII matches."""
    if df is None or df.empty:
        return []
    out: List[dict] = []
    sample = df.head(max_rows)
    for col in sample.columns:
        s = sample[col]
        if s.dtype != object:
            continue
        for idx, val in s.items():
            if not isinstance(val, str):
                continue
            for m in detect_pii_in_text(val):
                out.append({"column": col, "row": int(idx), **m})
    return out


def mask_text(text: str) -> str:
    """Replace detected PII patterns with '[REDACTED]'. Caller decides when to use."""
    if text is None:
        return text
    masked = text
    for pat in PII_PATTERNS.values():
        masked = re.sub(pat, "[REDACTED]", masked)
    return masked
