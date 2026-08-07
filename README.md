# Data Engineering Team Agent Harness

A Claude Code multi-agent harness that acts as a data engineering team. The
team's methodology is inherited from
[DataExpert-io/data-engineer-handbook](https://github.com/DataExpert-io/data-engineer-handbook)
— each specialist agent encodes one module of the handbook's curriculum
(see [`harness/handbook-map.md`](harness/handbook-map.md)).

## Team

| Agent | Role |
|---|---|
| `data-engineering-lead` | Orchestrator: intake, routing, review gates, final assembly |
| `dimensional-data-modeler` | Dimensions, SCDs, cumulative tables, graph models |
| `fact-data-modeler` | Event/fact grain, dedup, datelist ints, array metrics |
| `spark-engineer` | Batch compute: PySpark + Iceberg jobs, joins, tests |
| `streaming-engineer` | Flink/Kafka real-time pipelines, watermarks, windows |
| `analytics-engineer` | Analytical patterns, growth accounting, KPIs, experiments |
| `data-quality-engineer` | Mandatory QA gate: contracts, checks, write-audit-publish |
| `pipeline-ops-engineer` | Runbooks, ownership, SLAs, on-call, tech debt |

## Usage

Open this repo in Claude Code — agents in `.claude/agents/` load automatically.

- Full-team task: "As the data-engineering-lead, design a daily user activity
  pipeline from our event stream."
- Narrow task: "Use the fact-data-modeler subagent to design a datelist-int
  activity table."

Workflow, gates, and invocation details: [`harness/de-team-runbook.md`](harness/de-team-runbook.md).
Roster and routing rules: [`harness/team.yaml`](harness/team.yaml).
Deliverable templates: [`templates/`](templates/).

## Layout

```
.claude/agents/   # agent definitions (auto-loaded by Claude Code)
harness/          # team roster, operating runbook, handbook inheritance map
templates/        # data-model spec, pipeline runbook, quality checklist
deliverables/     # team outputs (models/, pipelines/, runbooks/, analyses/)
```
