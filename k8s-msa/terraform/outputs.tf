output "cluster_name" {
  description = "EKS 클러스터 이름"
  value       = module.eks.cluster_name
}

output "cluster_endpoint" {
  description = "EKS API 서버 엔드포인트 — kubectl 연결에 사용"
  value       = module.eks.cluster_endpoint
}

output "cluster_version" {
  description = "Kubernetes 버전"
  value       = module.eks.cluster_version
}

output "ecr_repository_urls" {
  description = "각 서비스의 ECR URL — docker push 시 사용"
  value       = { for k, v in aws_ecr_repository.services : k => v.repository_url }
}

output "kubeconfig_command" {
  description = "로컬 kubectl을 EKS에 연결하는 명령어"
  value       = "aws eks update-kubeconfig --region ${var.aws_region} --name ${module.eks.cluster_name}"
}
