resource "aws_ecr_repository" "backend" {
  name                 = var.project_name
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}

resource "aws_signer_signing_profile" "backend" {
  name        = "${replace(var.project_name, "-", "_")}_ecr"
  platform_id = "Notation-OCI-SHA384-ECDSA"

  signature_validity_period {
    value = 1
    type  = "YEARS"
  }
}

resource "aws_cloudcontrolapi_resource" "ecr_signing" {
  type_name = "AWS::ECR::SigningConfiguration"
  desired_state = jsonencode({
    Rules = [
      {
        SigningProfileArn = aws_signer_signing_profile.backend.arn
        RepositoryFilters = [
          {
            Filter     = aws_ecr_repository.backend.name
            FilterType = "WILDCARD_MATCH"
          }
        ]
      }
    ]
  })
}

resource "aws_ecr_lifecycle_policy" "backend" {
  repository = aws_ecr_repository.backend.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Remove untagged manifests after ${var.untagged_image_expiration_days} days"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = var.untagged_image_expiration_days
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
