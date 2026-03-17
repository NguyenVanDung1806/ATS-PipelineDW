# DE Senior Template — Claude Code Edition

> **Clone → Open Claude Code → Start building.**
> Everything is pre-configured. No setup required.

---

## Quick Start

```bash
# 1. Clone repo
git clone https://github.com/YOUR_ORG/de-template my-project
cd my-project

# 2. Copy env và điền thông tin
cp .env.example .env

# 3. Mở Claude Code với Opus để plan
claude --model opus

# Prompt đầu tiên trong Claude Code:
# "Read CLAUDE.md. I'm starting a new DE project.
#  My data sources are [list your sources].
#  Help me customize this template for my use case."
```

---

## What's Pre-loaded

Khi mày mở Claude Code trong repo này, Claude tự động có:

### Skills (auto-invoked — không cần gọi thủ công)
| Skill | Triggers khi nào |
|-------|-----------------|
| `pydantic-extractor` | Viết bất kỳ extractor/API client nào |
| `dbt-conventions` | Viết bất kỳ dbt model/test nào |
| `airflow-dag-pattern` | Viết bất kỳ Airflow DAG nào |
| `edge-case-checklist` | Review code, viết tests |
| `sql-optimizer` | Viết SQL queries phức tạp |
| `data-quality` | Thiết kế data quality checks |

### Agents (isolated context — delegate heavy tasks)
| Agent | Model | Dùng khi |
|-------|-------|----------|
| `pipeline-architect` | Opus | Design schema, architectural decisions |
| `codebase-explorer` | Haiku | Search files, grep patterns (fast + cheap) |
| `security-auditor` | Sonnet | Pre-commit credential scan |
| `reconciliation-analyst` | Opus | Investigate data discrepancies |
| `dbt-reviewer` | Sonnet | Review dbt model quality |
| `infra-checker` | Haiku | Check docker/infra status |

### Hooks (enforced — chạy tự động)
| Hook | Trigger | Action |
|------|---------|--------|
| PostToolUse | Write `*.py` | black format + mypy check |
| PostToolUse | Write `dbt/**/*.sql` | dbt compile check |
| PostToolUse | Write `dags/**/*.py` | Airflow syntax check |
| PreToolUse | `git commit` | Credential scan, block if found |
| Stop | End of session | Remind update MEMORY.md |

---

## Tech Stack

```
Orchestration    Apache Airflow 2.9+
Raw Layer        MinIO (S3-compatible, self-hosted)
Database         PostgreSQL 16+ with pg_partman
Transform        dbt Core 1.8+
Dashboard        Metabase Community Edition
Language         Python 3.12
Containers       Docker Compose v2
Validation       Pydantic v2
Testing          pytest + dbt tests
Alerting         Slack webhooks
```

---

## Architecture Pattern

```
Sources (APIs)
    │
    ▼ [Extract — Airflow DAG, daily, lookback 7d]
    │
    ├─→ MinIO raw/          ← immutable raw JSON, never delete
    │
    ▼ [Load — TRUNCATE staging, INSERT fresh]
    │
PostgreSQL raw.*            ← staging buffer, truncated each run
    │
    ▼ [Transform — dbt run + dbt test]
    │
PostgreSQL dw.*             ← fact/dim, partitioned by month, UPSERT
    │
    ▼
Metabase                    ← dashboards read from dw.* only
```

---

## Project Structure

```
.claude/
├── skills/                 ← Auto-invoked knowledge layers
│   ├── pydantic-extractor/ ← Extractor patterns + edge cases
│   ├── dbt-conventions/    ← dbt model standards + examples
│   ├── airflow-dag-pattern/← DAG patterns + templates
│   ├── edge-case-checklist/← 11 edge cases, auto-check on review
│   ├── sql-optimizer/      ← Query optimization patterns
│   └── data-quality/       ← DQ framework patterns
├── agents/                 ← Isolated specialist workers
│   ├── pipeline-architect.md  (Opus)
│   ├── codebase-explorer.md   (Haiku)
│   ├── security-auditor.md    (Sonnet)
│   ├── reconciliation-analyst.md (Opus)
│   ├── dbt-reviewer.md        (Sonnet)
│   └── infra-checker.md       (Haiku)
└── settings.json           ← Hooks + permissions config

extractors/
├── base/
│   ├── base_extractor.py   ← Abstract class (inherit this)
│   └── minio_client.py     ← MinIO upload utility
└── [platform]/             ← Add per platform

dbt/
├── models/
│   ├── staging/            ← stg_* models
│   ├── intermediate/       ← int_* models
│   ├── marts/              ← fct_* models
│   └── dimensions/         ← dim_* models
├── tests/                  ← Custom dbt tests
└── macros/                 ← Reusable SQL macros

dags/                       ← Airflow DAG definitions
infra/                      ← docker-compose + SQL schemas
scripts/                    ← Validation + setup utilities
docs/                       ← Architecture decisions (ADRs)
```

---

## Model Strategy

```bash
claude --model opus    # Planning, architecture, complex debugging
claude --model sonnet  # Daily building — default for coding
claude --model haiku   # Quick search via codebase-explorer agent
```

**OpusPlan pattern** — recommended cho task phức tạp:
1. `claude --model opus` → plan + design
2. `claude --model sonnet` → implement từ plan

---

## Phases

| Phase | Goal | Key deliverable |
|-------|------|----------------|
| 0 | Infrastructure | docker-compose running, schemas created |
| 1 | First pipeline | 1 platform E2E, CPL in Metabase |
| 2 | Multi-platform | All platforms flowing |
| 3 | Observability | Alerts, data quality, freshness checks |
| 4 | Analytics layer | Full dashboard suite |

---

## Session Workflow

```bash
# Đầu mỗi session
claude --model sonnet
> Read CLAUDE.md and MEMORY.md. Continue from where we left off.

# Khi cần architectural decision
claude --model opus
> [describe the decision needed]

# Khi search codebase
> Use the codebase-explorer agent to find all files using tenacity

# Trước khi merge
> Use the security-auditor agent to scan all changed files
> Run /validate-pipeline
```

---

## Docs

- `docs/ADR.md` — Architecture Decision Records
- `docs/EDGE_CASES.md` — 11 edge cases với strategy
- `docs/CONVENTIONS.md` — Naming conventions
- `MEMORY.md` — Session log (update mỗi ngày)
- `CLAUDE.md` — Project brain (đọc tự động)
