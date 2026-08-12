"""적기시정조치 판정 (은행업감독규정 제34조~제36조).

자본비율과 경영실태평가 등급 중 **어느 하나라도** 요건에 해당하면 조치 대상이
된다. 두 축을 AND로 묶으면 자본비율이 멀쩡한 취약 은행이 빠져나간다.

  경영개선권고  총자본 8% 미만 · 기본자본 6% 미만 · 보통주자본 4.5% 미만,
                또는 경영실태평가 종합 3등급 + 자산건전성/자본적정성 4등급 이하
  경영개선요구  총자본 6% 미만 · 기본자본 4.5% 미만 · 보통주자본 3.5% 미만,
                또는 경영실태평가 종합 4등급 이하
  경영개선명령  총자본 2% 미만 · 기본자본 1.5% 미만 · 보통주자본 1.2% 미만,
                또는 부실금융기관 결정
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

# (조치, 총자본, 기본자본, 보통주자본) — 미만이면 해당
THRESHOLDS: tuple[tuple[str, float, float, float], ...] = (
    ("경영개선명령", 0.020, 0.015, 0.012),
    ("경영개선요구", 0.060, 0.045, 0.035),
    ("경영개선권고", 0.080, 0.060, 0.045),
)
ACTION_ORDER = ("해당없음", "경영개선권고", "경영개선요구", "경영개선명령")


@dataclass(frozen=True)
class PromptAction:
    asof: str
    action: str
    capital_trigger: str | None
    camel_trigger: str | None
    detail: pd.DataFrame          # test, value, threshold, triggered, citation

    def passes(self) -> bool:
        return self.action == "해당없음"


def assess_prompt_action(result, camel=None) -> PromptAction:
    """자본비율 축과 경영실태평가 축을 **각각** 판정하고 더 무거운 쪽을 택한다."""
    asof = result.meta.get("asof", "1970-01-01")
    cet1, tier1, total = (float(result.bis.cet1_ratio),
                          float(result.bis.tier1_ratio),
                          float(result.bis.total_ratio))
    rows, capital_action = [], "해당없음"
    for action, t_total, t_tier1, t_cet1 in THRESHOLDS:
        hits = []
        for name, value, thr in (("총자본비율", total, t_total),
                                 ("기본자본비율", tier1, t_tier1),
                                 ("보통주자본비율", cet1, t_cet1)):
            triggered = value < thr
            rows.append({"test": f"{action} · {name}", "value": value,
                         "threshold": thr, "triggered": triggered,
                         "citation": "은행업감독규정 제34조~제36조"})
            if triggered:
                hits.append(name)
        if hits and ACTION_ORDER.index(action) > ACTION_ORDER.index(capital_action):
            capital_action = action
    capital_trigger = None
    if capital_action != "해당없음":
        fired = [r["test"] for r in rows
                 if r["triggered"] and r["test"].startswith(capital_action)]
        capital_trigger = ", ".join(fired)

    camel_action, camel_trigger = "해당없음", None
    if camel is not None:
        comp = int(camel.composite_grade)
        # 권고 요건은 "종합 3등급 이상 **이면서 자산건전성 또는 자본적정성**이
        # 4등급 이하"다. 아무 부문이나 4등급이면 걸리게 만들면 규정보다 넓게
        # 판정해 조치 근거가 흔들린다.
        core = camel.detail[camel.detail["component"].isin(
            ("자산건전성", "자본적정성"))]
        core_worst = int(core["grade"].max()) if len(core) else 1
        if comp >= 4:
            camel_action, camel_trigger = "경영개선요구", f"경영실태평가 종합 {comp}등급"
        elif comp >= 3 and core_worst >= 4:
            camel_action = "경영개선권고"
            camel_trigger = (f"종합 {comp}등급 + 자산건전성·자본적정성 "
                             f"{core_worst}등급")
        rows.append({"test": "경영실태평가 종합등급", "value": float(comp),
                     "threshold": 3.0, "triggered": comp >= 3,
                     "citation": "은행업감독규정 제31조~제33조 · 제34조"})

    action = max((capital_action, camel_action), key=ACTION_ORDER.index)
    return PromptAction(asof=asof, action=action,
                        capital_trigger=capital_trigger,
                        camel_trigger=camel_trigger,
                        detail=pd.DataFrame(rows))
