# dbt Medallion Project Quick Reference

## 📁 Project Structure

```
mpesa_safaricom/dbt/
├── dbt_project.yml                 # Project configuration
├── profiles.yml                    # Database connection (create locally)
├── macros/
│   └── safe_divide.sql            # Macro: null-safe division
├── models/
│   ├── sources.yml                # Source definitions (raw data)
│   ├── schema.yml                 # All tests and descriptions
│   ├── staging/
│   │   ├── stg_fraud_alerts.sql   # Types + validates raw alerts
│   │   ├── stg_review_outcomes.sql # Types + validates analyst outcomes
│   │   └── stg_check_results.sql  # Unnests JSON check results
│   ├── intermediate/
│   │   ├── int_txns_with_outcomes.sql           # Transactions + outcomes
│   │   ├── int_check_performance_daily.sql      # Daily check metrics
│   │   └── int_check_trigger_analysis.sql       # Time series trends
│   └── marts/
│       ├── fraud/
│       │   ├── fct_fraud_decisions.sql        # Primary fact table (incremental)
│       │   └── dim_msisdn_risk_profile.sql    # Customer risk dimension (SCD Type 2)
│       └── ops/
│           ├── review_queue_mart.sql          # Analyst review queue analytics
│           └── business_impact_mart.sql       # Leadership fraud value metrics
└── tests/
    └── mart_fct_fraud_decisions_unique.sql   # Custom uniqueness test
```

## 🎯 Layer Definitions

### Silver (Staging) — Typed Raw Data
- **Purpose:** Clean, consistent typing of raw data
- **Materialization:** `view`
- **Tests:** not_null, unique, accepted_values
- **Update Frequency:** Continuous (real-time from Kafka)

| Model | Input | Key Operations |
|-------|-------|-----------------|
| stg_fraud_alerts | raw.fraud_alerts | Type coercion, date extraction, flag validation |
| stg_review_outcomes | raw.review_outcomes | Label validation, timestamp coercion |
| stg_check_results | raw.fraud_alerts JSON | UNNEST rules_triggered array |

### Gold (Intermediate) — Analytics-Ready Datasets
- **Purpose:** Aggregations, joins, performance calculations
- **Materialization:** `view`
- **Tests:** freshness, relationships, custom logic checks
- **Update Frequency:** Near real-time

| Model | Purpose | Key Metrics |
|-------|---------|------------|
| int_txns_with_outcomes | Score + outcome join | outcome_classification, is_confirmed_fraud |
| int_check_performance_daily | Per-check daily agg | confirmed_fraud_rate, confirmed_legitimate_rate |
| int_check_trigger_analysis | Time series trends | precision_pct, recall_pct, trigger_rate_pct |

### Gold (Marts) — Business Metrics & Dimensions
- **Purpose:** Decision-support reporting, dashboards
- **Materialization:** `table` (replicated daily or incremental)
- **Tests:** Complete suite (not_null, unique, relationships, custom)
- **Update Frequency:** Daily or real-time

**Fraud Domain:**
| Model | Type | Key Columns | Use Cases |
|-------|------|------------|-----------|
| fct_fraud_decisions | Fact (Incremental) | alert_id (PK), risk_score, analyst_confirmed_label, review_lag_minutes | Fraud analysis, drill-down |
| dim_msisdn_risk_profile | Dimension (SCD Type 2) | msisdn (SK), risk_tier, velocity_limit, valid_from, is_current | Customer risk trends, risk-based segmentation |

**Ops Domain:**
| Model | Type | Key Columns | Use Cases |
|-------|------|------------|-----------|
| review_queue_mart | Mart | alert_id (PK), queue_status, sla_status, queue_age_hours, analyst_efficiency_score | Review queue management, SLA tracking |
| business_impact_mart | Mart | impact_date (PK), fraud_value_caught_kes, false_positive_cost_kes, block_accuracy_rate_pct | Leadership reporting, fraud value metrics |

## 🔧 Setup & Execution

### 1. Initial Setup
```bash
cd mpesa_safaricom/dbt

# Create profiles.yml
cat > profiles.yml << EOF
mpesa_analytics:
  target: dev
  outputs:
    dev:
      type: postgres
      host: localhost
      user: data_engineer
      password: <password>
      port: 5432
      dbname: mpesa_analytics
      schema: analytics
      threads: 4
      keepalives_idle: 0
EOF

# Install dependencies
dbt deps

# Validate setup
dbt debug
```

### 2. Build & Test
```bash
# Parse models (syntax check)
dbt parse

# Build all models
dbt build

# Run tests only
dbt test

# Build specific model
dbt build --select fct_fraud_decisions

# Build with dependencies
dbt build --select +fct_fraud_decisions
```

