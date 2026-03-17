---
name: airflow-dag-pattern
description: Apply when writing any Airflow DAG, task, operator, or pipeline
  schedule. Auto-invoked for any file in dags/ directory, any mention of
  DAG/pipeline scheduling/task dependencies/on_failure_callback/Slack alerts/
  cron schedules/Airflow operators/backfill. Use for all Airflow work.
allowed-tools: Read, Write, Bash(airflow *, python3 *)
---

# Airflow DAG Pattern — DE Senior Standard

## Schedule rules
```python
# CORRECT — 9h ICT (2h UTC), ad data finalized by then (EC-09)
schedule_interval = "0 2 * * *"

# Stagger platforms — avoid concurrent VPS resource spikes (EC-07)
# facebook:  "0 2 * * *"   →  09:00 ICT
# google:    "15 2 * * *"  →  09:15 ICT
# tiktok:    "30 2 * * *"  →  09:30 ICT
# zalo:      "45 2 * * *"  →  09:45 ICT
# crm:       "0 3 * * *"   →  10:00 ICT
```

## Mandatory default_args
```python
from datetime import datetime, timedelta

default_args = {
    "owner": "data-engineering",
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=30),
    "on_failure_callback": slack_alert_failure,
    "execution_timeout": timedelta(hours=2),
    "depends_on_past": False,
}
```

## Mandatory task order
```
extract_{platform}
    → validate_schema          ← Pydantic check
    → upload_to_minio          ← raw JSON first
    → load_to_staging          ← TRUNCATE then INSERT
    → dbt_run_staging          ← stg_ models
    → dbt_test_staging         ← must pass
    → dbt_run_marts            ← fct_ models
    → dbt_test_marts           ← must pass
    → log_pipeline_run         ← meta.pipeline_runs
    → notify_success
```

## on_failure_callback (required on every DAG)
```python
import requests, os

def slack_alert_failure(context: dict) -> None:
    dag_id  = context["dag"].dag_id
    task_id = context["task_instance"].task_id
    run_id  = context["run_id"]
    error   = str(context.get("exception", "Unknown"))[:400]
    log_url = context["task_instance"].log_url

    requests.post(
        os.environ["SLACK_WEBHOOK_URL"],
        json={
            "text": (
                f":rotating_light: *Pipeline FAILED*\n"
                f"DAG: `{dag_id}` | Task: `{task_id}`\n"
                f"Run: `{run_id}`\n"
                f"Error: ```{error}```\n"
                f"<{log_url}|View logs>"
            )
        },
        timeout=10,
    )
```

## Pipeline run logging
```python
from airflow.providers.postgres.hooks.postgres import PostgresHook

def log_pipeline_run(
    dag_id: str, platform: str, status: str,
    rows_extracted: int = 0, rows_loaded: int = 0,
    minio_key: str = None, error: str = None
) -> None:
    hook = PostgresHook(postgres_conn_id="postgres_dw")
    hook.run("""
        INSERT INTO meta.pipeline_runs
            (dag_id, platform, run_date, status, rows_extracted, rows_loaded,
             minio_key, error_message, finished_at)
        VALUES (%s, %s, CURRENT_DATE, %s, %s, %s, %s, %s, NOW())
    """, parameters=(dag_id, platform, status, rows_extracted,
                     rows_loaded, minio_key, error))
```

## Full DAG template
See `templates/dag_template.py` for complete working example.

## dbt tasks pattern
```python
from airflow.providers.bash.operators.bash import BashOperator

dbt_run = BashOperator(
    task_id="dbt_run_staging",
    bash_command="cd /opt/airflow/dbt && dbt run --select staging --no-version-check",
)
dbt_test = BashOperator(
    task_id="dbt_test_staging",
    bash_command="cd /opt/airflow/dbt && dbt test --select staging --no-version-check",
)
dbt_run >> dbt_test  # test always after run
```
