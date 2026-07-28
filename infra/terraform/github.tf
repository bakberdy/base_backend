resource "github_actions_repository_permissions" "backend" {
  count = var.manage_github_configuration ? 1 : 0

  repository           = var.github_repository
  enabled              = true
  allowed_actions      = "all"
  sha_pinning_required = false
}

resource "github_repository_environment" "backend" {
  for_each = var.manage_github_configuration ? local.environments : {}

  repository  = var.github_repository
  environment = each.key
}

resource "github_actions_environment_variable" "instance_id" {
  for_each = var.manage_github_configuration ? local.environments : {}

  repository    = var.github_repository
  environment   = github_repository_environment.backend[each.key].environment
  variable_name = "EC2_INSTANCE_ID"
  value         = aws_instance.backend[each.key].id
}

resource "github_actions_variable" "repository" {
  for_each = var.manage_github_configuration ? local.github_repository_variables : {}

  repository    = var.github_repository
  variable_name = each.key
  value         = each.value
}

resource "github_actions_secret" "deploy_role" {
  count = var.manage_github_configuration ? 1 : 0

  repository  = var.github_repository
  secret_name = "AWS_ROLE_TO_ASSUME"
  value       = aws_iam_role.github_deploy.arn
}
