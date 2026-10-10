variable "bucket_name" {
  description = "Landing-zone bucket. Same value as AIRFLOW_VAR_RAW_BUCKET in .env."
  type        = string
}

variable "owner" {
  description = "Value of the owner tag on every resource, lowercase kebab-case."
  type        = string
}

variable "region" {
  description = "Bucket region. Same value as region_name in the AWS connection."
  type        = string
  default     = "us-east-1"
}

variable "aws_profile" {
  description = "AWS CLI profile with rights over the bucket and IAM; no default on purpose."
  type        = string
}

variable "environment" {
  description = "Value of the environment tag."
  type        = string
  default     = "prod"
}

variable "snowflake_organization_name" {
  description = "First half of the account identifier, before the hyphen."
  type        = string
}

variable "snowflake_account_name" {
  description = "Second half of the account identifier, after the hyphen."
  type        = string
}

variable "snowflake_user" {
  description = "Service user created by include/sql/01_terraform_identity.sql."
  type        = string
  default     = "TERRAFORM_SVC"
}

variable "snowflake_role" {
  description = "The only role the service user's key pair can authenticate with."
  type        = string
  default     = "TERRAFORM"
}

variable "snowflake_private_key_path" {
  description = "Encrypted PKCS#8 private key, outside the repository."
  type        = string
  default     = "~/.snowflake/keys/edgar_13f_terraform.p8"
}

variable "snowflake_private_key_passphrase" {
  description = "Passphrase of the private key. Set TF_VAR_snowflake_private_key_passphrase."
  type        = string
  sensitive   = true
}
