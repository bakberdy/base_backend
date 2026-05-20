# AWS Infrastructure

This Terraform stack deploys the backend as a container on AWS:

- ECR repository for the Docker image
- VPC with public and private subnets
- public Application Load Balancer
- ECS Fargate service in private subnets
- RDS PostgreSQL in private subnets
- ElastiCache Redis in private subnets
- CloudWatch logs
- Secrets Manager for `DATABASE_URL`, `JWT_SECRET_KEY`, and `SMTP_PASSWORD`

## Prerequisites

- Terraform `>= 1.6`
- AWS CLI authenticated to the target account
- Docker running locally

## Configure

```bash
cd infra/aws
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` for region, CORS origins, SMTP settings, and optional `certificate_arn`.

## First Apply

```bash
terraform init
terraform plan
terraform apply
```

The first apply creates ECR and the infrastructure. If `container_image` is empty, ECS points to the stack ECR repository with the `latest` tag.

## Build And Push Image

```bash
aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

docker build -t mobile-app-backend .
docker tag mobile-app-backend:latest <ecr_repository_url>:latest
docker push <ecr_repository_url>:latest
```

Use the `ecr_repository_url` Terraform output for `<ecr_repository_url>`.

## Redeploy ECS

```bash
aws ecs update-service \
  --region us-east-1 \
  --cluster <ecs_cluster_name> \
  --service <ecs_service_name> \
  --force-new-deployment
```

Use the Terraform outputs for cluster and service names.

## Notes

- The public URL is the `alb_dns_name` output.
- The load balancer checks `GET /health`.
- RDS deletion protection is enabled.
- Terraform state contains generated database credentials and secret values. Store state in an encrypted remote backend before using this for real production.
- For production HTTPS, create or import an ACM certificate and set `certificate_arn`.
