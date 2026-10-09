-- 00_cost_guard.sql
-- Run once, as ACCOUNTADMIN, in JOPUFPW-EDGAR_13F (Standard, AWS_US_EAST_1)
-- before any other object exists. Idempotent (safe to rerun: a second run
-- of the same input changes nothing).
--
-- A resource monitor caps warehouse credits only. Snowpipe and other
-- serverless features are outside it; the account budget covers them with
-- a notification, not a stop.

use role accountadmin;

-- 1. Cap warehouse credits for the whole trial. FREQUENCY = NEVER so the
--    count does not reset on 1 November, halfway through the trial.
--    Standard in N. Virginia is $2.00 a credit, so the $400 balance is
--    about 200 credits. 150 credits ($300) leaves about $100 for
--    serverless Snowpipe and storage, which the monitor cannot see.
create resource monitor if not exists edgar_trial_monitor with
    credit_quota = 150
    frequency = never
    start_timestamp = immediately
    triggers
        on 50 percent do notify
        on 80 percent do notify
        on 90 percent do suspend
        on 100 percent do suspend_immediate;

-- 2. The project's one warehouse. Created suspended, so creating it costs
--    nothing. AUTO_SUSPEND = 60: the suspend poller runs about every 30 s,
--    so values below 30 or not a multiple of 30 behave unexpectedly.
--    GENERATION = '1' pins the documented 1 credit per hour for X-Small;
--    Gen2 bills more per hour. Query acceleration and multi-cluster are
--    Enterprise features, so Standard has neither to switch off.
create warehouse if not exists edgar_wh with
    warehouse_size = xsmall
    generation = '1'
    auto_suspend = 60
    auto_resume = true
    initially_suspended = true
    resource_monitor = edgar_trial_monitor
    statement_timeout_in_seconds = 3600;

-- 3. The notebook warehouse Snowflake provisioned with the account
--    (2026-10-09). Notebooks are not used here; it sits under the monitor
--    so it cannot run uncapped.
alter warehouse system$streamlit_notebook_wh set
    resource_monitor = edgar_trial_monitor;

-- 4. The account budget, the only guard that sees serverless spend. It
--    emails, it does not stop anything, and it refreshes up to 6.5 hours
--    behind. The limit is monthly; at threshold 50 the email goes out when
--    projected spending passes 90 credits. The address must be verified in
--    Snowsight; it is passed at run time so it stays out of the repository.
call snowflake.local.account_root_budget!activate();
call snowflake.local.account_root_budget!set_spending_limit(180);
call snowflake.local.account_root_budget!set_notification_threshold(50);
call snowflake.local.account_root_budget!set_email_notifications('<alert email>');

-- 5. The check that ends every session: every row should say SUSPENDED,
--    and the monitor shows credits used against the quota.
show warehouses;
show resource monitors;

-- The trial's first account (Enterprise, AWS_SA_EAST_1) stays as the
-- organization's ORGADMIN account. It ran sections 1 to 3 with query
-- acceleration switched off on its three warehouses, and is frozen with:
--   alter resource monitor edgar_trial_monitor set credit_quota = 1;
