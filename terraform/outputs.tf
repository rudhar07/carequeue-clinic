output "region" {
  description = "AWS region."
  value       = var.region
}

output "cluster_name" {
  description = "EKS cluster name."
  value       = module.eks.cluster_name
}

output "cluster_endpoint" {
  description = "Kubernetes API server endpoint."
  value       = module.eks.cluster_endpoint
}

output "cluster_version" {
  description = "Kubernetes version of the control plane."
  value       = module.eks.cluster_version
}

output "vpc_id" {
  description = "VPC ID."
  value       = module.vpc.vpc_id
}

output "availability_zones" {
  description = "AZs in use."
  value       = local.azs
}

output "public_subnet_ids" {
  description = "Public subnet IDs (tagged kubernetes.io/role/elb=1)."
  value       = module.vpc.public_subnets
}

output "private_subnet_ids" {
  description = "Private subnet IDs (empty unless enable_private_subnets = true)."
  value       = module.vpc.private_subnets
}

output "node_subnet_ids" {
  description = "Subnets the worker nodes run in."
  value       = local.node_subnet_ids
}

output "node_group_name" {
  description = "Name of the managed node group (as shown in the EKS console)."
  value       = split(":", module.eks.eks_managed_node_groups["default"].node_group_id)[1]
}

output "configure_kubectl" {
  description = "Run this to point kubectl at the new cluster."
  value       = "aws eks update-kubeconfig --region ${var.region} --name ${module.eks.cluster_name}"
}
