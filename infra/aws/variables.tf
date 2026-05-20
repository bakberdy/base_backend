variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Short project name used in AWS resource names."
  type        = string
  default     = "mobile-app-backend"
}

variable "environment" {
  description = "Application environment passed to the container."
  type        = string
  default     = "production"
}

variable "container_image" {
  description = "Full container image URI. Leave empty to use this stack's ECR repository with the latest tag."
  type        = string
  default     = ""
}

variable "certificate_arn" {
  description = "ACM certificate ARN for HTTPS. Leave empty to expose HTTP only."
  type        = string
  default     = ""
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.40.0.0/16"
}

variable "db_name" {
  description = "PostgreSQL database name."
  type        = string
  default     = "mobile_app"
}

variable "db_username" {
  description = "PostgreSQL master username."
  type        = string
  default     = "mobile_app"
}

variable "db_instance_class" {
  description = "RDS instance size."
  type        = string
  default     = "db.t4g.micro"
}

variable "db_allocated_storage" {
  description = "RDS storage in GB."
  type        = number
  default     = 20
}

variable "redis_node_type" {
  description = "ElastiCache Redis node size."
  type        = string
  default     = "cache.t4g.micro"
}

variable "app_cpu" {
  description = "Fargate task CPU units."
  type        = number
  default     = 512
}

variable "app_memory" {
  description = "Fargate task memory in MB."
  type        = number
  default     = 1024
}

variable "app_desired_count" {
  description = "Number of ECS tasks."
  type        = number
  default     = 1
}

variable "log_level" {
  description = "Application log level."
  type        = string
  default     = "INFO"
}

variable "cors_allowed_origins" {
  description = "Comma-separated CORS origins."
  type        = string
  default     = ""
}

variable "cors_allow_credentials" {
  description = "Whether CORS credentials are allowed."
  type        = bool
  default     = false
}

variable "access_token_expire_minutes" {
  description = "Access token lifetime in minutes."
  type        = number
  default     = 15
}

variable "refresh_token_expire_days" {
  description = "Refresh token lifetime in days."
  type        = number
  default     = 14
}

variable "otp_expire_seconds" {
  description = "OTP lifetime in seconds."
  type        = number
  default     = 600
}

variable "otp_max_attempts" {
  description = "Maximum OTP attempts."
  type        = number
  default     = 5
}

variable "otp_email_enabled" {
  description = "Whether SMTP OTP delivery is enabled."
  type        = bool
  default     = true
}

variable "smtp_host" {
  description = "SMTP host for OTP email delivery."
  type        = string
  default     = ""
}

variable "smtp_port" {
  description = "SMTP port."
  type        = number
  default     = 587
}

variable "smtp_username" {
  description = "SMTP username."
  type        = string
  default     = ""
}

variable "smtp_password" {
  description = "SMTP password. Stored in Secrets Manager."
  type        = string
  default     = ""
  sensitive   = true
}

variable "smtp_sender_email" {
  description = "SMTP sender email."
  type        = string
  default     = ""
}

variable "smtp_sender_name" {
  description = "SMTP sender name."
  type        = string
  default     = "Mobile App"
}

variable "smtp_use_tls" {
  description = "Use STARTTLS for SMTP."
  type        = bool
  default     = true
}

variable "smtp_use_ssl" {
  description = "Use SMTP SSL."
  type        = bool
  default     = false
}
