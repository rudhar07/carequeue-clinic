# EKS control plane + one managed node group.
#
# Access: EKS access entries (authentication_mode = "API"). The IAM identity
# that runs `terraform apply` becomes cluster admin through
# enable_cluster_creator_admin_permissions, so `aws eks update-kubeconfig`
# followed by `kubectl get nodes` works right away. No aws-auth ConfigMap.
#
# Accepted Trivy findings (deliberate lab trade-offs, see docs/TERRAFORM.md):
#   AWS-0040 public API endpoint: needed so kubectl works from a laptop. It is
#            still authenticated with IAM, and endpoint_public_access_cidrs can
#            narrow it to your own IP.
#   AWS-0041 0.0.0.0/0 on the public endpoint: default only; override
#            endpoint_public_access_cidrs = ["<your-ip>/32"].
#   AWS-0104 unrestricted node egress: nodes must reach ECR/GHCR/Docker Hub
#            and AWS APIs to pull images and join the cluster.
#trivy:ignore:AVD-AWS-0040
#trivy:ignore:AVD-AWS-0041
#trivy:ignore:AVD-AWS-0104
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 21.29"

  name               = var.cluster_name
  kubernetes_version = var.kubernetes_version

  # Public API endpoint so kubectl works from a laptop; private endpoint too,
  # so nodes reach the API inside the VPC.
  endpoint_public_access       = true
  endpoint_public_access_cidrs = var.endpoint_public_access_cidrs
  endpoint_private_access      = true

  authentication_mode                      = "API"
  enable_cluster_creator_admin_permissions = true

  # Add-on permissions use EKS Pod Identity (see aws_iam_role.ebs_csi), so the
  # IRSA OIDC provider is not needed.
  enable_irsa = false

  vpc_id                   = module.vpc.vpc_id
  subnet_ids               = local.node_subnet_ids
  control_plane_subnet_ids = module.vpc.public_subnets

  # All control-plane log types, kept for 1 day only (short-lived lab, tiny volume).
  enabled_log_types                      = ["api", "audit", "authenticator", "controllerManager", "scheduler"]
  cloudwatch_log_group_retention_in_days = 1

  # Kubernetes Secrets are envelope-encrypted with a KMS key that the module
  # creates (~$1/month, prorated). The key is scheduled for deletion on destroy.
  kms_key_deletion_window_in_days = 7

  # Managed add-ons. vpc-cni and the pod identity agent must exist before
  # the nodes join, otherwise nodes stay NotReady.
  addons = merge(
    {
      vpc-cni = {
        before_compute = true
      }
      eks-pod-identity-agent = {
        before_compute = true
      }
      kube-proxy = {}
      coredns    = {}
    },
    var.enable_ebs_csi_driver ? {
      aws-ebs-csi-driver = {
        pod_identity_association = [{
          role_arn        = aws_iam_role.ebs_csi[0].arn
          service_account = "ebs-csi-controller-sa"
        }]
      }
    } : {}
  )

  eks_managed_node_groups = {
    default = {
      name = "${var.cluster_name}-ng"

      ami_type       = "AL2023_x86_64_STANDARD"
      instance_types = var.node_instance_types
      capacity_type  = var.node_capacity_type

      min_size     = var.node_min_size
      max_size     = var.node_max_size
      desired_size = var.node_desired_size

      subnet_ids = local.node_subnet_ids

      # Encrypted gp3 root volume, deleted together with the instance.
      block_device_mappings = {
        xvda = {
          device_name = "/dev/xvda"
          ebs = {
            volume_size           = var.node_disk_size_gb
            volume_type           = "gp3"
            encrypted             = true
            delete_on_termination = true
          }
        }
      }

      labels = {
        "carequeue/pool" = "default"
      }
    }
  }

  tags = local.tags
}

# IAM role for the EBS CSI driver controller, assumed via EKS Pod Identity
# (no node-wide permissions, no OIDC provider needed).
data "aws_iam_policy_document" "ebs_csi_assume" {
  count = var.enable_ebs_csi_driver ? 1 : 0

  statement {
    actions = ["sts:AssumeRole", "sts:TagSession"]
    principals {
      type        = "Service"
      identifiers = ["pods.eks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ebs_csi" {
  count = var.enable_ebs_csi_driver ? 1 : 0

  name               = "${var.cluster_name}-ebs-csi"
  assume_role_policy = data.aws_iam_policy_document.ebs_csi_assume[0].json
  tags               = local.tags
}

resource "aws_iam_role_policy_attachment" "ebs_csi" {
  count = var.enable_ebs_csi_driver ? 1 : 0

  role       = aws_iam_role.ebs_csi[0].name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
}
