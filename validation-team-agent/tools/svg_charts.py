"""의존성 없는 inline SVG 차트 헬퍼.

보고서는 self-contained HTML 이어야 한다 (외부 JS/CDN 호출 금지 — 내부망/
감사 환경에서도 열람 가능). 모든 함수는 SVG 문자열을 반환한다.
"""

from __future__ import annotations

import html as _html
from typing import Sequence

PALETTE = {
    # status palette (ok/warning/fail/skipped) + neutral/simulated 시리즈.
    # dataviz validator: lightness band PASS / contrast ≥3:1 PASS /
    # CVD adjacent ΔE 13.2 PASS. skipped 는 의도적 무채색 (비활성 status —
    # categorical chroma floor 적용 대상 아님, WCAG contrast 로 검증).
    "ok": "#2e7d32",
    "warning": "#b8860b",
    "fail": "#b91c1c",
    "skipped": "#64748b",
    "simulated": "#0369a1",
    "neutral": "#1755a6",
}

# 차트 공통 텍스트/축 토큰 — 텍스트는 절대 series 색을 입지 않는다 (dataviz)
INK = "#0f172a"          # 주 텍스트
INK_MUTED = "#475569"    # 보조 텍스트 (축 라벨/범례)
INK_SUBTLE = "#94a3b8"   # 눈금·부가 정보
GRID = "#e4e8ee"         # recessive grid
AXIS = "#cbd5e1"         # recessive 축선


def _esc(s: object) -> str:
    return _html.escape(str(s))


def _aria(kind: str, name: str = "") -> str:
    """스크린리더용 role/aria-label 속성 (WAI-ARIA img role)."""
    label = f"{kind}: {name}" if name else kind
    return f'role="img" aria-label="{_esc(label)}"'


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
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" {_aria("가로 막대 차트", title)} width="{width}" height="{h}" '
           f'font-family="sans-serif" font-size="12">']
    if title:
        out.append(f'<text x="0" y="16" font-weight="600" fill="{INK}">'
                   f'{_esc(title)}</text>')
    zero_x = label_w + (chart_w / 2 if any(v < 0 for _, v in items) else 0)
    scale = (chart_w / 2 if any(v < 0 for _, v in items) else chart_w) / max_v
    # recessive grid — 1/4·1/2·3/4·최대 위치 (제로 기준 우측만)
    for frac in (0.25, 0.5, 0.75, 1.0):
        gx = zero_x + frac * max_v * scale
        if gx <= label_w + chart_w:
            out.append(f'<line x1="{gx:.1f}" y1="{title_h + 2}" x2="{gx:.1f}" '
                       f'y2="{h - 2}" stroke="{GRID}" stroke-width="1"/>')
    # 제로 기준선 (음수 존재 시)
    if any(v < 0 for _, v in items):
        out.append(f'<line x1="{zero_x:.1f}" y1="{title_h + 2}" x2="{zero_x:.1f}" '
                   f'y2="{h - 2}" stroke="{AXIS}" stroke-width="1"/>')
    for i, (label, v) in enumerate(items):
        y = title_h + gap + i * (bar_h + gap)
        color = (colors[i] if colors and i < len(colors) else PALETTE["neutral"])
        w = abs(v) * scale
        x = zero_x - w if v < 0 else zero_x
        out.append(f'<text x="{label_w - 8}" y="{y + bar_h - 6}" '
                   f'text-anchor="end" fill="{INK_MUTED}">{_esc(label)}</text>')
        out.append(f'<rect x="{x:.1f}" y="{y}" width="{max(w, 1):.1f}" '
                   f'height="{bar_h}" fill="{color}" rx="4"/>')
        out.append(f'<text x="{label_w + chart_w + 8}" y="{y + bar_h - 6}" '
                   f'fill="{INK}" font-weight="500">'
                   f'{_esc(fmt.format(v))}</text>')
    if vline is not None:
        vx = zero_x + vline * scale
        out.append(f'<line x1="{vx:.1f}" y1="{title_h}" x2="{vx:.1f}" y2="{h - 2}" '
                   f'stroke="{PALETTE["fail"]}" stroke-dasharray="4 3" '
                   f'stroke-width="1.5"/>')
        if vline_label:
            out.append(f'<text x="{vx + 5:.1f}" y="{title_h + 12}" '
                       f'fill="{PALETTE["fail"]}" font-size="11">'
                       f'{_esc(vline_label)}</text>')
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
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" {_aria("게이지 차트", label)} width="{width}" height="{h}" '
           f'font-family="sans-serif" font-size="12">']
    out.append(f'<text x="0" y="14" fill="{INK}">'
               f'<tspan font-weight="600">{_esc(label)}</tspan> '
               f'<tspan font-weight="700">{_esc(fmt.format(value))}</tspan></text>')
    out.append(f'<rect x="0" y="{bar_y}" width="{width - 90}" height="{bar_h}" '
               f'fill="{GRID}" rx="4"/>')
    out.append(f'<rect x="0" y="{bar_y}" width="{min(value, vmax) * scale:.1f}" '
               f'height="{bar_h}" fill="{color}" rx="4"/>')
    for thr, c, name in ((minimum, PALETTE["fail"], "min"),
                         (warning, PALETTE["warning"], "warn")):
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
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" {_aria("상태 도넛 차트", title)} width="{size + 130}" '
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
               f'font-size="20" font-weight="bold" fill="{INK}">{total}</text>')
    ly = 16
    for status in ("ok", "warning", "fail", "skipped", "simulated"):
        n = counts.get(status, 0)
        if not n:
            continue
        out.append(f'<rect x="{size + 6}" y="{ly - 10}" width="10" height="10" '
                   f'rx="2" fill="{PALETTE[status]}"/>')
        out.append(f'<text x="{size + 22}" y="{ly}" fill="{INK_MUTED}">'
                   f'{status}: {n}</text>')
        ly += 18
    if title:
        out.append(f'<text x="{size + 6}" y="{ly + 4}" font-weight="600" '
                   f'fill="{INK}">{_esc(title)}</text>')
    out.append("</svg>")
    return "".join(out)


