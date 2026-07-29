resource "github_actions_repository_permissions" "backend" {
  count = var.manage_github_configuration ? 1 : 0

  repository           = var.github_repository
  enabled              = true
  allowed_actions      = "all"
  sha_pinning_required = true
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

resource "github_actions_environment_variable" "deploy_health_url" {
  for_each = var.manage_github_configuration ? local.environments : {}

  repository    = var.github_repository
  environment   = github_repository_environment.backend[each.key].environment
  variable_name = "DEPLOY_HEALTH_URL"
  value = contains(keys(var.environment_domains), each.key) ? (
    "https://${var.environment_domains[each.key]}/health"
  ) : "http://${aws_eip.backend[each.key].public_ip}/health"
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

resource "github_branch_protection" "main" {
  count = var.manage_github_configuration ? 1 : 0

  repository_id                   = var.github_repository
  pattern                         = "main"
  enforce_admins                  = true
  allows_deletions                = false
  allows_force_pushes             = false
  require_conversation_resolution = true
  require_signed_commits          = false
  required_linear_history         = true

  required_status_checks {
    strict = true
    contexts = [
      "Delivery / Delivery Gate",
    ]
  }

  required_pull_request_reviews {
    dismiss_stale_reviews           = true
    required_approving_review_count = 0
  }
}
