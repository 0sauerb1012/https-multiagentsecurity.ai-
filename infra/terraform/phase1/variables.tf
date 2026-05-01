variable "aws_region" {
  description = "AWS region for the MVP deployment."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name prefix used for resource naming."
  type        = string
  default     = "multiagentsecurity-ai"
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "dev"
}

variable "web_image_tag" {
  description = "Container image tag to deploy to the ECS web service."
  type        = string
  default     = "latest"
}

variable "lambda_image_tag" {
  description = "Container image tag to deploy to the ingestion Lambda."
  type        = string
  default     = "latest"
}

variable "lambda_architecture" {
  description = "Lambda CPU architecture."
  type        = string
  default     = "x86_64"
}

variable "web_cpu" {
  description = "CPU units for the web ECS task definition."
  type        = number
  default     = 512
}

variable "web_memory" {
  description = "Memory in MiB for the web ECS task definition."
  type        = number
  default     = 1024
}

variable "web_desired_count" {
  description = "Desired number of ECS web tasks."
  type        = number
  default     = 1
}

variable "web_container_port" {
  description = "Container port exposed by the FastAPI web container."
  type        = number
  default     = 8000
}

variable "health_check_path" {
  description = "ALB health check path for the web service."
  type        = string
  default     = "/"
}

variable "ingestion_lambda_memory" {
  description = "Memory size in MB for the ingestion Lambda."
  type        = number
  default     = 2048
}

variable "ingestion_lambda_timeout" {
  description = "Timeout in seconds for the ingestion Lambda."
  type        = number
  default     = 900
}

variable "log_retention_days" {
  description = "CloudWatch log retention for application logs."
  type        = number
  default     = 7
}

variable "log_level" {
  description = "Runtime log level."
  type        = string
  default     = "INFO"
}

variable "vpc_cidr" {
  description = "CIDR block for the ECS/ALB VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_a_cidr" {
  description = "CIDR block for the first public subnet."
  type        = string
  default     = "10.0.1.0/24"
}

variable "public_subnet_b_cidr" {
  description = "CIDR block for the second public subnet."
  type        = string
  default     = "10.0.2.0/24"
}

variable "database_url" {
  description = "Optional direct DATABASE_URL value. Prefer SSM parameter names for production."
  type        = string
  default     = ""
  sensitive   = true
}

variable "database_url_param_name" {
  description = "Optional SSM parameter name containing DATABASE_URL."
  type        = string
  default     = ""
}

variable "openai_api_key" {
  description = "Optional direct OPENAI_API_KEY value. Prefer SSM parameter names for production."
  type        = string
  default     = ""
  sensitive   = true
}

variable "openai_api_key_param_name" {
  description = "Optional SSM parameter name containing OPENAI_API_KEY."
  type        = string
  default     = ""
}

variable "openalex_api_key" {
  description = "Optional direct OPENALEX_API_KEY value."
  type        = string
  default     = ""
  sensitive   = true
}

variable "openalex_api_key_param_name" {
  description = "Optional SSM parameter name containing OPENALEX_API_KEY."
  type        = string
  default     = ""
}

variable "openalex_email" {
  description = "Optional direct OPENALEX_EMAIL value."
  type        = string
  default     = ""
}

variable "openalex_email_param_name" {
  description = "Optional SSM parameter name containing OPENALEX_EMAIL."
  type        = string
  default     = ""
}

variable "crossref_email" {
  description = "Optional direct CROSSREF_EMAIL value."
  type        = string
  default     = ""
}

variable "crossref_email_param_name" {
  description = "Optional SSM parameter name containing CROSSREF_EMAIL."
  type        = string
  default     = ""
}

variable "semantic_scholar_api_key" {
  description = "Optional direct SEMANTIC_SCHOLAR_API_KEY value."
  type        = string
  default     = ""
  sensitive   = true
}

variable "semantic_scholar_api_key_param_name" {
  description = "Optional SSM parameter name containing SEMANTIC_SCHOLAR_API_KEY."
  type        = string
  default     = ""
}

variable "plain_env_vars" {
  description = "Additional non-secret environment variables to inject into both the web service and ingestion Lambda."
  type        = map(string)
  default     = {}
}

variable "years_back" {
  description = "Default maximum publication age used by ingestion."
  type        = number
  default     = 5
}

variable "incremental_target_limit" {
  description = "Daily incremental relevant paper target."
  type        = number
  default     = 250
}

variable "incremental_per_topic_limit" {
  description = "Daily incremental candidate fetch limit per topic per source."
  type        = number
  default     = 40
}

variable "incremental_overlap_days" {
  description = "Overlap window for daily incremental ingestion."
  type        = number
  default     = 3
}

variable "reconcile_target_limit" {
  description = "Weekly reconcile relevant paper target."
  type        = number
  default     = 500
}

variable "reconcile_per_topic_limit" {
  description = "Weekly reconcile candidate fetch limit per topic per source."
  type        = number
  default     = 60
}

variable "reconcile_lookback_days" {
  description = "Lookback window for weekly reconcile ingestion."
  type        = number
  default     = 30
}

variable "incremental_schedule_expression" {
  description = "EventBridge Scheduler cron expression for the daily incremental ingestion run."
  type        = string
  default     = "cron(0 11 * * ? *)"
}

variable "reconcile_schedule_expression" {
  description = "EventBridge Scheduler cron expression for the weekly reconcile ingestion run."
  type        = string
  default     = "cron(0 12 ? * SUN *)"
}
