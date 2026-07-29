check "route53_configuration" {
  assert {
    condition = (
      var.route53_zone_id == null && length(var.environment_domains) == 0
      ) || (
      var.route53_zone_id != null &&
      toset(keys(var.environment_domains)) == toset(["development", "production"])
    )
    error_message = "Configure neither Route53 input, or configure a zone ID and both environment domains."
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
