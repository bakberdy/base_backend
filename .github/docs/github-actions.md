# GitHub Actions for two EC2 environments

The deployment model is intentionally limited to two existing EC2 instances:

| GitHub environment | Branch | EC2 purpose |
| --- | --- | --- |
| `development` | `development` | Development API |
| `production` | `main` | Production API |

The repository has three workflows:

| Workflow | Purpose |
| --- | --- |
| `project-validation.yml` | Formatting, lint, types, tests, Uvicorn, Docker, secrets, and diff checks. |
| `publish-image.yml` | Builds an immutable GHCR image and automatically deploys the branch environment. |
| `deploy-app.yml` | Reusable and manual deployment to one exact EC2 instance over AWS SSM. |

## GitHub configuration

Create this repository secret:

| Secret | Value |
| --- | --- |
| `AWS_ROLE_TO_ASSUME` | ARN of the IAM role trusted by this GitHub repository through OIDC. |

Create these repository variables:

| Variable | Example |
| --- | --- |
| `AWS_REGION` | `eu-central-1` |
| `PROJECT_NAME` | `mobile-app-backend` |

Create two GitHub environments under **Settings -> Environments**:

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
3. Outbound internet access to AWS SSM, Docker Hub, GitHub, and GHCR.
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

Pull requests run validation only.

```text
PR -> project-validation.yml
```

Push to `development`:

```text
validate -> publish sha-<full-commit-sha> -> deploy development EC2
```

Push to `main`:

```text
validate -> publish sha-<full-commit-sha> -> production approval (optional)
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
image_tag=sha-<full-commit-sha>|v1.2.3|development-latest|production-latest
```

The GHCR package must be public. If it is private, log each instance into GHCR once with a
token that has only `read:packages`.
