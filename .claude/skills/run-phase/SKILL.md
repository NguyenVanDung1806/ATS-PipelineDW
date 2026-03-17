---
name: run-phase
description: Generate detailed execution plan for a specific project phase.
  Invoke with /run-phase [0-4] to get ordered task list with acceptance
  criteria, edge case flags, and time estimates. Use at the start of
  each new phase or sprint planning session.
argument-hint: [phase-number 0-4]
disable-model-invocation: false
---

Generate execution plan for Phase **$ARGUMENTS**.

## Before planning

1. Read `CLAUDE.md` — current phase, architecture decisions
2. Read `MEMORY.md` — what's already done, what's blocked
3. Use `codebase-explorer` agent to check current file state

## Phase definitions

### Phase 0 — Infrastructure
Tasks: docker-compose, PostgreSQL schemas, MinIO init, dbt project, Airflow connections
Done when: `docker-compose ps` shows all services healthy, `dbt debug` passes

### Phase 1 — First Pipeline
Tasks: BaseExtractor, first platform extractor, staging table, dbt stg model, dbt fct model, Airflow DAG, first Metabase dashboard
Done when: Pipeline runs end-to-end 3 times with stable row counts (idempotency verified)

### Phase 2 — Multi-Platform
Tasks: Repeat Phase 1 pattern for each remaining platform + CRM extractor
Done when: All platforms flowing, reconciliation model showing sync rates

### Phase 3 — Observability
Tasks: meta.pipeline_runs logging, Slack alerts, freshness checks, dbt test expansion, health dashboard
Done when: Any pipeline failure triggers Slack within 5 minutes

### Phase 4 — Analytics
Tasks: Marketing performance dashboard, executive dashboard, CRM pipeline dashboard
Done when: Simon and GD can answer top 3 business questions from dashboards alone

## Output format

```
Phase $ARGUMENTS Execution Plan
═══════════════════════════════════════

TASK 1: [Task name]
  Priority:    HIGH / MEDIUM / LOW
  Estimate:    X hours
  Edge cases:  EC-01, EC-06 (if applicable)
  Files:       extractors/facebook/extract.py
  Done when:   [specific, measurable criteria]

TASK 2: ...

RISKS:
  - [Risk 1]: [mitigation]
  - [Risk 2]: [mitigation]

FIRST ACTION:
  Start with: [exact first task]
  Prompt to use: "[suggested Claude prompt]"
```

Use Opus-level reasoning for this planning — think carefully about dependencies and ordering.
