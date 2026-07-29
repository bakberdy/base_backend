# Reusable backend infrastructure

This Terraform root is the source of truth for the backend platform and its GitHub Actions
configuration. Project-specific values live in a `.tfvars` file, so the same repository can
provision another backend without copying resources or editing HCL.

## Managed resources

AWS:

- one VPC, Internet Gateway, public subnet, route table, and subnet association;
- separate development and production security groups exposing only HTTP and HTTPS;
- separate development and production EC2 instances and Elastic IP addresses;
- one shared EC2 instance profile with SSM and repository-scoped ECR pull access;
- GitHub OIDC provider when the account does not already contain one;
- a repository/environment-scoped SSM deploy role;
- a ref-scoped ECR publisher role;
- one private immutable ECR repository with scan-on-push and lifecycle policy;
- optional Route53 A records when the hosted zone is in the same AWS account.

GitHub:

- Actions enabled with the current `allowed_actions = all` behavior;
- `development` and `production` environments;
- `EC2_INSTANCE_ID` in each environment;
- protected `main` requiring pull-request merges and `Delivery Gate`;
- repository variables `AWS_REGION`, `PROJECT_NAME`, `ECR_REPOSITORY_URI`, and
  `AWS_ECR_PUBLISH_ROLE_ARN`;
- repository secret `AWS_ROLE_TO_ASSUME`, whose value is the non-credential deploy role ARN.

Runtime application secrets such as SMTP credentials, JWT keys, and database passwords are not
Terraform inputs. The current deployment generates or stores them only on the EC2 host. Putting
their plaintext values into Terraform would persist them in state and would not reproduce the
current security boundary.

## State bootstrap

Terraform cannot create the S3 bucket that already stores its own state. Create it once with the
small bootstrap root:

```bash
cd infra/terraform/bootstrap
cp terraform.tfvars.example terraform.tfvars
# Set a globally unique state_bucket_name.
terraform init
terraform plan -out=bootstrap.tfplan
terraform apply bootstrap.tfplan
```

The bucket has versioning, AES-256 server-side encryption, complete public-access blocking, and
`prevent_destroy`. The main root uses native S3 lock files rather than the deprecated DynamoDB
locking path.

Copy the backend example and use the bootstrap output:

```bash
cd ..
cp backend.hcl.example backend.hcl
# Set bucket to the bootstrap output and choose a project-specific key.
terraform init -backend-config=backend.hcl
```

Do not put AWS or GitHub credentials in HCL or backend files. Use the normal AWS credential chain
and either `GITHUB_TOKEN` or the authenticated `gh` CLI.

## Create another project

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
```

At minimum change:

- `project_name` and `infrastructure_prefix`;
- AWS region, availability zone, and non-overlapping CIDRs when needed;
- both environment compute configurations;
- `github_owner` and `github_repository`;
- `github_oidc_provider_arn` to an existing provider, or `null` in a fresh AWS account;
- SSH settings, or leave them null and use SSM only;
- optional Route53 zone and domain names.

Then review and apply:

```bash
terraform fmt -check -recursive
terraform validate
terraform plan -out=platform.tfplan
terraform show platform.tfplan
terraform apply platform.tfplan
```

The GitHub repository must already exist. Terraform configures its deployment environments and
Actions settings but does not create or delete the source repository.

## Adopt the current project

The current infrastructure predates this root. It must be imported, not recreated:

```bash
cd infra/terraform
cp terraform.current.tfvars.example terraform.tfvars
terraform init -backend-config=backend.hcl
terraform plan -out=adopt-current.tfplan
terraform show adopt-current.tfplan
```

`terraform.current.tfvars.example` contains the read-only inventory captured from the active
project. Its declarative import blocks adopt VPC, subnet, route table, security groups, EC2,
Elastic IPs, SSM IAM resources, GitHub environments, Actions settings, existing variables, and
the deploy secret.

Before applying, the plan must show:

- no EC2, EIP, VPC, subnet, or security-group replacement;
- no destroy actions;
- only the expected ECR resources and least-privilege IAM additions;
- the deploy OIDC trust changing from a repository wildcard to the two environments;
- the two ECR GitHub variables required by the ECR-only workflow.

The legacy local state under `infra/aws` is intentionally unrelated. Never merge it into the new
state or copy its state resources manually.

## DNS

The current AWS account has no Route53 hosted zone, so DNS remains with its external provider.
For a project using Route53, set both `route53_zone_id` and `environment_domains`; Terraform then
points each environment name to its Elastic IP.
