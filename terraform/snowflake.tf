# Snowflake reads the landing zone through a storage integration that assumes
# an IAM role. Read-only: Snowflake loads from the bucket and never writes to
# it, so the landing zone stays append-only for both of its readers. The whole
# bucket is allowed because it holds nothing but this pipeline's data; each
# stage narrows to its own prefix.
data "aws_caller_identity" "current" {}

locals {
  snowflake_reader_role_name = "edgar-13f-warehouse-snowflake"
}

# The integration and the role refer to each other: Snowflake needs the role's
# ARN, and the role's trust policy needs the IAM user and external ID that
# Snowflake assigns. Building the ARN from the account and the name breaks the
# cycle, so the integration is created first and the role second.
resource "snowflake_storage_integration_aws" "landing" {
  name                      = "EDGAR_LANDING"
  enabled                   = true
  storage_provider          = "S3"
  storage_aws_role_arn      = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${local.snowflake_reader_role_name}"
  storage_allowed_locations = ["s3://${aws_s3_bucket.landing.bucket}/"]
  comment                   = "Read-only access to the EDGAR 13F landing bucket"
}

data "aws_iam_policy_document" "snowflake_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "AWS"
      identifiers = [snowflake_storage_integration_aws.landing.describe_output[0].iam_user_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "sts:ExternalId"
      values   = [snowflake_storage_integration_aws.landing.describe_output[0].external_id]
    }
  }
}

resource "aws_iam_role" "snowflake" {
  name               = local.snowflake_reader_role_name
  assume_role_policy = data.aws_iam_policy_document.snowflake_trust.json
}

# Snowflake's read-only policy for loading: get objects and their versions,
# list the bucket and find its region. No put, no delete.
data "aws_iam_policy_document" "landing_read_only" {
  statement {
    effect    = "Allow"
    actions   = ["s3:GetObject", "s3:GetObjectVersion"]
    resources = ["${aws_s3_bucket.landing.arn}/*"]
  }

  statement {
    effect    = "Allow"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = [aws_s3_bucket.landing.arn]
  }
}

resource "aws_iam_role_policy" "snowflake_landing_read_only" {
  name   = "landing-read-only"
  role   = aws_iam_role.snowflake.id
  policy = data.aws_iam_policy_document.landing_read_only.json
}
