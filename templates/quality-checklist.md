# Quality Review: <design/pipeline name>

Reviewer: data-quality-engineer
Verdict: approve | approve-with-conditions | reject

| # | Check | Pass? | Finding / required change |
|---|---|---|---|
| 1 | Grain stated; natural key defined and checked | | |
| 2 | Idempotent reruns & backfills | | |
| 3 | Dedup once at ingest, key stated | | |
| 4 | Explicit schema; null policy per column; dates typed | | |
| 5 | Automated checks: counts, non-null, uniqueness, accepted values, freshness | | |
| 6 | Write-Audit-Publish; failed audit blocks publish | | |
| 7 | Upstream contract documented; change notification path | | |

## Required changes (blocking)
-

## Recommendations (non-blocking)
-
