# The pipeline's audit records into AUDIT. The walk and the backfill each land
# one JSON record per attempt of a run, and one pipe per prefix loads each
# record as one row. The schema and tables come from numbered SQL
# (include/sql/08); only the S3 plumbing is declared here, as for the parsed
# filings. Each map key names the table its pipe loads.
locals {
  audit_records = {
    BACKFILL_RUNS = "raw/sec/audit/backfill/"
    WALK_RUNS     = "raw/edgar/audit/walk/"
  }
}

# One JSON object per file, which the inline JSON format reads as one row.
resource "snowflake_stage_external_s3" "audit" {
  for_each = local.audit_records

  database            = "EDGAR_13F"
  schema              = "AUDIT"
  name                = "${each.key}_STAGE"
  url                 = "s3://${aws_s3_bucket.landing.bucket}/${each.value}"
  storage_integration = snowflake_storage_integration_aws.landing.name
  comment             = "Audit records under ${each.value}, one per attempt of a run"

  file_format {
    json {
      compression = "AUTO"
    }
  }
}

# ON_ERROR = SKIP_FILE as for the parsed filings: a record loads whole or not
# at all. Every attempt writes a new key (include/landing.py), so the pipe's
# 14-day record of the paths it loaded never hides a rerun's record.
resource "snowflake_pipe" "audit" {
  for_each = local.audit_records

  database    = snowflake_stage_external_s3.audit[each.key].database
  schema      = snowflake_stage_external_s3.audit[each.key].schema
  name        = "${each.key}_PIPE"
  auto_ingest = true
  comment     = "Loads each new audit record into AUDIT.${each.key}"

  copy_statement = <<-SQL
    copy into EDGAR_13F.AUDIT.${each.key}
        (record, source_file, source_content_key, source_last_modified)
    from (
        select $1, metadata$filename,
               metadata$file_content_key, metadata$file_last_modified
        from @${snowflake_stage_external_s3.audit[each.key].fully_qualified_name}
    )
    on_error = skip_file
  SQL

  lifecycle {
    replace_triggered_by = [
      snowflake_stage_external_s3.audit[each.key].url,
      snowflake_stage_external_s3.audit[each.key].storage_integration,
    ]
  }
}
