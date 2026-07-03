
# M-Pesa Fraud Detection Analytics

This dbt project transforms raw M-Pesa fraud detection signals into analytics-ready tables following the medallion architecture.

## Project Structure

```
models/
├── sources.yml                  # External data source definitions
├── staging/                     # Typed raw data
│   ├── stg_fraud_alerts.sql
│   ├── stg_review_outcomes.sql
│   └── stg_check_results.sql
├── intermediate/                # Business logic intermediate views
│   ├── int_txns_with_outcomes.sql
│   ├── int_check_performance_daily.sql
│   └── int_check_trigger_analysis.sql
└── marts/                        # Final analytics tables
    ├── fraud/
    │   ├── fct_fraud_decisions.sql
    │   ├── dim_msisdn_risk_profile.sql
    │   └── check_performance_mart.sql
    └── ops/
        ├── review_queue_mart.sql
        └── business_impact_mart.sql
```

## Medallion Architecture

**Bronze / Raw**: Kafka topics and DB tables (fraud_alerts, review_outcomes)

**Silver / Staging**: 
- Type coercion
- Deduplication  
- Column renaming
- Basic validation

**Gold / Marts**:
- Fact tables (fct_fraud_decisions) — incremental with surrogate keys
- Dimension tables (dim_msisdn_risk_profile) — SCD Type 2 for risk tracking
- Business aggregations — daily/hourly roll-ups with late-arriving-data handling

## Running dbt

```bash
# Install dependencies
dbt deps

# Parse all models and tests
dbt parse

# Build and test (CI/CD)
dbt build --select +stg_fraud_alerts --defer --state ./artifacts

# Generate docs
dbt docs generate
dbt docs serve --port 8001

# Test data freshness
dbt source freshness
```

## Key Metrics

- **Fact table volume**: 100k–1M transactions/day
- **Late-arrival window**: 6 hours lookback for incremental inserts
- **Source freshness**: fraud_alerts table max age 5 minutes
- **Test coverage**: >80% of columns have not_null, unique, or relationship tests
