output "lambda_ecr_repository_url" {
  description = "ECR repository URL for the ingestion Lambda image."
  value       = aws_ecr_repository.app.repository_url
}

output "web_ecr_repository_url" {
  description = "ECR repository URL for the ECS web image."
  value       = aws_ecr_repository.web.repository_url
}

output "ingestion_lambda_name" {
  description = "Ingestion Lambda function name."
  value       = aws_lambda_function.ingestion.function_name
}

output "alb_dns_name" {
  description = "Public DNS name for the web Application Load Balancer."
  value       = aws_lb.web.dns_name
}

output "web_url" {
  description = "Public base URL for the ECS-hosted web app."
  value       = "http://${aws_lb.web.dns_name}"
}

output "custom_domain_url" {
  description = "HTTPS URL for the custom domain when enabled."
  value       = try("https://${aws_route53_record.apex_alias[0].fqdn}", null)
}

output "route53_zone_id" {
  description = "Route 53 hosted zone ID for the custom domain."
  value       = try(local.route53_zone_id, null)
}

output "route53_name_servers" {
  description = "Route 53 public hosted zone name servers to set at the registrar."
  value       = try(aws_route53_zone.primary[0].name_servers, [])
}

output "acm_certificate_arn" {
  description = "ACM certificate ARN for the custom domain."
  value       = try(aws_acm_certificate.web[0].arn, null)
}

output "ecs_cluster_name" {
  description = "ECS cluster name for the web service."
  value       = aws_ecs_cluster.web.name
}

output "ecs_service_name" {
  description = "ECS service name for the web service."
  value       = aws_ecs_service.web.name
}

output "incremental_schedule_name" {
  description = "EventBridge Scheduler name for the daily incremental job."
  value       = aws_scheduler_schedule.incremental.name
}

output "reconcile_schedule_name" {
  description = "EventBridge Scheduler name for the weekly reconcile job."
  value       = aws_scheduler_schedule.reconcile.name
}

output "managed_postgres_endpoint" {
  description = "Endpoint for the managed PostgreSQL instance when enabled."
  value       = try(aws_db_instance.postgres[0].address, null)
}

output "managed_postgres_port" {
  description = "Port for the managed PostgreSQL instance when enabled."
  value       = try(aws_db_instance.postgres[0].port, null)
}

output "managed_postgres_db_name" {
  description = "Database name for the managed PostgreSQL instance when enabled."
  value       = try(aws_db_instance.postgres[0].db_name, null)
}

output "managed_postgres_master_secret_arn" {
  description = "Secrets Manager ARN holding the managed PostgreSQL master password when enabled."
  value       = try(aws_db_instance.postgres[0].master_user_secret[0].secret_arn, null)
}
