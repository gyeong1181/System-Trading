# ──────────────────────────────────────────
# VPC — EKS 전용 네트워크
# ──────────────────────────────────────────
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "${var.cluster_name}-vpc"
  cidr = var.vpc_cidr

  # 서울 리전 3개 가용영역 — 고가용성
  azs             = ["${var.aws_region}a", "${var.aws_region}b", "${var.aws_region}c"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

  # 프라이빗 서브넷의 Pod가 인터넷 아웃바운드 가능하도록
  enable_nat_gateway   = true
  single_nat_gateway   = true # 비용 절감 (prod는 각 AZ마다)
  enable_dns_hostnames = true

  # EKS가 서브넷을 자동 탐색하는 데 필요한 태그
  public_subnet_tags = {
    "kubernetes.io/role/elb" = "1"
  }
  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = "1"
  }

  tags = {
    Project     = "msa-on-k8s"
    Environment = "dev"
  }
}

# ──────────────────────────────────────────
# EKS 클러스터
# ──────────────────────────────────────────
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = var.cluster_name
  cluster_version = var.cluster_version

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets # 워커 노드는 프라이빗 서브넷

  # 개발 환경: kubectl 접근을 위해 퍼블릭 엔드포인트 허용
  cluster_endpoint_public_access = true

  # 관리형 노드 그룹 — AWS가 EC2 프로비저닝/패치 자동 관리
  eks_managed_node_groups = {
    main = {
      instance_types = [var.node_instance_type]
      min_size       = var.node_min
      max_size       = var.node_max
      desired_size   = var.node_desired

      labels = {
        role = "worker"
      }
    }
  }

  tags = {
    Project     = "msa-on-k8s"
    Environment = "dev"
  }
}
