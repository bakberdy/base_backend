check "route53_configuration" {
  assert {
    condition = (
      length(var.environment_domains) == 0
      ) || (
      toset(keys(var.environment_domains)) == toset(["development", "production"])
    )
    error_message = "Configure neither environment domain, or configure both development and production domains."
  }
}

check "github_oidc_account" {
  assert {
    condition = (
      var.github_oidc_provider_arn == null ||
      startswith(
        var.github_oidc_provider_arn,
        "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/",
      )
    )
    error_message = "github_oidc_provider_arn must belong to the AWS account used by this root."
  }
}
