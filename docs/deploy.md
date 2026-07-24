# Deploy backend to two EC2 instances

## Target architecture

```text
development branch                     main branch
      |                                     |
      v                                     v
GHCR immutable image                 GHCR immutable image
      |                                     |
      v                                     v
Development EC2                     Production EC2
  nginx                                  nginx
  Uvicorn/FastAPI                        Uvicorn/FastAPI
  PostgreSQL                             PostgreSQL
  Redis                                  Redis
```

There is no Terraform, ECS, Fargate, ECR, RDS, ElastiCache, or load balancer configuration in
this repository. Each environment is one independent EC2 instance with its own Docker volumes
and server-local secrets.

## 1. Prepare the two EC2 instances

Use Amazon Linux 2023 or Ubuntu. Assign a stable Elastic IP to each instance.

Each Security Group should allow:

| Port | Source |
| --- | --- |
| `80` | `0.0.0.0/0` |
| `443` | `0.0.0.0/0` |
| `22` | Optional; only your trusted IP as `/32` |

Do not open PostgreSQL `5432`, Redis `6379`, or Uvicorn `8000` in the Security Group.

Attach an EC2 IAM role containing:

```text
AmazonSSMManagedInstanceCore
```

Verify both instances appear as managed nodes in AWS Systems Manager.

## 2. Configure GitHub

Follow `.github/docs/github-actions.md`.

Required configuration:

```text
Secret:
  AWS_ROLE_TO_ASSUME

Repository variables:
  AWS_REGION
  PROJECT_NAME=mobile-app-backend

GitHub environment development:
  EC2_INSTANCE_ID=<development-instance-id>

GitHub environment production:
  EC2_INSTANCE_ID=<production-instance-id>
```

Make the `ghcr.io/<owner>/<repo>` package public so EC2 can pull it without a stored registry
token.

## 3. First deployment

Create and push the development branch:

```bash
git switch -c development
git push -u origin development
```

The first successful workflow will bootstrap the development EC2 automatically.

Push the reviewed commit to `main` to bootstrap production:

```bash
git switch main
git merge --ff-only development
git push origin main
```

Runtime directories:

```text
/opt/mobile-app-backend-development
/opt/mobile-app-backend-production
```

The first deployment creates `.env` with random values for:

```text
JWT_SECRET_KEY
POSTGRES_PASSWORD
```

It never uploads local `config.production.env` or application secrets from GitHub.

## 4. Configure each server

Open an SSM session or connect with SSH, then edit:

```bash
sudo nano /opt/mobile-app-backend-development/.env
sudo nano /opt/mobile-app-backend-production/.env
```

Set environment-specific values:

```env
CORS_ALLOWED_ORIGINS=https://your-frontend.example
OTP_EMAIL_ENABLED=true
SMTP_HOST=...
SMTP_PORT=...
SMTP_USERNAME=...
SMTP_PASSWORD=...
SMTP_SENDER_EMAIL=...
SMTP_SENDER_NAME=Mobile App
```

Apply changes:

```bash
cd /opt/mobile-app-backend-production
sudo docker compose up -d
sudo docker compose ps
sudo docker compose logs --tail=100 app
```

Use the development directory on the development instance.

## 5. Domain and HTTPS

Create DNS A records:

```text
dev-api.example.com -> development Elastic IP
api.example.com     -> production Elastic IP
```

Wait until DNS resolves to the correct instance, then run the helper installed by deployment:

```bash
sudo /opt/mobile-app-backend-development/enable_https.sh \
  development \
  dev-api.example.com \
  admin@example.com

sudo /opt/mobile-app-backend-production/enable_https.sh \
  production \
  api.example.com \
  admin@example.com
```

The helper obtains a Let's Encrypt certificate, switches nginx to it, installs daily renewal,
and checks `/health`.

## 6. Normal releases

Development:

```text
push development -> validate -> publish immutable image -> deploy development
```

Production:

```text
push main -> validate -> publish immutable image -> deploy production
```

For rollback, manually run `Deploy Backend to EC2` with an older immutable tag:

```text
sha-<full-commit-sha>
```

## 7. Operations

Inspect an environment:

```bash
cd /opt/mobile-app-backend-production
sudo docker compose ps
sudo docker compose logs -f app
sudo docker compose logs -f nginx
curl https://api.example.com/health
```

Database, Redis, and uploads are stored on that instance in Docker volumes. Configure EC2
snapshots and database backups before relying on this layout for production data.

## Local development and validation

```bash
make install
make dev
make validate
make test-all
```
