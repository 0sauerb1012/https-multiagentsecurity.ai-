resource "aws_lambda_function" "this" {
  function_name    = "${var.name_prefix}-ingestion"
  role             = var.role_arn
  handler          = var.handler
  runtime          = var.runtime
  timeout          = var.timeout
  memory_size      = var.memory_size
  filename         = var.package_file
  source_code_hash = filebase64sha256(var.package_file)

  environment {
    variables = var.environment_variables
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-ingestion"
  })
}

# TODO: move artifact handling to S3-based deployment and connect to VPC if the
# Lambda needs direct private database access.
