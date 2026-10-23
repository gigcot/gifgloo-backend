BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '15s';

SELECT payment_environment, status, currency,
       count(*) AS orders, count(DISTINCT user_id) AS accounts,
       sum(amount) AS order_amount,
       count(*) FILTER (WHERE credit_granted_at IS NOT NULL) AS credit_granted_orders
FROM payments
WHERE created_at >= :'cohort_start'::timestamptz
  AND created_at < :'cohort_end'::timestamptz
  AND created_at <= :'observed_until'::timestamptz
  AND user_id != ALL(string_to_array(:'internal_account_ids', ','))
GROUP BY payment_environment, status, currency
ORDER BY payment_environment, status, currency;

ROLLBACK;
