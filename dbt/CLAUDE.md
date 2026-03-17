# dbt Layer Context

> Auto-loaded khi Claude Code làm việc trong dbt/
> Supplement root CLAUDE.md, không replace

## Model Status
<!-- Updated automatically -->

### Staging (stg_*)
| Model | Tests | Status |
|-------|-------|--------|
| stg_facebook_ads | 0 | EXAMPLE — delete when real models added |

### Marts (fct_*)
| Model | Tests | Status |
|-------|-------|--------|
| fct_ad_spend | 0 | EXAMPLE |

### Dimensions (dim_*)
| Model | Tests | Status |
|-------|-------|--------|
| (none yet) | — | — |

## dbt-specific Gotchas
<!-- Add as discovered -->
- packages.yml must be synced: run `dbt deps` after any change
- unique_key in incremental models MUST include partition column (date)
- `on_schema_change='fail'` is intentional — explicit is better than silent

## Run Order
```bash
dbt deps              # first time or after packages.yml change
dbt run --select staging && dbt test --select staging
dbt run --select marts  && dbt test --select marts
```

## Current Focus
Working on: —
