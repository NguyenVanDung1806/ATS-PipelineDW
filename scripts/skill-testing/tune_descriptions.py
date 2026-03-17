#!/usr/bin/env python3
"""
Skill Description Tuner
Đọc test results và tự động patch skill descriptions để tăng trigger rate.

Usage:
  python3 scripts/skill-testing/tune_descriptions.py          # dry run
  python3 scripts/skill-testing/tune_descriptions.py --apply  # apply changes
"""
import json, re, sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent.parent

# Keywords to add per skill nếu trigger rate < 85%
KEYWORD_SUPPLEMENTS = {
    "pydantic-extractor": [
        "fix extractor", "update parser", "debug API response",
        "extraction bug", "data fetch", "pull from API",
        "ingest data", "response validation", "field mapping"
    ],
    "dbt-conventions": [
        "fix dbt", "dbt bug", "model failing", "test failing",
        "SQL model", "transform data", "data model", "mart model",
        "source definition", "ref model", "select from"
    ],
    "airflow-dag-pattern": [
        "pipeline schedule", "task runner", "workflow",
        "orchestrate", "trigger pipeline", "run at", "daily job",
        "pipeline task", "airflow task", "dag file"
    ],
    "edge-case-checklist": [
        "before commit", "ready to merge", "double check",
        "potential bug", "handle error", "null handling",
        "looks good?", "is this right", "anything missing"
    ],
    "sql-optimizer": [
        "query slow", "long running query", "database performance",
        "query tuning", "execution plan", "scan type",
        "missing index", "join optimization", "group by performance"
    ],
    "data-quality": [
        "data stale", "pipeline health", "data freshness",
        "data issue", "data problem", "data alert",
        "quality check", "sla breach", "monitor data"
    ],
    "update-context": [
        "save state", "record progress", "update status",
        "done with", "wrapped up", "task complete",
        "checkpoint", "log progress", "mark complete"
    ],
}


def read_last_results() -> dict:
    results_file = ROOT / "scripts" / "skill-testing" / "last_results.json"
    if not results_file.exists():
        print("No test results found. Run test_triggers.py first.")
        return {}
    return json.loads(results_file.read_text())


def get_skill_path(skill_name: str) -> Path:
    return ROOT / ".claude" / "skills" / skill_name / "SKILL.md"


def read_skill_content(skill_name: str) -> str:
    path = get_skill_path(skill_name)
    return path.read_text() if path.exists() else ""


def patch_description(content: str, new_keywords: list[str]) -> str:
    """Add keywords to skill description without breaking frontmatter."""
    # Find description in frontmatter
    lines   = content.split("\n")
    result  = []
    in_fm   = False
    fm_done = False
    desc_end_idx = None

    for i, line in enumerate(lines):
        if line.strip() == "---":
            if not in_fm:
                in_fm = True
            else:
                fm_done = True
        if in_fm and not fm_done and (
            line.startswith("  ") or
            (i > 0 and lines[i-1].startswith("description:"))
        ):
            # Track where description ends
            if lines[i-1].startswith("description:") or (
                i > 1 and lines[i-2].startswith("description:")
            ):
                desc_end_idx = i
        result.append(line)

    if desc_end_idx is None:
        return content  # Can't find description

    # Add keyword line before description ends
    keyword_line = (
        f"  Also triggers on: "
        + ", ".join(new_keywords[:6])
        + "."
    )

    result.insert(desc_end_idx, keyword_line)
    return "\n".join(result)


def tune_all(apply: bool = False):
    results = read_last_results()
    if not results:
        return

    print(f"\n{'═'*52}")
    print(f"  Skill Description Tuner")
    print(f"  Mode: {'APPLY' if apply else 'DRY RUN'}")
    print(f"{'═'*52}")

    overall = results.get("results", {})
    patched = 0

    for skill_name, data in overall.items():
        recall    = data.get("recall", 1.0)
        precision = data.get("precision", 1.0)
        score     = (recall + precision) / 2
        missed    = data.get("missed", [])

        if score >= 0.85:
            print(f"\n  ✓ {skill_name}: {score*100:.0f}% — OK, no changes")
            continue

        supplements = KEYWORD_SUPPLEMENTS.get(skill_name, [])
        if not supplements:
            print(f"\n  ⚠ {skill_name}: {score*100:.0f}% — no supplements defined")
            continue

        print(f"\n  ✗ {skill_name}: {score*100:.0f}% — needs tuning")
        print(f"    Adding keywords: {', '.join(supplements[:4])}...")

        if apply:
            content = read_skill_content(skill_name)
            if content:
                new_content = patch_description(content, supplements)
                get_skill_path(skill_name).write_text(new_content)
                patched += 1
                print(f"    ✓ Patched")
        else:
            print(f"    (dry run — use --apply to patch)")

    if apply and patched > 0:
        print(f"\n  Patched {patched} skill descriptions")
        print(f"  Run test_triggers.py again to verify improvement")
    elif not apply:
        print(f"\n  Run with --apply to apply changes")


if __name__ == "__main__":
    apply = "--apply" in sys.argv
    tune_all(apply=apply)
