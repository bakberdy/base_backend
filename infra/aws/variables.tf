variable "project_name" {
  description = "Short project name used in AWS resource names."
  type        = string
  default     = "mobile-app-backend"
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "production"
}

variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "us-east-1"
}

variable "instance_type" {
  description = "EC2 instance type for the single-host MVP."
  type        = string
  default     = "t3.micro"
}

variable "key_name" {
  description = "Existing EC2 key pair name for SSH access."
  type        = string
}

variable "allowed_ssh_cidr" {
  description = "CIDR allowed to connect over SSH."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.40.0.0/16"
}

variable "domain_name" {
  description = "Domain name served by nginx. Leave empty to accept any host."
  type        = string
  default     = ""
}

variable "container_image" {
  description = "Backend container image URI pulled by Docker Compose on EC2."
  type        = string

  validation {
    condition     = length(trimspace(var.container_image)) > 0
    error_message = "container_image must be set to a pullable backend image."
  }
}
