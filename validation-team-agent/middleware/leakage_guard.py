"""Target leakage 점검.

설명변수 목록(feature_names)에 target / outcome / default_date 같은 누수
가능성이 높은 변수가 포함되었는지 점검한다.
"""

from __future__ import annotations

import re
from typing import Iterable, List


_DEFAULT_FORBIDDEN_PATTERNS = [
    r"^target$",
    r"^y$",
    r"^label$",
    r"^outcome$",
    r"^bad$",
    r"^default(_|$)",
    r"^post_default(_|$)",
    r"^future_(\w+)$",
    r"_after$",
    r"_post$",
]


def check_leakage(
    feature_names: Iterable[str],
    target_name: str = "target",
    extra_forbidden: Iterable[str] | None = None,
) -> dict:
    """누수 가능성이 있는 변수명을 탐지한다.

    target_name이 features에 그대로 있는 경우는 즉시 위반으로 처리한다.
    반환 dict 키: passed, leaked (list), patterns_used (list)
    """
    features = list(feature_names)
    patterns = list(_DEFAULT_FORBIDDEN_PATTERNS)
    if extra_forbidden:
        patterns.extend(extra_forbidden)

    compiled = [re.compile(p, flags=re.IGNORECASE) for p in patterns]

    leaked: List[dict] = []
    if target_name in features:
        leaked.append({"feature": target_name, "reason": "target name appears as feature"})
    for f in features:
        if f == target_name:
            continue
        for pat in compiled:
            if pat.search(f):
                leaked.append({"feature": f, "reason": f"matches {pat.pattern}"})
                break
    return {
        "passed": len(leaked) == 0,
        "leaked": leaked,
        "patterns_used": patterns,
    }
