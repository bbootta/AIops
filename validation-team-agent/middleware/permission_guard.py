"""권한 / 위험 명령어 점검.

Bash 명령 또는 작업 설명 문자열이 운영계 변경, 삭제, 외부 전송, 자격증명 노출에
해당하는지 패턴 기반으로 탐지한다. 본 모듈은 절대 명령을 실행하지 않으며,
탐지 결과만 반환한다.

위험 패턴 SSoT는 ``harness/permission_matrix.json``. 호출자가 patterns 인자를
명시하면 해당 패턴이 사용되고, 그렇지 않으면 매트릭스 파일에서 로드한다.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence


@dataclass(frozen=True)
class PermissionFinding:
    category: str
    pattern: str
    matched: str

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "pattern": self.pattern,
            "matched": self.matched,
        }


_MATRIX_PATH = Path(__file__).resolve().parent.parent / "harness" / "permission_matrix.json"

_FALLBACK_PATTERNS: list[tuple[str, str]] = [
    ("destructive_fs", r"\brm\s+-rf\b"),
    ("destructive_fs", r"\bmkfs\b"),
    ("destructive_fs", r"\bdd\s+if=.*of=/dev/"),
    ("force_push", r"git\s+push.*--force"),
    ("hard_reset", r"git\s+reset\s+--hard"),
    ("skip_hook", r"--no-verify\b"),
    ("ops_db", r"\b(drop\s+table|truncate\s+table|delete\s+from)\b"),
    ("ops_db", r"\bUPDATE\s+\w+\s+SET\b"),
    ("external_io", r"\bcurl\s+-X\s+POST\b"),
    ("external_io", r"\bscp\s+\S+\s+\S+@"),
    ("credential_exposure", r"AKIA[0-9A-Z]{16}"),
    ("credential_exposure", r"-----BEGIN (?:RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ("credential_exposure", r"\b(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"]{8,}['\"]"),
]


def load_patterns(matrix_path: str | Path | None = None) -> list[tuple[str, str]]:
    """``harness/permission_matrix.json``에서 (category, regex) 목록을 로드한다.

    파일이 없거나 형식이 잘못되면 _FALLBACK_PATTERNS을 사용한다.
    """
    p = Path(matrix_path) if matrix_path else _MATRIX_PATH
    if not p.exists():
        return list(_FALLBACK_PATTERNS)
    try:
        cfg = json.loads(p.read_text(encoding="utf-8"))
        return [(it["category"], it["regex"]) for it in cfg.get("patterns", [])] or list(
            _FALLBACK_PATTERNS
        )
    except (OSError, ValueError, KeyError):
        return list(_FALLBACK_PATTERNS)


def detect_permission_violations(
    text: str,
    patterns: Sequence[tuple[str, str]] | None = None,
) -> List[PermissionFinding]:
    """주어진 명령 또는 설명 문자열에서 위반 패턴을 탐지한다."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    pats = list(patterns) if patterns is not None else load_patterns()
    findings: List[PermissionFinding] = []
    for category, pattern in pats:
        for m in re.finditer(pattern, text, flags=re.IGNORECASE):
            findings.append(
                PermissionFinding(category=category, pattern=pattern, matched=m.group(0))
            )
    return findings


def check_commands(
    commands: Iterable[str],
    patterns: Sequence[tuple[str, str]] | None = None,
) -> dict:
    """여러 명령을 일괄 점검한다.

    반환 dict 키: clean (bool), findings (list of dict)
    """
    pats = list(patterns) if patterns is not None else load_patterns()
    all_findings: List[dict] = []
    for cmd in commands:
        for f in detect_permission_violations(cmd, patterns=pats):
            all_findings.append({"command": cmd, **f.to_dict()})
    return {"clean": len(all_findings) == 0, "findings": all_findings}
