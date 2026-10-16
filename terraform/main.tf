# CareQueue on AWS: one VPC (2 public subnets in 2 AZs) + one EKS cluster with
# one managed node group. See docs/TERRAFORM.md for the runbook and costs.

data "aws_availability_zones" "available" {
  state = "available"

  # Only normal AZs (no Local Zones / Wavelength Zones).
  filter {
    name   = "opt-in-status"
    values = ["opt-in-not-required"]
  }
}

data "aws_partition" "current" {}

locals {
  azs = length(var.availability_zones) > 0 ? var.availability_zones : slice(data.aws_availability_zones.available.names, 0, 2)

  # Where the worker nodes go: public subnets by default (no NAT gateway),
  # private subnets when enable_private_subnets = true.
  node_subnet_ids = var.enable_private_subnets ? module.vpc.private_subnets : module.vpc.public_subnets

  tags = merge(var.tags, {
    Cluster = var.cluster_name
  })
}
