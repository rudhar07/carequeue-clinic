terraform {
  # 1.6+ for the module features used below; tested with Terraform 1.16.
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.69" # exact version pinned in .terraform.lock.hcl
    }
  }

  # State stays local (terraform.tfstate, gitignored). This is a short-lived,
  # single-person lab: apply, screenshot, destroy. A team would use the S3
  # backend with state locking instead, for example:
  #
  # backend "s3" {
  #   bucket       = "carequeue-tfstate-<account-id>"
  #   key          = "eks/terraform.tfstate"
  #   region       = "ap-south-1"
  #   use_lockfile = true
  #   encrypt      = true
  # }
}
