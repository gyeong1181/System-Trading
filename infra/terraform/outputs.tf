output "instance_id" {
  description = "EC2 instance ID."
  value       = aws_instance.this.id
}

output "security_group_id" {
  description = "Security group ID."
  value       = aws_security_group.this.id
}

output "public_ip" {
  description = "Public IP address."
  value       = var.allocate_eip ? aws_eip.this[0].public_ip : aws_instance.this.public_ip
}

output "public_dns" {
  description = "Public DNS name."
  value       = aws_instance.this.public_dns
}

output "ssh_hint" {
  description = "SSH command template."
  value       = "ssh -i <your-key>.pem ${var.app_user}@${var.allocate_eip ? aws_eip.this[0].public_ip : aws_instance.this.public_ip}"
}

output "grafana_url" {
  description = "Grafana URL when monitoring ports are exposed."
  value       = var.enable_monitoring_ports ? "http://${var.allocate_eip ? aws_eip.this[0].public_ip : aws_instance.this.public_ip}:3000" : "Expose monitoring ports or use SSH tunnel."
}

output "prometheus_url" {
  description = "Prometheus URL when monitoring ports are exposed."
  value       = var.enable_monitoring_ports ? "http://${var.allocate_eip ? aws_eip.this[0].public_ip : aws_instance.this.public_ip}:9090" : "Expose monitoring ports or use SSH tunnel."
}
