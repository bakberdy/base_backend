# Backend Deploy

## Local Development

Install dependencies once:

```bash
make install
```

Start local stack:

```bash
make dev
```

Open:

```text
http://localhost:8080
https://localhost:8443
http://localhost:8000/docs
```

Local HTTPS uses a self-signed certificate, so browser warnings are expected.

Stop local stack:

```bash
make stop
```

Run tests:

```bash
make test
```

Run the same analyzer used by GitHub:

```bash
.venv/bin/python -m mypy
```

Local env file:

```text
config/run/config.development.env
```

## GitHub Analyzer

Detailed GitHub Actions setup is documented in:

```text
.github/docs/github-actions.md
```

The analyzer workflow is:

```text
.github/workflows/analyzer-check.yml
```

It runs automatically for pull requests with these actions:

```text
opened, synchronize, reopened, ready_for_review
```

It also supports `workflow_call`, so other workflows can reuse the same check before publishing or deploying.

The workflow does this:

```text
checkout repo
set up Python 3.13
install requirements.txt
run python -m mypy
write success-analyze to the GitHub summary
```

Use it locally before pushing backend code changes:

```bash
cd backend
make install
.venv/bin/python -m mypy
```

If GitHub fails with an import error that does not fail locally, first check that the dependency is listed in `requirements.txt`, then rerun the same command with a clean environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m mypy
```

## GitHub Image

Push to GitHub. The workflow publishes:

```text
ghcr.io/<github-owner>/<github-repo>:latest
```

The workflow is:

```text
.github/workflows/publish-image.yml
```

It runs on pushes to `main` or `master`, tags matching `v*`, and manual dispatch.

Before the Docker image is built and pushed, `publish-image.yml` calls `analyzer-check.yml`. If `python -m mypy` fails, the image is not published.

If the package is private, login on EC2:

```bash
echo <github-token-with-read-packages> | sudo docker login ghcr.io -u <github-username> --password-stdin
```

## GitHub App Deploy

The workflow is:

```text
.github/workflows/deploy-app.yml
```

It does not store app env files in GitHub. Each AWS environment keeps its own `.env` on the EC2 host:

```text
production  -> /opt/mobile-app-backend-production/.env
development -> /opt/mobile-app-backend-development/.env
```

The workflow input `target_environment` selects which EC2 host to deploy by AWS tags:

```text
Project=mobile-app-backend
Environment=production
```

or:

```text
Project=mobile-app-backend
Environment=development
```

Deploy production:

```text
GitHub -> Actions -> Deploy Backend App -> Run workflow
target_environment=production
image_tag=latest
```

Deploy development:

```text
GitHub -> Actions -> Deploy Backend App -> Run workflow
target_environment=development
image_tag=latest
```

For exact deploys, use the immutable image tag from `publish-image.yml`:

```text
image_tag=sha-<commit-sha>
```

The workflow updates only `CONTAINER_IMAGE` in the selected server `.env`, then runs:

```bash
docker compose pull app
docker compose up -d app
```

Run Terraform apply once per environment before using app deploy, because the EC2 instance profile needs AWS SSM permissions:

```text
GitHub -> Actions -> Terraform AWS -> Run workflow -> target_environment=production -> apply=true
GitHub -> Actions -> Terraform AWS -> Run workflow -> target_environment=development -> apply=true
```

## AWS Production

Domain convention:

```text
production  -> api.bakberdi.dev
development -> dev.bakberdi.dev
```

Prepare Terraform vars:

```bash
cd infra/aws
cp terraform.tfvars.example terraform.tfvars
```

Edit:

```hcl
aws_region        = "eu-central-1"
key_name          = "your-ec2-key-pair-name"
allowed_ssh_cidr  = "your-public-ip/32"
domain_name       = "api.bakberdi.dev"
certificate_email = "admin@example.com"
container_image   = "ghcr.io/<github-owner>/<github-repo>:latest"
```

Apply:

```bash
terraform init
terraform apply
```

Point DNS:

```text
api.bakberdi.dev A <production terraform elastic_ip output>
dev.bakberdi.dev A <development terraform elastic_ip output>
```

Connect:

```bash
ssh -i ~/.ssh/<key-file>.pem ec2-user@<elastic_ip>
```

Server env file:

```bash
cd /opt/mobile-app-backend-production
sudo nano .env
```

Restart after env changes:

```bash
sudo docker compose up -d
```

Deploy a new image:

```bash
cd /opt/mobile-app-backend-production
sudo docker compose pull app
sudo docker compose up -d app
```

Check:

```bash
sudo docker compose ps
sudo docker compose logs --tail=100 app
curl http://localhost/health
curl -I https://api.bakberdi.dev/health
```

For local Terraform files, use:

```bash
cp infra/aws/terraform.production.tfvars.example infra/aws/terraform.tfvars
```

or:

```bash
cp infra/aws/terraform.development.tfvars.example infra/aws/terraform.tfvars
```

## GitHub Terraform Apply

The workflow is:

```text
.github/workflows/terraform.yml
```

It runs `terraform plan` on pull requests and pushes. It runs `terraform apply` only by manual dispatch with `apply=true`.

Before enabling apply in GitHub, configure a remote Terraform backend such as S3 plus DynamoDB locking. Do not use local Terraform state in GitHub Actions.

Create an AWS IAM OIDC provider for GitHub, then create an IAM role that GitHub Actions can assume. Trust policy shape:

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
          "token.actions.githubusercontent.com:sub": "repo:<github-owner>/<github-repo>:*"
        }
      }
    }
  ]
}
```

Add the GitHub Actions secret and repository variables from `.github/docs/github-actions.md`.

The workflow uses Terraform workspaces named `production` and `development` so the two environments do not share the same state.

Manual apply:

```text
GitHub -> Actions -> Terraform AWS -> Run workflow -> target_environment=production -> apply=true
GitHub -> Actions -> Terraform AWS -> Run workflow -> target_environment=development -> apply=true
```
