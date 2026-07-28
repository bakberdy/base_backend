output "state_bucket_name" {
  description = "Bucket value for ../backend.hcl."
  value       = aws_s3_bucket.terraform_state.id
}

output "backend_configuration" {
  description = "Non-secret values used to populate ../backend.hcl."
  value = {
    bucket       = aws_s3_bucket.terraform_state.id
    region       = var.aws_region
    encrypt      = true
    use_lockfile = true
  }
}
