# The landing zone holds every byte fetched from EDGAR before any parser runs,
# so it is the one store the warehouse can be rebuilt from. Versioning backs
# the deterministic keys: a rerun of the same day overwrites the same objects,
# and the overwritten version stays.
resource "aws_s3_bucket" "landing" {
  bucket = var.bucket_name
}

resource "aws_s3_bucket_versioning" "landing" {
  bucket = aws_s3_bucket.landing.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "landing" {
  bucket                  = aws_s3_bucket.landing.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# The pipeline identity. Append-only by policy: it can put, get and list, and
# no statement grants delete. With versioning on, even an overwrite adds a
# version rather than removing one. Removing history takes the account owner.
# At cp2 Snowflake gets its own role for the stage; this user never reads for
# the warehouse, it only lands.
resource "aws_iam_user" "airflow" {
  name = "edgar-13f-warehouse-airflow"
}

data "aws_iam_policy_document" "landing_append_only" {
  statement {
    effect    = "Allow"
    actions   = ["s3:PutObject", "s3:GetObject", "s3:ListBucket"]
    resources = [aws_s3_bucket.landing.arn, "${aws_s3_bucket.landing.arn}/*"]
  }
}

resource "aws_iam_user_policy" "landing_append_only" {
  name   = "landing-append-only"
  user   = aws_iam_user.airflow.name
  policy = data.aws_iam_policy_document.landing_append_only.json
}

resource "aws_iam_access_key" "airflow" {
  user = aws_iam_user.airflow.name
}
