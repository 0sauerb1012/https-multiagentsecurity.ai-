data "aws_caller_identity" "current" {}

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  name_prefix  = "${var.project_name}-${var.environment}"
  lambda_image = "${aws_ecr_repository.app.repository_url}:${var.lambda_image_tag}"
  web_image    = "${aws_ecr_repository.web.repository_url}:${var.web_image_tag}"
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
  )
  direct_secret_env = merge(
    var.database_url != "" ? { DATABASE_URL = var.database_url } : {},
    var.openai_api_key != "" ? { OPENAI_API_KEY = var.openai_api_key } : {},
    var.openalex_api_key != "" ? { OPENALEX_API_KEY = var.openalex_api_key } : {},
    var.openalex_email != "" ? { OPENALEX_EMAIL = var.openalex_email } : {},
    var.crossref_email != "" ? { CROSSREF_EMAIL = var.crossref_email } : {},
    var.semantic_scholar_api_key != "" ? { SEMANTIC_SCHOLAR_API_KEY = var.semantic_scholar_api_key } : {},
  )
  parameter_secret_env = merge(
    var.database_url_param_name != "" ? { DATABASE_URL_PARAM = var.database_url_param_name } : {},
    var.openai_api_key_param_name != "" ? { OPENAI_API_KEY_PARAM = var.openai_api_key_param_name } : {},
    var.openalex_api_key_param_name != "" ? { OPENALEX_API_KEY_PARAM = var.openalex_api_key_param_name } : {},
    var.openalex_email_param_name != "" ? { OPENALEX_EMAIL_PARAM = var.openalex_email_param_name } : {},
    var.crossref_email_param_name != "" ? { CROSSREF_EMAIL_PARAM = var.crossref_email_param_name } : {},
    var.semantic_scholar_api_key_param_name != "" ? { SEMANTIC_SCHOLAR_API_KEY_PARAM = var.semantic_scholar_api_key_param_name } : {},
  )
  web_environment = merge(
    local.runtime_env_common,
    local.direct_secret_env,
    {
      HOST = "0.0.0.0"
      PORT = tostring(var.web_container_port)
    }
  )
  web_secrets = [
    for pair in [
      { name = "DATABASE_URL", value_from = var.database_url_param_name },
      { name = "OPENAI_API_KEY", value_from = var.openai_api_key_param_name },
      { name = "OPENALEX_API_KEY", value_from = var.openalex_api_key_param_name },
      { name = "OPENALEX_EMAIL", value_from = var.openalex_email_param_name },
      { name = "CROSSREF_EMAIL", value_from = var.crossref_email_param_name },
      { name = "SEMANTIC_SCHOLAR_API_KEY", value_from = var.semantic_scholar_api_key_param_name },
      ] : {
      name      = pair.name
      valueFrom = pair.value_from
    } if pair.value_from != ""
  ]
  ingestion_environment = merge(
    local.runtime_env_common,
    local.direct_secret_env,
    local.parameter_secret_env,
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

resource "aws_ecr_repository" "web" {
  name                 = "${local.name_prefix}-web"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_cloudwatch_log_group" "ingestion" {
  name              = "/aws/lambda/${local.name_prefix}-ingestion"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "web" {
  name              = "/ecs/${local.name_prefix}-web"
  retention_in_days = var.log_retention_days
}

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
}

resource "aws_subnet" "public_a" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.public_subnet_a_cidr
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = true
}

resource "aws_subnet" "public_b" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.public_subnet_b_cidr
  availability_zone       = data.aws_availability_zones.available.names[1]
  map_public_ip_on_launch = true
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
}

resource "aws_route" "public_internet_access" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.main.id
}

resource "aws_route_table_association" "public_a" {
  subnet_id      = aws_subnet.public_a.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "public_b" {
  subnet_id      = aws_subnet.public_b.id
  route_table_id = aws_route_table.public.id
}

resource "aws_security_group" "alb" {
  name        = "${local.name_prefix}-alb"
  description = "Public ingress for the research hub web service."
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "ecs_web" {
  name        = "${local.name_prefix}-ecs-web"
  description = "Allow ALB traffic to the ECS web task."
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = var.web_container_port
    to_port         = var.web_container_port
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
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

data "aws_iam_policy_document" "ecs_task_execution_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ecs_task_execution" {
  name               = "${local.name_prefix}-ecs-task-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_execution_assume.json
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_default" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "ecs_task" {
  name               = "${local.name_prefix}-ecs-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_execution_assume.json
}

data "aws_iam_policy_document" "ecs_ssm" {
  count = length(local.parameter_arns) > 0 ? 1 : 0

  statement {
    actions   = ["ssm:GetParameter", "ssm:GetParameters"]
    resources = local.parameter_arns
  }
}

resource "aws_iam_policy" "ecs_ssm" {
  count  = length(local.parameter_arns) > 0 ? 1 : 0
  name   = "${local.name_prefix}-ecs-ssm"
  policy = data.aws_iam_policy_document.ecs_ssm[0].json
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_ssm" {
  count      = length(local.parameter_arns) > 0 ? 1 : 0
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = aws_iam_policy.ecs_ssm[0].arn
}

resource "aws_ecs_cluster" "web" {
  name = "${local.name_prefix}-web"
}

resource "aws_lb" "web" {
  name               = substr(replace("${local.name_prefix}-web", "/[^a-zA-Z0-9-]/", "-"), 0, 32)
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = [aws_subnet.public_a.id, aws_subnet.public_b.id]
}

resource "aws_lb_target_group" "web" {
  name        = substr(replace("${local.name_prefix}-web-tg", "/[^a-zA-Z0-9-]/", "-"), 0, 32)
  port        = var.web_container_port
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.main.id

  health_check {
    enabled             = true
    path                = var.health_check_path
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
    timeout             = 5
    matcher             = "200-399"
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.web.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.web.arn
  }
}

resource "aws_ecs_task_definition" "web" {
  family                   = "${local.name_prefix}-web"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = tostring(var.web_cpu)
  memory                   = tostring(var.web_memory)
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "web"
      image     = local.web_image
      essential = true
      portMappings = [
        {
          containerPort = var.web_container_port
          hostPort      = var.web_container_port
          protocol      = "tcp"
        }
      ]
      environment = [
        for key, value in local.web_environment : {
          name  = key
          value = value
        }
      ]
      secrets = local.web_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.web.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "web" {
  name            = "${local.name_prefix}-web"
  cluster         = aws_ecs_cluster.web.id
  task_definition = aws_ecs_task_definition.web.arn
  desired_count   = var.web_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    assign_public_ip = true
    security_groups  = [aws_security_group.ecs_web.id]
    subnets          = [aws_subnet.public_a.id, aws_subnet.public_b.id]
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.web.arn
    container_name   = "web"
    container_port   = var.web_container_port
  }

  depends_on = [aws_lb_listener.http]
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
