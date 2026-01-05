# ET Phone Home - Terraform Outputs

output "server_public_ip" {
  description = "Public IP address of the server"
  value       = aws_eip.server.public_ip
}

output "server_public_dns" {
  description = "Public DNS name of the server"
  value       = aws_eip.server.public_dns
}

output "server_instance_id" {
  description = "EC2 instance ID"
  value       = aws_instance.server.id
}

output "ssh_connection_string" {
  description = "SSH connection string for clients"
  value       = "ssh -p ${var.ssh_port} etphonehome@${aws_eip.server.public_ip}"
}

output "admin_ssh_connection" {
  description = "Admin SSH connection (if admin CIDRs configured)"
  value       = length(var.allowed_admin_cidrs) > 0 ? "ssh -i <key> ubuntu@${aws_eip.server.public_ip}" : "Admin SSH not configured"
}

output "admin_private_key" {
  description = "Private key for admin SSH access (if created)"
  value       = var.create_key_pair ? tls_private_key.admin[0].private_key_openssh : "Using existing key pair"
  sensitive   = true
}

output "api_key" {
  description = "API key for MCP authentication (if enabled)"
  value       = var.enable_api_key ? random_password.api_key[0].result : "API key not enabled"
  sensitive   = true
}

output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}

output "security_group_id" {
  description = "Security group ID for the server"
  value       = aws_security_group.server.id
}

output "client_config_example" {
  description = "Example client configuration"
  value       = <<-EOT
    # Client config.yaml
    server_host: ${aws_eip.server.public_ip}
    server_port: ${var.ssh_port}
    server_user: etphonehome
  EOT
}
