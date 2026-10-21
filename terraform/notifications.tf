# S3 tells each pipe about its new files through the SQS queue Snowflake
# created for it. Snowflake reuses one queue for the account's pipes in a
# region, so the ARNs usually match, and S3 refuses two notifications on
# overlapping paths, so each pipe's prefix is its own entry. S3 sends a test
# message when the configuration is saved and rejects it if it cannot
# publish, so a clean apply proves the wiring. This resource owns the
# bucket's whole notification configuration: any other notification on this
# bucket has to be added here.
resource "aws_s3_bucket_notification" "landing" {
  bucket = aws_s3_bucket.landing.id

  queue {
    id            = "parsed-filings-to-snowpipe"
    queue_arn     = snowflake_pipe.parsed_filings.notification_channel
    events        = ["s3:ObjectCreated:*"]
    filter_prefix = "parsed/edgar/filings/"
    filter_suffix = ".jsonl"
  }

  dynamic "queue" {
    for_each = local.audit_records

    content {
      id            = "${lower(replace(queue.key, "_", "-"))}-to-snowpipe"
      queue_arn     = snowflake_pipe.audit[queue.key].notification_channel
      events        = ["s3:ObjectCreated:*"]
      filter_prefix = queue.value
      filter_suffix = ".json"
    }
  }
}
