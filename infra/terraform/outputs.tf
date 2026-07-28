output "aws_account_id" {
  description = "AWS account that owns the infrastructure."
  value       = data.aws_caller_identity.current.account_id
}

output "ec2_instance_ids" {
  description = "EC2 instance IDs keyed by deployment environment."
  value       = { for environment, instance in aws_instance.backend : environment => instance.id }
}

output "elastic_ips" {
  description = "Stable public IPv4 addresses keyed by deployment environment."
  value       = { for environment, eip in aws_eip.backend : environment => eip.public_ip }
}

output "ecr_repository_name" {
  description = "Private ECR repository name."
  value       = aws_ecr_repository.backend.name
}

output "ecr_repository_uri" {
  description = "Private ECR repository URI."
  value       = aws_ecr_repository.backend.repository_url
}

output "github_deploy_role_arn" {
  description = "Role ARN stored as the AWS_ROLE_TO_ASSUME GitHub secret."
  value       = aws_iam_role.github_deploy.arn
}

output "github_ecr_publish_role_arn" {
  description = "Role ARN stored as the AWS_ECR_PUBLISH_ROLE_ARN GitHub variable."
  value       = aws_iam_role.github_ecr_publisher.arn
}

output "ecr_signing_profile_arn" {
  description = "AWS Signer profile used by ECR managed signing."
  value       = aws_signer_signing_profile.backend.arn
}

output "domain_records" {
  description = "Route53 records when route53_zone_id and environment_domains are configured."
  value       = { for environment, record in aws_route53_record.backend : environment => record.fqdn }
}
