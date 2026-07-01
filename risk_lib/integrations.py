"""External integrations — webhook dispatch + REST/GraphQL API schema.

Extends risk_lib.notifications (which builds Slack/email payloads) with the
plumbing to actually deliver them and to expose the results to external
systems:

  - `WebhookDispatcher`: POSTs a JSON payload to a webhook URL (Slack, MS
    Teams, PagerDuty, generic). Uses stdlib urllib — no `requests`
    dependency. Supports dry-run (returns the request without sending) so
    unit tests never touch the network.
  - `build_rest_openapi`: emits a minimal OpenAPI 3.1 spec describing the
    read-only risk API (the endpoints already served by risk_lib.api.serve).
  - `build_graphql_schema`: emits an SDL string for the same data model.
  - `dispatch_alerts`: convenience — collect alerts from a result and POST
    the Slack payload (or dry-run).

Reference: Slack Incoming Webhooks, OpenAPI 3.1, GraphQL SDL.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Webhook dispatch
# ---------------------------------------------------------------------------

@dataclass
class WebhookRequest:
    url: str
    method: str
    headers: dict[str, str]
    body: str


@dataclass
class WebhookResult:
    ok: bool
    status: int | None
    error: str | None
    request: WebhookRequest


@dataclass
class WebhookDispatcher:
    """Deliver JSON payloads to a webhook. dry_run avoids network in tests."""
    url: str
    kind: str = "slack"           # slack / teams / pagerduty / generic
    timeout: float = 5.0
    dry_run: bool = False
    extra_headers: dict[str, str] = field(default_factory=dict)

    def _prepare(self, payload: dict[str, Any]) -> WebhookRequest:
        headers = {"Content-Type": "application/json", **self.extra_headers}
        return WebhookRequest(
            url=self.url, method="POST", headers=headers,
            body=json.dumps(payload, ensure_ascii=False),
        )

    def send(self, payload: dict[str, Any]) -> WebhookResult:
        req = self._prepare(payload)
        if self.dry_run:
            return WebhookResult(ok=True, status=None, error=None, request=req)
        try:
            request = urllib.request.Request(
                req.url, data=req.body.encode("utf-8"),
                headers=req.headers, method="POST")
            with urllib.request.urlopen(request, timeout=self.timeout) as resp:
                return WebhookResult(ok=200 <= resp.status < 300,
                                     status=resp.status, error=None, request=req)
        except urllib.error.HTTPError as e:
            return WebhookResult(ok=False, status=e.code, error=str(e), request=req)
        except Exception as e:                          # noqa: BLE001
            return WebhookResult(ok=False, status=None, error=str(e), request=req)


def dispatch_alerts(result, url: str, *, kind: str = "slack",
                    dry_run: bool = False, manifest=None) -> WebhookResult:
    """Collect alerts from a result and POST them as a Slack payload."""
    from risk_lib.notifications import collect_alerts, build_slack_payload
    bundle = collect_alerts(result)
    if manifest is not None:
        bundle.headline_digest = manifest.headline_digest
    payload = build_slack_payload(bundle)
    return WebhookDispatcher(url=url, kind=kind, dry_run=dry_run).send(payload)


# ---------------------------------------------------------------------------
# REST — OpenAPI 3.1 spec
# ---------------------------------------------------------------------------

_ENDPOINTS = {
    "/healthz":       "헬스체크",
    "/headline":      "헤드라인 집계 (RWA/BIS/Leverage/ECL/LCR/NSFR/IRRBB/ICAAP)",
    "/raf":           "RAF 12개 KRI 스코어카드",
    "/validation":   "자체검증 체크리스트",
    "/alm/lcr":       "LCR 상세",
    "/alm/nsfr":      "NSFR 상세",
    "/alm/irrbb":     "IRRBB ΔEVE/ΔNII",
    "/icaap":         "내부자본 경제자본",
    "/sensitivity":  "1F/2F 민감도",
    "/climate":       "기후 시나리오 ECL",
    "/alerts":        "알림 번들",
    "/manifest":      "재현성 manifest",
}


def build_rest_openapi(*, title: str = "risk_lib Risk API",
                       version: str = "0.25.0",
                       server_url: str = "http://localhost:8765") -> dict[str, Any]:
    """Minimal OpenAPI 3.1 document describing the read-only risk API."""
    paths = {}
    for path, desc in _ENDPOINTS.items():
        paths[path] = {
            "get": {
                "summary": desc,
                "operationId": "get" + path.replace("/", "_"),
                "responses": {
                    "200": {
                        "description": "성공",
                        "content": {
                            "application/json": {
                                "schema": {"type": "object"}
                            }
                        },
                    }
                },
            }
        }
    return {
        "openapi": "3.1.0",
        "info": {
            "title": title, "version": version,
            "description": ("리스크관리 read-only API — 모든 응답은 manifest "
                            "digest로 재현 가능. 출처: Basel III + IFRS9 + "
                            "금감원 감독세칙."),
        },
        "servers": [{"url": server_url}],
        "paths": paths,
    }


# ---------------------------------------------------------------------------
# GraphQL — SDL schema
# ---------------------------------------------------------------------------

def build_graphql_schema() -> str:
    """GraphQL SDL for the risk data model."""
    return """\
\"\"\"리스크관리 GraphQL API — read-only. 모든 필드는 manifest digest로 재현 가능.\"\"\"
type Query {
  headline: Headline!
  raf: RAF!
  validation: Validation!
  alm: ALM!
  icaap: ICAAP!
  manifest: Manifest!
}

type Headline {
  rwaFinalTotal: Float!
  cet1: Float!
  tier1: Float!
  total: Float!
  leverage: Float!
  eclTtc: Float!
  eclPitWeighted: Float!
  lcr: Float!
  nsfr: Float!
  irrbbWorstPctTier1: Float!
  icaapUtilisation: Float!
  reverseStressSeverity: Float!
}

type KRI {
  name: String!
  category: String!
  actual: Float!
  grade: Grade!
  board: Float!
  citation: String!
}

enum Grade { GREEN WATCH AMBER RED }

type RAF {
  worst: Grade!
  kris: [KRI!]!
}

type Check {
  name: String!
  status: CheckStatus!
  detail: String!
}

enum CheckStatus { PASS WARN FAIL }

type Validation {
  passes: Boolean!
  checks: [Check!]!
}

type ALM {
  lcr: Float!
  nsfr: Float!
  irrbbWorstPctTier1: Float!
}

type ICAAP {
  grade: Grade!
  utilisation: Float!
  ecDiversified: Float!
  availableCapital: Float!
}

type Manifest {
  headlineDigest: String!
  portfolioSha256: String!
  gitCommit: String
}
"""


def write_api_specs(out_dir, *, manifest=None) -> dict[str, str]:
    """Write openapi.json + schema.graphql to a directory."""
    from pathlib import Path
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    openapi = build_rest_openapi()
    graphql = build_graphql_schema()
    p1 = out / "openapi.json"
    p1.write_text(json.dumps(openapi, indent=2, ensure_ascii=False),
                  encoding="utf-8")
    p2 = out / "schema.graphql"
    p2.write_text(graphql, encoding="utf-8")
    return {"openapi.json": str(p1.resolve()),
            "schema.graphql": str(p2.resolve())}
