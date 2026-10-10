# The profile is configuration, not environment: this machine's default
# profile belongs to another project, and a plan run under it reads the
# bucket as deleted and plans to create it again.
provider "aws" {
  region  = var.region
  profile = var.aws_profile

  # Every resource carries the four project tags, lowercase kebab-case.
  default_tags {
    tags = {
      project     = "edgar-13f-warehouse"
      environment = var.environment
      owner       = var.owner
      managed-by  = "terraform"
    }
  }
}

# TERRAFORM_SVC is a SERVICE user from include/sql/01_terraform_identity.sql;
# its key pair is restricted to the TERRAFORM role, so the role is fixed here.
# The provider takes private_key and its passphrase from one source, so both
# come in as variables: the key from a path outside the repository, the
# passphrase from TF_VAR_snowflake_private_key_passphrase in the shell.
provider "snowflake" {
  organization_name      = var.snowflake_organization_name
  account_name           = var.snowflake_account_name
  user                   = var.snowflake_user
  role                   = var.snowflake_role
  authenticator          = "SNOWFLAKE_JWT"
  private_key            = file(pathexpand(var.snowflake_private_key_path))
  private_key_passphrase = var.snowflake_private_key_passphrase
}
