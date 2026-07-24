"""Localization — English board pack for global / dual-listed institutions.

A Top-IB bank with US/EU listings or foreign board members needs an English
Risk Committee pack alongside the Korean one. This module produces a
condensed English board summary from the same PipelineResult, so the numbers
are identical and only the presentation language differs.

The English glossary maps the same acronyms used in the Korean report to
English one-liners, keeping the two versions consistent.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from risk_lib.html_report import CSS, _won, _pct, _esc


def _usd(krw: float, fx: float = 1350.0) -> str:
    """Convert KRW to a USD-equivalent string (indicative, fx configurable)."""
    usd = krw / fx
    a = abs(usd)
    if a >= 1e9:  return f"${usd/1e9:,.1f}bn"
    if a >= 1e6:  return f"${usd/1e6:,.0f}mn"
    return f"${usd:,.0f}"


_EN_GLOSSARY = [
    ("CET1", "Common Equity Tier 1 ratio — core capital / RWA, ≥4.5% min"),
    ("RWA", "Risk-Weighted Assets"),
    ("LCR", "Liquidity Coverage Ratio — HQLA / 30-day net outflow, ≥100%"),
    ("NSFR", "Net Stable Funding Ratio — ASF / RSF, ≥100%"),
    ("IRRBB", "Interest Rate Risk in the Banking Book — ΔEVE / ΔNII"),
    ("ICAAP", "Internal Capital Adequacy Assessment Process (Pillar 2)"),
    ("ECL", "Expected Credit Loss (IFRS 9)"),
    ("CECL", "Current Expected Credit Losses (US GAAP ASC 326)"),
    ("RAF", "Risk Appetite Framework"),
    ("KRI", "Key Risk Indicator"),
    ("MDA", "Maximum Distributable Amount (buffer-breach distribution limit)"),
    ("SRISK", "Systemic capital shortfall in a severe stress"),
]


def _briefing_en(result, fx: float) -> str:
    """English CRO briefing — same derivations as the Korean narrative
    (html_exec.briefing_facts), so the two language editions cannot diverge."""
    from risk_lib.html_exec import briefing_facts
    f = briefing_facts(result)
    paras = []
    paras.append(
        f"<b>Capital</b> — CET1 {f['cet1']*100:.2f}%, "
        f"{f['cet1_surplus_pp']:+.2f}pp above requirement. The largest RWA "
        f"component is <b>{_esc(f['top_rwa_component'])}</b> "
        f"({f['top_rwa_share']*100:.0f}%), making its limit/growth management "
        f"the primary lever for ratio defence.")
    paras.append(
        f"<b>Provisions</b> — probability-weighted PIT ECL "
        f"{_usd(f['pit'], fx)} runs <b>{f['gap_pct']:+.0f}%</b> above TTC "
        f"{_usd(f['ttc'], fx)}; downside macro weights are pushing allowances "
        f"up and should be pre-funded in the quarterly plan.")
    red_txt = (" RAF RED: " + ", ".join(_esc(n) for n in f["raf_red"]) + "."
               if f["raf_red"] else "")
    paras.append(
        f"<b>Concentration</b> — the most concentrated dimension is "
        f"<b>{_esc(f['conc_dim'])}</b> (HHI {f['conc_hhi']:.3f}, top bucket "
        f"{f['conc_top1']*100:.0f}%).{red_txt}")
    if f["sev"]:
        s = f["sev"]
        ratio_label = {"cet1": "CET1", "tier1": "Tier 1",
                       "total": "Total capital"}.get(s.get("breach_ratio") or "",
                                                     "capital")
        breach = (f"first <b>{_esc(ratio_label)}</b> requirement breach in "
                  f"<b>{_esc(s['first_breach'])}</b>, "
                  if s["first_breach"] else "no breach of the requirement, ")
        paras.append(
            f"<b>Stress resilience</b> — under the severely adverse scenario "
            f"CET1 troughs at <b>{s['trough']*100:.2f}%</b> "
            f"({_esc(s['trough_q'])}), {breach}recovering to "
            f"{s['end']*100:.2f}% by horizon end. Reverse-stress critical "
            f"severity s={f['rev_severity']:.2f} (implied GDP "
            f"{f['rev_gdp']:+.1%}).")
    paras.append(
        f"<b>Liquidity</b> — LCR {f['lcr']*100:.1f}% / NSFR "
        f"{f['nsfr']*100:.1f}% (minimum 100% each); LCR sits in the "
        f"early-warning band and HQLA burn-rate is monitored intraday.")
    if f["raf_amber"]:
        paras.append(
            "<b>AMBER escalations</b> — " +
            ", ".join(f"{_esc(n)} ({v})" for n, v in f["raf_amber"]) +
            " breach management thresholds and are escalated.")
    return "".join(f'<p style="margin:8px 0; line-height:1.6;">{p}</p>'
                   for p in paras)


def build_english_board_pack(result, out_path, *,
                             meeting_date: str = "", fx: float = 1350.0) -> str:
    """Condensed English Risk Committee summary."""
    if not meeting_date:
        meeting_date = date.today().isoformat()

    v = result.validation
    summ = v.summary()
    passes = v.passes()
    verdict = "APPROVED (PASS)" if passes else "NOT APPROVED (FAIL present)"
    raf_worst = result.raf.worst() if result.raf else "-"
    bis = result.bis
    lev = result.leverage
    lcr = result.alm["lcr"]
    nsfr = result.alm["nsfr"]
    irrbb = result.alm["irrbb"]

    def _row(label, actual, req, ok):
        tone = "#1f7437" if ok else "#a3160d"
        return (f'<tr><td>{label}</td>'
                f'<td style="text-align:right;color:{tone};font-weight:700">{actual}</td>'
                f'<td style="text-align:right">{req}</td></tr>')

    capital_rows = "".join([
        _row("CET1 ratio", _pct(bis.cet1_ratio), _pct(bis.required["cet1"]),
             bis.cet1_ratio >= bis.required["cet1"]),
        _row("Tier 1 ratio", _pct(bis.tier1_ratio), _pct(bis.required["tier1"]),
             bis.tier1_ratio >= bis.required["tier1"]),
        _row("Total capital ratio", _pct(bis.total_ratio), _pct(bis.required["total"]),
             bis.total_ratio >= bis.required["total"]),
        _row("Leverage ratio", _pct(lev.leverage_ratio), "3.00%",
             lev.leverage_ratio >= 0.03),
        _row("LCR", _pct(lcr.lcr, 1), "100%", lcr.passes()),
        _row("NSFR", _pct(nsfr.nsfr, 1), "100%", nsfr.passes()),
        _row("IRRBB ΔEVE / Tier1", _pct(irrbb.worst_pct_tier1),
             "≤15%", not irrbb.outlier()),
    ])

    # top actions
    actions = []
    if result.raf:
        for k in result.raf.kris:
            if k.grade in ("RED", "AMBER"):
                actions.append(
                    f'<li><b>[{k.grade}] {_esc(k.name)}</b> — actual '
                    f'{k.actual:.4f} vs board limit {k.threshold.board:.4f} '
                    f'({_esc(k.category)})</li>')
    actions_html = "".join(actions[:6]) or "<li>No action items.</li>"

    glossary_rows = "".join(
        f'<tr><td style="font-family:monospace;font-weight:600">{_esc(a)}</td>'
        f'<td>{_esc(d)}</td></tr>' for a, d in _EN_GLOSSARY)

    rwa = result.rwa
    body = f"""
