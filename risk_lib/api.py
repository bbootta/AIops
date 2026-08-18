"""JSON export + minimal stdlib HTTP API.

`export_json(result, manifest, out_dir)` writes a structured JSON dump of all
headline aggregates, RAF, validation, sensitivity, attribution, ALM, ICAAP,
and the deep-dive tables — suitable for any downstream BI/datalake.

`serve(result, manifest, host, port)` runs a stdlib http.server with:
  GET /healthz                → {"status":"ok"}
  GET /                       → endpoint index
  GET /headline               → headline aggregates
  GET /raf                    → KRI scorecard with grades and thresholds
  GET /validation             → self-verification check list
  GET /alm/lcr                → LCR detail
  GET /alm/nsfr               → NSFR detail
  GET /alm/irrbb              → IRRBB scenarios + delta_eve table
  GET /icaap                  → economic capital and grade
  GET /sensitivity/oneF       → 1F shock grid
  GET /climate                → climate scenarios summary
  GET /manifest               → manifest digest + portfolio fingerprint
  GET /alerts                 → notification bundle
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any


def _to_jsonable(obj: Any) -> Any:
    """Recursively convert numpy/pandas/dataclass values into JSON types."""
    import numpy as np
    import pandas as pd
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return [_to_jsonable(x) for x in obj.tolist()]
    if isinstance(obj, pd.DataFrame):
        return [{k: _to_jsonable(v) for k, v in r.items()}
                for r in obj.to_dict(orient="records")]
    if isinstance(obj, pd.Series):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if is_dataclass(obj):
        return _to_jsonable(asdict(obj))
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(x) for x in obj]
    # Fallback — everything else gets stringified
    return str(obj)


# ---------------------------------------------------------------- endpoints

def endpoint_headline(result) -> dict[str, Any]:
    return _to_jsonable({
        "rwa": {k: v for k, v in result.rwa.items() if k not in
                ("output_floor", "market_detail", "op_detail")},
        "bis": {"cet1": result.bis.cet1_ratio, "tier1": result.bis.tier1_ratio,
                "total": result.bis.total_ratio, "rwa": result.bis.rwa,
                "required": result.bis.required,
                "surplus": result.bis.surplus_shortfall,
                "passes": result.bis.passes()},
        "leverage": {"ratio": result.leverage.leverage_ratio,
                     "exposure": result.leverage.exposure_measure,
                     "required": result.leverage.required,
                     "passes": result.leverage.passes()},
        "ecl_ttc": result.ecl["total"],
        "ecl_pit_weighted": result.macro_ecl.weighted_total,
        "lcr": result.alm["lcr"].lcr,
        "nsfr": result.alm["nsfr"].nsfr,
        "irrbb_worst_pct_tier1": result.alm["irrbb"].worst_pct_tier1,
        "irrbb_worst_scenario": result.alm["irrbb"].worst_eve_scenario,
        "icaap_utilisation": result.icaap.utilisation,
        "icaap_grade": result.icaap.grade,
        "reverse_stress_severity": result.reverse_stress.critical_severity,
    })


def endpoint_raf(result) -> dict[str, Any]:
    raf = result.raf
    return _to_jsonable({
        "worst": raf.worst(),
        "summary": raf.summary(),
        "kris": [{"name": k.name, "category": k.category,
                  "actual": k.actual, "grade": k.grade,
                  "board": k.threshold.board,
                  "management": k.threshold.management,
                  "operational": k.threshold.operational,
                  "direction": k.threshold.direction,
                  "fmt": k.fmt, "citation": k.citation}
                 for k in raf.kris],
    })


def endpoint_validation(result) -> dict[str, Any]:
    return _to_jsonable({
        "passes": result.validation.passes(),
        "summary": result.validation.summary(),
        "checks": [{"name": c.name, "status": c.status, "detail": c.detail,
                    "metric": c.metric}
                   for c in result.validation.checks],
    })


def endpoint_alm(result, leg: str) -> dict[str, Any]:
    alm = result.alm
    if leg == "lcr":
        lcr = alm["lcr"]
        return _to_jsonable({
            "lcr": lcr.lcr, "passes": lcr.passes(),
            "hqla_total": lcr.hqla_total,
            "hqla_detail": lcr.hqla_detail,
            "outflows": lcr.outflows,
            "inflows": lcr.inflows,
            "gross_outflow": lcr.gross_outflow,
            "inflow_capped": lcr.inflow_capped,
            "net_outflow": lcr.net_outflow,
        })
    if leg == "nsfr":
        n = alm["nsfr"]
        return _to_jsonable({
            "nsfr": n.nsfr, "passes": n.passes(),
            "asf_total": n.asf_total, "rsf_total": n.rsf_total,
            "asf": n.asf, "rsf": n.rsf,
        })
    if leg == "irrbb":
        i = alm["irrbb"]
        return _to_jsonable({
            "worst_eve_decline": i.worst_eve_decline,
            "worst_eve_scenario": i.worst_eve_scenario,
            "worst_pct_tier1": i.worst_pct_tier1,
            "outlier_test_passes": not i.outlier(),
            "delta_eve": i.delta_eve, "delta_nii": i.delta_nii,
            "repricing": i.repricing,
        })
    raise KeyError(f"unknown alm leg: {leg}")


def endpoint_icaap(result) -> dict[str, Any]:
    ic = result.icaap
    return _to_jsonable({
        "grade": ic.grade, "utilisation": ic.utilisation,
        "ec_by_type": ic.ec_by_type,
        "ec_standalone_sum": ic.ec_standalone_sum,
        "ec_diversified": ic.ec_diversified,
        "diversification_benefit": ic.diversification_benefit,
        "concentration_addon": ic.concentration_addon,
        "available_capital": ic.available_capital,
        "buffer": ic.buffer,
    })


def endpoint_sensitivity(result) -> dict[str, Any]:
    return _to_jsonable({
        "one_factor": result.sensitivity["one_factor"],
        "two_factor": result.sensitivity["two_factor"],
    })


def endpoint_climate(result) -> dict[str, Any]:
    cl = result.climate
    return _to_jsonable({
        "worst_transition": cl.worst_transition,
        "worst_physical": cl.worst_physical,
        "transition": [{"scenario": l.scenario, "narrative": l.narrative,
                        "total_ear": l.total_ear, "base_ecl": l.base_ecl,
                        "climate_ecl": l.climate_ecl, "uplift": l.uplift,
                        "by_sector": l.by_sector}
                       for l in cl.transition],
        "physical": [{"scenario": l.scenario, "narrative": l.narrative,
                       "total_ear": l.total_ear, "base_ecl": l.base_ecl,
                       "climate_ecl": l.climate_ecl, "uplift": l.uplift,
                       "by_sector": l.by_sector}
                      for l in cl.physical],
    })


def endpoint_manifest(manifest) -> dict[str, Any]:
    if manifest is None:
        return {"error": "no manifest attached"}
    return {"headline_digest": manifest.headline_digest,
            "portfolio_sha256": manifest.portfolio["sha256"],
            "portfolio_rows": manifest.portfolio["n_rows"],
            "ead_total": manifest.portfolio["ead_total"],
            "parameters": manifest.parameters,
            "code": manifest.code,
            "environment": manifest.environment,
            "timing": manifest.timing,
            "validation": manifest.validation}


def endpoint_alerts(result, manifest=None) -> dict[str, Any]:
    from risk_lib.notifications import collect_alerts
    b = collect_alerts(result)
    if manifest:
        b.headline_digest = manifest.headline_digest
    return _to_jsonable({
        "verdict": b.verdict, "summary": b.summary,
        "raf_summary": b.raf_summary,
        "worst_severity": b.worst_severity(),
        "asof": b.asof, "seed": b.seed,
        "headline_digest": b.headline_digest,
        "alerts": [asdict(a) for a in b.alerts],
    })


# ---------------------------------------------------------------- exporter

def export_json(result, out_dir, *, manifest=None) -> dict[str, str]:
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    files = {
        "headline.json":    endpoint_headline(result),
        "raf.json":         endpoint_raf(result),
        "validation.json":  endpoint_validation(result),
        "alm_lcr.json":     endpoint_alm(result, "lcr"),
        "alm_nsfr.json":    endpoint_alm(result, "nsfr"),
        "alm_irrbb.json":   endpoint_alm(result, "irrbb"),
        "icaap.json":       endpoint_icaap(result),
        "sensitivity.json": endpoint_sensitivity(result),
        "climate.json":     endpoint_climate(result),
        "alerts.json":      endpoint_alerts(result, manifest),
        "manifest.json":    endpoint_manifest(manifest),
    }
    paths = {}
    for name, payload in files.items():
        p = out / name
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                      encoding="utf-8")
        paths[name] = str(p.resolve())
    return paths


# ---------------------------------------------------------------- HTTP server

ROUTES = {
    "/healthz":          lambda res, mf: {"status": "ok"},
    "/":                 lambda res, mf: {"endpoints": [
        "/healthz", "/", "/headline", "/raf", "/validation",
        "/alm/lcr", "/alm/nsfr", "/alm/irrbb",
        "/icaap", "/sensitivity", "/climate", "/manifest", "/alerts",
    ]},
    "/headline":         lambda res, mf: endpoint_headline(res),
    "/raf":              lambda res, mf: endpoint_raf(res),
    "/validation":       lambda res, mf: endpoint_validation(res),
    "/alm/lcr":          lambda res, mf: endpoint_alm(res, "lcr"),
    "/alm/nsfr":         lambda res, mf: endpoint_alm(res, "nsfr"),
    "/alm/irrbb":        lambda res, mf: endpoint_alm(res, "irrbb"),
    "/icaap":            lambda res, mf: endpoint_icaap(res),
    "/sensitivity":      lambda res, mf: endpoint_sensitivity(res),
    "/climate":          lambda res, mf: endpoint_climate(res),
    "/manifest":         lambda res, mf: endpoint_manifest(mf),
    "/alerts":           lambda res, mf: endpoint_alerts(res, mf),
}


def make_handler(result, manifest):
    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args): pass    # quiet
        def do_GET(self):
            route = self.path.split("?")[0].rstrip("/") or "/"
            handler = ROUTES.get(route)
            if handler is None:
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"error":"not found"}')
                return
            payload = handler(result, manifest)
            body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    return _Handler


def serve(result, *, manifest=None, host: str = "127.0.0.1", port: int = 8765):
    handler = make_handler(result, manifest)
    server = HTTPServer((host, port), handler)
    print(f"Serving risk_lib API on http://{host}:{port}/ — Ctrl-C to stop")
    server.serve_forever()
