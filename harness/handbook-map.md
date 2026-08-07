# Handbook Inheritance Map

This harness inherits its methodology from
[DataExpert-io/data-engineer-handbook](https://github.com/DataExpert-io/data-engineer-handbook).
Each agent's core methods trace to specific handbook material:

| Agent | Handbook source | Key inherited patterns |
|---|---|---|
| dimensional-data-modeler | `intermediate-bootcamp/materials/1-dimensional-data-modeling` | Cumulative table design (yesterday FULL OUTER JOIN today), `season_stats` array-of-struct history, SCD Type 2 generation (`players_scd_table.sql`, `incremental_scd_query.sql`), graph vertices/edges (`graph_ddls.sql`), `UNNEST` flattening, consumer-driven modeling |
| fact-data-modeler | `intermediate-bootcamp/materials/2-fact-data-modeling` | `users_cumulated` activity tables, `user_datelist_int` bit-packed history, `array_metrics` monthly arrays, dedup on natural keys, fact immutability |
| spark-engineer | `intermediate-bootcamp/materials/3-spark-fundamentals` | Testable job functions (`src/jobs` + `src/tests` pytest pattern), Iceberg bucket joins (`bucket-joins-in-iceberg.ipynb`), caching tradeoffs (`Caching.ipynb`), explicit schemas (Dataset API), broadcast joins |
| streaming-engineer | `intermediate-bootcamp/materials/4-apache-flink-training` | PyFlink Kafka source → JDBC sink jobs (`start_job.py`, `aggregation_job.py`), event-time watermarks, tumbling-window aggregation, 10s checkpointing |
| analytics-engineer | `intermediate-bootcamp/materials/4-applying-analytical-patterns`, `5-kpis-and-experimentation`, `6-data-impact-training` | Growth accounting (`growth_accounting.sql`), retention (`retention_analysis.sql`), funnels (`funnel_analysis.sql`), `GROUPING SETS` (`grouping_sets.sql`), window analyses, hypothesis/leading-lagging-metric experiment design |
| data-quality-engineer | `data_cleaning.md` + bootcamp data-quality weeks | Dedup before modeling, standardized column names, explicit null/type handling, datetime parsing, validation before use |
| pipeline-ops-engineer | `intermediate-bootcamp/materials/6-data-pipeline-maintenance` | Runbooks (`RunbookforEcZachlyIncGrowthPipeline.pdf` structure), ownership & on-call design, SLA derivation, tech-debt vs business-velocity tradeoffs |

To refresh the inheritance, re-read the handbook module and update the matching
agent file in `.claude/agents/` — agent prompts should stay short summaries of
method, not copies of handbook text.