<h1 class="title">Risk Committee Pack — Executive Summary (EN)</h1>
<p class="section-lead">As of {_esc(date.today().isoformat())} · seed
{result.meta.get('seed', '-')} · Basel III + IFRS 9 + FSS regulations ·
FX ref {fx:,.0f} KRW/USD (indicative)</p>

<div class="card">
<h2>0. Verdict</h2>
<p style="font-size:16px;font-weight:700">{_esc(verdict)}</p>
<p>Self-validation: PASS {summ.get('PASS',0)} / WARN {summ.get('WARN',0)} /
FAIL {summ.get('FAIL',0)} · RAF worst grade {_esc(raf_worst)} ·
ICAAP grade {_esc(result.icaap.grade if result.icaap else '-')}</p>
</div>

<div class="card">
<h2>1. Capital & Liquidity Position</h2>
<table class="t"><thead><tr><th>Metric</th><th style="text-align:right">Actual</th>
<th style="text-align:right">Requirement</th></tr></thead>
<tbody>{capital_rows}</tbody></table>
<p class="section-lead">Final RWA {_won(rwa['final_total'])} ({_usd(rwa['final_total'], fx)}).</p>
</div>

<div class="card">
<h2>2. Top Action Items</h2>
<ul>{actions_html}</ul>
</div>

<div class="card">
<h2>2-b. CRO Briefing</h2>
{_briefing_en(result, fx)}
</div>

<div class="card">
<h2>3. Stress & Reverse Stress</h2>
<p>Reverse-stress critical severity s = <b>{result.reverse_stress.critical_severity:.2f}</b>
(implied GDP {result.reverse_stress.implied_gdp_shock:+.1%},
LGD +{result.reverse_stress.implied_lgd_addon:.1%}pp).</p>
</div>

<div class="card">
<h2>4. Reproducibility</h2>
<p style="font-family:monospace;font-size:11px">
Every figure is reproducible via the manifest digest.<br>
<code>python -m risk_lib.cli reproduce --manifest manifest.json</code></p>
</div>

<div class="card">
<h2>Glossary</h2>
<table class="t"><thead><tr><th>Acronym</th><th>Definition</th></tr></thead>
<tbody>{glossary_rows}</tbody></table>
</div>
"""
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"/>
<title>Risk Committee Pack (EN) — {_esc(meeting_date)}</title>
<style>{CSS}</style></head>
<body>
<header class="top"><div class="wrap">
<h1>Risk Committee Pack — {_esc(meeting_date)}</h1>
<div class="meta">English executive summary · risk_lib v0.27</div>
</div></header>
<div class="container">{body}</div>
<footer>risk_lib v0.27 · English board pack</footer>
</body></html>"""
    p = Path(out_path); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(doc, encoding="utf-8")
    return str(p.resolve())
