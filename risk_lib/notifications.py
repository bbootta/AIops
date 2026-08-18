"""Notification / alert payload builders.

Doesn't actually send — just builds the payload so the user/ops team can
post it to Slack via webhook or email via SMTP / their own pipeline.

Three formats:
  - slack:    Slack Block Kit JSON payload (paste into webhook)
  - email:    HTML body + subject + plain-text alt
  - markdown: Plain markdown summary (works as Slack mrkdwn or anywhere)

Trigger logic: any KRI not GREEN, plus any FAIL/WARN validation check.
Severity = max severity in the alert set (RED > AMBER > WATCH > WARN).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


_SEVERITY_ORDER = {"RED": 4, "FAIL": 4, "AMBER": 3, "WARN": 2, "WATCH": 1, "GREEN": 0, "PASS": 0}
_EMOJI = {"RED": "🔴", "FAIL": "🔴", "AMBER": "🟠", "WARN": "🟡",
          "WATCH": "🟡", "GREEN": "🟢", "PASS": "🟢"}


@dataclass
class Alert:
    """One alertable item."""
    severity: str               # RED | AMBER | WATCH | FAIL | WARN
    category: str               # capital / liquidity / model / ...
    title: str
    detail: str
    citation: str = ""

    def emoji(self) -> str:
        return _EMOJI.get(self.severity, "⚪")


@dataclass
class AlertBundle:
    asof: str
    headline_digest: str
    seed: int
    verdict: str                # PASS | FAIL
    summary: dict[str, int]     # PASS/WARN/FAIL counts
    raf_summary: dict[str, int] # GREEN/WATCH/AMBER/RED counts
    alerts: list[Alert] = field(default_factory=list)

    def worst_severity(self) -> str:
        if not self.alerts: return "GREEN"
        return max(self.alerts, key=lambda a: _SEVERITY_ORDER.get(a.severity, 0)).severity


def collect_alerts(result) -> AlertBundle:
    """Walk validation + RAF, build the bundle."""
    bundle = AlertBundle(
        asof=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        headline_digest="",   # filled by caller if manifest given
        seed=int(result.meta.get("seed", 0)),
        verdict="PASS" if result.validation.passes() else "FAIL",
        summary=result.validation.summary(),
        raf_summary=result.raf.summary() if result.raf else {},
    )
    # RAF non-GREEN
    if result.raf:
        for k in result.raf.kris:
            if k.grade == "GREEN": continue
            bundle.alerts.append(Alert(
                severity=k.grade, category=k.category, title=k.name,
                detail=(f"실측 {k.actual:.4f} vs board 한계 {k.threshold.board:.4f}"),
                citation=k.citation,
            ))
    # Validation WARN/FAIL
    for c in result.validation.checks:
        if c.status == "PASS": continue
        bundle.alerts.append(Alert(
            severity=c.status, category="validation",
            title=c.name, detail=c.detail,
        ))
    # Order by severity descending
    bundle.alerts.sort(key=lambda a: -_SEVERITY_ORDER.get(a.severity, 0))
    return bundle


def build_slack_payload(bundle: AlertBundle) -> dict[str, Any]:
    """Slack Block Kit message (post to incoming webhook)."""
    worst = bundle.worst_severity()
    header = (f"{_EMOJI.get(worst, '⚪')} 리스크관리 알림 — "
              f"판정 {bundle.verdict} / 최악 KRI {worst}")
    summary_line = (f"*PASS* {bundle.summary.get('PASS',0)} · "
                    f"*WARN* {bundle.summary.get('WARN',0)} · "
                    f"*FAIL* {bundle.summary.get('FAIL',0)}  |  "
                    f"RAF GREEN {bundle.raf_summary.get('GREEN',0)} · "
                    f"WATCH {bundle.raf_summary.get('WATCH',0)} · "
                    f"AMBER {bundle.raf_summary.get('AMBER',0)} · "
                    f"RED {bundle.raf_summary.get('RED',0)}")

    alert_blocks = []
    for a in bundle.alerts[:10]:    # cap to keep payload <40k chars
        alert_blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn",
                     "text": f"{a.emoji()} *[{a.severity}]* {a.title}\n"
                             f"_{a.category}_ — {a.detail}"
                             + (f" · `{a.citation}`" if a.citation else "")},
        })

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": header}},
        {"type": "context",
         "elements": [{"type": "mrkdwn", "text": summary_line},
                      {"type": "mrkdwn",
                       "text": f"산출 {bundle.asof} · seed {bundle.seed} · "
                               f"digest `{bundle.headline_digest[:12]}`"}]},
        {"type": "divider"},
    ]
    blocks += alert_blocks
    if len(bundle.alerts) > 10:
        blocks.append({"type": "context",
                       "elements": [{"type": "mrkdwn",
                                     "text": f"+ {len(bundle.alerts) - 10}건 추가"}]})
    return {"text": header, "blocks": blocks}


def build_markdown(bundle: AlertBundle) -> str:
    """Plain-markdown summary for chat, email body, or notes."""
    worst = bundle.worst_severity()
    lines = [
        f"# {_EMOJI.get(worst, '⚪')} 리스크 알림 — 판정 {bundle.verdict}",
        "",
        f"- 산출: {bundle.asof}",
        f"- 시드: {bundle.seed} · digest `{bundle.headline_digest[:12]}`",
        f"- 검증: PASS {bundle.summary.get('PASS',0)} / "
        f"WARN {bundle.summary.get('WARN',0)} / FAIL {bundle.summary.get('FAIL',0)}",
        f"- RAF: GREEN {bundle.raf_summary.get('GREEN',0)} / "
        f"WATCH {bundle.raf_summary.get('WATCH',0)} / "
        f"AMBER {bundle.raf_summary.get('AMBER',0)} / RED {bundle.raf_summary.get('RED',0)}",
        "",
        f"## 알림 ({len(bundle.alerts)}건)",
        "",
    ]
    if not bundle.alerts:
        lines.append("_조치 필요 항목 없음_")
    else:
        for a in bundle.alerts:
            lines.append(f"- {a.emoji()} **[{a.severity}]** `{a.category}` "
                         f"**{a.title}** — {a.detail}"
                         + (f" _({a.citation})_" if a.citation else ""))
    return "\n".join(lines)


def build_email_payload(bundle: AlertBundle) -> dict[str, str]:
    """Subject + plain-text + HTML body for email."""
    worst = bundle.worst_severity()
    subject = (f"[리스크관리 알림 / {bundle.verdict}] "
               f"최악 등급 {worst} · {bundle.asof[:10]}")
    plain = build_markdown(bundle)
    rows = "".join(
        f"<tr><td>{a.emoji()}</td>"
        f"<td><b>{a.severity}</b></td>"
        f"<td>{a.category}</td>"
        f"<td><b>{a.title}</b></td>"
        f"<td>{a.detail}</td>"
        f"<td><code>{a.citation}</code></td></tr>"
        for a in bundle.alerts)
    html = f"""<!doctype html><html lang=ko><body
