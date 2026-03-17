variable "aws_region" {
  description = "AWS region for the trading infrastructure."
  type        = string
  default     = "us-west-2"
}

variable "project_name" {
  description = "Base name used for resources."
  type        = string
  default     = "quant-fleet-core"
}

variable "instance_type" {
  description = "EC2 instance type."
  type        = string
  default     = "t3.small"
}

variable "key_name" {
  description = "Existing EC2 key pair name for SSH access."
  type        = string
}

variable "subnet_id" {
  description = "Optional subnet ID. Leave empty to use the first default subnet."
  type        = string
  default     = ""
}

variable "ssh_allowed_cidrs" {
  description = "CIDR blocks allowed to access SSH."
  type        = list(string)
}

variable "http_allowed_cidrs" {
  description = "CIDR blocks allowed to access the webhook endpoint on port 80."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "enable_monitoring_ports" {
  description = "Whether to expose Grafana and Prometheus directly."
  type        = bool
  default     = false
}

variable "monitoring_ports" {
  description = "Monitoring ports to expose when enable_monitoring_ports is true."
  type        = list(number)
  default     = [3000, 9090]
}

variable "monitoring_allowed_cidrs" {
  description = "CIDR blocks allowed to access Grafana and Prometheus."
  type        = list(string)
  default     = []
}

variable "allocate_eip" {
  description = "Allocate and associate an Elastic IP."
  type        = bool
  default     = true
}

variable "root_volume_size" {
  description = "Root EBS volume size in GiB."
  type        = number
  default     = 20
}

variable "app_user" {
  description = "Linux user that owns the deployment directory."
  type        = string
  default     = "ec2-user"
}

variable "strategy_stack_dir" {
  description = "Directory on the instance where docker-compose stack files are written."
  type        = string
  default     = "/opt/trading-stack"
}

variable "deploy_strategy_stack" {
  description = "Whether to auto-start the multi-strategy docker-compose stack at boot."
  type        = bool
  default     = false
}

variable "psar_rsi_image" {
  description = "Container image for your existing PSAR RSI system."
  type        = string
  default     = ""
}

variable "enable_psar_container" {
  description = "Whether to run PSAR RSI as a container in the strategy stack."
  type        = bool
  default     = false
}

variable "enable_okx_qqq_container" {
  description = "Whether to run the OKX QQQ vendor container in the strategy stack."
  type        = bool
  default     = true
}

variable "enable_okx_xau_container" {
  description = "Whether to run the OKX XAU vendor container in the strategy stack."
  type        = bool
  default     = true
}

variable "okx_qqq_image" {
  description = "External OKX QQQ strategy container image."
  type        = string
  default     = ""
}

variable "okx_xau_image" {
  description = "External OKX XAU strategy container image."
  type        = string
  default     = ""
}

variable "psar_rsi_container_port" {
  description = "Internal container port for the PSAR RSI webhook app."
  type        = number
  default     = 8000
}

variable "use_ssm_env" {
  description = "Whether to load strategy env files from AWS SSM Parameter Store."
  type        = bool
  default     = true
}

variable "ssm_parameter_prefix" {
  description = "Base SSM path for strategy secrets (example: /trading/prod)."
  type        = string
  default     = "/trading/prod"
}

variable "ssm_kms_key_arn" {
  description = "Optional KMS key ARN used for SecureString decrypt. Leave empty to allow decrypt on all keys."
  type        = string
  default     = ""
}

variable "extra_tags" {
  description = "Additional tags for all resources."
  type        = map(string)
  default     = {}
}
