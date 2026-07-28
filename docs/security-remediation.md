# Security remediation tasks

Owner for the baseline exceptions: `@bakberdy`.

These tasks back the temporary entries in `security/exceptions.json`. An exception must be removed
when its task is completed and cannot be renewed without a new review of the reason and scope.

## Dependency: PyJWT

Upgrade PyJWT to the newest compatible fixed release, run the complete authentication test suite,
and remove all `PYSEC` exceptions assigned to this task. Target: 31 August 2026.

## Dependency: pytest

Upgrade pytest to `9.0.3` or newer, validate unit and integration tests, and remove
`PYSEC-2026-1845`. Target: 31 August 2026.

## Dependency: Starlette

Upgrade FastAPI and Starlette as one compatible change, validate request parsing, uploads,
authentication, middleware, and runtime smoke, then remove the assigned exceptions. Target:
31 August 2026.

## Container: non-root

Move the application runtime to a dedicated non-root user while preserving upload permissions and
container health. This is part of the container-hardening backlog. Target: 30 September 2026.

## State: KMS

Design and test migration of the adopted Terraform state bucket from SSE-S3 to a customer-managed
KMS key, including state recovery access. Target: 30 September 2026.

## Root volume encryption

Create a no-data-loss replacement procedure for the adopted development and production EC2 root
volumes, prove it in development, and then enable encrypted roots. Target: 30 September 2026.

## Restricted egress

Inventory required outbound destinations and replace unrestricted egress with VPC endpoints,
proxies, or explicit rules without breaking ECR, SSM, packages, DNS, and certificate renewal.
Target: 30 September 2026.

## Private subnet

Design the load balancer/NAT or endpoint topology needed to move application instances out of the
public subnet without losing HTTPS or SSM operations. Target: 30 September 2026.