def heatmap(
    rows: Sequence[tuple[str, str, str, str | None]],
    *,
    width: int = 720,
    row_h: int = 32,
    title: str = "",
) -> str:
    """부문 × 상태 히트맵.

    rows: [(domain_name, status, detail_text, deep_link_href), ...]
    """
    if not rows:
        return "<svg/>"
    label_w = 220
    title_h = 24 if title else 0
    h = title_h + 8 + len(rows) * (row_h + 4)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" {_aria("히트맵", title)} width="{width}" height="{h}" '
           f'font-family="sans-serif" font-size="12">']
    if title:
        out.append(f'<text x="0" y="16" font-weight="600" fill="{INK}">'
                   f'{_esc(title)}</text>')
    for i, (name, status, detail, href) in enumerate(rows):
        y = title_h + 8 + i * (row_h + 4)
        color = PALETTE.get(status, PALETTE["skipped"])
        out.append(f'<rect x="0" y="{y}" width="{width}" height="{row_h}" '
                   f'fill="white" stroke="{GRID}" rx="4"/>')
        out.append(f'<rect x="0" y="{y}" width="{label_w}" height="{row_h}" '
                   f'fill="{color}" fill-opacity="0.12" stroke="{color}" rx="4"/>')
        label = name + (" →" if href else "")
        # 부문 라벨: ink 토큰 (색은 status pill 이 담당 — 텍스트에 series 색 금지)
        out.append(f'<text x="10" y="{y + row_h / 2 + 4:.0f}" '
                   f'fill="{INK}" font-weight="600">{_esc(label)}</text>')
        out.append(f'<rect x="{label_w + 10}" y="{y + 8}" width="80" height="{row_h - 16}" '
                   f'rx="10" fill="{color}"/>')
        out.append(f'<text x="{label_w + 50}" y="{y + row_h / 2 + 4:.0f}" '
                   f'text-anchor="middle" fill="white" font-weight="600" '
                   f'font-size="11">{_esc(status)}</text>')
        # detail (clip 처리)
        d = detail if len(detail) <= 70 else detail[:67] + "…"
        out.append(f'<text x="{label_w + 100}" y="{y + row_h / 2 + 4:.0f}" '
                   f'fill="{INK_MUTED}">{_esc(d)}</text>')
    out.append("</svg>")
    return "".join(out)


