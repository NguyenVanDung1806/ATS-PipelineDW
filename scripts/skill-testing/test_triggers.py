#!/usr/bin/env python3
"""
Skill Trigger Rate Tester
Test xem mỗi skill có được Claude auto-invoke đúng lúc không.

Usage:
  python3 scripts/skill-testing/test_triggers.py              # test all skills
  python3 scripts/skill-testing/test_triggers.py pydantic     # test 1 skill
  python3 scripts/skill-testing/test_triggers.py --fix        # suggest fixes
"""
import subprocess, json, sys, time
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent.parent

# ── Colors ────────────────────────────────────────────────────────────────────
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[94m"
BOLD = "\033[1m"; DIM = "\033[2m"; RESET = "\033[0m"

def ok(msg):    print(f"  {G}✓{RESET} {msg}")
def fail(msg):  print(f"  {R}✗{RESET} {R}{msg}{RESET}")
def warn(msg):  print(f"  {Y}⚠{RESET} {Y}{msg}{RESET}")
def info(msg):  print(f"  {DIM}·{RESET} {msg}")


# ── Test cases per skill ───────────────────────────────────────────────────────
SKILL_TEST_CASES = {
    "pydantic-extractor": {
        "should_trigger": [
            "Write a Facebook ads extractor",
            "Create extract.py for TikTok platform",
            "Build API client for CRM Live1",
            "Write schema.py with Pydantic validation",
            "Fix the extractor bug in facebook/extract.py",
            "Update API response parser for Google Ads",
            "Debug rate limit error in TikTok extractor",
            "Add retry logic to the extractor",
            "Create new platform ingestion script",
            "The extractor is returning null spend values",
        ],
        "should_not_trigger": [
            "Write a dbt model for ad spend",
            "Create an Airflow DAG",
            "What is the CPL this month?",
            "Update MEMORY.md",
            "Show me the docker-compose file",
        ],
        "keywords": [
            "extractor", "extract.py", "schema.py", "API client",
            "Pydantic", "ingestion", "fetch data", "pull data",
            "rate limit", "retry", "tenacity", "platform data"
        ]
    },

    "dbt-conventions": {
        "should_trigger": [
            "Write a staging model for Facebook ads",
            "Create fct_ad_spend incremental model",
            "Add dbt test for unique campaign_id",
            "Write schema.yml for the staging layer",
            "Fix the dbt model that's failing",
            "Create dim_counselor with SCD2",
            "Add not_null test to spend column",
            "Write int_leads_reconciled model",
            "The dbt test is failing on unique constraint",
            "Create a report model for Metabase",
        ],
        "should_not_trigger": [
            "Write a Python extractor",
            "Create an Airflow DAG",
            "Show me the docker-compose",
            "What is CPL?",
            "Update MEMORY.md",
        ],
        "keywords": [
            "dbt", "model", "staging", "stg_", "fct_", "dim_",
            "incremental", "schema.yml", "dbt test", "unique_key",
            "materialized", "ref(", "source("
        ]
    },

    "airflow-dag-pattern": {
        "should_trigger": [
            "Write an Airflow DAG for Facebook pipeline",
            "Create a DAG that runs at 9h every day",
            "Add on_failure_callback to the pipeline",
            "Set up task dependencies in the DAG",
            "The Airflow scheduler is not picking up the DAG",
            "Write a PythonOperator for the extract task",
            "Configure retry logic in default_args",
            "Create cron schedule for Facebook pipeline",
            "Add Slack alert when pipeline fails",
            "Write BashOperator for dbt run task",
        ],
        "should_not_trigger": [
            "Write a dbt model",
            "Create a Pydantic schema",
            "What is CPL?",
            "Show me MinIO folder structure",
            "Update MEMORY.md",
        ],
        "keywords": [
            "DAG", "Airflow", "schedule", "cron", "pipeline",
            "on_failure_callback", "PythonOperator", "BashOperator",
            "task dependency", "retry", "default_args"
        ]
    },

    "edge-case-checklist": {
        "should_trigger": [
            "Review this extractor before I commit",
            "Check if this code handles edge cases",
            "Is this dbt model correct?",
            "Validate my extractor implementation",
            "Before I merge, check this file",
            "Review the Facebook extractor",
            "Is the retry logic correct here?",
            "Check this for potential issues",
            "Does this handle null values properly?",
            "Verify the attribution window logic",
        ],
        "should_not_trigger": [
            "Write a new extractor",
            "Create a dbt model",
            "What is the current phase?",
            "Show me the project structure",
            "Update MEMORY.md",
        ],
        "keywords": [
            "review", "check", "validate", "verify", "before merge",
            "is this correct", "edge case", "handle null", "test coverage"
        ]
    },

    "sql-optimizer": {
        "should_trigger": [
            "This query is running very slowly",
            "Write a window function for MoM comparison",
            "Optimize this PostgreSQL query",
            "Add index for faster date filtering",
            "Write a complex JOIN with multiple aggregations",
            "The EXPLAIN ANALYZE shows sequential scan",
            "Calculate CPL with safe division",
            "Write a partition pruning query",
            "LAG function for previous month comparison",
            "Optimize the reconciliation query",
        ],
        "should_not_trigger": [
            "Write a dbt model",
            "Create an extractor",
            "Set up Airflow DAG",
            "What is CPL?",
            "Update MEMORY.md",
        ],
        "keywords": [
            "slow query", "optimize", "window function", "LAG", "LEAD",
            "partition pruning", "index", "EXPLAIN", "safe division",
            "NULLIF", "complex JOIN", "aggregation"
        ]
    },

    "data-quality": {
        "should_trigger": [
            "Add data freshness monitoring",
            "Write anomaly detection for spend spikes",
            "Log pipeline runs to meta table",
            "Set up Slack alert for stale data",
            "Add dbt_utils recency test",
            "Monitor data quality metrics",
            "Write freshness check for fact table",
            "Detect when spend is abnormally high",
            "Set up SLA monitoring for pipeline",
            "Add data quality log entry",
        ],
        "should_not_trigger": [
            "Write an extractor",
            "Create a dbt model",
            "Set up Airflow DAG",
            "What is CPL?",
            "Update MEMORY.md",
        ],
        "keywords": [
            "freshness", "anomaly", "data quality", "SLA",
            "monitoring", "alert", "stale data", "pipeline health",
            "meta.pipeline_runs", "data quality log"
        ]
    },

    "update-context": {
        "should_trigger": [
            "I'm done with the Facebook extractor",
            "The dbt model is finished and tests pass",
            "Moving on to the next task",
            "That's working now, save progress",
            "Completed Phase 0 setup",
            "Just finished writing the DAG",
            "All tests passing, marking done",
        ],
        "should_not_trigger": [
            "Write a new extractor",
            "What is CPL?",
            "Show me docker-compose",
            "The query is slow",
        ],
        "keywords": [
            "done", "finished", "completed", "moving on",
            "save progress", "tests pass", "marking done",
            "that's working", "all good"
        ]
    },
}


# ── Trigger tester ────────────────────────────────────────────────────────────

def read_skill_description(skill_name: str) -> str:
    """Read current description from SKILL.md."""
    skill_file = ROOT / ".claude" / "skills" / skill_name / "SKILL.md"
    if not skill_file.exists():
        return ""

    content = skill_file.read_text()
    # Extract description from frontmatter
    lines = content.split("\n")
    in_frontmatter = False
    desc_lines = []
    collecting = False

    for line in lines:
        if line.strip() == "---":
            if not in_frontmatter:
                in_frontmatter = True
                continue
            else:
                break
        if in_frontmatter:
            if line.startswith("description:"):
                desc_lines.append(line[12:].strip())
                collecting = True
            elif collecting and line.startswith(" "):
                desc_lines.append(line.strip())
            elif collecting:
                collecting = False

    return " ".join(desc_lines)


def simulate_trigger(prompt: str, skill_name: str, description: str) -> bool:
    """
    Simulate whether Claude would trigger a skill given a prompt.
    Uses keyword matching as proxy for Claude's actual decision.
    """
    test_cases = SKILL_TEST_CASES.get(skill_name, {})
    keywords = test_cases.get("keywords", [])

    prompt_lower = prompt.lower()
    desc_lower = description.lower()

    # Check if prompt contains any skill keywords
    keyword_match = any(kw.lower() in prompt_lower for kw in keywords)

    # Check if description contains relevant words from prompt
    prompt_words = set(w for w in prompt_lower.split() if len(w) > 3)
    desc_words = set(w for w in desc_lower.split() if len(w) > 3)
    word_overlap = len(prompt_words & desc_words) / max(len(prompt_words), 1)

    # Trigger if keyword match OR significant word overlap
    return keyword_match or word_overlap > 0.15


def test_skill(skill_name: str) -> dict:
    """Test trigger rate for a specific skill."""
    test_cases = SKILL_TEST_CASES.get(skill_name)
    if not test_cases:
        return {"error": f"No test cases for {skill_name}"}

    description = read_skill_description(skill_name)
    if not description:
        return {"error": f"Skill not found: {skill_name}"}

    should_trigger = test_cases["should_trigger"]
    should_not = test_cases["should_not_trigger"]

    # Test positive cases (should trigger)
    true_positives  = 0
    false_negatives = []
    for prompt in should_trigger:
        if simulate_trigger(prompt, skill_name, description):
            true_positives += 1
        else:
            false_negatives.append(prompt)

    # Test negative cases (should NOT trigger)
    true_negatives  = 0
    false_positives = []
    for prompt in should_not:
        if not simulate_trigger(prompt, skill_name, description):
            true_negatives += 1
        else:
            false_positives.append(prompt)

    total_positive = len(should_trigger)
    total_negative = len(should_not)

    recall    = true_positives / total_positive if total_positive else 0
    precision = true_negatives / total_negative if total_negative else 0

    return {
        "skill":            skill_name,
        "recall":           recall,
        "precision":        precision,
        "true_positives":   true_positives,
        "false_negatives":  false_negatives,
        "true_negatives":   true_negatives,
        "false_positives":  false_positives,
        "total_positive":   total_positive,
        "total_negative":   total_negative,
        "description_len":  len(description),
    }


def suggest_description_fix(skill_name: str, result: dict) -> str:
    """Suggest keywords to add to fix low trigger rate."""
    test_cases   = SKILL_TEST_CASES.get(skill_name, {})
    keywords     = test_cases.get("keywords", [])
    missed       = result.get("false_negatives", [])
    description  = read_skill_description(skill_name)

    # Find keywords from missed prompts not in description
    missing_keywords = []
    for prompt in missed:
        for word in prompt.lower().split():
            if len(word) > 4 and word not in description.lower():
                missing_keywords.append(word)

    missing_keywords = list(set(missing_keywords))[:8]

    suggestion = f"""
Add these keywords to {skill_name} description:
  {', '.join(missing_keywords)}

Missed prompts:
"""
    for p in missed[:3]:
        suggestion += f"  - {p}\n"

    return suggestion


def print_result(result: dict):
    """Pretty print test result for one skill."""
    if "error" in result:
        warn(f"{result['error']}")
        return

    skill   = result["skill"]
    recall  = result["recall"]
    prec    = result["precision"]
    score   = (recall + prec) / 2

    color = G if score >= 0.85 else (Y if score >= 0.70 else R)
    bar_len = int(score * 20)
    bar = "█" * bar_len + "░" * (20 - bar_len)

    print(f"\n  {BOLD}{skill}{RESET}")
    print(f"  [{color}{bar}{RESET}] {color}{score*100:.0f}%{RESET}")
    print(f"  Trigger rate:  {recall*100:.0f}%  "
          f"({result['true_positives']}/{result['total_positive']} should-trigger cases)")
    print(f"  Precision:     {prec*100:.0f}%  "
          f"({result['true_negatives']}/{result['total_negative']} should-not cases)")

    if result["false_negatives"]:
        print(f"  {Y}Missed triggers:{RESET}")
        for p in result["false_negatives"][:3]:
            print(f"    · {p}")

    if result["false_positives"]:
        print(f"  {R}False triggers:{RESET}")
        for p in result["false_positives"][:2]:
            print(f"    · {p}")


def run_all_tests(fix_mode: bool = False) -> dict:
    """Run tests for all skills and return summary."""
    print(f"\n{BOLD}{B}{'═'*52}{RESET}")
    print(f"{BOLD}{B}  Skill Trigger Rate Test{RESET}")
    print(f"{BOLD}{B}  {datetime.now().strftime('%Y-%m-%d %H:%M')}{RESET}")
    print(f"{BOLD}{B}{'═'*52}{RESET}")

    results = {}
    for skill_name in SKILL_TEST_CASES:
        result = test_skill(skill_name)
        results[skill_name] = result
        print_result(result)

        if fix_mode and "error" not in result:
            score = (result["recall"] + result["precision"]) / 2
            if score < 0.85:
                print(suggest_description_fix(skill_name, result))

    # Summary
    valid = {k: v for k, v in results.items() if "error" not in v}
    if valid:
        avg = sum(
            (v["recall"] + v["precision"]) / 2
            for v in valid.values()
        ) / len(valid)

        passing = sum(
            1 for v in valid.values()
            if (v["recall"] + v["precision"]) / 2 >= 0.85
        )

        print(f"\n{BOLD}{'═'*52}{RESET}")
        print(f"{BOLD}  Overall: {avg*100:.0f}% | "
              f"{passing}/{len(valid)} skills passing (≥85%){RESET}")

        if avg >= 0.90:
            ok(f"Skills well-tuned — Claude will invoke them reliably")
        elif avg >= 0.75:
            warn(f"Some skills may be missed — review descriptions above")
        else:
            fail(f"Low trigger rate — skills need description updates")

        # Save results
        results_file = ROOT / "scripts" / "skill-testing" / "last_results.json"
        results_file.write_text(
            json.dumps({
                "tested_at": datetime.now().isoformat(),
                "overall_score": avg,
                "results": {
                    k: {
                        "recall":    v.get("recall", 0),
                        "precision": v.get("precision", 0),
                        "missed":    v.get("false_negatives", []),
                    }
                    for k, v in valid.items()
                }
            }, indent=2)
        )
        info(f"Results saved to scripts/skill-testing/last_results.json")

    return results


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args      = sys.argv[1:]
    fix_mode  = "--fix" in args
    skill_arg = next((a for a in args if not a.startswith("--")), None)

    if skill_arg:
        # Test single skill
        result = test_skill(skill_arg)
        print_result(result)
        if fix_mode and "error" not in result:
            print(suggest_description_fix(skill_arg, result))
    else:
        run_all_tests(fix_mode=fix_mode)
