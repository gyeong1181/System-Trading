# 5개 MSA 서비스 각각의 ECR 리포지토리
# EKS 배포 시 이 URL에서 이미지를 pull함
locals {
  services = [
    "user-service",
    "product-service",
    "order-service",
    "payment-service",
    "notification-service",
  ]
}

resource "aws_ecr_repository" "services" {
  for_each = toset(local.services)

  name                 = "msa/${each.key}"
  image_tag_mutability = "MUTABLE" # 같은 태그로 덮어쓰기 허용 (dev 환경)

  image_scanning_configuration {
    scan_on_push = true # 푸시 시 보안 취약점 자동 스캔
  }

  tags = {
    Project = "msa-on-k8s"
    Service = each.key
  }
}

# 이미지 보관 정책 — 최신 10개만 유지 (스토리지 비용 절감)
resource "aws_ecr_lifecycle_policy" "services" {
  for_each   = aws_ecr_repository.services
  repository = each.value.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "최신 10개 이미지만 유지"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 10
      }
      action = { type = "expire" }
    }]
  })
}
