"""Tests for external integrations (webhook + API spec)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from risk_lib.integrations import (
    WebhookDispatcher, WebhookResult, dispatch_alerts,
    build_rest_openapi, build_graphql_schema, write_api_specs,
    _ENDPOINTS,
)

# `result` fixture: session-scoped shared — see conftest.py.


# ----- webhook dispatch (dry-run only, no network) ------------------------

def test_dispatcher_dry_run_no_network():
    disp = WebhookDispatcher(url="https://example.com/hook", dry_run=True)
    res = disp.send({"text": "hello"})
    assert isinstance(res, WebhookResult)
    assert res.ok is True
    assert res.status is None
    assert res.request.method == "POST"
    assert res.request.url == "https://example.com/hook"
    assert json.loads(res.request.body) == {"text": "hello"}


def test_dispatcher_sets_content_type():
    disp = WebhookDispatcher(url="https://x", dry_run=True,
                             extra_headers={"X-Token": "abc"})
    res = disp.send({"a": 1})
    assert res.request.headers["Content-Type"] == "application/json"
    assert res.request.headers["X-Token"] == "abc"


def test_dispatch_alerts_builds_slack_payload(result):
    res = dispatch_alerts(result, "https://hooks.slack.com/x", dry_run=True)
    payload = json.loads(res.request.body)
    assert "blocks" in payload
    types = {b["type"] for b in payload["blocks"]}
    assert "header" in types


def test_dispatcher_bad_url_returns_error():
    """A non-dry-run to an unroutable host must fail gracefully, not raise."""
    disp = WebhookDispatcher(url="http://127.0.0.1:1/nope", timeout=0.5)
    res = disp.send({"a": 1})
    assert res.ok is False
    assert res.error is not None


# ----- OpenAPI ------------------------------------------------------------

def test_openapi_is_valid_3_1():
    spec = build_rest_openapi()
    assert spec["openapi"] == "3.1.0"
    assert "info" in spec and "paths" in spec
    # every declared endpoint present
    for ep in _ENDPOINTS:
        assert ep in spec["paths"]
        assert "get" in spec["paths"][ep]
    # JSON serialisable
    json.dumps(spec)


def test_openapi_operation_ids_unique():
    spec = build_rest_openapi()
    op_ids = [m["get"]["operationId"] for m in spec["paths"].values()]
    assert len(op_ids) == len(set(op_ids))


# ----- GraphQL ------------------------------------------------------------

def test_graphql_schema_has_core_types():
    sdl = build_graphql_schema()
    for t in ("type Query", "type Headline", "type RAF", "type KRI",
              "enum Grade", "type Manifest"):
        assert t in sdl
    # grades enumerated
    assert "GREEN WATCH AMBER RED" in sdl


# ----- write specs --------------------------------------------------------

def test_write_api_specs(tmp_path):
    paths = write_api_specs(tmp_path)
    assert set(paths) == {"openapi.json", "schema.graphql"}
    # openapi parses as JSON
    spec = json.loads(Path(paths["openapi.json"]).read_text(encoding="utf-8"))
    assert spec["openapi"] == "3.1.0"
    # graphql has content
    assert "type Query" in Path(paths["schema.graphql"]).read_text(encoding="utf-8")


# ----- CLI ----------------------------------------------------------------

def test_cli_dispatch_dry_run(capsys):
    from risk_lib.cli import main
    rc = main(["dispatch", "--url", "https://hooks.slack.com/x",
               "--dry-run", "--seed", "42"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "dry-run" in out


def test_cli_api_spec(tmp_path):
    from risk_lib.cli import main
    rc = main(["api-spec", "--out", str(tmp_path)])
    assert rc == 0
    assert (tmp_path / "openapi.json").exists()
    assert (tmp_path / "schema.graphql").exists()
