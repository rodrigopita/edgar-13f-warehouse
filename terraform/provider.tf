provider "aws" {
  region = var.region

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
