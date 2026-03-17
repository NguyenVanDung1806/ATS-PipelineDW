---
name: validate-pipeline
description: Run full pipeline validation suite before merging any branch.
  Invoke with /validate-pipeline to run security scan, dbt compile,
  dbt run, dbt test, and infrastructure checks in sequence.
  Use before every git merge, PR review, or deployment.
disable-model-invocation: false
context: fork
agent: general-purpose
---

Run full pipeline validation. Stop at first failure and report clearly.

## Validation sequence

Execute these steps **in order**. Stop immediately on any failure.

### Step 1 — Security scan
```bash
python3 scripts/validate/check_credentials.py
```
Expected: "Security scan: clean"
Fail: BLOCKED — shows file and line with credential

### Step 2 — Infrastructure check
Use the `infra-checker` agent to verify all Docker services are running.

### Step 3 — dbt compile
```bash
cd dbt && dbt compile --quiet
```
Expected: exit code 0
Fail: show compilation errors

### Step 4 — dbt staging
```bash
cd dbt && dbt run --select staging --quiet
cd dbt && dbt test --select staging --quiet
```
Both must pass before continuing.

### Step 5 — dbt marts
```bash
cd dbt && dbt run --select marts --quiet
cd dbt && dbt test --select marts --quiet
```
All tests must pass.

### Step 6 — Edge case check
Use the `edge-case-checklist` skill on any files changed in the last commit:
```bash
git diff --name-only HEAD~1
```
Run checklist against each changed extractor or dbt model.

## Final report format

```
══════════════════════════════════
Pipeline Validation Report
══════════════════════════════════
Step 1 Security scan:    PASS ✓
Step 2 Infrastructure:   PASS ✓
Step 3 dbt compile:      PASS ✓
Step 4 dbt staging:      PASS ✓ (12 tests)
Step 5 dbt marts:        PASS ✓ (8 tests)
Step 6 Edge cases:       PASS ✓

RESULT: Ready to merge ✓
══════════════════════════════════
```

If any step fails:
```
Step 4 dbt staging:  FAIL ✗
  Error: unique constraint violated on fct_ad_spend
  File: dbt/models/marts/fct_ad_spend.sql
  Fix: check unique_key config includes all partition columns

RESULT: DO NOT MERGE — fix Step 4 first
```
