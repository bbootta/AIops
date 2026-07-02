"""Tests for v0.5 extras: notifications, JSON API, PDF, comparison."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from risk_lib import generate_portfolio, run_pipeline

# `result` fixture: session-scoped shared — see conftest.py.


# ---- notifications -------------------------------------------------------

def test_alert_bundle_collects_non_green_kris(result):
    from risk_lib.notifications import collect_alerts
    b = collect_alerts(result)
    assert len(b.alerts) > 0
    # Every non-GREEN KRI in the RAF should map to an alert
    raf_non_green = [k for k in result.raf.kris if k.grade != "GREEN"]
    n_raf_alerts = sum(1 for a in b.alerts if a.category != "validation")
    assert n_raf_alerts == len(raf_non_green)


def test_alert_ordering_by_severity(result):
    from risk_lib.notifications import collect_alerts, _SEVERITY_ORDER
    b = collect_alerts(result)
    sevs = [_SEVERITY_ORDER.get(a.severity, 0) for a in b.alerts]
    assert sevs == sorted(sevs, reverse=True)


def test_slack_payload_structure(result):
    from risk_lib.notifications import collect_alerts, build_slack_payload
    b = collect_alerts(result)
    p = build_slack_payload(b)
    assert "blocks" in p and isinstance(p["blocks"], list)
    types = {blk["type"] for blk in p["blocks"]}
    assert "header" in types and "section" in types


def test_email_payload_has_subject_plain_html(result):
    from risk_lib.notifications import collect_alerts, build_email_payload
    em = build_email_payload(collect_alerts(result))
    assert "subject" in em and "plain" in em and "html" in em
    assert "<table" in em["html"]


def test_write_bundle_writes_5_files(tmp_path, result):
    from risk_lib.notifications import collect_alerts, write_bundle
    paths = write_bundle(collect_alerts(result), tmp_path)
    assert len(paths) == 5
    for p in paths.values():
        assert Path(p).exists() and Path(p).stat().st_size > 0


# ---- API / JSON exporter -------------------------------------------------

def test_export_json_writes_all_endpoints(tmp_path, result):
    from risk_lib.api import export_json
    paths = export_json(result, tmp_path)
    expected = {"headline.json", "raf.json", "validation.json", "alm_lcr.json",
                "alm_nsfr.json", "alm_irrbb.json", "icaap.json",
                "sensitivity.json", "climate.json", "alerts.json", "manifest.json"}
    assert set(paths) == expected
    for p in paths.values():
        json.loads(Path(p).read_text(encoding="utf-8"))    # parseable


def test_headline_endpoint_keys(result):
    from risk_lib.api import endpoint_headline
    h = endpoint_headline(result)
    for k in ("rwa", "bis", "leverage", "ecl_ttc", "lcr", "nsfr",
              "irrbb_worst_pct_tier1", "icaap_grade"):
        assert k in h


def test_raf_endpoint_kri_count_matches(result):
    from risk_lib.api import endpoint_raf
    r = endpoint_raf(result)
    assert len(r["kris"]) == len(result.raf.kris)
    assert r["worst"] == result.raf.worst()


def test_http_server_routes_smoke(result):
    """Boot the stdlib server on a free port, hit each route, assert 200."""
    import socket, threading, time, urllib.request
    from risk_lib.api import make_handler
    from http.server import HTTPServer

    s = socket.socket(); s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]; s.close()
    server = HTTPServer(("127.0.0.1", port), make_handler(result, None))
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        for route in ("/healthz", "/", "/headline", "/raf", "/validation",
                      "/alm/lcr", "/alm/nsfr", "/alm/irrbb",
                      "/icaap", "/sensitivity", "/climate", "/alerts"):
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}{route}", timeout=5) as resp:
                assert resp.status == 200
                json.loads(resp.read().decode("utf-8"))    # parseable
    finally:
        server.shutdown()


def test_http_server_404_on_unknown(result):
    import socket, threading, urllib.request, urllib.error
    from risk_lib.api import make_handler
    from http.server import HTTPServer
    s = socket.socket(); s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]; s.close()
    server = HTTPServer(("127.0.0.1", port), make_handler(result, None))
    t = threading.Thread(target=server.serve_forever, daemon=True); t.start()
    try:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/bogus", timeout=5)
            assert False, "should 404"
        except urllib.error.HTTPError as e:
            assert e.code == 404
    finally:
        server.shutdown()


# ---- printable HTML (browser Print-to-PDF source) -----------------------

def test_printable_html_renders_korean(tmp_path, result):
    """Korean characters must end up in the printable HTML as real UTF-8
    bytes — never escaped to ascii — so browser print rendering works."""
    from risk_lib.printable import build_printable_html
    out = tmp_path / "exec.html"
    build_printable_html(result, str(out))
    text = out.read_text(encoding="utf-8")
    # Critical Korean phrases must appear literally
    for needle in ("결재 가능", "리스크관리", "PDF로 저장", "스트레스"):
        assert needle in text, f"missing literal Korean: {needle}"
    # @page rule and Korean-capable font stack
    assert "@page" in text
    assert "Apple SD Gothic Neo" in text or "Malgun Gothic" in text


def test_printable_html_includes_kri_scorecard_and_actions(tmp_path, result):
    from risk_lib.printable import build_printable_html
    out = tmp_path / "exec.html"
    build_printable_html(result, str(out))
    text = out.read_text(encoding="utf-8")
    # SVG scorecard must be inline
    assert text.count("<svg") >= 3
    # Each non-GREEN RAF KRI must be reflected in the actions section
    raf_non_green = [k for k in result.raf.kris if k.grade != "GREEN"]
    if raf_non_green:
        assert any(k.name in text for k in raf_non_green)


def test_printable_html_includes_manifest_digest(tmp_path, result):
    from risk_lib.printable import build_printable_html
    from risk_lib.repro import build_manifest, now_utc
    p = generate_portfolio(seed=42)
    mf = build_manifest(portfolio=p, parameters={"seed": 42}, result=result,
                        start_utc=now_utc(), end_utc=now_utc())
    out = tmp_path / "exec.html"
    build_printable_html(result, str(out), manifest=mf)
    text = out.read_text(encoding="utf-8")
    assert mf.headline_digest[:24] in text


# ---- comparison ----------------------------------------------------------

def test_compare_results_self_zero_delta(result):
    from risk_lib.comparison import compare_results
    d = compare_results(result, result)
    assert abs(d.bis_change_pp) < 1e-9
    assert abs(d.rwa_change_krw) < 1.0
    assert abs(d.lcr_change_pp) < 1e-9


def test_compare_results_nonzero_delta(result):
    from risk_lib.comparison import compare_results
    other = run_pipeline(generate_portfolio(seed=99), seed=99)
    d = compare_results(result, other)
    # at least one of these should move
    assert any(abs(x) > 1e-6 for x in
               [d.bis_change_pp, d.lcr_change_pp, d.nsfr_change_pp,
                d.rwa_change_krw, d.ecl_change_krw])


def test_history_from_results(result):
    from risk_lib.comparison import history_from_results
    other = run_pipeline(generate_portfolio(seed=99), seed=99)
    h = history_from_results([("Q1", result), ("Q2", other)])
    assert len(h) == 2
    for col in ("cet1", "rwa_final", "lcr", "nsfr"):
        assert col in h.columns


def test_history_from_manifests(tmp_path, result):
    from risk_lib.comparison import history_from_manifests
    from risk_lib.repro import build_manifest, now_utc
    p = generate_portfolio(seed=42)
    mf1 = build_manifest(portfolio=p, parameters={"seed": 42}, result=result,
                          start_utc=now_utc(), end_utc=now_utc())
    other = run_pipeline(generate_portfolio(seed=99), seed=99)
    mf2 = build_manifest(portfolio=generate_portfolio(seed=99),
                          parameters={"seed": 99}, result=other,
                          start_utc=now_utc(), end_utc=now_utc())
    p1 = tmp_path / "Q1" / "manifest.json"; p1.parent.mkdir()
    p2 = tmp_path / "Q2" / "manifest.json"; p2.parent.mkdir()
    p1.write_text(mf1.to_json(), encoding="utf-8")
    p2.write_text(mf2.to_json(), encoding="utf-8")
    h = history_from_manifests([p1, p2])
    assert len(h) == 2
    assert {"Q1", "Q2"} == set(h["label"])


# ---- CLI ------------------------------------------------------------------

def test_cli_notify(tmp_path):
    from risk_lib.cli import main
    out = tmp_path / "alerts"
    rc = main(["notify", "--out", str(out), "--seed", "42"])
    # rc 2 if any RED alerts exist (which they do for default seed)
    assert rc in (0, 2)
    assert (out / "alert_slack.json").exists()
    assert (out / "alert_email.html").exists()


def test_cli_printable(tmp_path):
    from risk_lib.cli import main
    out = tmp_path / "exec.html"
    rc = main(["printable", "--out", str(out), "--seed", "42"])
    assert rc == 0
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "결재" in text and "@page" in text


def test_cli_export_json(tmp_path):
    from risk_lib.cli import main
    out = tmp_path / "json"
    rc = main(["export-json", "--out", str(out), "--seed", "42"])
    assert rc == 0
    assert (out / "headline.json").exists()
    headline = json.loads((out / "headline.json").read_text(encoding="utf-8"))
    assert "bis" in headline and "lcr" in headline


def test_cli_compare(tmp_path, capsys):
    from risk_lib.cli import main
    # build two manifests via the CLI
    a = tmp_path / "a"; b = tmp_path / "b"
    main(["report-set", "--out", str(a), "--seed", "42"])
    main(["report-set", "--out", str(b), "--seed", "99"])
    rc = main(["compare", "--manifests",
                str(a / "manifest.json"), str(b / "manifest.json"),
                "--out", str(tmp_path / "hist.csv")])
    assert rc == 0
    assert (tmp_path / "hist.csv").exists()
