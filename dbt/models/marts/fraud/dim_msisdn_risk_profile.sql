{{
  config(
    materialized='table',
    description='Customer risk profile dimension with SCD Type 2 (slowly changing dimension)',
    tags=['marts', 'fraud', 'scd']
  )
}}

-- SCD Type 2: tracks customer risk profile changes over time
-- Enables historical analysis of when and how customer risk tier changed

SELECT
    -- Surrogate key
    {{ dbt_utils.surrogate_key(['msisdn', 'valid_from']) }} AS risk_profile_sk,
    
    -- Natural key
    msisdn,
    
    -- Risk attributes
    risk_tier,
    velocity_limit,
    velocity_breach_count_30d,
    avg_transaction_size,
    distinct_recipients_30d,
    distinct_locations_30d,
    
    -- SCD Type 2 columns
    valid_from,
    valid_to,
    is_current,
    
    -- Audit
    CURRENT_TIMESTAMP AS dbt_load_timestamp
    
FROM (
    SELECT
        msisdn,
        
        -- Risk tier assignment logic
        CASE
            WHEN avg_transaction_size > 100000 AND velocity_breach_count_30d > 2 THEN 'CRITICAL'
            WHEN avg_transaction_size > 50000 OR velocity_breach_count_30d > 1 THEN 'HIGH'
            WHEN distinct_recipients_30d > 50 THEN 'MEDIUM'
            ELSE 'LOW'
        END AS risk_tier,
        
        -- Per-tier velocity limits (daily)
        CASE
            WHEN avg_transaction_size > 100000 THEN 500000
            WHEN avg_transaction_size > 50000 THEN 1000000
            WHEN distinct_recipients_30d > 50 THEN 2000000
            ELSE 5000000
        END AS velocity_limit,
        
        velocity_breach_count_30d,
        avg_transaction_size,
        distinct_recipients_30d,
        distinct_locations_30d,
        
        -- Effective dates
        DATE(detected_timestamp) AS valid_from,
        NULL AS valid_to,
        TRUE AS is_current
        
    FROM {{ ref('int_txns_with_outcomes') }}
    WINDOW transactions_per_msisdn AS (
        PARTITION BY msisdn 
        ORDER BY detected_timestamp DESC
    )
    WHERE ROW_NUMBER() OVER transactions_per_msisdn = 1
)
