# The historical path into Snowflake: the backfill DAG extracts each table of
# each SEC 13F data set zip into extracted/sec/datasets/table=<TABLE>/ as gzip,
# and a bulk COPY run as LOADER loads them into RAW.DATASET_<TABLE>. No pipe
# and no bucket notification: the backfill is one load, run and reconciled by
# hand, not a stream.

# The TSV format, settled by a scan of all 125.9 million rows on 2026-10-11:
# one header line, tab-separated, no quoting and no escape character. 4,100
# rows carry a backslash, which the default escape would misread, and 7,907 a
# double quote, which stays literal. A row with the wrong number of fields
# fails the file instead of shifting columns. NULL_IF drops its default '\N',
# so only an empty field becomes NULL.
resource "snowflake_stage_external_s3" "datasets" {
  database            = "EDGAR_13F"
  schema              = "RAW"
  name                = "DATASETS_STAGE"
  url                 = "s3://${aws_s3_bucket.landing.bucket}/extracted/sec/datasets/"
  storage_integration = snowflake_storage_integration_aws.landing.name
  comment             = "Gzip TSVs extracted from the SEC 13F data set zips, one per table and zip"

  file_format {
    csv {
      compression                    = "GZIP"
      field_delimiter                = "\t"
      skip_header                    = 1
      field_optionally_enclosed_by   = "NONE"
      escape_unenclosed_field        = "NONE"
      error_on_column_count_mismatch = "true"
      null_if                        = [""]
      encoding                       = "UTF8"
    }
  }
}
