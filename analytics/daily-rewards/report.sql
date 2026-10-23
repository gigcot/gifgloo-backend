BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '15s';

WITH survey_users AS (
    SELECT user_id, submitted_at
    FROM experiment_survey_responses
    WHERE experiment_code = 'EXP-001'
      AND submitted_at >= :'cohort_start'::timestamptz
      AND submitted_at < :'cohort_end'::timestamptz
      AND submitted_at <= :'observed_until'::timestamptz
      AND user_id != ALL(string_to_array(:'internal_account_ids', ','))
), claims AS (
    SELECT l.account_user_id AS user_id,
           min(l.created_at) AS first_claim_at,
           count(*) AS claim_days,
           sum(l.granted_amount) / 10 AS granted_uses
    FROM credit_lots l
    JOIN survey_users s ON s.user_id = l.account_user_id
    WHERE l.source_type = 'DAILY_REWARD'
      AND l.created_at <= :'observed_until'::timestamptz
    GROUP BY l.account_user_id
), daily_consumption AS (
    SELECT d.account_user_id AS user_id,
           count(*) AS deducted_jobs,
           count(*) FILTER (WHERE r.id IS NOT NULL) AS refunded_jobs,
           count(*) FILTER (WHERE j.status = 'COMPLETED' AND r.id IS NULL) AS completed_daily_jobs,
           count(*) FILTER (WHERE j.status = 'FAILED') AS failed_daily_jobs
    FROM credit_transactions d
    JOIN credit_lots l ON l.id = d.credit_lot_id AND l.source_type = 'DAILY_REWARD'
    JOIN survey_users s ON s.user_id = d.account_user_id
    LEFT JOIN composition_jobs j ON j.id = d.source_id AND j.user_id = d.account_user_id
    LEFT JOIN credit_transactions r ON r.account_user_id = d.account_user_id
        AND r.source_type = 'COMPOSITION' AND r.source_id = d.source_id
        AND r.transaction_type = 'REFUND' AND r.created_at <= :'observed_until'::timestamptz
    WHERE d.transaction_type = 'DEDUCT' AND d.source_type = 'COMPOSITION'
      AND d.created_at <= :'observed_until'::timestamptz
    GROUP BY d.account_user_id
), production AS (
    SELECT j.user_id,
           count(*) FILTER (WHERE j.status = 'COMPLETED') AS completed_jobs_after_first_claim,
           count(DISTINCT (j.created_at AT TIME ZONE 'Asia/Seoul')::date)
               FILTER (WHERE j.status = 'COMPLETED') AS production_days_kst,
           min(j.created_at) FILTER (WHERE j.status = 'COMPLETED') AS first_production_at,
           max(j.created_at) FILTER (WHERE j.status = 'COMPLETED') AS last_production_at
    FROM composition_jobs j
    JOIN claims c ON c.user_id = j.user_id
    WHERE j.created_at >= c.first_claim_at
      AND j.created_at <= :'observed_until'::timestamptz
    GROUP BY j.user_id
)
SELECT s.user_id, s.submitted_at, :'observed_until'::timestamptz AS observed_until,
       c.first_claim_at,
       extract(epoch FROM (:'observed_until'::timestamptz - c.first_claim_at)) / 86400 AS days_since_first_claim,
       coalesce(c.claim_days, 0) AS claim_days,
       coalesce(c.granted_uses, 0) AS granted_uses,
       coalesce(d.deducted_jobs, 0) AS deducted_daily_jobs,
       coalesce(d.refunded_jobs, 0) AS refunded_daily_jobs,
       coalesce(d.completed_daily_jobs, 0) AS completed_daily_jobs,
       coalesce(d.failed_daily_jobs, 0) AS failed_daily_jobs,
       coalesce(p.completed_jobs_after_first_claim, 0) AS completed_jobs_after_first_claim,
       coalesce(p.production_days_kst, 0) AS production_days_kst,
       p.first_production_at, p.last_production_at
FROM survey_users s
LEFT JOIN claims c ON c.user_id = s.user_id
LEFT JOIN daily_consumption d ON d.user_id = s.user_id
LEFT JOIN production p ON p.user_id = s.user_id
ORDER BY completed_daily_jobs DESC, s.submitted_at;

ROLLBACK;
