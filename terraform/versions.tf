terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }

    # Pinned exactly: snowflake_pipe is a preview resource in 2.x, and the
    # provider says preview features may break between non-major versions.
    snowflake = {
      source  = "snowflakedb/snowflake"
      version = "2.21.0"
    }
  }

  required_version = ">= 1.5, < 2.0"
}
