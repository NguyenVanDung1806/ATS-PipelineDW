"""
Template DAG — copy this for each platform.
Skills auto-loaded when editing: airflow-dag-pattern, edge-case-checklist

Replace: PLATFORM, EXTRACTOR_CLASS, schedule_interval
"""
from datetime import datetime, timedelta

import requests, os
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.bash.operators.bash import BashOperator

# ── Platform config ────────────────────────────────────────
PLATFORM = "facebook"          # change per platform
SCHEDULE = "0 2 * * *"         # 9h ICT (2h UTC) — EC-09


# ── Alerting ──────────────────────────────────────────────
def slack_alert_failure(context: dict) -> None:
    """Required on every DAG. Never remove."""
    dag_id  = context["dag"].dag_id
    task_id = context["task_instance"].task_id
    error   = str(context.get("exception", "Unknown"))[:400]
    log_url = context["task_instance"].log_url

    requests.post(
        os.environ["SLACK_WEBHOOK_URL"],
        json={"text": (
            f":rotating_light: *Pipeline FAILED*\n"
            f"DAG: `{dag_id}` | Task: `{task_id}`\n"
            f"Error: ```{error}```\n"
            f"<{log_url}|View logs>"
        )},
        timeout=10,
    )


# ── Tasks ─────────────────────────────────────────────────
def task_extract(**context) -> dict:
    """Extract + validate + upload to MinIO. Returns metadata."""
    from extractors.facebook.extract import FacebookExtractor
    extractor = FacebookExtractor()
    result = extractor.run()
    context["task_instance"].xcom_push(key="extract_result", value=result)
    return result


def task_load_staging(**context) -> int:
    """TRUNCATE staging table, then load validated data."""
    ti = context["task_instance"]
    result = ti.xcom_pull(task_ids="extract", key="extract_result")

    hook = PostgresHook(postgres_conn_id="postgres_dw")
    # TRUNCATE first — staging is always fresh (never append)
    hook.run(f"TRUNCATE TABLE raw.{PLATFORM}_ads")

    # Load from MinIO or pass validated records directly
    # TODO: implement load from MinIO key in result["minio_key"]
    rows_loaded = result.get("rows_validated", 0)
    return rows_loaded


def task_log_run(status: str = "success", **context) -> None:
    """Log pipeline run to meta.pipeline_runs."""
    ti = context["task_instance"]
    result = ti.xcom_pull(task_ids="extract", key="extract_result") or {}

    hook = PostgresHook(postgres_conn_id="postgres_dw")
    hook.run("""
        INSERT INTO meta.pipeline_runs
            (dag_id, platform, run_date, status,
             rows_extracted, rows_loaded, minio_key, finished_at)
        VALUES (%s, %s, CURRENT_DATE, %s, %s, %s, %s, NOW())
    """, parameters=(
        context["dag"].dag_id,
        PLATFORM,
        status,
        result.get("rows_extracted", 0),
        result.get("rows_validated", 0),
        result.get("minio_key"),
    ))


# ── DAG definition ─────────────────────────────────────────
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

with DAG(
    dag_id=f"{PLATFORM}_pipeline",
    default_args=default_args,
    description=f"{PLATFORM.upper()} Ads → MinIO → Staging → dbt → DW",
    schedule_interval=SCHEDULE,
    start_date=datetime(2026, 3, 1),
    catchup=False,
    max_active_runs=1,
    tags=["marketing", PLATFORM, "daily"],
) as dag:

    extract = PythonOperator(
        task_id="extract",
        python_callable=task_extract,
    )

    load_staging = PythonOperator(
        task_id="load_staging",
        python_callable=task_load_staging,
    )

    dbt_run_staging = BashOperator(
        task_id="dbt_run_staging",
        bash_command=(
            f"cd /opt/airflow/dbt && "
            f"dbt run --select stg_{PLATFORM}_ads --no-version-check"
        ),
    )

    dbt_test_staging = BashOperator(
        task_id="dbt_test_staging",
        bash_command=(
            f"cd /opt/airflow/dbt && "
            f"dbt test --select stg_{PLATFORM}_ads --no-version-check"
        ),
    )

    dbt_run_marts = BashOperator(
        task_id="dbt_run_marts",
        bash_command=(
            "cd /opt/airflow/dbt && "
            "dbt run --select fct_ad_spend --no-version-check"
        ),
    )

    dbt_test_marts = BashOperator(
        task_id="dbt_test_marts",
        bash_command=(
            "cd /opt/airflow/dbt && "
            "dbt test --select fct_ad_spend --no-version-check"
        ),
    )

    log_success = PythonOperator(
        task_id="log_success",
        python_callable=task_log_run,
        op_kwargs={"status": "success"},
        trigger_rule="all_success",
    )

    # ── Task dependencies ──────────────────────────────────
    (
        extract
        >> load_staging
        >> dbt_run_staging
        >> dbt_test_staging
        >> dbt_run_marts
        >> dbt_test_marts
        >> log_success
    )
