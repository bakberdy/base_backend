# AWS MVP Infrastructure

This Terraform stack deploys a low-cost production-like MVP on one EC2 instance.

Architecture:

```text
Internet
  |
Elastic IP
  |
EC2
  |- Docker Compose
     |- nginx
     |- backend container
     |- postgres container
     |- redis container
```

## Included

- VPC with one public subnet
- Internet Gateway and public route table
- Security Group with SSH, HTTP, and HTTPS ingress
- Elastic IP
- EC2 instance using Amazon Linux 2023
- IAM instance profile for CloudWatch Agent
- CloudWatch log group
- User data bootstrap for Docker, Docker Compose, CloudWatch Agent, and the Compose app

## Not Included

This MVP intentionally removes higher-cost managed services:

- ECS Fargate
- ECR
- RDS
- ElastiCache Redis
- Application Load Balancer
- NAT Gateway
- private subnets
- ECS IAM roles
- ECS task definitions
- ECS cluster and service resources

## Prerequisites

- Terraform `>= 1.6`
- AWS CLI authenticated to the target account
- An existing EC2 key pair in the target region
- A pullable backend container image in GitHub Container Registry

## Publish Image With GitHub

This repo includes `.github/workflows/publish-image.yml`. When pushed to GitHub, it builds the backend Docker image and publishes it to GitHub Container Registry:

```text
ghcr.io/<github-owner>/<github-repo>:latest
ghcr.io/<github-owner>/<github-repo>:sha-<commit>
```

In GitHub, make the package public if you want EC2 to pull it without registry credentials:

```text
GitHub repository -> Packages -> package -> Package settings -> Change visibility -> Public
```

If you keep the package private, log in to GHCR on EC2 before running Compose:

```bash
echo <github-token-with-read-packages> | docker login ghcr.io -u <github-username> --password-stdin
```

## Configure

```bash
cd infra/aws
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`:

- `key_name`: existing EC2 key pair name.
- `allowed_ssh_cidr`: your current public IP as a `/32`, or a narrow trusted CIDR.
- `container_image`: GitHub Container Registry image, for example `ghcr.io/<github-owner>/<github-repo>:latest`.
- `domain_name`: DNS name nginx should serve. Leave empty to accept any host.

Do not commit `terraform.tfvars`. It is ignored by git.

## Deploy

```bash
terraform init
terraform plan
terraform apply
```

After apply, use the outputs:

- `elastic_ip`: stable IP for DNS.
- `ssh_connection_command`: base SSH command.
- `domain_setup_instructions`: DNS A-record guidance.

## Runtime Files On EC2

Bootstrap creates `/opt/<project>-<environment>` with:

- `.env`
- `docker-compose.yml`
- `nginx/default.conf`

The `.env` file is generated on the instance with random `JWT_SECRET_KEY` and `POSTGRES_PASSWORD`. It is not stored in Terraform files or git.

To inspect the app:

```bash
cd /opt/<project>-<environment>
docker compose ps
docker compose logs -f app
```

To update runtime settings:

```bash
sudo nano /opt/<project>-<environment>/.env
cd /opt/<project>-<environment>
docker compose up -d
```

To deploy a new image after GitHub publishes it:

```bash
cd /opt/<project>-<environment>
docker compose pull app
docker compose up -d app
```

## Logs And Metrics

CloudWatch Agent sends:

- cloud-init bootstrap output
- Docker container JSON logs
- nginx access and error logs from the nginx Docker volume
- CPU, memory, and disk metrics

Logs are written to `/ec2/<project>-<environment>`.

## Security Notes

- SSH is restricted to `allowed_ssh_cidr`.
- HTTP and HTTPS are public.
- PostgreSQL and Redis are only available on the Docker network and are not exposed through the Security Group or host ports.
- Secrets are generated into the EC2-local `.env` file.
- For a real production hardening pass, move secrets to AWS Secrets Manager or SSM Parameter Store and mount them during bootstrap.

## Cost Notes

The expected monthly cost is primarily:

- one small EC2 instance
- one gp3 root volume
- one Elastic IP while attached
- CloudWatch logs and metrics usage

This avoids the main fixed costs of NAT Gateway, ALB, RDS, ElastiCache, ECS, and ECR.

## Migration Path

This layout keeps migration simple:

- Move PostgreSQL from the Compose service to RDS and point `.env` database values to RDS.
- Move Redis from the Compose service to ElastiCache and point `.env` Redis values to ElastiCache.
- Move the backend container from Compose to ECS/Fargate.
- Add ALB in front of ECS when horizontal scaling is needed.
