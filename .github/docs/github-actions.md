# GitHub Actions for two EC2 environments

The deployment model uses two EC2 instances managed or adopted by `infra/terraform`:

| GitHub environment | Source | EC2 purpose |
| --- | --- | --- |
| `development` | `vX.Y.Z-dev.N` tag on current `main` HEAD | Development API |
| `production` | `vX.Y.Z` tag on current `main` HEAD | Production API |

The repository separates orchestration from implementation:

| Workflow | Purpose |
| --- | --- |
| `delivery.yml` | Runs all required checks for pull requests targeting `main`. |
| `project-validation.yml` | Formatting, lint, types, tests, Uvicorn, and diff checks. |
| `repository-security.yml` | Secrets, dependencies, workflow, and configuration security. |
| `container-image.yml` | PR container validation or one trusted release image. |
| `publish-image.yml` | Routes release tags to the correct environment. |
| `deploy-app.yml` | Reusable and manual deployment to one exact EC2 instance over AWS SSM. |

## GitHub configuration

Terraform creates this repository secret:

| Secret | Value |
| --- | --- |
| `AWS_ROLE_TO_ASSUME` | ARN of the IAM role trusted by this GitHub repository through OIDC. |

Terraform creates these repository variables:

| Variable | Example |
| --- | --- |
| `AWS_ECR_PUBLISH_ROLE_ARN` | `arn:aws:iam::<account-id>:role/<project>-github-ecr-publisher` |
| `AWS_REGION` | `eu-central-1` |
| `ECR_REPOSITORY_URI` | `<account-id>.dkr.ecr.eu-central-1.amazonaws.com/<project>` |
| `PROJECT_NAME` | `mobile-app-backend` |

All repository variables are created and maintained by the Terraform root in `infra/terraform`.
Image publication fails closed when its ECR configuration is missing; there is no public-registry
fallback.

Terraform protects `main`: direct and force pushes are blocked, pull requests are required, the
branch must be current, and `Delivery / Delivery Gate` must succeed before merge. A newer commit
in the same pull request cancels the older Delivery run.

Terraform creates two GitHub environments:

### `development`

Environment variable:

```text
EC2_INSTANCE_ID=i-development-instance-id
```

### `production`

Environment variable:

```text
EC2_INSTANCE_ID=i-production-instance-id
```

Add required reviewers to the `production` environment if production deployments must wait
for manual approval.

## AWS configuration

Both EC2 instances need:

1. SSM Agent installed and running.
2. An EC2 IAM instance profile containing `AmazonSSMManagedInstanceCore`.
3. Outbound internet access to AWS SSM, ECR, Docker Hub, and GitHub.
4. Security Group ingress for public HTTP `80` and HTTPS `443`.
5. Optional SSH `22` restricted to a trusted `/32` address.

The GitHub OIDC role needs permission to run the deployment document only on the two backend
instances:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "ssm:SendCommand",
      "Resource": [
        "arn:aws:ssm:eu-central-1::document/AWS-RunShellScript",
        "arn:aws:ec2:eu-central-1:<account-id>:instance/<development-instance-id>",
        "arn:aws:ec2:eu-central-1:<account-id>:instance/<production-instance-id>"
      ]
    },
    {
      "Effect": "Allow",
      "Action": "ssm:GetCommandInvocation",
      "Resource": "*"
    }
  ]
}
```

Restrict the role trust policy to this repository and the two GitHub environments:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::<account-id>:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": [
            "repo:<github-owner>/<github-repo>:environment:development",
            "repo:<github-owner>/<github-repo>:environment:production"
          ]
        }
      }
    }
  ]
}
```

## Deployment behavior

Pull requests targeting `main` run all required checks without publishing or deploying.

```text
PR -> validation + repository security + PR container -> Delivery Gate
```

Development release:

```text
v1.2.3-dev.1 on main HEAD -> validate -> publish exact digest -> deploy development EC2
```

Production release:

```text
v1.2.3 on main HEAD -> validate -> publish/reuse exact digest -> production approval (if configured)
         -> deploy production EC2
```

The deployment sends the Compose, nginx, and bootstrap files through SSM. On first deployment
it installs Docker and Docker Compose, generates database/JWT secrets in an EC2-local `.env`,
and starts the complete stack. Later deployments preserve `.env`, update the immutable image,
apply Compose changes, and verify the application health endpoint.

Manual deployment or rollback:

```text
Actions -> Deploy Backend to EC2 -> Run workflow
target_environment=development|production
source_sha=<full-commit-sha>
image_reference=<repository>@sha256:<digest>
security_evidence_id=<run-id>:<attempt>:sha256
```

The EC2 bootstrap logs Docker into the private ECR registry for every deployment using the
instance profile, pulls the image, and immediately logs out. No static registry token is required.
