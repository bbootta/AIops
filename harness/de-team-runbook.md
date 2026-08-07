# Data Engineering Team — Operating Runbook

How the agent team turns a request into a shipped deliverable.

## Workflow

```
1. Intake      (lead)              → verify: goal restated with data, grain, consumer, SLA
2. Design      (modeler(s))        → verify: DDL + grain statement + load strategy drafted
3. Build       (spark|streaming)   → verify: job code + tests written; tests pass
4. QA gate     (data-quality)      → verify: checklist verdict is approve (or conditions met)
5. Ops gate    (pipeline-ops)      → verify: runbook + owner + SLA exist (scheduled pipelines only)
6. Assemble    (lead)              → verify: single coherent deliverable, open questions listed
```

Analysis-only requests (metrics, experiments, ad-hoc questions) go
Intake → analytics-engineer → QA gate → Assemble.

## Invocation

- Point Claude Code at this repo; the agents in `.claude/agents/` auto-load.
- For a full-team task, address the lead:
  `데이터 엔지니어링 리드로서 처리해줘: <request>` /
  "As the data-engineering-lead, handle: <request>".
- For a narrow task, invoke the specialist directly
  ("use the spark-engineer subagent to ...").

## Ground rules

- The QA gate is not optional. A design that skips step 4 is a draft.
- Batch is the default; streaming must be justified by a stated latency SLA.
- Specialists write; the lead edits. Conflicting recommendations never reach
  the user unresolved.
- Deliverables use `templates/`; deviations are fine if the template's
  required fields still appear.

## Deliverable homes

| Type | Location |
|---|---|
| Data model specs | `deliverables/models/` |
| Pipeline code | `deliverables/pipelines/` |
| Runbooks | `deliverables/runbooks/` |
| Analyses & experiment designs | `deliverables/analyses/` |
