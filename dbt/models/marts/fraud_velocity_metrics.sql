with flagged as (
    select * from {{ ref('int_flagged_transactions') }}
),
velocity as (
    select
        txn_hour,
        channel,
        count(*) as txn_count,
        sum(case when is_fraud_label = 1 then 1 else 0 end) as fraud_count,
        avg(amount_kes) as avg_amount
    from flagged
    group by 1, 2
)
select * from velocity
