-- Applications submitted per calendar month, publishable as-is.
--
-- Counts only rows with an applied_date, so this is "applications actually
-- submitted in a month", not the full 460: To Apply rows have no submission
-- date by definition. The dashboard labels it accordingly.
--
-- Separate from mart_public_metrics for the same reason as the channel
-- counts: that model is a fixed name/value table, and months are a
-- variable-width set of keys.
select
    format_date('%Y-%m', applied_date) as month,
    count(*) as applied_count
from {{ ref('stg_applications') }}
where applied_date is not null
group by month
order by month
