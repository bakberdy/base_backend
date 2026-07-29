variable "aws_region" {
  description = "AWS region for all backend resources."
  type        = string
  default     = "eu-central-1"

  validation {
    condition     = can(regex("^[a-z]{2}(-gov)?-[a-z]+-[0-9]+$", var.aws_region))
    error_message = "aws_region must be a valid AWS region name."
  }
}

variable "availability_zone" {
  description = "Availability zone used by the public subnet."
  type        = string
  default     = "eu-central-1a"
}

variable "project_name" {
  description = "Application name used for EC2, ECR, GitHub variables, and deployment directories."
  type        = string
  default     = "template-backend"

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]*$", var.project_name))
    error_message = "project_name may contain only lowercase letters, digits, and hyphens."
  }
}

variable "infrastructure_prefix" {
  description = "Short prefix used by shared network and IAM resource names."
  type        = string
  default     = "template"

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]*$", var.infrastructure_prefix))
    error_message = "infrastructure_prefix may contain only lowercase letters, digits, and hyphens."
  }
}

variable "vpc_cidr" {
  description = "IPv4 CIDR for the backend VPC."
  type        = string
  default     = "10.40.0.0/16"

  validation {
    condition     = can(cidrnetmask(var.vpc_cidr))
    error_message = "vpc_cidr must be a valid IPv4 CIDR."
  }
}

variable "public_subnet_cidr" {
  description = "IPv4 CIDR for the public EC2 subnet."
  type        = string
  default     = "10.40.1.0/24"

  validation {
    condition     = can(cidrnetmask(var.public_subnet_cidr))
    error_message = "public_subnet_cidr must be a valid IPv4 CIDR."
  }
}

variable "environment_config" {
  description = "Per-environment compute and naming configuration."
  type = map(object({
    instance_type              = string
    root_volume_size           = number
    eip_name                   = string
    security_group_description = string
    disable_api_stop           = bool
    disable_api_termination    = bool
  }))
  default = {
    development = {
      instance_type              = "t3.micro"
      root_volume_size           = 30
      eip_name                   = "template-backend-develop-eip"
      security_group_description = "Development backend HTTP and HTTPS"
      disable_api_stop           = false
      disable_api_termination    = false
    }
    production = {
      instance_type              = "t3.micro"
      root_volume_size           = 50
      eip_name                   = "template-backend-production-eip"
      security_group_description = "Production backend HTTP and HTTPS"
      disable_api_stop           = true
      disable_api_termination    = true
    }
  }

  validation {
    condition     = toset(keys(var.environment_config)) == toset(["development", "production"])
    error_message = "environment_config must define exactly development and production."
  }

  validation {
    condition     = alltrue([for config in values(var.environment_config) : config.root_volume_size >= 8])
    error_message = "Every root_volume_size must be at least 8 GiB."
  }
}

variable "ami_id" {
  description = "Optional pinned Amazon Linux 2023 AMI. Null selects the newest matching x86_64 AMI."
  type        = string
  default     = null
  nullable    = true
}

variable "root_volume_encrypted" {
  description = "Encrypt EC2 root volumes. False reproduces the current instances exactly."
  type        = bool
  default     = false
}

variable "existing_ssh_key_name" {
  description = "Existing EC2 key pair to attach. Leave null when access is SSM-only."
  type        = string
  default     = null
  nullable    = true
}

variable "ssh_public_key" {
  description = "OpenSSH public key to create and attach through Terraform. Takes precedence over existing_ssh_key_name."
  type        = string
  default     = null
  nullable    = true
}

variable "ssh_ingress_cidr" {
  description = "Optional trusted IPv4 CIDR allowed to reach SSH port 22."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition     = var.ssh_ingress_cidr == null || can(cidrnetmask(var.ssh_ingress_cidr))
    error_message = "ssh_ingress_cidr must be null or a valid IPv4 CIDR."
  }
}

variable "github_owner" {
  description = "GitHub user or organization that owns the repository."
  type        = string
  default     = "bakberdy"
}

variable "github_repository" {
  description = "Existing GitHub repository configured by Terraform."
  type        = string
  default     = "base_backend"
}

variable "manage_github_configuration" {
  description = "Manage GitHub Actions permissions, environments, variables, and deploy secret."
  type        = bool
  default     = true
}

variable "adopt_existing_github_configuration" {
  description = "Import the current Actions settings, environments, variables, and deploy secret before managing them."
  type        = bool
  default     = false
}

variable "existing_github_repository_variables" {
  description = "Repository variable names already present and requiring import."
  type        = set(string)
  default     = []
}

variable "existing_resource_ids" {
  description = "Existing AWS resource IDs to import. Null creates a new project stack."
  type = object({
    vpc_id              = string
    internet_gateway_id = string
    subnet_id           = string
    route_table_id      = string
    security_group_ids  = map(string)
    instance_ids        = map(string)
    eip_allocation_ids  = map(string)
  })
  default  = null
  nullable = true

  validation {
    condition = var.existing_resource_ids == null || (
      toset(keys(var.existing_resource_ids.security_group_ids)) == toset(["development", "production"]) &&
      toset(keys(var.existing_resource_ids.instance_ids)) == toset(["development", "production"]) &&
      toset(keys(var.existing_resource_ids.eip_allocation_ids)) == toset(["development", "production"])
    )
    error_message = "Existing security group, instance, and EIP maps must contain development and production."
  }
}

variable "github_oidc_provider_arn" {
  description = "Existing GitHub OIDC provider ARN. Null creates the provider in this AWS account."
  type        = string
  default     = null
  nullable    = true
}

variable "github_oidc_thumbprints" {
  description = "Thumbprints used only when Terraform creates the GitHub OIDC provider."
  type        = list(string)
  default     = ["ab9d0263244dd0326eb67015705a667e79cfe998"]
}

variable "untagged_image_expiration_days" {
  description = "Age after which ECR removes untagged manifests."
  type        = number
  default     = 14

  validation {
    condition     = var.untagged_image_expiration_days >= 1
    error_message = "untagged_image_expiration_days must be at least 1."
  }
}

variable "route53_zone_id" {
  description = "Optional Route53 hosted zone ID. Null leaves DNS with the external provider used by the current project."
  type        = string
  default     = null
  nullable    = true
}

variable "environment_domains" {
  description = "Optional DNS names keyed by development and production."
  type        = map(string)
  default     = {}

  validation {
    condition = alltrue([
      for environment in keys(var.environment_domains) :
      contains(["development", "production"], environment)
    ])
    error_message = "environment_domains supports only development and production keys."
  }
}
