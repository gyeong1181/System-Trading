variable "aws_region" {
  description = "AWS region for the trading infrastructure."
  type        = string
  default     = "ap-northeast-2"
}

variable "project_name" {
  description = "Base name used for resources."
  type        = string
  default     = "psar-rsi-bot"
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

variable "extra_tags" {
  description = "Additional tags for all resources."
  type        = map(string)
  default     = {}
}