### 3. Continuous Validation
```bash
# Validate data freshness (alerts if source is stale)
dbt source freshness

# Generate documentation
dbt docs generate

# Serve documentation locally
dbt docs serve
```

## 📊 Model Dependencies

```
raw.fraud_alerts ─────────┬─────────► stg_fraud_alerts ───┐
                          │                                ├─► int_txns_with_outcomes
raw.review_outcomes ───► stg_review_outcomes ─────────────┤
                                                           ├─► fct_fraud_decisions ──┬─► review_queue_mart
                          stg_check_results ──────┬────────┤                        │
                                                  │        ├─► int_check_performance_daily
                                                  └────────┤
                                                           └─► int_check_trigger_analysis
                                                                     │
                                                                     └─► business_impact_mart

dim_msisdn_risk_profile ◄──────────── fct_fraud_decisions
```

## 🧪 Test Coverage

### Staging Models (stg_*)
- ✅ Not null on all key columns
- ✅ Unique on primary keys
- ✅ Accepted values on enums (severity, labels)

### Intermediate Models (int_*)
- ✅ Freshness checks on source data
- ✅ Relationships (FK constraints)
- ✅ Custom: data quality flags, no future timestamps

### Mart Models
- ✅ Uniqueness on surrogate/primary keys
- ✅ Not null on decision columns
- ✅ Relationships to upstream tables
- ✅ Custom: review lag reasonableness, confirmed rate logic
- ✅ Source freshness: fraud_alerts (warn 5m, error 10m)

## 📈 Key Features & Patterns

### 1. Safe Division (Macro)
```sql
{{ safe_divide('numerator', 'denominator') }}
-- Returns NULL if denominator = 0, avoiding division errors
```

### 2. Incremental Fact Table (fct_fraud_decisions)
```sql
{{ config(
    materialized='incremental',
    unique_id='alert_id'
) }}

WHERE ingestion_timestamp >= DATEADD(HOUR, -6, run_started_at)
-- Allows late arrivals up to 6 hours after initial ingestion
```

### 3. SCD Type 2 Dimension (dim_msisdn_risk_profile)
```sql
-- Surrogate key = dbt_utils.surrogate_key(['msisdn', 'valid_from'])
-- valid_to = NULL (current), is_current = TRUE (current), valid_from = DATE (when change occurred)
-- Tracks risk tier changes (CRITICAL/HIGH/MEDIUM/LOW) per customer
```

### 4. Macro Usage
```sql
-- In int_check_performance_daily.sql
{{ safe_divide(
    'COUNT(DISTINCT fraud_alerts)',
    'COUNT(DISTINCT all_alerts)'
) }} AS fraud_confirmation_rate
```

## 📋 Common Maintenance Tasks

### Add New Check to Model
```sql
-- In stg_check_results or int_check_trigger_analysis
-- Add new check name and enable triggering in schema.yml

# In schema.yml
- name: int_check_trigger_analysis
  columns:
    - name: check_name
      tests:
        - accepted_values:
            values: ['velocity_check', 'blacklist_check', 'new_check_name']
```

### Adjust Risk Tier Logic
```sql
-- In dim_msisdn_risk_profile.sql
-- Modify case statement for CRITICAL/HIGH/MEDIUM/LOW based on business rules
```

### Update SLA Thresholds
```sql
-- In review_queue_mart.sql
-- Change "24 HOUR" to desired SLA window (currently 24h target, 12h warning)
```

## 🔍 Troubleshooting

**Build Fails on Foreign Key**
- Verify upstream table exists: `dbt ls --select parent_table`
- Check column names match exactly (SQL is case-sensitive)

**Tests Pass Locally, Fail in CI**
- Check thread count: reduce from 4 to 1 for debugging
- Verify database user has SELECT permissions on all schemas

**Incremental Model Grows Too Large**
- Check late-arrival window: 6-hour lookback may be too wide
- Consider reducing to 1-2 hours if ingestion latency is low

**SCD Type 2 Dimension Not Updating**
- Verify `valid_from` date changes when risk tier changes
- Check `is_current` flag is set correctly for latest records

## 📚 References

- dbt Best Practices: https://docs.getdbt.com/guides/best-practices
- Incremental Models: https://docs.getdbt.com/docs/build/incremental-models
- Testing: https://docs.getdbt.com/docs/build/tests
- Macros: https://docs.getdbt.com/docs/build/jinja-macros

---

**Last Updated:** 2026-01-03  
**Maintained By:** Data Engineering Team  
**Version:** 1.0 (Production Ready)
