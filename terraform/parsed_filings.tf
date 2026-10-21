# The XML path into Snowflake: include/edgar_xml.py writes one JSON-lines file
# per filing under parsed/edgar/filings/, and this pipe loads each new file
# into RAW.PARSED_FILINGS. The database, schema and table come from numbered
# SQL (include/sql/02 and 03); only the S3 plumbing is declared here.

# The stage carries the JSON format inline: one object per line, the default.
resource "snowflake_stage_external_s3" "parsed_filings" {
  database            = "EDGAR_13F"
  schema              = "RAW"
  name                = "PARSED_FILINGS_STAGE"
  url                 = "s3://${aws_s3_bucket.landing.bucket}/parsed/edgar/filings/"
  storage_integration = snowflake_storage_integration_aws.landing.name
  comment             = "JSON-lines files written by the parser, one per filing"

  file_format {
    json {
      compression = "AUTO"
    }
  }
}

# Every row names the file and line it came from through the METADATA$
# columns. ON_ERROR = SKIP_FILE is Snowpipe's default, written out because it
# is the contract: one bad line keeps the whole filing out, so a filing loads
# whole or not at all.
resource "snowflake_pipe" "parsed_filings" {
  database    = snowflake_stage_external_s3.parsed_filings.database
  schema      = snowflake_stage_external_s3.parsed_filings.schema
  name        = "PARSED_FILINGS_PIPE"
  auto_ingest = true
  comment     = "Loads each new parsed filing into RAW.PARSED_FILINGS"

  copy_statement = <<-SQL
    copy into EDGAR_13F.RAW.PARSED_FILINGS
        (record, source_file, source_row, source_content_key, source_last_modified)
    from (
        select $1, metadata$filename, metadata$file_row_number,
               metadata$file_content_key, metadata$file_last_modified
        from @${snowflake_stage_external_s3.parsed_filings.fully_qualified_name}
    )
    on_error = skip_file
  SQL

  # A pipe keeps the stage definition it was created with; the provider's
  # example recreates it when the stage's location or credentials change.
  lifecycle {
    replace_triggered_by = [
      snowflake_stage_external_s3.parsed_filings.url,
      snowflake_stage_external_s3.parsed_filings.storage_integration,
    ]
  }
}

# The bucket notification that feeds this pipe is in notifications.tf, beside
# the entries for the audit pipes.
