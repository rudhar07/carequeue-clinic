# Network layout (default, enable_private_subnets = false):
#
#   Internet <-> Internet Gateway <-> public route table (0.0.0.0/0 -> IGW)
#                                       |- public subnet AZ-a 10.0.0.0/20   (nodes + load balancers)
#                                       '- public subnet AZ-b 10.0.16.0/20  (nodes + load balancers)
#
# There is no NAT gateway: a NAT gateway costs ~$0.045/h + $0.045/GB processed
# and would roughly double the network bill of a 2-hour lab. Instead the worker
# nodes get a public IPv4 address (map_public_ip_on_launch) so they can pull
# images and talk to the EKS API directly. Inbound traffic is still blocked by
# the node security group (only the control plane and other nodes may connect).
#
# Production-style layout (enable_private_subnets = true): the module also
# creates 2 private subnets + 1 NAT gateway in the first public subnet, and the
# nodes move to the private subnets (no public IPs on nodes at all):
#
#   private subnet AZ-a 10.0.128.0/20 --+
#   private subnet AZ-b 10.0.144.0/20 --+--> private route table (0.0.0.0/0 -> NAT GW) --> IGW

# Accepted Trivy findings (deliberate lab trade-offs, see docs/TERRAFORM.md):
#   AWS-0164 public IP on launch: required for nodes in public subnets without
#            a NAT gateway. Set enable_private_subnets = true to avoid it.
#   AWS-0178 no VPC flow logs by default: set enable_flow_log = true to turn
#            them on (CloudWatch Logs, 1-day retention).
#trivy:ignore:AVD-AWS-0164
#trivy:ignore:AVD-AWS-0178
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 6.7"

  name = "${var.cluster_name}-vpc"
  cidr = var.vpc_cidr
  azs  = local.azs

  public_subnets          = var.public_subnet_cidrs
  map_public_ip_on_launch = true # nodes in public subnets need a public IP without a NAT gateway

  private_subnets = var.enable_private_subnets ? var.private_subnet_cidrs : []

  # NAT only exists in the private-subnet variant; one shared NAT keeps it cheap.
  enable_nat_gateway     = var.enable_private_subnets
  single_nat_gateway     = true
  one_nat_gateway_per_az = false

  # EKS needs DNS support + hostnames in the VPC.
  enable_dns_support   = true
  enable_dns_hostnames = true

  # The module's default security group / NACL stay locked down (no rules).
  manage_default_security_group  = true
  default_security_group_ingress = []
  default_security_group_egress  = []

  # Optional VPC flow logs (off by default to keep the lab cheap and quiet).
  enable_flow_log                                 = var.enable_flow_log
  create_flow_log_cloudwatch_log_group            = var.enable_flow_log
  create_flow_log_cloudwatch_iam_role             = var.enable_flow_log
  flow_log_cloudwatch_log_group_retention_in_days = 1
  flow_log_max_aggregation_interval               = 60

  public_subnet_tags = {
    # Internet-facing load balancers (e.g. the ingress-nginx NLB) go here.
    "kubernetes.io/role/elb" = "1"
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = "1"
  }

  tags = local.tags
}
