# Runbook: <pipeline_name>

## Ownership
- Primary owner (team):
- Secondary owner:
- Escalation path:

## Purpose & consumers
What the pipeline produces, who consumes it, how to reach them.

## SLA
- Data must land by: <time, timezone>
- Derived from: <consumer need>
- "Late" severity: | "Wrong" severity:

## Upstream dependencies
| Dataset | Owner | Expected landing time | Contact |
|---|---|---|---|

## Schedule & infrastructure
Orchestrator, schedule, compute, storage locations.

## Common failure modes
| Symptom | Likely cause | Diagnosis | Fix |
|---|---|---|---|
| no data / partial data | upstream late or missing | check upstream partitions | wait / escalate to upstream owner |
| schema error | upstream schema change | diff current vs contract | patch mapping, notify producer |
| volume anomaly | dupes or drop upstream | row count vs 7-day band | investigate before publish |
| job failure | infra / OOM / skew | logs, stage metrics | see remediation notes |

## Backfill procedure
Exact commands/steps, safe ordering, idempotency notes, expected runtime.

## On-call notes
What the secondary needs to know to act without the primary.
