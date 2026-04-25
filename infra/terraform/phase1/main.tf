data "aws_caller_identity" "current" {}

locals {
  name_prefix  = "${var.project_name}-${var.environment}"
  lambda_image = "${aws_ecr_repository.app.repository_url}:${var.image_tag}"
  parameter_names = compact([
    var.database_url_param_name,
    var.openai_api_key_param_name,
    var.openalex_api_key_param_name,
    var.openalex_email_param_name,
    var.crossref_email_param_name,
    var.semantic_scholar_api_key_param_name,
  ])
  parameter_arns = [
    for name in local.parameter_names :
    "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${startswith(name, "/") ? name : "/${name}"}"
  ]
  runtime_env_common = merge(
    {
      APP_ENV          = var.environment
      APP_NAME         = "Multi-Agent Security Research Hub"
      DATABASE_BACKEND = "postgres"
      LOG_LEVEL        = var.log_level
    },
    var.plain_env_vars,
    var.database_url != "" ? { DATABASE_URL = var.database_url } : {},
    var.database_url_param_name != "" ? { DATABASE_URL_PARAM = var.database_url_param_name } : {},
    var.openai_api_key != "" ? { OPENAI_API_KEY = var.openai_api_key } : {},
    var.openai_api_key_param_name != "" ? { OPENAI_API_KEY_PARAM = var.openai_api_key_param_name } : {},
    var.openalex_api_key != "" ? { OPENALEX_API_KEY = var.openalex_api_key } : {},
    var.openalex_api_key_param_name != "" ? { OPENALEX_API_KEY_PARAM = var.openalex_api_key_param_name } : {},
    var.openalex_email != "" ? { OPENALEX_EMAIL = var.openalex_email } : {},
    var.openalex_email_param_name != "" ? { OPENALEX_EMAIL_PARAM = var.openalex_email_param_name } : {},
    var.crossref_email != "" ? { CROSSREF_EMAIL = var.crossref_email } : {},
    var.crossref_email_param_name != "" ? { CROSSREF_EMAIL_PARAM = var.crossref_email_param_name } : {},
    var.semantic_scholar_api_key != "" ? { SEMANTIC_SCHOLAR_API_KEY = var.semantic_scholar_api_key } : {},
    var.semantic_scholar_api_key_param_name != "" ? { SEMANTIC_SCHOLAR_API_KEY_PARAM = var.semantic_scholar_api_key_param_name } : {},
  )
  api_environment = local.runtime_env_common
  ingestion_environment = merge(
    local.runtime_env_common,
    {
      INGEST_MODE             = "incremental"
      TARGET_LIMIT            = tostring(var.incremental_target_limit)
      PER_TOPIC_LIMIT         = tostring(var.incremental_per_topic_limit)
      YEARS_BACK              = tostring(var.years_back)
      OVERLAP_DAYS            = tostring(var.incremental_overlap_days)
      RECONCILE_LOOKBACK_DAYS = tostring(var.reconcile_lookback_days)
    }
  )
}

resource "aws_ecr_repository" "app" {
  name                 = "${local.name_prefix}-lambda"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/lambda/${local.name_prefix}-api"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "ingestion" {
  name              = "/aws/lambda/${local.name_prefix}-ingestion"
  retention_in_days = var.log_retention_days
}

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${local.name_prefix}-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "lambda_ssm" {
  count = length(local.parameter_arns) > 0 ? 1 : 0

  statement {
    actions   = ["ssm:GetParameter", "ssm:GetParameters"]
    resources = local.parameter_arns
  }
}

resource "aws_iam_policy" "lambda_ssm" {
  count  = length(local.parameter_arns) > 0 ? 1 : 0
  name   = "${local.name_prefix}-lambda-ssm"
  policy = data.aws_iam_policy_document.lambda_ssm[0].json
}

resource "aws_iam_role_policy_attachment" "lambda_ssm" {
  count      = length(local.parameter_arns) > 0 ? 1 : 0
  role       = aws_iam_role.lambda.name
  policy_arn = aws_iam_policy.lambda_ssm[0].arn
}

