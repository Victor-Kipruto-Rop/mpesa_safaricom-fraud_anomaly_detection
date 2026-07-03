with transactions as (
    select * from {{ ref('int_transactions_cleaned') }}
),
county_performance as (
    select
        county,
        count(*) as total_transactions,
        sum(amount_kes) as total_volume_kes,
        avg(amount_kes) as avg_transaction_value,
        count(distinct sender_id) as unique_senders
    from transactions
    group by 1
)
select * from county_performance
