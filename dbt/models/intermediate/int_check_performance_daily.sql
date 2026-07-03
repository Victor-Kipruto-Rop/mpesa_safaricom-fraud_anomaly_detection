{{
  config(
    materialized='view',
    description='Intermediate: Daily check performance metrics',
    tags=['intermediate']
  )
}}

-- Aggregates per-check trigger and confirmation stats by day

SELECT
    alert_date,
    check_name,
    
    -- Volume metrics
    COUNT(DISTINCT c.alert_id) AS total_triggers,
    COUNT(DISTINCT CASE WHEN c.check_triggered THEN c.alert_id END) AS true_triggers,
    
    -- Confirmed outcomes
    COUNT(DISTINCT CASE 
        WHEN fct.analyst_confirmed_label = 'FRAUD' 
        THEN fct.alert_id 
    END) AS confirmed_fraud_count,
    
    COUNT(DISTINCT CASE 
        WHEN fct.analyst_confirmed_label = 'LEGITIMATE' 
        THEN fct.alert_id 
    END) AS confirmed_legitimate_count,
    
    -- Calculated rates
    {{ safe_divide(
        'COUNT(DISTINCT CASE WHEN fct.analyst_confirmed_label = \'FRAUD\' THEN fct.alert_id END)',
        'COUNT(DISTINCT CASE WHEN fct.analyst_confirmed_label IN (\'FRAUD\', \'LEGITIMATE\') THEN fct.alert_id END)'
    ) }} AS confirmed_fraud_rate,
    
    {{ safe_divide(
        'COUNT(DISTINCT CASE WHEN fct.analyst_confirmed_label = \'LEGITIMATE\' THEN fct.alert_id END)',
        'COUNT(DISTINCT CASE WHEN fct.analyst_confirmed_label IN (\'FRAUD\', \'LEGITIMATE\') THEN fct.alert_id END)'
    ) }} AS confirmed_legitimate_rate,
    
    -- Average score for triggered checks
    AVG(CASE WHEN c.check_triggered THEN c.check_score END) AS avg_check_score_when_triggered,
    
    CURRENT_TIMESTAMP AS dbt_load_timestamp
    
FROM {{ ref('stg_check_results') }} c
LEFT JOIN {{ ref('fct_fraud_decisions') }} fct
    ON c.alert_id = fct.alert_id
    
GROUP BY alert_date, check_name
