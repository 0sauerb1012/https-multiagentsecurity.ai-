terraform {
  backend "s3" {}
}

provider "aws" {
  region = var.aws_region
}

locals {
  common_tags = {
    Project     = "multiagentsecurity-ai"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

module "networking" {
  source = "../../modules/networking"

  name_prefix          = var.name_prefix
  vpc_cidr             = "10.20.0.0/16"
  availability_zones   = ["${var.aws_region}a", "${var.aws_region}b"]
  private_subnet_cidrs = ["10.20.1.0/24", "10.20.2.0/24"]
  public_subnet_cidrs  = ["10.20.101.0/24", "10.20.102.0/24"]
  tags                 = local.common_tags
}

resource "aws_security_group" "database" {
  name        = "${var.name_prefix}-database"
  description = "Database access controls"
  vpc_id      = module.networking.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.common_tags
}

module "iam" {
  source = "../../modules/iam"

  name_prefix = var.name_prefix
  tags        = local.common_tags
}

module "secrets" {
  source = "../../modules/secrets"

  name_prefix = var.name_prefix
  secret_values = {
    username = var.db_username
    password = var.db_password
  }
  tags = local.common_tags
}

module "rds_postgres" {
  source = "../../modules/rds_postgres"

  name_prefix             = var.name_prefix
  subnet_ids              = module.networking.private_subnet_ids
  security_group_ids      = [aws_security_group.database.id]
  db_name                 = var.db_name
  username                = var.db_username
  password                = var.db_password
  skip_final_snapshot     = true
  deletion_protection     = false
  backup_retention_period = 7
  tags                    = local.common_tags
}

module "s3_artifacts" {
  source = "../../modules/s3_artifacts"

  bucket_name = "${var.name_prefix}-artifacts"
  tags        = local.common_tags
}

module "lambda_ingestion" {
  source = "../../modules/lambda_ingestion"

  name_prefix  = var.name_prefix
  role_arn     = module.iam.lambda_role_arn
  package_file = "../../../services/ingestion/build/ingestion.zip"
  environment_variables = {
    APP_ENV      = var.environment
    DATABASE_URL = "TODO"
  }
  tags = local.common_tags
}

module "eventbridge_schedule" {
  source = "../../modules/eventbridge_schedule"

  name_prefix         = var.name_prefix
  schedule_expression = var.ingestion_schedule_expression
  lambda_arn          = module.lambda_ingestion.function_arn
  lambda_name         = module.lambda_ingestion.function_name
}

# TODO: add Amplify application provisioning if the team decides it is worth
# managing in Terraform rather than through the AWS console initially.
