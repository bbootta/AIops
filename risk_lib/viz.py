"""Lightweight inline SVG charts for the HTML report.

Why hand-roll SVG: matplotlib is not in the container, and inline SVG renders
crisply inside email/HTML without a separate image asset. Each helper takes the
raw numbers and returns a self-contained <svg>…</svg> string that the report
embeds directly.

Charts intentionally stay declarative and small (≤ ~120 lines each) so they
remain auditable next to the regulator-cited tables they accompany.
"""

from __future__ import annotations

from collections.abc import Sequence


# Modest, print-friendly palette (Tableau 10 lite).
PALETTE = ["#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f",
           "#edc948", "#b07aa1", "#ff9da7", "#9c755f", "#bab0ac"]
GREEN = "#2e8540"
RED = "#c5221f"
AMBER = "#e8a33d"
GREY = "#6b7280"


def _esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _fmt_axis(v: float) -> str:
    av = abs(v)
    if av >= 1e12: return f"{v/1e12:.1f}조"
    if av >= 1e9:  return f"{v/1e9:.0f}십억"
    if av >= 1e6:  return f"{v/1e6:.0f}M"
    if av >= 1e3:  return f"{v/1e3:.0f}k"
    if av == 0:    return "0"
    return f"{v:.2f}"


def _fmt_pct(v: float) -> str:
    return f"{v*100:.1f}%"


def _svg_open(w: int, h: int, title: str = "") -> str:
    t = f'<title>{_esc(title)}</title>' if title else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'width="100%" style="max-width:{w}px;height:auto;'
            f'font-family:Segoe UI,Apple SD Gothic Neo,Malgun Gothic,sans-serif;'
            f'font-size:12px">{t}')


def bar_chart(
    labels: Sequence[str], values: Sequence[float], *,
    width: int = 720, height: int = 280, title: str = "",
    value_fmt=_fmt_axis, colors: Sequence[str] | None = None,
    reference_value: float | None = None, reference_label: str = "",
    y_zero: bool = True,
) -> str:
    """Vertical bar chart with axis ticks, value labels, optional reference line."""
    pad_l, pad_r, pad_t, pad_b = 70, 24, 36 if title else 16, 60
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    n = len(values)
    vmax = max(list(values) + ([reference_value] if reference_value else [0]) + [0])
    vmin = min(list(values) + ([reference_value] if reference_value else [0]) + [0])
    if y_zero:
        vmin = min(vmin, 0)
    if vmax == vmin:
        vmax = vmin + 1
    span = vmax - vmin
    pad_span = span * 0.08
    vmax += pad_span
    if vmin < 0: vmin -= pad_span

    def y(v): return pad_t + plot_h * (1 - (v - vmin) / (vmax - vmin))
    def x(i): return pad_l + (plot_w / n) * (i + 0.5)

    parts = [_svg_open(width, height, title)]
    if title:
        parts.append(f'<text x="{width/2}" y="22" text-anchor="middle" '
                     f'font-weight="600" font-size="14">{_esc(title)}</text>')

    # gridlines + y-axis
    for i in range(5):
        gv = vmin + span * i / 4
        gy = y(gv)
        parts.append(f'<line x1="{pad_l}" x2="{width-pad_r}" y1="{gy}" y2="{gy}" '
                     f'stroke="#e5e7eb" stroke-width="1"/>')
        parts.append(f'<text x="{pad_l-6}" y="{gy+4}" text-anchor="end" '
                     f'fill="#374151">{_esc(value_fmt(gv))}</text>')

    # bars
    bar_w = plot_w / n * 0.68
    y0 = y(0)
    for i, (lbl, v) in enumerate(zip(labels, values)):
        cx = x(i)
        color = (colors[i] if colors else PALETTE[i % len(PALETTE)])
        top, bot = (y(v), y0) if v >= 0 else (y0, y(v))
        parts.append(f'<rect x="{cx-bar_w/2}" y="{top}" width="{bar_w}" '
                     f'height="{max(bot-top, 1)}" fill="{color}" opacity="0.92"/>')
        # value label
        ly = top - 4 if v >= 0 else bot + 12
        parts.append(f'<text x="{cx}" y="{ly}" text-anchor="middle" '
                     f'fill="#111827" font-size="11">{_esc(value_fmt(v))}</text>')
        # x label, rotated if long
        rotate = "" if max(map(len, labels)) <= 8 else f' transform="rotate(-25 {cx} {height-pad_b+18})"'
        parts.append(f'<text x="{cx}" y="{height-pad_b+18}" text-anchor="middle" '
                     f'fill="#374151"{rotate}>{_esc(lbl)}</text>')

    # reference line (e.g. regulatory floor)
    if reference_value is not None:
        ry = y(reference_value)
        parts.append(f'<line x1="{pad_l}" x2="{width-pad_r}" y1="{ry}" y2="{ry}" '
                     f'stroke="{RED}" stroke-width="1.5" stroke-dasharray="6,3"/>')
        parts.append(f'<text x="{width-pad_r}" y="{ry-4}" text-anchor="end" '
                     f'fill="{RED}" font-size="11">{_esc(reference_label or value_fmt(reference_value))}</text>')

    parts.append('</svg>')
    return "".join(parts)


