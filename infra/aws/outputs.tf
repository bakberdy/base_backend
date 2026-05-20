output "alb_dns_name" {
  description = "Public ALB DNS name."
  value       = aws_lb.api.dns_name
}

output "ecr_repository_url" {
  description = "ECR repository URL for the API image."
  value       = aws_ecr_repository.api.repository_url
}

output "ecs_cluster_name" {
  description = "ECS cluster name."
  value       = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  description = "ECS service name."
  value       = aws_ecs_service.api.name
}

output "app_secret_arn" {
  description = "Secrets Manager secret used by the ECS task."
  value       = aws_secretsmanager_secret.app.arn
}

output "database_endpoint" {
  description = "RDS endpoint."
  value       = aws_db_instance.postgres.address
}

output "redis_endpoint" {
  description = "Redis primary endpoint."
  value       = aws_elasticache_replication_group.redis.primary_endpoint_address
}
