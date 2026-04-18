output "vpc_id" {
  value = module.networking.vpc_id
}

output "db_endpoint" {
  value = module.rds_postgres.endpoint
}

output "lambda_function_name" {
  value = module.lambda_ingestion.function_name
}

output "artifacts_bucket" {
  value = module.s3_artifacts.bucket_name
}
