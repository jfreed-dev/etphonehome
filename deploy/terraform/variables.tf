# ET Phone Home - Terraform Variables

# AWS Configuration
variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (e.g., prod, staging, dev)"
  type        = string
  default     = "prod"
}

# Network Configuration
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "availability_zones" {
  description = "Availability zones to use"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

# EC2 Configuration
variable "instance_type" {
  description = "EC2 instance type for the server"
  type        = string
  default     = "t3.micro"
}

variable "ami_id" {
  description = "AMI ID for the server (leave empty for latest Ubuntu)"
  type        = string
  default     = ""
}

variable "key_name" {
  description = "Name of existing SSH key pair for EC2 access"
  type        = string
  default     = ""
}

variable "create_key_pair" {
  description = "Create a new SSH key pair"
  type        = bool
  default     = true
}

# ET Phone Home Configuration
variable "ssh_port" {
  description = "Port for client SSH connections"
  type        = number
  default     = 2222
}

variable "http_port" {
  description = "Port for MCP HTTP server"
  type        = number
  default     = 8765
}

variable "enable_api_key" {
  description = "Enable API key authentication"
  type        = bool
  default     = true
}

variable "allowed_ssh_cidrs" {
  description = "CIDR blocks allowed to connect via SSH"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "allowed_admin_cidrs" {
  description = "CIDR blocks allowed for admin SSH access (port 22)"
  type        = list(string)
  default     = []
}

# Storage
variable "root_volume_size" {
  description = "Size of root volume in GB"
  type        = number
  default     = 20
}

variable "enable_ebs_encryption" {
  description = "Enable EBS volume encryption"
  type        = bool
  default     = true
}

# Monitoring
variable "enable_cloudwatch_logs" {
  description = "Enable CloudWatch log shipping"
  type        = bool
  default     = false
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}