resource "aws_lambda_function" "api" {
  function_name = "${local.name_prefix}-api"
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = local.lambda_image
  memory_size   = var.api_lambda_memory
  timeout       = var.api_lambda_timeout
  architectures = [var.lambda_architecture]

  image_config {
    command = ["lambda_handlers.api.handler"]
  }

  environment {
    variables = local.api_environment
  }

  depends_on = [aws_cloudwatch_log_group.api]
}

resource "aws_lambda_function" "ingestion" {
  function_name = "${local.name_prefix}-ingestion"
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = local.lambda_image
  memory_size   = var.ingestion_lambda_memory
  timeout       = var.ingestion_lambda_timeout
  architectures = [var.lambda_architecture]

  image_config {
    command = ["lambda_handlers.ingest.handler"]
  }

  environment {
    variables = local.ingestion_environment
  }

  depends_on = [aws_cloudwatch_log_group.ingestion]
}

resource "aws_apigatewayv2_api" "http" {
  name          = "${local.name_prefix}-http"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "api_lambda" {
  api_id                 = aws_apigatewayv2_api.http.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "default" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.api_lambda.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowHttpApiInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http.execution_arn}/*/*"
}

data "aws_iam_policy_document" "scheduler_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "scheduler" {
  name               = "${local.name_prefix}-scheduler"
  assume_role_policy = data.aws_iam_policy_document.scheduler_assume.json
}

data "aws_iam_policy_document" "scheduler_invoke_lambda" {
  statement {
    actions   = ["lambda:InvokeFunction"]
    resources = [aws_lambda_function.ingestion.arn]
  }
}

resource "aws_iam_policy" "scheduler_invoke_lambda" {
  name   = "${local.name_prefix}-scheduler-invoke-lambda"
  policy = data.aws_iam_policy_document.scheduler_invoke_lambda.json
}

resource "aws_iam_role_policy_attachment" "scheduler_invoke_lambda" {
  role       = aws_iam_role.scheduler.name
  policy_arn = aws_iam_policy.scheduler_invoke_lambda.arn
}

resource "aws_scheduler_schedule" "incremental" {
  name                = "${local.name_prefix}-incremental"
  group_name          = "default"
  schedule_expression = var.incremental_schedule_expression

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_lambda_function.ingestion.arn
    role_arn = aws_iam_role.scheduler.arn
    input = jsonencode({
      mode            = "incremental"
      target_limit    = var.incremental_target_limit
      per_topic_limit = var.incremental_per_topic_limit
      overlap_days    = var.incremental_overlap_days
      years_back      = var.years_back
    })

    retry_policy {
      maximum_event_age_in_seconds = 3600
      maximum_retry_attempts       = 1
    }
  }
}

resource "aws_scheduler_schedule" "reconcile" {
  name                = "${local.name_prefix}-reconcile"
  group_name          = "default"
  schedule_expression = var.reconcile_schedule_expression

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_lambda_function.ingestion.arn
    role_arn = aws_iam_role.scheduler.arn
    input = jsonencode({
      mode                    = "reconcile"
      target_limit            = var.reconcile_target_limit
      per_topic_limit         = var.reconcile_per_topic_limit
      reconcile_lookback_days = var.reconcile_lookback_days
      years_back              = var.years_back
    })

    retry_policy {
      maximum_event_age_in_seconds = 3600
      maximum_retry_attempts       = 1
    }
  }
}

resource "aws_lambda_permission" "scheduler_incremental" {
  statement_id  = "AllowIncrementalSchedulerInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ingestion.function_name
  principal     = "scheduler.amazonaws.com"
  source_arn    = aws_scheduler_schedule.incremental.arn
}

resource "aws_lambda_permission" "scheduler_reconcile" {
  statement_id  = "AllowReconcileSchedulerInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ingestion.function_name
  principal     = "scheduler.amazonaws.com"
  source_arn    = aws_scheduler_schedule.reconcile.arn
}
