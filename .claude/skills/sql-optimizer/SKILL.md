---
name: sql-optimizer
description: Apply when writing complex SQL queries, optimizing slow queries,
  designing indexes, writing window functions, CTEs, or any advanced SQL.
  Auto-invoked for: complex JOIN queries, GROUP BY with multiple aggregations,
  window functions (ROW_NUMBER, LAG, LEAD), query performance issues,
  partition pruning, explain plan analysis, index design.
  Use whenever SQL performance or correctness is a concern.
allowed-tools: Read, Write, Bash(psql *)
---

# SQL Optimizer — PostgreSQL 16 Patterns

## Partition pruning (critical with pg_partman)
```sql
-- GOOD: filter on partition key = only scan relevant partition
SELECT * FROM dw.fct_ad_spend
WHERE date BETWEEN '2026-03-01' AND '2026-03-31';

-- BAD: no partition key filter = full table scan
SELECT * FROM dw.fct_ad_spend
WHERE platform = 'facebook';
-- Fix: always include date range even when filtering other columns
```

## Window functions for marketing analytics
```sql
-- MoM CPL change
SELECT
    date_trunc('month', date)                              AS month,
    platform,
    SUM(spend) / NULLIF(SUM(leads), 0)                    AS cpl,
    LAG(SUM(spend) / NULLIF(SUM(leads), 0))
        OVER (PARTITION BY platform ORDER BY date_trunc('month', date))
                                                           AS prev_month_cpl,
    ROUND(
        (SUM(spend) / NULLIF(SUM(leads), 0) -
         LAG(SUM(spend) / NULLIF(SUM(leads), 0))
             OVER (PARTITION BY platform ORDER BY date_trunc('month', date)))
        / NULLIF(LAG(SUM(spend) / NULLIF(SUM(leads), 0))
             OVER (PARTITION BY platform ORDER BY date_trunc('month', date)), 0)
        * 100, 1
    )                                                       AS cpl_pct_change
FROM dw.fct_ad_spend
GROUP BY 1, 2;
```

## Reconciliation query pattern
```sql
-- EC-04: compare ad platform leads vs CRM leads
SELECT
    f.date,
    f.platform,
    f.leads                                     AS platform_reported_leads,
    COUNT(l.lead_id)                            AS crm_received_leads,
    f.leads - COUNT(l.lead_id)                  AS discrepancy,
    ROUND(COUNT(l.lead_id)::numeric
          / NULLIF(f.leads, 0) * 100, 1)        AS sync_rate_pct
FROM dw.fct_ad_spend f
LEFT JOIN dw.fact_leads l
    ON l.platform_source = f.platform
    AND DATE(l.created_at) = f.date
WHERE f.date >= CURRENT_DATE - 14
GROUP BY 1, 2, 3
ORDER BY 1 DESC, sync_rate_pct ASC;
```

## Index design for common query patterns
```sql
-- Composite index for date + platform queries (most common)
CREATE INDEX CONCURRENTLY idx_fct_ad_spend_date_platform
    ON dw.fct_ad_spend (date, platform)
    WHERE date >= '2026-01-01';

-- Partial index for active leads only
CREATE INDEX CONCURRENTLY idx_fact_leads_active
    ON dw.fact_leads (office, counselor_id, created_at)
    WHERE stage NOT IN ('contract', 'lost');
```

## EXPLAIN ANALYZE pattern
```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT ...;
-- Look for: Seq Scan on large tables → needs index
-- Look for: Hash Join on large sets → consider nested loop with index
-- Look for: high Buffers hit/read ratio → cache miss, add index
```

## Safe division (never divide by zero)
```sql
-- Always use NULLIF for denominators
SUM(spend) / NULLIF(SUM(leads), 0)   AS cpl
SUM(clicks) / NULLIF(SUM(impressions), 0) * 100  AS ctr_pct
```
