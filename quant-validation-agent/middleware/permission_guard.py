"""Permission guard.

Detects risky / production-affecting commands or strings.
Used to gate any command-string or generated code before it runs.
"""
from __future__ import annotations

import re
from typing import Iterable, List

DEFAULT_RISK_PATTERNS = [
    # SQL DDL / DML
    r"\bDROP\b",
    r"\bTRUNCATE\b",
    r"\bALTER\b",
    r"\bDELETE\s+FROM\b",
    r"\bUPDATE\b",
    r"\bINSERT\s+INTO\b",
    # Filesystem destruction
    r"\brm\s+-rf\b",
    r"\bdel\s+/s\b",
    r"\bformat\b",
    # Deployment / pushes
    r"\bgit\s+push\b",
    r"\bdeploy\b",
    r"\bdocker\s+push\b",
    r"\bkubectl\s+apply\b",
    r"\bterraform\s+apply\b",
    # Operational keywords
    r"\bproduction\b",
    r"\bprod\b",
    r"운영계",
    r"운영\s*DB",
    r"운영\s*테이블",
]


def detect_risky_commands(
    text: str, extra_patterns: Iterable[str] | None = None
) -> List[dict]:
    """Return a list of matches for any risky pattern in `text`."""
    if text is None:
        return []
    patterns = list(DEFAULT_RISK_PATTERNS)
    if extra_patterns:
        patterns.extend(extra_patterns)
    matches = []
    for p in patterns:
        for m in re.finditer(p, text, flags=re.IGNORECASE):
            matches.append({"pattern": p, "match": m.group(0), "span": list(m.span())})
    return matches


def assert_no_risky_commands(text: str) -> None:
    """Raise PermissionError if any risky pattern is found."""
    matches = detect_risky_commands(text)
    if matches:
        joined = ", ".join(sorted({m["match"] for m in matches}))
        raise PermissionError(
            f"Risky command/keyword detected; aborting. Matches: {joined}"
        )
