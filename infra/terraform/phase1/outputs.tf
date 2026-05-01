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
