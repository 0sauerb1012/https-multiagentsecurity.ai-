output "ecr_repository_url" {
  description = "ECR repository URL for the shared Lambda image."
  value       = aws_ecr_repository.app.repository_url
}

output "api_lambda_name" {
  description = "API Lambda function name."
  value       = aws_lambda_function.api.function_name
}

output "ingestion_lambda_name" {
  description = "Ingestion Lambda function name."
  value       = aws_lambda_function.ingestion.function_name
}

output "http_api_url" {
  description = "Public HTTP API base URL."
  value       = aws_apigatewayv2_stage.default.invoke_url
}

output "incremental_schedule_name" {
  description = "EventBridge Scheduler name for the daily incremental job."
  value       = aws_scheduler_schedule.incremental.name
}

output "reconcile_schedule_name" {
  description = "EventBridge Scheduler name for the weekly reconcile job."
  value       = aws_scheduler_schedule.reconcile.name
}
