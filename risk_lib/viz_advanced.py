"""Advanced inline-SVG visualisations: heatmap, fan chart, treemap, sankey,
KRI scorecard, attribution waterfall.

Same self-contained style as risk_lib.viz — no external dependencies.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from risk_lib.viz import (
    PALETTE, GREEN, RED, AMBER, GREY, _svg_open, _esc, _fmt_axis, _fmt_pct,
)


# ---------------------------------------------------------------- heatmap

def heatmap(
    rows: Sequence[str], cols: Sequence[str],
    matrix: Sequence[Sequence[float]], *,
    width: int = 720, height: int | None = None, title: str = "",
    value_fmt=lambda v: f"{v:.2f}", diverging: bool = False,
    vmin: float | None = None, vmax: float | None = None,
    cell_label: bool = True,
) -> str:
    """2D heatmap. `diverging=True` uses a red-white-green palette centred on 0."""
    n_rows, n_cols = len(rows), len(cols)
    cell_w = min(80, (width - 200) / max(n_cols, 1))
    cell_h = 28
    if height is None:
        height = 60 + cell_h * n_rows + 40
    pad_l = 150
    pad_t = 40 if title else 16

    flat = [v for r in matrix for v in r]
    vmax = vmax if vmax is not None else max(flat + [0])
    vmin = vmin if vmin is not None else min(flat + [0])
    if vmax == vmin: vmax = vmin + 1

    def color(v):
        if diverging:
            # red for negative, green for positive, white at 0
            span = max(abs(vmin), abs(vmax)) or 1
            t = max(-1, min(1, v / span))
            if t >= 0:
                # white → green
                g = int(45 + (200 - 45) * (1 - t))  # white=255, green=darker
                return f"rgb({g},{200 + int(40 * (1-t))},{g})"
            t = -t
            r = int(245); g = int(245 - 100 * t); b = int(245 - 100 * t)
            return f"rgb({r},{g},{b})"
        # sequential blue
        t = (v - vmin) / (vmax - vmin)
        r = int(245 - 168 * t); g = int(245 - 121 * t); b = int(245 - 51 * t)
        return f"rgb({r},{g},{b})"

    parts = [_svg_open(width, height, title)]
    if title:
        parts.append(f'<text x="{width/2}" y="22" text-anchor="middle" '
                     f'font-weight="600" font-size="14">{_esc(title)}</text>')

    # column headers
    for j, c in enumerate(cols):
        cx = pad_l + cell_w * (j + 0.5)
        parts.append(f'<text x="{cx}" y="{pad_t}" text-anchor="middle" '
                     f'fill="#374151" font-size="11">{_esc(c)}</text>')
    # rows
    for i, r_lbl in enumerate(rows):
        y = pad_t + 6 + cell_h * i
        parts.append(f'<text x="{pad_l-8}" y="{y+cell_h/2+4}" text-anchor="end" '
                     f'fill="#374151">{_esc(r_lbl)}</text>')
        for j, c_lbl in enumerate(cols):
            x = pad_l + cell_w * j
            v = matrix[i][j]
            parts.append(f'<rect x="{x}" y="{y}" width="{cell_w-1}" '
                         f'height="{cell_h-1}" fill="{color(v)}"/>')
            if cell_label:
                parts.append(f'<text x="{x+cell_w/2}" y="{y+cell_h/2+4}" '
                             f'text-anchor="middle" font-size="11" '
                             f'fill="#111827">{_esc(value_fmt(v))}</text>')
    parts.append('</svg>')
    return "".join(parts)


# ---------------------------------------------------------------- fan chart

def fan_chart(
    x_labels: Sequence[str],
    baseline: Sequence[float],
    lower_band: Sequence[float],
    upper_band: Sequence[float], *,
    extra_series: dict[str, Sequence[float]] | None = None,
    width: int = 720, height: int = 280, title: str = "",
    value_fmt=_fmt_pct,
    reference_value: float | None = None, reference_label: str = "",
) -> str:
    """Single baseline line with a shaded band (e.g. adverse..severe envelope)."""
    pad_l, pad_r, pad_t, pad_b = 70, 130, 36 if title else 16, 50
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    n = len(x_labels)
    all_vals = list(baseline) + list(lower_band) + list(upper_band)
    if extra_series:
        for s in extra_series.values(): all_vals += list(s)
    if reference_value is not None: all_vals.append(reference_value)
    vmax = max(all_vals); vmin = min(all_vals)
    if vmax == vmin: vmax = vmin + 1
    span = vmax - vmin
    vmax += span * 0.08; vmin -= span * 0.08

    def y(v): return pad_t + plot_h * (1 - (v - vmin) / (vmax - vmin))
    def x(i): return pad_l + (plot_w * (i / max(n - 1, 1)))

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

    step = max(1, n // 8)
    for i in range(0, n, step):
        parts.append(f'<text x="{x(i)}" y="{height-pad_b+18}" '
                     f'text-anchor="middle" fill="#374151">{_esc(x_labels[i])}</text>')

    # band polygon
    up = " ".join(f"{x(i):.1f},{y(upper_band[i]):.1f}" for i in range(n))
    down = " ".join(f"{x(i):.1f},{y(lower_band[i]):.1f}" for i in range(n-1, -1, -1))
    parts.append(f'<polygon points="{up} {down}" fill="{PALETTE[0]}" '
                 f'opacity="0.18"/>')

    # baseline
    path = " ".join(f"{'M' if i==0 else 'L'} {x(i):.1f} {y(baseline[i]):.1f}"
                    for i in range(n))
    parts.append(f'<path d="{path}" fill="none" stroke="{PALETTE[0]}" '
                 f'stroke-width="2"/>')

    # legend
    parts.append(f'<rect x="{width-pad_r+6}" y="20" width="10" height="10" '
                 f'fill="{PALETTE[0]}"/>')
    parts.append(f'<text x="{width-pad_r+20}" y="29" fill="#111827">기준선</text>')
    parts.append(f'<rect x="{width-pad_r+6}" y="36" width="10" height="10" '
                 f'fill="{PALETTE[0]}" opacity="0.3"/>')
    parts.append(f'<text x="{width-pad_r+20}" y="45" fill="#111827">불확실성 밴드</text>')

    if extra_series:
        for k, (name, vals) in enumerate(extra_series.items()):
            color = [RED, AMBER, GREEN][k % 3]
            path2 = " ".join(f"{'M' if i==0 else 'L'} {x(i):.1f} {y(vals[i]):.1f}"
                             for i in range(n))
            parts.append(f'<path d="{path2}" fill="none" stroke="{color}" '
                         f'stroke-width="1.5" stroke-dasharray="4,3"/>')
            ly = 56 + k * 14
            parts.append(f'<line x1="{width-pad_r+6}" x2="{width-pad_r+16}" '
                         f'y1="{ly+5}" y2="{ly+5}" stroke="{color}" stroke-dasharray="4,3" stroke-width="1.5"/>')
            parts.append(f'<text x="{width-pad_r+20}" y="{ly+9}" fill="#111827">'
                         f'{_esc(name)}</text>')

    if reference_value is not None:
        ry = y(reference_value)
        parts.append(f'<line x1="{pad_l}" x2="{width-pad_r}" y1="{ry}" y2="{ry}" '
                     f'stroke="{RED}" stroke-width="1.5" stroke-dasharray="6,3"/>')
        parts.append(f'<text x="{width-pad_r+4}" y="{ry+4}" '
                     f'fill="{RED}" font-size="11">{_esc(reference_label)}</text>')

    parts.append('</svg>')
    return "".join(parts)


# ---------------------------------------------------------------- treemap

def treemap(
    labels: Sequence[str], values: Sequence[float], *,
    width: int = 720, height: int = 320, title: str = "",
    value_fmt=_fmt_axis,
) -> str:
    """Simple squarified treemap."""
    total = sum(values) or 1
    pad_t = 36 if title else 12
    plot_h = height - pad_t - 12
    items = sorted(zip(labels, values), key=lambda x: -x[1])

    parts = [_svg_open(width, height, title)]
    if title:
        parts.append(f'<text x="{width/2}" y="22" text-anchor="middle" '
                     f'font-weight="600" font-size="14">{_esc(title)}</text>')

    # squarified: simple row-wise greedy layout
    remaining = list(items)
    x0, y0, w, h = 0, pad_t, width, plot_h
    color_idx = 0
    while remaining:
        # take a row's worth: items totaling ~ w/h fraction
        row = [remaining.pop(0)]
        row_sum = row[0][1]
        target_area = (total - sum(v for _, v in remaining) - row_sum) * (w * h) / total
        while remaining and (remaining[0][1] / total) * w * h > 800:
            row.append(remaining.pop(0))
            row_sum += row[-1][1]
            if len(row) >= 4: break
        row_h = max(min(plot_h, row_sum / total * w * h / w), 30)
        cx = x0
        for lbl, v in row:
            cw = (v / row_sum) * w
            color = PALETTE[color_idx % len(PALETTE)]
            color_idx += 1
            parts.append(f'<rect x="{cx}" y="{y0}" width="{cw-1}" '
                         f'height="{row_h-1}" fill="{color}" opacity="0.92"/>')
            if cw > 60 and row_h > 24:
                parts.append(f'<text x="{cx+6}" y="{y0+16}" '
                             f'font-size="11" font-weight="600" fill="#fff">{_esc(lbl)}</text>')
                parts.append(f'<text x="{cx+6}" y="{y0+30}" '
                             f'font-size="11" fill="#fff">{_esc(value_fmt(v))}</text>')
            cx += cw
        y0 += row_h
        h = max(plot_h - (y0 - pad_t), 0)
        if h <= 1: break
    parts.append('</svg>')
    return "".join(parts)


# ---------------------------------------------------------------- KRI scorecard grid

def kri_scorecard(kri_rows: list[dict], *, width: int = 1000) -> str:
    """Compact card-grid scorecard for the executive summary.

    Each row is `{name, category, actual_text, grade, distance_text, threshold_text}`.
    Grade colors: GREEN good, WATCH amber-light, AMBER amber-dark, RED bad.
    """
    cols = 3
    card_w = (width - 24) / cols - 12
    card_h = 110
    rows = (len(kri_rows) + cols - 1) // cols
    height = rows * (card_h + 12) + 16

    parts = [_svg_open(width, height, "KRI Scorecard")]
    color_map = {"GREEN": GREEN, "WATCH": "#88a4c2",
                 "AMBER": AMBER, "RED": RED}
    bg_map = {"GREEN": "#e6f3ec", "WATCH": "#e7eef6",
              "AMBER": "#fbecd0", "RED": "#fcdedb"}
    for i, k in enumerate(kri_rows):
        r, c = divmod(i, cols)
        x = 12 + c * (card_w + 12)
        y = 12 + r * (card_h + 12)
        grade = k["grade"]
        parts.append(f'<rect x="{x}" y="{y}" width="{card_w}" height="{card_h}" '
                     f'rx="6" fill="{bg_map.get(grade, "#f3f4f6")}" stroke="{color_map.get(grade, GREY)}" stroke-width="1.5"/>')
        parts.append(f'<text x="{x+12}" y="{y+22}" font-size="11" '
                     f'fill="#6b7280">{_esc(k.get("category",""))}</text>')
        parts.append(f'<text x="{x+12}" y="{y+44}" font-size="13" '
                     f'font-weight="700" fill="#1f2937">{_esc(k["name"])}</text>')
        parts.append(f'<text x="{x+12}" y="{y+72}" font-size="20" '
                     f'font-weight="700" fill="{color_map.get(grade, GREY)}">{_esc(k["actual_text"])}</text>')
        parts.append(f'<text x="{x+12}" y="{y+92}" font-size="10" '
                     f'fill="#6b7280">{_esc(k.get("threshold_text", ""))}</text>')
        parts.append(f'<rect x="{x+card_w-58}" y="{y+12}" width="48" height="20" '
                     f'rx="10" fill="{color_map.get(grade, GREY)}"/>')
        parts.append(f'<text x="{x+card_w-34}" y="{y+27}" text-anchor="middle" '
                     f'font-size="11" font-weight="600" fill="#fff">{_esc(grade)}</text>')
    parts.append('</svg>')
    return "".join(parts)


# ---------------------------------------------------------------- attribution waterfall (alt)

def attribution_waterfall(
    labels: Sequence[str], deltas: Sequence[float], start_value: float, *,
    end_value: float | None = None,
    width: int = 760, height: int = 300, title: str = "",
    value_fmt=_fmt_axis,
) -> str:
    """Waterfall built for bridge analyses: shows start, each delta (signed),
    and the implied end. Positive=green, negative=red, totals=grey."""
    cumulative = [start_value]
    for d in deltas:
        cumulative.append(cumulative[-1] + d)
    if end_value is None:
        end_value = cumulative[-1]

    all_labels = ["기초"] + list(labels) + ["기말"]
    all_vals   = [start_value] + list(deltas) + [end_value]

    pad_l, pad_r, pad_t, pad_b = 80, 30, 36 if title else 12, 60
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    n = len(all_labels)

    vmax = max(cumulative + [end_value])
    vmin = min(cumulative + [end_value, 0])
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

    for i, (lbl, v) in enumerate(zip(all_labels, all_vals)):
        if i == 0:
            top, bot = y(start_value), y(0)
            color = GREY
        elif i == n - 1:
            top, bot = y(end_value), y(0)
            color = GREY
        else:
            d = v  # delta
            base = cumulative[i - 1]
            top, bot = y(base + d), y(base)
            color = GREEN if d >= 0 else RED
        parts.append(f'<rect x="{x(i)}" y="{min(top, bot)}" width="{bar_w}" '
                     f'height="{max(abs(bot-top), 1)}" fill="{color}" opacity="0.85"/>')
        # connector
        if 0 < i < n - 1:
            prev_y = y(cumulative[i - 1])
            parts.append(f'<line x1="{x(i-1)+bar_w}" x2="{x(i)}" y1="{prev_y}" y2="{prev_y}" '
                         f'stroke="#9ca3af" stroke-dasharray="3,3"/>')
        if i == n - 1 and len(cumulative) > 1:
            prev_y = y(cumulative[-1])
            parts.append(f'<line x1="{x(i-1)+bar_w}" x2="{x(i)}" y1="{prev_y}" y2="{prev_y}" '
                         f'stroke="#9ca3af" stroke-dasharray="3,3"/>')

        label_v = v if (i == 0 or i == n - 1) else v
        parts.append(f'<text x="{x(i)+bar_w/2}" y="{min(top, bot)-4}" '
                     f'text-anchor="middle" font-size="11" fill="#111827">'
                     f'{_esc(value_fmt(label_v))}</text>')
        parts.append(f'<text x="{x(i)+bar_w/2}" y="{height-pad_b+18}" '
                     f'text-anchor="middle" fill="#374151" font-size="11">'
                     f'<tspan>{_esc(lbl)}</tspan></text>')

    parts.append('</svg>')
    return "".join(parts)