style="font-family:'Segoe UI','Apple SD Gothic Neo',sans-serif;color:#1a202c;max-width:900px;margin:0 auto">
<h2>{_EMOJI.get(worst,'⚪')} 리스크 알림 — 판정 {bundle.verdict} · 최악 KRI {worst}</h2>
<p>산출 {bundle.asof} · seed {bundle.seed} · digest <code>{bundle.headline_digest[:16]}</code></p>
<p><b>검증</b> PASS {bundle.summary.get('PASS',0)} /
WARN {bundle.summary.get('WARN',0)} /
FAIL {bundle.summary.get('FAIL',0)} &nbsp;|&nbsp;
<b>RAF</b> GREEN {bundle.raf_summary.get('GREEN',0)} /
WATCH {bundle.raf_summary.get('WATCH',0)} /
AMBER {bundle.raf_summary.get('AMBER',0)} /
RED {bundle.raf_summary.get('RED',0)}</p>
<table border=1 cellpadding=6 cellspacing=0 style="border-collapse:collapse;font-size:13px">
<tr style="background:#f3f4f6"><th></th><th>등급</th><th>분류</th><th>지표</th><th>상세</th><th>근거</th></tr>
{rows or '<tr><td colspan=6>조치 필요 항목 없음</td></tr>'}
</table>
</body></html>"""
    return {"subject": subject, "plain": plain, "html": html}


def write_bundle(bundle: AlertBundle, out_dir, *, prefix: str = "alert") -> dict[str, str]:
    """Write all three formats to disk."""
    from pathlib import Path
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    slack = build_slack_payload(bundle)
    md = build_markdown(bundle)
    email = build_email_payload(bundle)
    paths = {
        "slack.json": out / f"{prefix}_slack.json",
        "markdown.md": out / f"{prefix}.md",
        "email_subject.txt": out / f"{prefix}_subject.txt",
        "email_plain.txt": out / f"{prefix}_plain.txt",
        "email.html": out / f"{prefix}_email.html",
    }
    paths["slack.json"].write_text(json.dumps(slack, ensure_ascii=False, indent=2),
                                    encoding="utf-8")
    paths["markdown.md"].write_text(md, encoding="utf-8")
    paths["email_subject.txt"].write_text(email["subject"], encoding="utf-8")
    paths["email_plain.txt"].write_text(email["plain"], encoding="utf-8")
    paths["email.html"].write_text(email["html"], encoding="utf-8")
    return {k: str(v.resolve()) for k, v in paths.items()}
