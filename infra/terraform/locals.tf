locals {
  environments = var.environment_config

  ec2_instance_role_name  = "${var.infrastructure_prefix}-ec2-ssm-instance"
  github_deploy_role_name = "${var.infrastructure_prefix}-github-deploy"
  github_ecr_role_name    = "${var.project_name}-github-ecr-publisher"

  github_oidc_provider_arn = var.github_oidc_provider_arn != null ? var.github_oidc_provider_arn : aws_iam_openid_connect_provider.github[0].arn

  ec2_key_name = var.ssh_public_key != null ? aws_key_pair.backend[0].key_name : var.existing_ssh_key_name

  github_repository_variables = {
    AWS_ECR_PUBLISH_ROLE_ARN    = aws_iam_role.github_ecr_publisher.arn
    AWS_ECR_SIGNING_PROFILE_ARN = aws_signer_signing_profile.backend.arn
    AWS_REGION                  = var.aws_region
    ECR_REPOSITORY_URI          = aws_ecr_repository.backend.repository_url
    PROJECT_NAME                = var.project_name
  }
}
