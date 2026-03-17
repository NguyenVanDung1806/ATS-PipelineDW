---
name: update-context
description: Update MEMORY.md and sub-CLAUDE.md files with current progress.
  Auto-invoked when: completing a task, finishing a file, before switching
  to a different component, when asked to save progress, after any
  significant milestone. Claude should call this proactively — not wait
  for user to ask. Triggers on: "done", "finished", "completed", "save",
  "moving on", "next task", "that's working".
disable-model-invocation: false
---

Update project context with current progress. Execute these steps:

## Step 1 — Auto-update via script
```bash
python3 scripts/context/context_manager.py session-end
```

## Step 2 — Update relevant sub-CLAUDE.md

If working on extractors → update `extractors/CLAUDE.md`:
- Change status table for completed platform (○ → ✓)
- Add any new gotchas discovered
- Update "Current Focus" line

If working on dbt → update `dbt/CLAUDE.md`:
- Add completed model to status table
- Note test count
- Update "Current Focus" line

If working on dags → update `dags/CLAUDE.md`:
- Add new DAG to status table
- Update "Current Focus" line

## Step 3 — Update MEMORY.md QUICK CONTEXT manually if needed

If auto-script missed something, update directly:
```
Current file: [exact file path]
Last action:  [what was just completed — specific]
Next action:  [exact next step — actionable]
```

## Step 4 — Confirm to user

Report:
```
Context updated:
  ✓ MEMORY.md QUICK CONTEXT refreshed
  ✓ [layer]/CLAUDE.md status updated
  ✓ Next action: [what user should do next]
```