def kpi_card_strip(
    cards: Sequence[tuple[str, str, str]],
    *,
    width: int = 760,
    card_w: int = 180,
    card_h: int = 90,
    gap: int = 12,
) -> str:
    """KPI 카드 strip — (label, value, status_key).

    status_key 는 PALETTE 키 (ok/warning/fail) 또는 임의 색.
    """
    if not cards:
        return "<svg/>"
    n = len(cards)
    per_row = max(1, (width + gap) // (card_w + gap))
    h = ((n + per_row - 1) // per_row) * (card_h + gap)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" {_aria("KPI 카드")} width="{width}" height="{h}" '
           f'font-family="sans-serif" font-size="12">']
    for i, (label, value, key) in enumerate(cards):
        col = i % per_row
        row = i // per_row
        x = col * (card_w + gap)
        y = row * (card_h + gap)
        color = PALETTE.get(key, key) if key else PALETTE["neutral"]
        out.append(f'<rect x="{x}" y="{y}" width="{card_w}" height="{card_h}" '
                   f'rx="8" fill="white" stroke="{GRID}" stroke-width="1"/>')
        out.append(f'<rect x="{x}" y="{y}" width="6" height="{card_h}" '
                   f'rx="3" fill="{color}"/>')
        out.append(f'<text x="{x + 16}" y="{y + 22}" fill="{INK_MUTED}" '
                   f'font-size="11">{_esc(label)}</text>')
        out.append(f'<text x="{x + 16}" y="{y + 56}" fill="{INK}" '
                   f'font-size="22" font-weight="bold">{_esc(value)}</text>')
        out.append(f'<rect x="{x + 16}" y="{y + 70}" width="62" height="14" '
                   f'rx="7" fill="{color}"/>')
        out.append(f'<text x="{x + 47}" y="{y + 80}" text-anchor="middle" '
                   f'fill="white" font-size="10" font-weight="600">'
                   f'{_esc(key if key in PALETTE else "info")}</text>')
    out.append("</svg>")
    return "".join(out)


def trend_line(
    series: Sequence[tuple[str, float]],
    *,
    width: int = 460,
    height: int = 140,
    minimum: float | None = None,
    title: str = "",
    fmt: str = "{:.3f}",
) -> str:
    """단순 line chart — (period_label, value) 시계열. minimum 임계선 옵션."""
    if not series:
        return "<svg/>"
    pad_l, pad_r, pad_t, pad_b = 44, 16, 26 if title else 12, 26
    inner_w = width - pad_l - pad_r
    inner_h = height - pad_t - pad_b
    vals = [v for _, v in series]
    vmin = min(vals + ([minimum] if minimum is not None else []))
    vmax = max(vals + ([minimum] if minimum is not None else []))
    if vmin == vmax:
        vmin -= 1
        vmax += 1
    span = vmax - vmin
    vmin -= span * 0.1
    vmax += span * 0.1
    span = vmax - vmin

    def y_of(v: float) -> float:
        return pad_t + inner_h * (1 - (v - vmin) / span)

    n = len(series)
    pts = [(pad_l + i * inner_w / max(1, n - 1), y_of(v)) for i, (_, v) in enumerate(series)]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" {_aria("추이 차트", title)} width="{width}" height="{height}" '
           f'font-family="sans-serif" font-size="11">']
    if title:
        out.append(f'<text x="0" y="14" font-weight="600" fill="{INK}">'
                   f'{_esc(title)}</text>')
    # recessive 수평 grid (3 단계) + y 축 눈금 값
    for frac in (0.0, 0.5, 1.0):
        gy = pad_t + inner_h * frac
        gv = vmax - span * frac
        out.append(f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{pad_l + inner_w}" '
                   f'y2="{gy:.1f}" stroke="{GRID}" stroke-width="1"/>')
        out.append(f'<text x="{pad_l - 6}" y="{gy + 3.5:.1f}" text-anchor="end" '
                   f'fill="{INK_SUBTLE}" font-size="10">'
                   f'{_esc(fmt.format(gv))}</text>')
    # recessive 축
    out.append(f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + inner_h}" '
               f'stroke="{AXIS}" stroke-width="1"/>')
    out.append(f'<line x1="{pad_l}" y1="{pad_t + inner_h}" x2="{pad_l + inner_w}" '
               f'y2="{pad_t + inner_h}" stroke="{AXIS}" stroke-width="1"/>')
    # 임계선
    if minimum is not None:
        my = y_of(minimum)
        out.append(f'<line x1="{pad_l}" y1="{my:.1f}" x2="{pad_l + inner_w}" y2="{my:.1f}" '
                   f'stroke="{PALETTE["fail"]}" stroke-dasharray="4 3"/>')
        out.append(f'<text x="{pad_l + inner_w - 4}" y="{my - 4:.1f}" '
                   f'text-anchor="end" fill="{PALETTE["fail"]}" font-size="10">'
                   f'min {fmt.format(minimum)}</text>')
    # line + 포인트 — 값 라벨은 selective (첫/끝/임계 위반) 만.
    # dataviz anti-pattern: "never a number on every point".
    path = " ".join(("M" if i == 0 else "L") + f"{p[0]:.1f},{p[1]:.1f}"
                    for i, p in enumerate(pts))
    out.append(f'<path d="{path}" fill="none" stroke="{PALETTE["neutral"]}" '
               f'stroke-width="2" stroke-linejoin="round" '
               f'stroke-linecap="round"/>')
    breach = [minimum is not None and v < minimum for _, v in series]
    for i, ((label, v), (x, y)) in enumerate(zip(series, pts)):
        color = PALETTE["fail"] if breach[i] else PALETTE["ok"]
        # 2px surface ring (marker ≥ 8px 직경)
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="white"/>')
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color}"/>')
        # x 축 라벨은 처음/중간/끝만 (혼잡 방지, ≤5 개면 전부)
        show_x = n <= 5 or i in (0, n // 2, n - 1)
        if show_x:
            out.append(f'<text x="{x:.1f}" y="{pad_t + inner_h + 16}" '
                       f'text-anchor="middle" fill="{INK_MUTED}" '
                       f'font-size="10">{_esc(label)}</text>')
        # 값 라벨: 첫 점 / 끝 점 / 임계 위반 점만 (selective)
        show_v = i == 0 or i == n - 1 or breach[i]
        if show_v:
            anchor = ("start" if i == 0 else
                      "end" if i == n - 1 else "middle")
            tx = x + (4 if i == 0 else -4 if i == n - 1 else 0)
            out.append(f'<text x="{tx:.1f}" y="{y - 9:.1f}" '
                       f'text-anchor="{anchor}" fill="{INK}" '
                       f'font-weight="500" font-size="10.5">'
                       f'{_esc(fmt.format(v))}</text>')
    out.append("</svg>")
    return "".join(out)
