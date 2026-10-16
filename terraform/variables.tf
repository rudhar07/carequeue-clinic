variable "region" {
  description = "AWS region for every resource."
  type        = string
  default     = "ap-south-1" # Mumbai
}

variable "cluster_name" {
  description = "EKS cluster name; also used as the prefix for the VPC and other resources."
  type        = string
  default     = "carequeue-eks"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,30}[a-z0-9]$", var.cluster_name))
    error_message = "Use 3-32 lowercase letters, digits and hyphens, starting with a letter."
  }
}

variable "kubernetes_version" {
  description = "EKS Kubernetes minor version. 1.36 is in EKS standard support (checked 2026-10-16: 1.34-1.37 standard)."
  type        = string
  default     = "1.36"
}

variable "vpc_cidr" {
  description = "CIDR block of the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Exactly 2 AZs to use. Empty = the first 2 available AZs of the region."
  type        = list(string)
  default     = []

  validation {
    condition     = length(var.availability_zones) == 0 || length(var.availability_zones) == 2
    error_message = "Give exactly 2 availability zones, or leave the list empty."
  }
}

variable "public_subnet_cidrs" {
  description = "One public subnet per AZ (2 AZs)."
  type        = list(string)
  default     = ["10.0.0.0/20", "10.0.16.0/20"]

  validation {
    condition     = length(var.public_subnet_cidrs) == 2
    error_message = "Exactly 2 public subnets (one per AZ) are expected."
  }
}

variable "enable_private_subnets" {
  description = <<-EOT
    false (default, cheapest): no NAT gateway; worker nodes live in the public
    subnets with public IPs (inbound still blocked by security groups).
    true (production-style): also create 2 private subnets + 1 NAT gateway and
    put the worker nodes there. Adds about $0.056/h (NAT gateway hourly + its
    Elastic IP) plus NAT data processing charges.
  EOT
  type        = bool
  default     = false
}

variable "private_subnet_cidrs" {
  description = "Private subnets, only used when enable_private_subnets = true."
  type        = list(string)
  default     = ["10.0.128.0/20", "10.0.144.0/20"]

  validation {
    condition     = length(var.private_subnet_cidrs) == 2
    error_message = "Exactly 2 private subnets (one per AZ) are expected."
  }
}

variable "enable_flow_log" {
  description = "Send VPC flow logs to CloudWatch Logs (1-day retention). Off by default for cost."
  type        = bool
  default     = false
}

variable "node_instance_types" {
  description = "Instance types for the managed node group (more than one helps when using SPOT)."
  type        = list(string)
  default     = ["t3.medium"]
}

variable "node_capacity_type" {
  description = "ON_DEMAND (default, predictable) or SPOT (cheaper, can be reclaimed at any time)."
  type        = string
  default     = "ON_DEMAND"

  validation {
    condition     = contains(["ON_DEMAND", "SPOT"], var.node_capacity_type)
    error_message = "node_capacity_type must be ON_DEMAND or SPOT."
  }
}

variable "node_desired_size" {
  description = "Initial number of worker nodes."
  type        = number
  default     = 2
}

variable "node_min_size" {
  description = "Minimum number of worker nodes."
  type        = number
  default     = 1
}

variable "node_max_size" {
  description = "Maximum number of worker nodes."
  type        = number
  default     = 3

  validation {
    condition     = var.node_max_size >= 1 && var.node_max_size <= 5
    error_message = "Keep node_max_size between 1 and 5 for this lab (cost guard)."
  }
}

variable "node_disk_size_gb" {
  description = "Root EBS volume (gp3) size per worker node, in GiB."
  type        = number
  default     = 20
}

variable "enable_ebs_csi_driver" {
  description = "Install the aws-ebs-csi-driver add-on so PersistentVolumeClaims (e.g. PostgreSQL) can get EBS volumes."
  type        = bool
  default     = true
}

variable "endpoint_public_access_cidrs" {
  description = "CIDRs allowed to reach the public Kubernetes API endpoint. Narrow it to your own IP (x.x.x.x/32) if you can."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "tags" {
  description = "Extra tags merged into every resource (on top of the provider default_tags)."
  type        = map(string)
  default     = {}
}
