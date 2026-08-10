variable "aws_region" {
  description = "AWS 리전"
  type        = string
  default     = "ap-northeast-2" # 서울
}

variable "cluster_name" {
  description = "EKS 클러스터 이름"
  type        = string
  default     = "msa-eks-cluster"
}

variable "cluster_version" {
  description = "Kubernetes 버전"
  type        = string
  default     = "1.29"
}

variable "node_instance_type" {
  description = "워커 노드 EC2 인스턴스 타입"
  type        = string
  default     = "t3.medium" # 2vCPU 4GB — MSA 5개 서비스 적정 사양
}

variable "node_desired" {
  description = "기본 노드 수"
  type        = number
  default     = 2
}

variable "node_min" {
  description = "최소 노드 수"
  type        = number
  default     = 1
}

variable "node_max" {
  description = "최대 노드 수 (HPA 확장 대비)"
  type        = number
  default     = 4
}

variable "vpc_cidr" {
  description = "VPC CIDR 블록"
  type        = string
  default     = "10.0.0.0/16"
}
