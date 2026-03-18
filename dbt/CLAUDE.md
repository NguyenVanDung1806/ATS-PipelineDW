# dbt Layer Context

> Auto-loaded khi Claude Code làm việc trong dbt/
> Supplement root CLAUDE.md, không replace

## Model Status
<!-- Updated automatically -->

### Staging (stg_*)
| Model | Tests | Status |
|-------|-------|--------|
| stg_facebook_ads | built-in | ✓ LIVE — view in raw schema |

### Marts (fct_*)
| Model | Tests | Status |
|-------|-------|--------|
| fct_ad_spend | built-in | ✓ LIVE — incremental UPSERT in dw schema |

### Dimensions (dim_*)
| Model | Tests | Status |
|-------|-------|--------|
| (none yet) | — | — |

## dbt-specific Gotchas
<!-- Add as discovered -->
- packages.yml must be synced: run `dbt deps` after any change
- unique_key in incremental models MUST include partition column (date)
- `on_schema_change='fail'` is intentional — explicit is better than silent
- **Schema prefix bug (fixed)**: dbt default concatenates profile.schema + model.schema → `raw` + `dw` = `raw_dw`. Fix: `macros/generate_schema_name.sql` overrides this to use custom_schema directly. ALWAYS have this macro.

## Run Order
```bash
dbt deps              # first time or after packages.yml change
dbt run --select staging && dbt test --select staging
dbt run --select marts  && dbt test --select marts
```

## Current Focus
Working on: Phase 1 complete — fct_ad_spend LIVE with 142 rows (FB, 2026-03-11→18). Next: Metabase dashboard setup.
