"""의존성 없는 inline SVG 차트 헬퍼.

보고서는 self-contained HTML 이어야 한다 (외부 JS/CDN 호출 금지 — 내부망/
감사 환경에서도 열람 가능). 모든 함수는 SVG 문자열을 반환한다.
"""

from __future__ import annotations

import html as _html
from typing import Sequence

PALETTE = {
    "ok": "#2e7d32",
    "warning": "#f9a825",
    "fail": "#c62828",
    "skipped": "#9e9e9e",
    "simulated": "#0288d1",
    "neutral": "#1565c0",
}


def _esc(s: object) -> str:
    return _html.escape(str(s))


def hbar(
    items: Sequence[tuple[str, float]],
    *,
    width: int = 640,
    bar_h: int = 22,
    gap: int = 8,
    colors: Sequence[str] | None = None,
    fmt: str = "{:.3f}",
    vline: float | None = None,
    vline_label: str = "",
    title: str = "",
) -> str:
    """가로 막대 차트. vline 으로 임계선 표시 가능."""
    if not items:
        return "<svg/>"
    label_w = 170
    val_w = 80
    chart_w = width - label_w - val_w
    max_v = max(abs(v) for _, v in items) or 1.0
    if vline is not None:
        max_v = max(max_v, abs(vline))
    max_v *= 1.08
    n = len(items)
    title_h = 24 if title else 0
    h = title_h + n * (bar_h + gap) + gap
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{h}" '
           f'font-family="sans-serif" font-size="12">']
    if title:
        out.append(f'<text x="0" y="16" font-weight="bold">{_esc(title)}</text>')
    zero_x = label_w + (chart_w / 2 if any(v < 0 for _, v in items) else 0)
    scale = (chart_w / 2 if any(v < 0 for _, v in items) else chart_w) / max_v
    for i, (label, v) in enumerate(items):
        y = title_h + gap + i * (bar_h + gap)
        color = (colors[i] if colors and i < len(colors) else PALETTE["neutral"])
        w = abs(v) * scale
        x = zero_x - w if v < 0 else zero_x
        out.append(f'<text x="{label_w - 6}" y="{y + bar_h - 6}" '
                   f'text-anchor="end">{_esc(label)}</text>')
        out.append(f'<rect x="{x:.1f}" y="{y}" width="{max(w, 1):.1f}" '
                   f'height="{bar_h}" fill="{color}" rx="3"/>')
        out.append(f'<text x="{label_w + chart_w + 6}" y="{y + bar_h - 6}">'
                   f'{_esc(fmt.format(v))}</text>')
    if vline is not None:
        vx = zero_x + vline * scale
        out.append(f'<line x1="{vx:.1f}" y1="{title_h}" x2="{vx:.1f}" y2="{h - 2}" '
                   f'stroke="#c62828" stroke-dasharray="4 3" stroke-width="1.5"/>')
        if vline_label:
            out.append(f'<text x="{vx + 4:.1f}" y="{title_h + 12}" '
                       f'fill="#c62828">{_esc(vline_label)}</text>')
    out.append("</svg>")
    return "".join(out)


def gauge(
    value: float,
    *,
    minimum: float,
    warning: float | None = None,
    vmax: float | None = None,
    label: str = "",
    fmt: str = "{:.3f}",
    width: int = 320,
    higher_is_better: bool = True,
) -> str:
    """수평 게이지: 최소 기준선 / 경고선 대비 현재 값."""
    vmax = vmax if vmax is not None else max(value, minimum,
                                             warning or minimum) * 1.25 or 1.0
    h = 56
    bar_y, bar_h = 26, 16
    scale = (width - 90) / vmax
    if higher_is_better:
        color = (PALETTE["fail"] if value < minimum
                 else PALETTE["warning"] if warning is not None and value < warning
                 else PALETTE["ok"])
    else:
        color = (PALETTE["fail"] if value > minimum
                 else PALETTE["warning"] if warning is not None and value > warning
                 else PALETTE["ok"])
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{h}" '
           f'font-family="sans-serif" font-size="12">']
    out.append(f'<text x="0" y="14" font-weight="bold">{_esc(label)} '
               f'{_esc(fmt.format(value))}</text>')
    out.append(f'<rect x="0" y="{bar_y}" width="{width - 90}" height="{bar_h}" '
               f'fill="#eceff1" rx="3"/>')
    out.append(f'<rect x="0" y="{bar_y}" width="{min(value, vmax) * scale:.1f}" '
               f'height="{bar_h}" fill="{color}" rx="3"/>')
    for thr, c, name in ((minimum, "#c62828", "min"),
                         (warning, "#f9a825", "warn")):
        if thr is None:
            continue
        tx = thr * scale
        out.append(f'<line x1="{tx:.1f}" y1="{bar_y - 4}" x2="{tx:.1f}" '
                   f'y2="{bar_y + bar_h + 4}" stroke="{c}" stroke-width="1.5"/>')
        out.append(f'<text x="{tx + 2:.1f}" y="{bar_y + bar_h + 14}" fill="{c}" '
                   f'font-size="10">{name} {_esc(fmt.format(thr))}</text>')
    out.append("</svg>")
    return "".join(out)


def status_donut(
    counts: dict[str, int],
    *,
    size: int = 150,
    title: str = "",
) -> str:
    """status 분포 도넛 차트 (ok/warning/fail/skipped)."""
    import math

    total = sum(counts.values()) or 1
    cx = cy = size / 2
    r, ring = size / 2 - 8, 20
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{size + 130}" '
           f'height="{size}" font-family="sans-serif" font-size="12">']
    angle = -90.0
    for status in ("ok", "warning", "fail", "skipped", "simulated"):
        n = counts.get(status, 0)
        if not n:
            continue
        frac = n / total
        sweep = frac * 360
        a0, a1 = math.radians(angle), math.radians(angle + min(sweep, 359.99))
        x0, y0 = cx + r * math.cos(a0), cy + r * math.sin(a0)
        x1, y1 = cx + r * math.cos(a1), cy + r * math.sin(a1)
        large = 1 if sweep > 180 else 0
        out.append(
            f'<path d="M{x0:.1f},{y0:.1f} A{r},{r} 0 {large} 1 {x1:.1f},{y1:.1f}" '
            f'stroke="{PALETTE[status]}" stroke-width="{ring}" fill="none"/>')
        angle += sweep
    out.append(f'<text x="{cx}" y="{cy + 4}" text-anchor="middle" '
               f'font-size="20" font-weight="bold">{total}</text>')
    ly = 16
    for status in ("ok", "warning", "fail", "skipped", "simulated"):
        n = counts.get(status, 0)
        if not n:
            continue
        out.append(f'<rect x="{size + 6}" y="{ly - 10}" width="10" height="10" '
                   f'fill="{PALETTE[status]}"/>')
        out.append(f'<text x="{size + 22}" y="{ly}">{status}: {n}</text>')
        ly += 18
    if title:
        out.append(f'<text x="{size + 6}" y="{ly + 4}" font-weight="bold">'
                   f'{_esc(title)}</text>')
    out.append("</svg>")
    return "".join(out)
