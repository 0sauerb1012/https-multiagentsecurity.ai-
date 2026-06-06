data "aws_caller_identity" "current" {}

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  name_prefix          = "${var.project_name}-${var.environment}"
  lambda_image         = "${aws_ecr_repository.app.repository_url}:${var.lambda_image_tag}"
  web_image            = "${aws_ecr_repository.web.repository_url}:${var.web_image_tag}"
  route53_zone_enabled = var.create_public_hosted_zone || var.hosted_zone_id != ""
  custom_domain_name   = trim(var.domain_name, ".")
  custom_domain_enabled = (
    var.enable_custom_domain &&
    local.route53_zone_enabled &&
    local.custom_domain_name != ""
  )
  parameter_names = compact([
    var.managed_postgres_enabled ? "" : var.database_url_param_name,
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
    (!var.managed_postgres_enabled && var.database_url != "") ? { DATABASE_URL = var.database_url } : {},
    var.openai_api_key != "" ? { OPENAI_API_KEY = var.openai_api_key } : {},
    var.openalex_api_key != "" ? { OPENALEX_API_KEY = var.openalex_api_key } : {},
    var.openalex_email != "" ? { OPENALEX_EMAIL = var.openalex_email } : {},
    var.crossref_email != "" ? { CROSSREF_EMAIL = var.crossref_email } : {},
    var.semantic_scholar_api_key != "" ? { SEMANTIC_SCHOLAR_API_KEY = var.semantic_scholar_api_key } : {},
  )
  parameter_secret_env = merge(
    (!var.managed_postgres_enabled && var.database_url_param_name != "") ? { DATABASE_URL_PARAM = var.database_url_param_name } : {},
    var.openai_api_key_param_name != "" ? { OPENAI_API_KEY_PARAM = var.openai_api_key_param_name } : {},
    var.openalex_api_key_param_name != "" ? { OPENALEX_API_KEY_PARAM = var.openalex_api_key_param_name } : {},
    var.openalex_email_param_name != "" ? { OPENALEX_EMAIL_PARAM = var.openalex_email_param_name } : {},
    var.crossref_email_param_name != "" ? { CROSSREF_EMAIL_PARAM = var.crossref_email_param_name } : {},
    var.semantic_scholar_api_key_param_name != "" ? { SEMANTIC_SCHOLAR_API_KEY_PARAM = var.semantic_scholar_api_key_param_name } : {},
  )
  managed_database_env = var.managed_postgres_enabled ? {
    DATABASE_HOST    = aws_db_instance.postgres[0].address
    DATABASE_PORT    = tostring(aws_db_instance.postgres[0].port)
    DATABASE_NAME    = var.managed_postgres_db_name
    DATABASE_USER    = var.managed_postgres_username
    DATABASE_SSLMODE = "require"
  } : {}
  managed_database_lambda_secret_env = (
    var.managed_postgres_enabled && var.lambda_vpc_enabled
    ) ? {
    DATABASE_PASSWORD_SECRET_ARN = aws_db_instance.postgres[0].master_user_secret[0].secret_arn
  } : {}
  managed_database_web_secret_arn = (
    var.managed_postgres_enabled
    ? "${aws_db_instance.postgres[0].master_user_secret[0].secret_arn}:password::"
    : ""
  )
  secret_arns = compact([
    var.managed_postgres_enabled && var.lambda_vpc_enabled ? aws_db_instance.postgres[0].master_user_secret[0].secret_arn : "",
    var.managed_postgres_enabled ? aws_db_instance.postgres[0].master_user_secret[0].secret_arn : "",
  ])
  web_environment = merge(
    local.runtime_env_common,
    local.direct_secret_env,
    local.managed_database_env,
    {
      HOST = "0.0.0.0"
      PORT = tostring(var.web_container_port)
    }
  )
  web_secrets = [
    for pair in [
      { name = "DATABASE_URL", value_from = var.managed_postgres_enabled ? "" : var.database_url_param_name },
      { name = "DATABASE_PASSWORD", value_from = local.managed_database_web_secret_arn },
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
    local.managed_database_env,
    local.managed_database_lambda_secret_env,
    {
      INGEST_MODE             = "incremental"
      TARGET_LIMIT            = tostring(var.incremental_target_limit)
      PER_TOPIC_LIMIT         = tostring(var.incremental_per_topic_limit)
      YEARS_BACK              = tostring(var.years_back)
      OVERLAP_DAYS            = tostring(var.incremental_overlap_days)
      RECONCILE_LOOKBACK_DAYS = tostring(var.reconcile_lookback_days)
    }
  )
  incremental_scheduler_input = jsonencode({
    containerOverrides = [
      {
        name = "web"
        command = [
          "python",
          "-m",
          "services.ingest",
          "--mode",
          "incremental",
          "--target-limit",
          tostring(var.incremental_target_limit),
          "--per-topic-limit",
          tostring(var.incremental_per_topic_limit),
          "--overlap-days",
          tostring(var.incremental_overlap_days),
          "--years-back",
          tostring(var.years_back),
        ]
      }
    ]
  })
  reconcile_scheduler_input = jsonencode({
    containerOverrides = [
      {
        name = "web"
        command = [
          "python",
          "-m",
          "services.ingest",
          "--mode",
          "reconcile",
          "--target-limit",
          tostring(var.reconcile_target_limit),
          "--per-topic-limit",
          tostring(var.reconcile_per_topic_limit),
          "--reconcile-lookback-days",
          tostring(var.reconcile_lookback_days),
          "--years-back",
          tostring(var.years_back),
        ]
      }
    ]
  })
}

resource "aws_route53_zone" "primary" {
  count = var.create_public_hosted_zone ? 1 : 0
  name  = local.custom_domain_name
}

locals {
  route53_zone_id = var.create_public_hosted_zone ? aws_route53_zone.primary[0].zone_id : var.hosted_zone_id
}

resource "aws_route53_record" "preserved" {
  for_each = local.route53_zone_enabled ? {
    for index, record in var.dns_records :
    "${upper(record.type)}-${record.name == "" ? "apex" : record.name}-${index}" => record
  } : {}

  zone_id = local.route53_zone_id
  name    = each.value.name == "" ? local.custom_domain_name : "${each.value.name}.${local.custom_domain_name}"
  type    = upper(each.value.type)
  ttl     = each.value.ttl
  records = each.value.records
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

resource "aws_subnet" "private_a" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.private_subnet_a_cidr
  availability_zone = data.aws_availability_zones.available.names[0]
}

resource "aws_subnet" "private_b" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.private_subnet_b_cidr
  availability_zone = data.aws_availability_zones.available.names[1]
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

  ingress {
    from_port   = 443
    to_port     = 443
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

resource "aws_security_group" "lambda_vpc" {
  count       = var.lambda_vpc_enabled ? 1 : 0
  name        = "${local.name_prefix}-lambda-vpc"
  description = "Allow the ingestion Lambda to access private resources in the VPC."
  vpc_id      = aws_vpc.main.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "postgres" {
  count       = var.managed_postgres_enabled ? 1 : 0
  name        = "${local.name_prefix}-postgres"
  description = "Allow application access to the managed PostgreSQL instance."
  vpc_id      = aws_vpc.main.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group_rule" "postgres_ingress_from_ecs" {
  count                    = var.managed_postgres_enabled ? 1 : 0
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = aws_security_group.postgres[0].id
  source_security_group_id = aws_security_group.ecs_web.id
  description              = "Allow ECS web tasks to connect to the managed PostgreSQL instance."
}

resource "aws_security_group_rule" "postgres_ingress_from_lambda" {
  count                    = var.managed_postgres_enabled && var.lambda_vpc_enabled ? 1 : 0
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = aws_security_group.postgres[0].id
  source_security_group_id = aws_security_group.lambda_vpc[0].id
  description              = "Allow the ingestion Lambda to connect to the managed PostgreSQL instance."
}

resource "aws_db_subnet_group" "postgres" {
  count      = var.managed_postgres_enabled ? 1 : 0
  name       = "${local.name_prefix}-postgres"
  subnet_ids = [aws_subnet.private_a.id, aws_subnet.private_b.id]

  tags = {
    Name = "${local.name_prefix}-postgres"
  }
}

resource "aws_db_instance" "postgres" {
  count                       = var.managed_postgres_enabled ? 1 : 0
  identifier                  = "${local.name_prefix}-postgres"
  engine                      = "postgres"
  engine_version              = var.managed_postgres_engine_version
  instance_class              = var.managed_postgres_instance_class
  allocated_storage           = var.managed_postgres_allocated_storage
  db_name                     = var.managed_postgres_db_name
  username                    = var.managed_postgres_username
  manage_master_user_password = true
  db_subnet_group_name        = aws_db_subnet_group.postgres[0].name
  vpc_security_group_ids      = [aws_security_group.postgres[0].id]
  publicly_accessible         = var.managed_postgres_publicly_accessible
  backup_retention_period     = var.managed_postgres_backup_retention_period
  deletion_protection         = var.managed_postgres_deletion_protection
  skip_final_snapshot         = var.managed_postgres_skip_final_snapshot
  storage_encrypted           = true
  auto_minor_version_upgrade  = true

  tags = {
    Name = "${local.name_prefix}-postgres"
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

resource "aws_iam_role_policy_attachment" "lambda_vpc_access" {
  count      = var.lambda_vpc_enabled ? 1 : 0
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

data "aws_iam_policy_document" "lambda_ssm" {
  count = length(local.parameter_arns) > 0 ? 1 : 0

  statement {
    actions   = ["ssm:GetParameter", "ssm:GetParameters"]
    resources = local.parameter_arns
  }
}

data "aws_iam_policy_document" "lambda_secrets" {
  count = var.managed_postgres_enabled && var.lambda_vpc_enabled ? 1 : 0

  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = local.secret_arns
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

resource "aws_iam_policy" "lambda_secrets" {
  count  = var.managed_postgres_enabled && var.lambda_vpc_enabled ? 1 : 0
  name   = "${local.name_prefix}-lambda-secrets"
  policy = data.aws_iam_policy_document.lambda_secrets[0].json
}

resource "aws_iam_role_policy_attachment" "lambda_secrets" {
  count      = var.managed_postgres_enabled && var.lambda_vpc_enabled ? 1 : 0
  role       = aws_iam_role.lambda.name
  policy_arn = aws_iam_policy.lambda_secrets[0].arn
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

  dynamic "vpc_config" {
    for_each = var.lambda_vpc_enabled ? [1] : []

    content {
      security_group_ids = [aws_security_group.lambda_vpc[0].id]
      subnet_ids         = [aws_subnet.private_a.id, aws_subnet.private_b.id]
    }
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

data "aws_iam_policy_document" "ecs_secrets" {
  count = var.managed_postgres_enabled ? 1 : 0

  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = local.secret_arns
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

resource "aws_iam_policy" "ecs_secrets" {
  count  = var.managed_postgres_enabled ? 1 : 0
  name   = "${local.name_prefix}-ecs-secrets"
  policy = data.aws_iam_policy_document.ecs_secrets[0].json
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_secrets" {
  count      = var.managed_postgres_enabled ? 1 : 0
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = aws_iam_policy.ecs_secrets[0].arn
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

  dynamic "default_action" {
    for_each = local.custom_domain_enabled ? [] : [1]

    content {
      type             = "forward"
      target_group_arn = aws_lb_target_group.web.arn
    }
  }

  dynamic "default_action" {
    for_each = local.custom_domain_enabled ? [1] : []

    content {
      type = "redirect"

      redirect {
        port        = "443"
        protocol    = "HTTPS"
        status_code = "HTTP_301"
      }
    }
  }
}

resource "aws_acm_certificate" "web" {
  count                     = local.custom_domain_enabled ? 1 : 0
  domain_name               = local.custom_domain_name
  subject_alternative_names = var.create_www_record ? ["www.${local.custom_domain_name}"] : []
  validation_method         = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "web_cert_validation" {
  for_each = local.custom_domain_enabled ? {
    for dvo in aws_acm_certificate.web[0].domain_validation_options :
    dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  } : {}

  zone_id = local.route53_zone_id
  name    = each.value.name
  type    = each.value.type
  ttl     = 300
  records = [each.value.record]
}

resource "aws_acm_certificate_validation" "web" {
  count = local.custom_domain_enabled ? 1 : 0

  certificate_arn         = aws_acm_certificate.web[0].arn
  validation_record_fqdns = [for record in aws_route53_record.web_cert_validation : record.fqdn]
}

resource "aws_lb_listener" "https" {
  count             = local.custom_domain_enabled ? 1 : 0
  load_balancer_arn = aws_lb.web.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-2016-08"
  certificate_arn   = aws_acm_certificate_validation.web[0].certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.web.arn
  }
}

resource "aws_route53_record" "apex_alias" {
  count   = local.custom_domain_enabled ? 1 : 0
  zone_id = local.route53_zone_id
  name    = local.custom_domain_name
  type    = "A"

  alias {
    name                   = aws_lb.web.dns_name
    zone_id                = aws_lb.web.zone_id
    evaluate_target_health = true
  }
}

resource "aws_route53_record" "www_alias" {
  count   = local.custom_domain_enabled && var.create_www_record ? 1 : 0
  zone_id = local.route53_zone_id
  name    = "www.${local.custom_domain_name}"
  type    = "A"

  alias {
    name                   = aws_lb.web.dns_name
    zone_id                = aws_lb.web.zone_id
    evaluate_target_health = true
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

  lifecycle {
    ignore_changes = [desired_count]
  }
}

resource "aws_appautoscaling_target" "web" {
  count = var.web_autoscaling_enabled ? 1 : 0

  max_capacity       = var.web_autoscaling_max_capacity
  min_capacity       = var.web_autoscaling_min_capacity
  resource_id        = "service/${aws_ecs_cluster.web.name}/${aws_ecs_service.web.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "web_cpu" {
  count = var.web_autoscaling_enabled ? 1 : 0

  name               = "${local.name_prefix}-web-cpu"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.web[0].resource_id
  scalable_dimension = aws_appautoscaling_target.web[0].scalable_dimension
  service_namespace  = aws_appautoscaling_target.web[0].service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }

    target_value       = var.web_autoscaling_cpu_target
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
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

data "aws_iam_policy_document" "scheduler_run_ecs" {
  statement {
    actions   = ["ecs:RunTask"]
    resources = [aws_ecs_task_definition.web.arn_without_revision]
  }

  statement {
    actions   = ["ecs:RunTask"]
    resources = ["${aws_ecs_task_definition.web.arn_without_revision}:*"]
  }

  statement {
    actions = ["iam:PassRole"]
    resources = [
      aws_iam_role.ecs_task_execution.arn,
      aws_iam_role.ecs_task.arn,
    ]
  }
}

resource "aws_iam_policy" "scheduler_run_ecs" {
  name   = "${local.name_prefix}-scheduler-run-ecs"
  policy = data.aws_iam_policy_document.scheduler_run_ecs.json
}

resource "aws_iam_role_policy_attachment" "scheduler_run_ecs" {
  role       = aws_iam_role.scheduler.name
  policy_arn = aws_iam_policy.scheduler_run_ecs.arn
}

resource "aws_scheduler_schedule" "incremental" {
  name                = "${local.name_prefix}-incremental"
  group_name          = "default"
  schedule_expression = var.incremental_schedule_expression

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_ecs_cluster.web.arn
    role_arn = aws_iam_role.scheduler.arn
    input    = local.incremental_scheduler_input

    ecs_parameters {
      task_definition_arn = aws_ecs_task_definition.web.arn
      launch_type         = "FARGATE"
      platform_version    = "1.4.0"
      task_count          = 1

      network_configuration {
        assign_public_ip = true
        security_groups  = [aws_security_group.ecs_web.id]
        subnets          = [aws_subnet.public_a.id, aws_subnet.public_b.id]
      }
    }

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
    arn      = aws_ecs_cluster.web.arn
    role_arn = aws_iam_role.scheduler.arn
    input    = local.reconcile_scheduler_input

    ecs_parameters {
      task_definition_arn = aws_ecs_task_definition.web.arn
      launch_type         = "FARGATE"
      platform_version    = "1.4.0"
      task_count          = 1

      network_configuration {
        assign_public_ip = true
        security_groups  = [aws_security_group.ecs_web.id]
        subnets          = [aws_subnet.public_a.id, aws_subnet.public_b.id]
      }
    }

    retry_policy {
      maximum_event_age_in_seconds = 3600
      maximum_retry_attempts       = 1
    }
  }
}