def line_chart(
    x_labels: Sequence[str], series: dict[str, Sequence[float]], *,
    width: int = 720, height: int = 280, title: str = "",
    value_fmt=_fmt_pct, reference_value: float | None = None,
    reference_label: str = "",
) -> str:
    """Multi-series line chart with shared x-axis."""
    pad_l, pad_r, pad_t, pad_b = 70, 110, 36 if title else 16, 50
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    all_vals = [v for s in series.values() for v in s]
    if reference_value is not None: all_vals.append(reference_value)
    vmax = max(all_vals); vmin = min(all_vals)
    if vmax == vmin: vmax = vmin + 1
    span = vmax - vmin
    vmax += span * 0.08; vmin -= span * 0.08
    n = len(x_labels)
    def y(v): return pad_t + plot_h * (1 - (v - vmin) / (vmax - vmin))
    def x(i): return pad_l + (plot_w * (i / max(n - 1, 1)))

    parts = [_svg_open(width, height, title)]
    if title:
        parts.append(f'<text x="{(pad_l + width - pad_r)/2}" y="22" '
                     f'text-anchor="middle" font-weight="600" font-size="14">{_esc(title)}</text>')

    for i in range(5):
        gv = vmin + (vmax - vmin) * i / 4
        gy = y(gv)
        parts.append(f'<line x1="{pad_l}" x2="{width-pad_r}" y1="{gy}" y2="{gy}" '
                     f'stroke="#e5e7eb" stroke-width="1"/>')
        parts.append(f'<text x="{pad_l-6}" y="{gy+4}" text-anchor="end" '
                     f'fill="#374151">{_esc(value_fmt(gv))}</text>')

    # x axis labels — show ≤ 8
    step = max(1, n // 8)
    for i in range(0, n, step):
        parts.append(f'<text x="{x(i)}" y="{height-pad_b+18}" text-anchor="middle" '
                     f'fill="#374151">{_esc(x_labels[i])}</text>')

    if reference_value is not None:
        ry = y(reference_value)
        parts.append(f'<line x1="{pad_l}" x2="{width-pad_r}" y1="{ry}" y2="{ry}" '
                     f'stroke="{RED}" stroke-width="1.5" stroke-dasharray="6,3"/>')
        parts.append(f'<text x="{width-pad_r+4}" y="{ry+4}" '
                     f'fill="{RED}" font-size="11">{_esc(reference_label)}</text>')

    for k, (name, vals) in enumerate(series.items()):
        color = PALETTE[k % len(PALETTE)]
        path = " ".join(f"{'M' if i==0 else 'L'} {x(i):.1f} {y(v):.1f}"
                        for i, v in enumerate(vals))
        parts.append(f'<path d="{path}" fill="none" stroke="{color}" '
                     f'stroke-width="2"/>')
        for i, v in enumerate(vals):
            parts.append(f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="2.5" '
                         f'fill="{color}"/>')
        # legend
        ly = pad_t + 14 + k * 16
        parts.append(f'<rect x="{width-pad_r+6}" y="{ly-9}" width="10" height="10" '
                     f'fill="{color}"/>')
        parts.append(f'<text x="{width-pad_r+20}" y="{ly}" fill="#111827">'
                     f'{_esc(name)}</text>')

    parts.append('</svg>')
    return "".join(parts)


def stacked_bar(
    categories: Sequence[str], series: dict[str, Sequence[float]], *,
    width: int = 720, height: int = 240, title: str = "",
    value_fmt=_fmt_axis,
) -> str:
    """Vertical stacked bars: categories on x, sum on y."""
    pad_l, pad_r, pad_t, pad_b = 70, 130, 36 if title else 16, 50
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    n = len(categories)
    totals = [sum(series[k][i] for k in series) for i in range(n)]
    vmax = max(totals + [1])
    def y(v): return pad_t + plot_h * (1 - v / vmax)
    def x(i): return pad_l + (plot_w / n) * (i + 0.1)
    bar_w = plot_w / n * 0.8

    parts = [_svg_open(width, height, title)]
    if title:
        parts.append(f'<text x="{(pad_l + width - pad_r)/2}" y="22" '
                     f'text-anchor="middle" font-weight="600" font-size="14">{_esc(title)}</text>')
    for i in range(5):
        gv = vmax * i / 4; gy = y(gv)
        parts.append(f'<line x1="{pad_l}" x2="{width-pad_r}" y1="{gy}" y2="{gy}" '
                     f'stroke="#e5e7eb"/>')
        parts.append(f'<text x="{pad_l-6}" y="{gy+4}" text-anchor="end" '
                     f'fill="#374151">{_esc(value_fmt(gv))}</text>')

    keys = list(series.keys())
    for i, cat in enumerate(categories):
        running = 0
        for k, name in enumerate(keys):
            v = series[name][i]
            top = y(running + v); bot = y(running)
            color = PALETTE[k % len(PALETTE)]
            parts.append(f'<rect x="{x(i)}" y="{top}" width="{bar_w}" '
                         f'height="{max(bot-top, 0.5)}" fill="{color}" opacity="0.9"/>')
            running += v
        parts.append(f'<text x="{x(i)+bar_w/2}" y="{height-pad_b+18}" '
                     f'text-anchor="middle" fill="#374151">{_esc(cat)}</text>')

    for k, name in enumerate(keys):
        ly = pad_t + 14 + k * 16
        parts.append(f'<rect x="{width-pad_r+6}" y="{ly-9}" width="10" height="10" '
                     f'fill="{PALETTE[k % len(PALETTE)]}"/>')
        parts.append(f'<text x="{width-pad_r+20}" y="{ly}" fill="#111827">'
                     f'{_esc(name)}</text>')

    parts.append('</svg>')
    return "".join(parts)


def donut_chart(
    labels: Sequence[str], values: Sequence[float], *,
    width: int = 380, height: int = 240, title: str = "",
    center_label: str = "",
) -> str:
    import math
    cx, cy, r_outer, r_inner = 110, height/2 + (10 if title else 0), 92, 56
    total = sum(values) or 1
    parts = [_svg_open(width, height, title)]
    if title:
        parts.append(f'<text x="{width/2}" y="22" text-anchor="middle" '
                     f'font-weight="600" font-size="14">{_esc(title)}</text>')
    start = -math.pi / 2
    for k, (lbl, v) in enumerate(zip(labels, values)):
        if v <= 0: continue
        frac = v / total
        end = start + 2 * math.pi * frac
        x1 = cx + r_outer * math.cos(start); y1 = cy + r_outer * math.sin(start)
        x2 = cx + r_outer * math.cos(end);   y2 = cy + r_outer * math.sin(end)
        x3 = cx + r_inner * math.cos(end);   y3 = cy + r_inner * math.sin(end)
        x4 = cx + r_inner * math.cos(start); y4 = cy + r_inner * math.sin(start)
        large = 1 if frac > 0.5 else 0
        color = PALETTE[k % len(PALETTE)]
        d = (f"M {x1:.1f} {y1:.1f} A {r_outer} {r_outer} 0 {large} 1 {x2:.1f} {y2:.1f} "
             f"L {x3:.1f} {y3:.1f} A {r_inner} {r_inner} 0 {large} 0 {x4:.1f} {y4:.1f} Z")
        parts.append(f'<path d="{d}" fill="{color}" opacity="0.92"/>')
        # legend
        ly = (height - 14*len(labels)) / 2 + 14 * k + 10
        parts.append(f'<rect x="{220}" y="{ly-9}" width="10" height="10" '
                     f'fill="{color}"/>')
        parts.append(f'<text x="{235}" y="{ly}" fill="#111827">'
                     f'{_esc(lbl)} · {frac*100:.1f}%</text>')
        start = end
    if center_label:
        parts.append(f'<text x="{cx}" y="{cy-4}" text-anchor="middle" '
                     f'font-weight="700" font-size="14">{_esc(center_label.split(chr(10))[0])}</text>')
        rest = center_label.split('\n')[1:]
        for i, ln in enumerate(rest):
            parts.append(f'<text x="{cx}" y="{cy+12 + i*14}" text-anchor="middle" '
                         f'fill="#6b7280" font-size="11">{_esc(ln)}</text>')
    parts.append('</svg>')
    return "".join(parts)


def waterfall(
    labels: Sequence[str], values: Sequence[float], *,
    width: int = 720, height: int = 280, title: str = "",
    value_fmt=_fmt_axis,
) -> str:
    """Cumulative waterfall: first and last bars are totals, middle ones are deltas."""
    pad_l, pad_r, pad_t, pad_b = 80, 30, 36 if title else 16, 60
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    n = len(values)
    # running totals
    starts, ends = [], []
    run = 0.0
    for i, v in enumerate(values):
        if i == 0 or i == n - 1:
            starts.append(0); ends.append(v); run = v
        else:
            s = run; e = run + v; starts.append(min(s, e)); ends.append(max(s, e))
            run = e
    vmax = max(ends + [0]); vmin = min(starts + [0])
    span = vmax - vmin or 1
    vmax += span * 0.08
    def y(v): return pad_t + plot_h * (1 - (v - vmin) / (vmax - vmin))
    def x(i): return pad_l + (plot_w / n) * (i + 0.15)
    bar_w = plot_w / n * 0.7

    parts = [_svg_open(width, height, title)]
    if title:
        parts.append(f'<text x="{(pad_l + width - pad_r)/2}" y="22" '
                     f'text-anchor="middle" font-weight="600" font-size="14">{_esc(title)}</text>')
    for i in range(5):
        gv = vmin + (vmax - vmin) * i / 4; gy = y(gv)
        parts.append(f'<line x1="{pad_l}" x2="{width-pad_r}" y1="{gy}" y2="{gy}" '
                     f'stroke="#e5e7eb"/>')
        parts.append(f'<text x="{pad_l-6}" y="{gy+4}" text-anchor="end" '
                     f'fill="#374151">{_esc(value_fmt(gv))}</text>')

    for i, (lbl, v) in enumerate(zip(labels, values)):
        top, bot = y(ends[i]), y(starts[i])
        is_total = (i == 0 or i == n - 1)
        color = "#374151" if is_total else (GREEN if v >= 0 else RED)
        parts.append(f'<rect x="{x(i)}" y="{min(top, bot)}" width="{bar_w}" '
                     f'height="{max(abs(bot-top), 1)}" fill="{color}" opacity="0.85"/>')
        # connector
        if i < n - 1 and not (i == n - 2):
            cy = ends[i]
            parts.append(f'<line x1="{x(i)+bar_w}" x2="{x(i+1)}" y1="{y(cy)}" y2="{y(cy)}" '
                         f'stroke="#9ca3af" stroke-dasharray="3,3"/>')
        parts.append(f'<text x="{x(i)+bar_w/2}" y="{min(top, bot)-4}" '
                     f'text-anchor="middle" font-size="11" fill="#111827">'
                     f'{_esc(value_fmt(v))}</text>')
        parts.append(f'<text x="{x(i)+bar_w/2}" y="{height-pad_b+18}" '
                     f'text-anchor="middle" fill="#374151" font-size="11">{_esc(lbl)}</text>')
    parts.append('</svg>')
    return "".join(parts)


def horizontal_bar(
    labels: Sequence[str], values: Sequence[float], *,
    width: int = 720, height: int | None = None, title: str = "",
    value_fmt=_fmt_axis, color: str = PALETTE[0],
    reference_value: float | None = None, reference_label: str = "",
) -> str:
    n = len(values)
    row_h = 22
    if height is None:
        height = 30 + 24 * (1 if title else 0) + row_h * n + 30
    pad_l, pad_r, pad_t, pad_b = 160, 80, 36 if title else 12, 24
    plot_w = width - pad_l - pad_r
    vmax = max(list(values) + ([reference_value] if reference_value else [0]) + [0])
    vmin = min(list(values) + [0])
    if vmax == vmin: vmax = vmin + 1
    span = vmax - vmin or 1
    def x(v): return pad_l + plot_w * (v - vmin) / span

    parts = [_svg_open(width, height, title)]
    if title:
        parts.append(f'<text x="{width/2}" y="22" text-anchor="middle" '
                     f'font-weight="600" font-size="14">{_esc(title)}</text>')
    x0 = x(0)
    parts.append(f'<line x1="{x0}" x2="{x0}" y1="{pad_t}" y2="{height-pad_b}" '
                 f'stroke="#9ca3af"/>')
    for i, (lbl, v) in enumerate(zip(labels, values)):
        yc = pad_t + row_h * i + row_h / 2
        bx0, bx1 = (x0, x(v)) if v >= 0 else (x(v), x0)
        parts.append(f'<rect x="{bx0}" y="{yc-row_h/2+3}" width="{max(bx1-bx0,1)}" '
                     f'height="{row_h-6}" fill="{color}" opacity="0.9"/>')
        parts.append(f'<text x="{pad_l-8}" y="{yc+4}" text-anchor="end" '
                     f'fill="#374151">{_esc(lbl)}</text>')
        parts.append(f'<text x="{bx1+4 if v>=0 else bx0-4}" y="{yc+4}" '
                     f'text-anchor="{"start" if v>=0 else "end"}" '
                     f'fill="#111827" font-size="11">{_esc(value_fmt(v))}</text>')

    if reference_value is not None:
        rx = x(reference_value)
        parts.append(f'<line x1="{rx}" x2="{rx}" y1="{pad_t}" y2="{height-pad_b}" '
                     f'stroke="{RED}" stroke-dasharray="6,3" stroke-width="1.5"/>')
        parts.append(f'<text x="{rx+4}" y="{pad_t+10}" fill="{RED}" font-size="11">'
                     f'{_esc(reference_label)}</text>')
    parts.append('</svg>')
    return "".join(parts)


def gauge(
    value: float, *, vmin: float = 0, vmax: float = 1.5,
    title: str = "", width: int = 320, height: int = 200,
    thresholds: list[tuple[float, str]] | None = None,
    value_fmt=_fmt_pct,
) -> str:
    """Half-circle gauge with colored zones."""
    import math
    if thresholds is None:
        thresholds = [(0.5, RED), (0.8, AMBER), (1.0, AMBER), (vmax, GREEN)]
    cx, cy, r = width/2, height - 30, min(width/2 - 20, height - 40)
    def angle(v):
        v = max(min(v, vmax), vmin)
        return math.pi * (1 - (v - vmin) / (vmax - vmin))
    parts = [_svg_open(width, height, title)]
    if title:
        parts.append(f'<text x="{cx}" y="22" text-anchor="middle" '
                     f'font-weight="600" font-size="14">{_esc(title)}</text>')
    # zones
    last = vmin
    for upper, color in thresholds:
        a1, a2 = angle(last), angle(min(upper, vmax))
        x1 = cx + r * math.cos(a1); y1 = cy - r * math.sin(a1)
        x2 = cx + r * math.cos(a2); y2 = cy - r * math.sin(a2)
        x1i = cx + (r-20) * math.cos(a1); y1i = cy - (r-20) * math.sin(a1)
        x2i = cx + (r-20) * math.cos(a2); y2i = cy - (r-20) * math.sin(a2)
        large = 1 if abs(a1 - a2) > math.pi else 0
        d = (f"M {x1:.1f} {y1:.1f} A {r} {r} 0 {large} 0 {x2:.1f} {y2:.1f} "
             f"L {x2i:.1f} {y2i:.1f} A {r-20} {r-20} 0 {large} 1 {x1i:.1f} {y1i:.1f} Z")
        parts.append(f'<path d="{d}" fill="{color}" opacity="0.78"/>')
        last = upper
    # needle
    a = angle(value)
    nx = cx + (r-6) * math.cos(a); ny = cy - (r-6) * math.sin(a)
    parts.append(f'<line x1="{cx}" y1="{cy}" x2="{nx:.1f}" y2="{ny:.1f}" '
                 f'stroke="#111827" stroke-width="3"/>')
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="6" fill="#111827"/>')
    parts.append(f'<text x="{cx}" y="{cy-r-4}" text-anchor="middle" '
                 f'font-weight="700" font-size="16">{_esc(value_fmt(value))}</text>')
    parts.append('</svg>')
    return "".join(parts)
