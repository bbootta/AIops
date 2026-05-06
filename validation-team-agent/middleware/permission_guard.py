"""권한 / 위험 명령어 점검.

Bash 명령 또는 작업 설명 문자열이 운영계 변경, 삭제, 외부 전송, 자격증명 노출에
해당하는지 패턴 기반으로 탐지한다. 본 모듈은 절대 명령을 실행하지 않으며,
탐지 결과만 반환한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List


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


_DANGEROUS_PATTERNS = [
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


def detect_permission_violations(text: str) -> List[PermissionFinding]:
    """주어진 명령 또는 설명 문자열에서 위반 패턴을 탐지한다."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    findings: List[PermissionFinding] = []
    for category, pattern in _DANGEROUS_PATTERNS:
        for m in re.finditer(pattern, text, flags=re.IGNORECASE):
            findings.append(
                PermissionFinding(category=category, pattern=pattern, matched=m.group(0))
            )
    return findings


def check_commands(commands: Iterable[str]) -> dict:
    """여러 명령을 일괄 점검한다.

    반환 dict 키: clean (bool), findings (list of dict)
    """
    all_findings: List[dict] = []
    for cmd in commands:
        for f in detect_permission_violations(cmd):
            all_findings.append({"command": cmd, **f.to_dict()})
    return {"clean": len(all_findings) == 0, "findings": all_findings}
