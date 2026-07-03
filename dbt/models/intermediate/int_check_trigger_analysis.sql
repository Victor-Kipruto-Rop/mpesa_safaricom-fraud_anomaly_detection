{{
  config(
    materialized='view',
    description='Intermediate: Time series analysis of check triggers and performance',
    tags=['intermediate']
  )
}}

-- Time series data for check trigger trends
-- Enables trending analysis of individual check behavior over time

SELECT
    alert_date,
    check_name,
    
    -- Hourly aggregations
    COUNT(DISTINCT alert_id) AS hourly_triggers,
    COUNT(DISTINCT CASE WHEN check_triggered THEN alert_id END) AS hourly_true_triggers,
    SUM(check_score) AS hourly_score_sum,
    AVG(check_score) AS hourly_avg_score,
    MAX(check_score) AS hourly_max_score,
    MIN(check_score) AS hourly_min_score,
    
    -- Trigger rate (percent of transactions that triggered check)
    ROUND(
        100.0 * COUNT(DISTINCT CASE WHEN check_triggered THEN alert_id END) /
        NULLIF(COUNT(DISTINCT alert_id), 0),
        2
    ) AS trigger_rate_pct,
    
    -- Confirmed outcomes for triggered checks
    COUNT(DISTINCT CASE
        WHEN check_triggered
        AND fct.analyst_confirmed_label = 'FRAUD'
        THEN checks.alert_id
    END) AS confirmed_fraud_when_triggered,
    
    COUNT(DISTINCT CASE
        WHEN check_triggered
        AND fct.analyst_confirmed_label = 'LEGITIMATE'
        THEN checks.alert_id
    END) AS confirmed_legitimate_when_triggered,
    
    -- Calculate precision (TP / (TP + FP))
    ROUND(
        100.0 * COUNT(DISTINCT CASE
            WHEN check_triggered
            AND fct.analyst_confirmed_label = 'FRAUD'
            THEN checks.alert_id
        END) / NULLIF(
            COUNT(DISTINCT CASE WHEN check_triggered THEN checks.alert_id END),
            0
        ),
        2
    ) AS check_precision_pct,
    
    -- Calculate recall (TP / (TP + FN)) - among confirmed frauds
    ROUND(
        100.0 * COUNT(DISTINCT CASE
            WHEN check_triggered
            AND fct.analyst_confirmed_label = 'FRAUD'
            THEN checks.alert_id
        END) / NULLIF(
            COUNT(DISTINCT CASE WHEN fct.analyst_confirmed_label = 'FRAUD' THEN checks.alert_id END),
            0
        ),
        2
    ) AS check_recall_pct,
    
    -- Audit
    CURRENT_TIMESTAMP AS dbt_load_timestamp
    
FROM {{ ref('stg_check_results') }} checks
LEFT JOIN {{ ref('fct_fraud_decisions') }} fct
    ON checks.alert_id = fct.alert_id

WHERE alert_date >= CURRENT_DATE - INTERVAL '90 days'

GROUP BY alert_date, check_name

ORDER BY alert_date DESC, check_name
