with stg as (
    select * from {{ ref('stg_transactions') }}
),
cleaned as (
    select
        *,
        extract(hour from transaction_timestamp) as transaction_hour,
        case 
            when extract(hour from transaction_timestamp) between 0 and 5 then 'Night'
            when extract(hour from transaction_timestamp) between 6 and 11 then 'Morning'
            when extract(hour from transaction_timestamp) between 12 and 17 then 'Afternoon'
            else 'Evening'
        end as time_bin
    from stg
    where amount_kes > 0
)
select * from cleaned
