"""
Facebook Ads Backfill Pipeline DAG.
Manual only. Use for controlled historical loads in small date chunks.

Required trigger config:
{
  "start_date": "2026-04-01",
  "end_date": "2026-04-07",
  "full_refresh": true
}

Production rule:
- Use full_refresh=true only for the first historical chunk.
- Use full_refresh=false for subsequent chunks so fct_ad_spend accumulates.
- Keep each chunk <= 14 days to reduce Facebook API/rate-limit risk.
- Run chunks in chronological order. Incremental marts only process staging rows
  inside the current 7-day lookback from the existing max fact date.
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

from facebook_pipeline import (
    default_args,
    slack_alert_failure,
    task_extract_backfill,
    task_load_staging,
    task_log_run,
)


MAX_BACKFILL_DAYS = 14


def task_validate_backfill_conf(**context) -> None:
    """Validate manual backfill config before calling Facebook API."""
    from datetime import date

    conf = context.get("dag_run").conf or {}
    missing = [key for key in ("start_date", "end_date") if not conf.get(key)]
    if missing:
        raise ValueError(
            "facebook_backfill_pipeline requires dag_run.conf keys: "
            "start_date, end_date. Example: "
            '{"start_date":"2026-04-01","end_date":"2026-04-07","full_refresh":true}'
        )

    start_date = date.fromisoformat(conf["start_date"])
    end_date = date.fromisoformat(conf["end_date"])
    days = (end_date - start_date).days + 1

    if start_date > end_date:
        raise ValueError("start_date must be <= end_date")

    if days > MAX_BACKFILL_DAYS:
        raise ValueError(
            f"Backfill range is {days} days; max allowed is {MAX_BACKFILL_DAYS}. "
            "Split the run into smaller chunks to avoid Facebook API throttling."
        )

    print(
        "[facebook_backfill] Validated config: "
        f"{start_date} -> {end_date}, full_refresh={bool(conf.get('full_refresh'))}"
    )


backfill_args = {
    **default_args,
    "execution_timeout": timedelta(hours=4),
    "on_failure_callback": slack_alert_failure,
}


with DAG(
    dag_id="facebook_backfill_pipeline",
    default_args=backfill_args,
    description="Manual Facebook Ads historical backfill in controlled chunks",
    schedule=None,
    start_date=datetime(2026, 3, 1),
    catchup=False,
    max_active_runs=1,
    tags=["marketing", "facebook", "backfill"],
) as dag:

    validate_conf = PythonOperator(
        task_id="validate_backfill_conf",
        python_callable=task_validate_backfill_conf,
    )

    extract = PythonOperator(
        task_id="extract",
        python_callable=task_extract_backfill,
    )

    load_staging = PythonOperator(
        task_id="load_staging",
        python_callable=task_load_staging,
    )

    dbt_verify_packages = BashOperator(
        task_id="dbt_verify_packages",
        bash_command=(
            "mkdir -p /tmp/dbt-logs && "
            "cd /opt/airflow/dbt && "
            "test -d dbt_packages/dbt_utils && "
            "test -d dbt_packages/dbt_expectations"
        ),
    )

    dbt_run_staging = BashOperator(
        task_id="dbt_run_staging",
        bash_command=(
            "cd /opt/airflow/dbt && "
            "dbt run --profiles-dir /opt/airflow/dbt --log-path /tmp/dbt-logs "
            "--select stg_facebook_ads --no-version-check --target prod"
        ),
    )

    dbt_test_staging = BashOperator(
        task_id="dbt_test_staging",
        bash_command=(
            "cd /opt/airflow/dbt && "
            "dbt test --profiles-dir /opt/airflow/dbt --log-path /tmp/dbt-logs "
            "--select stg_facebook_ads --no-version-check --target prod"
        ),
    )

    dbt_run_marts = BashOperator(
        task_id="dbt_run_marts",
        bash_command=(
            "cd /opt/airflow/dbt && "
            "dbt run --profiles-dir /opt/airflow/dbt --log-path /tmp/dbt-logs "
            "--select fct_ad_spend --no-version-check --target prod "
            "{% if dag_run.conf.get('full_refresh') %}--full-refresh{% endif %}"
        ),
    )

    dbt_test_marts = BashOperator(
        task_id="dbt_test_marts",
        bash_command=(
            "cd /opt/airflow/dbt && "
            "dbt test --profiles-dir /opt/airflow/dbt --log-path /tmp/dbt-logs "
            "--select fct_ad_spend --no-version-check --target prod"
        ),
    )

    log_success = PythonOperator(
        task_id="log_success",
        python_callable=task_log_run,
        op_kwargs={"status": "success"},
        trigger_rule="all_success",
    )

    (
        validate_conf
        >> extract
        >> load_staging
        >> dbt_verify_packages
        >> dbt_run_staging
        >> dbt_test_staging
        >> dbt_run_marts
        >> dbt_test_marts
        >> log_success
    )
