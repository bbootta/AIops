# Data Model Spec: <table_name>

## Grain
One row per <entity / entity-per-period / event>.

## Consumer(s)
Who reads this and how (analyst SQL, ML features, downstream pipeline, app).

## Natural key
Columns that uniquely identify a row; where uniqueness is enforced/checked.

## Schema (DDL)
```sql
-- explicit types; enums/accepted values noted per column
```

## Load strategy
- Pattern: full recompute | cumulative (yesterday FULL OUTER JOIN today) | incremental merge
- Idempotency: what guarantees reruns/backfills give identical results
- Backfill procedure: how far back, in what order, expected cost

## History handling
SCD type and rationale, or "immutable facts — no updates".

## Quality checks
| Check | Rule | On failure |
|---|---|---|
| non-null keys | | block publish |
| uniqueness on natural key | | block publish |
| row count band vs prior run | | page owner |
| freshness vs SLA | | page owner |

## Owner
Team, primary contact.
