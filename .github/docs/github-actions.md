# Backend GitHub Actions (step by step)

## Step 1 - Workflows

The backend uses four GitHub Actions workflows:

| Workflow | Purpose |
| -------- | ------- |
| `.github/workflows/project-validation.yml` | Runs formatting, lint, types, tests, Uvicorn, Docker, secrets, and diff checks. |
| `.github/workflows/publish-image.yml` | Runs full validation first, then builds and publishes the Docker image to GitHub Container Registry. |
| `.github/workflows/terraform.yml` | Runs Terraform plan/apply for AWS infrastructure. |
| `.github/workflows/deploy-app.yml` | Uses AWS SSM to deploy a selected GHCR image tag to the selected EC2 environment. |

`publish-image.yml` uses GitHub's built-in `GITHUB_TOKEN` for GHCR publishing. You do not need to create a secret for that token.

## Step 2 - GitHub Actions secret

**Repo -> Settings -> Secrets and variables -> Actions -> New repository secret.**

| Secret | Value | Used by |
| ------ | ----- | ------- |
| `AWS_ROLE_TO_ASSUME` | `arn:aws:iam::<account-id>:role/<github-actions-backend-role>` | `.github/workflows/terraform.yml`, `.github/workflows/deploy-app.yml` |

The role must allow GitHub Actions to assume it through GitHub OIDC.

For `deploy-app.yml`, the role also needs permission to find the target EC2 instance and run SSM commands:

```text
ec2:DescribeInstances
ssm:SendCommand
ssm:GetCommandInvocation
```

For `terraform.yml`, the role needs the AWS permissions required to create and update the Terraform resources in `infra/aws`.

## Step 3 - GitHub Actions variables

**Repo -> Settings -> Secrets and variables -> Actions -> Variables -> New repository variable.**

| Variable | Example value | Used for |
| -------- | ------------- | -------- |
| `AWS_REGION` | `eu-central-1` | AWS provider region. |
| `TF_PROJECT_NAME` | `mobile-app-backend` | Terraform project/resource naming. |
| `TF_ENVIRONMENT` | `production` | Default environment for non-manual workflow runs. |
| `TF_INSTANCE_TYPE` | `t3.micro` | EC2 instance size. |
| `TF_KEY_NAME` | `<existing-ec2-key-pair-name>` | EC2 SSH key pair name. |
| `TF_ALLOWED_SSH_CIDR` | `<your-ip-or-office-cidr>` | CIDR allowed to SSH into EC2. |
| `TF_PRODUCTION_VPC_CIDR` | `10.40.0.0/16` | Production VPC CIDR. |
| `TF_DEVELOPMENT_VPC_CIDR` | `10.41.0.0/16` | Development VPC CIDR. |
| `TF_PRODUCTION_DOMAIN_NAME` | `api.bakberdi.dev` | Production API domain. |
| `TF_DEVELOPMENT_DOMAIN_NAME` | `dev.bakberdi.dev` | Development API domain. |
| `TF_CERTIFICATE_EMAIL` | `admin@example.com` | Let's Encrypt registration email. |

Keep runtime app secrets out of GitHub variables. The EC2 bootstrap creates the server `.env`; edit runtime values on the server when needed.

Each environment keeps its own env file on AWS:

| Environment | EC2 app directory | Env file |
| ----------- | ----------------- | -------- |
| `production` | `/opt/mobile-app-backend-production` | `/opt/mobile-app-backend-production/.env` |
| `development` | `/opt/mobile-app-backend-development` | `/opt/mobile-app-backend-development/.env` |

`deploy-app.yml` does not create or upload env files from GitHub. It selects the EC2 host by AWS tags, updates only `CONTAINER_IMAGE` in that host's existing `.env`, and runs Docker Compose.

The EC2 instance role must include `AmazonSSMManagedInstanceCore`. Terraform manages this attachment in `infra/aws/main.tf`; run Terraform apply once for each environment before using `deploy-app.yml`.

## Step 4 - Optional GHCR read token

This is not used by the workflows.

Create a GitHub token with `read:packages` only if the GHCR package is private and EC2 must run `docker login` manually:

| Token | Use |
| ----- | --- |
| `GHCR_READ_TOKEN` | Optional local/operator value for logging EC2 into GHCR. |

Login on EC2:

```bash
echo <github-token-with-read-packages> | docker login ghcr.io -u <github-username> --password-stdin
```

If the backend package is public, EC2 can pull without this token.

## Step 5 - CI behavior

Pull requests:

```text
project-validation.yml
  -> Ruff format and lint
  -> mypy
  -> unit and integration tests
  -> Uvicorn smoke test
  -> Docker build
  -> Gitleaks
  -> git diff --check
```

Pushes to `main` or `master`, tags matching `v*`, and manual image runs:

```text
publish-image.yml -> project-validation.yml -> Docker build -> GHCR push
```

Manual app deployment:

```text
deploy-app.yml -> select target_environment -> update AWS .env CONTAINER_IMAGE -> docker compose pull app -> docker compose up -d app
```

Terraform changes:

```text
terraform.yml -> terraform fmt -> init -> workspace -> validate -> plan
```

Terraform apply is manual only:

```text
GitHub -> Actions -> Terraform AWS -> Run workflow -> target_environment=<environment> -> apply=true
```

App deployment is manual and environment-specific:

```text
GitHub -> Actions -> Deploy Backend App -> Run workflow -> target_environment=production -> image_tag=latest
GitHub -> Actions -> Deploy Backend App -> Run workflow -> target_environment=development -> image_tag=latest
```

Use a pinned image tag when you want exact deploy control:

```text
image_tag=sha-<commit-sha>
image_tag=v1.2.3
```

## Step 6 - Local verification

Before pushing backend code changes, run:

```bash
cd backend
make install
make validate
make test-all
```

Before changing Terraform workflow or infra files, run locally from `backend/infra/aws` when Terraform is installed:

```bash
terraform fmt -check -recursive
terraform init
terraform validate
terraform plan
```
