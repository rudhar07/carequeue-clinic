# Credentials are NOT configured here. The AWS provider reads them from the
# environment (aws configure / aws login / AWS_PROFILE / SSO), so nothing
# secret ever lands in this repository.
provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = "CareQueue"
      Owner     = "rudhar07"
      ManagedBy = "Terraform"
    }
  }
}
