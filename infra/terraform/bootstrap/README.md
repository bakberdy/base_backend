# Terraform state bootstrap

This root creates the S3 bucket required by the main infrastructure backend. It deliberately has
its own small local state because a backend cannot store state in a bucket before that bucket
exists.

After the bucket exists, keep the bootstrap state in a protected administrative location. Do not
commit it. The main root uses S3 native lock files and bucket versioning for recovery.
