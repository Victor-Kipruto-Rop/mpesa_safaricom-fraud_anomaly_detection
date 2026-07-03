with transactions as (
    select * from {{ ref('int_transactions_cleaned') }}
),
fraud_metrics as (
    select
        county,
        time_bin,
        count(*) as total_transactions,
        sum(case when is_fraud_flag then 1 else 0 end) as fraud_count,
        sum(amount_kes) as total_volume_kes,
        sum(case when is_fraud_flag then amount_kes else 0 end) as fraud_volume_kes
    from transactions
    group by 1, 2
)
select 
    *,
    (fraud_count::float / nullif(total_transactions, 0)) * 100 as fraud_rate_percentage
from fraud_metrics
