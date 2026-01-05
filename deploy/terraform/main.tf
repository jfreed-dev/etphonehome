# ET Phone Home - Main Terraform Configuration

# Data sources
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# Random API key generation
resource "random_password" "api_key" {
  count   = var.enable_api_key ? 1 : 0
  length  = 64
  special = false
}

# SSH Key Pair
resource "tls_private_key" "admin" {
  count     = var.create_key_pair ? 1 : 0
  algorithm = "ED25519"
}

resource "aws_key_pair" "admin" {
  count      = var.create_key_pair ? 1 : 0
  key_name   = "etphonehome-${var.environment}"
  public_key = tls_private_key.admin[0].public_key_openssh
}

# VPC
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "etphonehome-${var.environment}"
  }
}

# Internet Gateway
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "etphonehome-${var.environment}"
  }
}

# Public Subnets
resource "aws_subnet" "public" {
  count                   = length(var.public_subnet_cidrs)
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.public_subnet_cidrs[count.index]
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name = "etphonehome-${var.environment}-public-${count.index + 1}"
  }
}

# Route Table
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "etphonehome-${var.environment}-public"
  }
}

resource "aws_route_table_association" "public" {
  count          = length(aws_subnet.public)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# Security Group
resource "aws_security_group" "server" {
  name        = "etphonehome-${var.environment}-server"
  description = "Security group for ET Phone Home server"
  vpc_id      = aws_vpc.main.id

  # Client SSH connections
  ingress {
    description = "ET Phone Home SSH"
    from_port   = var.ssh_port
    to_port     = var.ssh_port
    protocol    = "tcp"
    cidr_blocks = var.allowed_ssh_cidrs
  }

  # Admin SSH access (optional)
  dynamic "ingress" {
    for_each = length(var.allowed_admin_cidrs) > 0 ? [1] : []
    content {
      description = "Admin SSH"
      from_port   = 22
      to_port     = 22
      protocol    = "tcp"
      cidr_blocks = var.allowed_admin_cidrs
    }
  }

  # HTTP for internal MCP (localhost only, exposed via SSH tunnel)
  ingress {
    description = "MCP HTTP (localhost)"
    from_port   = var.http_port
    to_port     = var.http_port
    protocol    = "tcp"
    self        = true
  }

  # Outbound
  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "etphonehome-${var.environment}-server"
  }
}

# IAM Role for EC2
resource "aws_iam_role" "server" {
  name = "etphonehome-${var.environment}-server"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.server.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "server" {
  name = "etphonehome-${var.environment}-server"
  role = aws_iam_role.server.name
}

# CloudWatch Log Group (optional)
resource "aws_cloudwatch_log_group" "server" {
  count             = var.enable_cloudwatch_logs ? 1 : 0
  name              = "/etphonehome/${var.environment}/server"
  retention_in_days = var.log_retention_days
}

# EC2 Instance
resource "aws_instance" "server" {
  ami                    = var.ami_id != "" ? var.ami_id : data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  key_name               = var.create_key_pair ? aws_key_pair.admin[0].key_name : var.key_name
  vpc_security_group_ids = [aws_security_group.server.id]
  subnet_id              = aws_subnet.public[0].id
  iam_instance_profile   = aws_iam_instance_profile.server.name

  root_block_device {
    volume_size = var.root_volume_size
    volume_type = "gp3"
    encrypted   = var.enable_ebs_encryption
  }

  user_data = base64encode(templatefile("${path.module}/templates/user_data.sh.tftpl", {
    ssh_port           = var.ssh_port
    http_port          = var.http_port
    api_key            = var.enable_api_key ? random_password.api_key[0].result : ""
    enable_cloudwatch  = var.enable_cloudwatch_logs
    log_group_name     = var.enable_cloudwatch_logs ? aws_cloudwatch_log_group.server[0].name : ""
  }))

  tags = {
    Name = "etphonehome-${var.environment}-server"
  }

  lifecycle {
    ignore_changes = [ami, user_data]
  }
}

# Elastic IP
resource "aws_eip" "server" {
  instance = aws_instance.server.id
  domain   = "vpc"

  tags = {
    Name = "etphonehome-${var.environment}-server"
  }
}
