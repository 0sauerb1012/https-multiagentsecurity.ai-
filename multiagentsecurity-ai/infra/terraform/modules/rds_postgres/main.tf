resource "aws_db_subnet_group" "this" {
  name       = "${var.name_prefix}-db-subnets"
  subnet_ids = var.subnet_ids

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-db-subnets"
  })
}

resource "aws_db_instance" "this" {
  identifier              = "${var.name_prefix}-postgres"
  engine                  = "postgres"
  engine_version          = var.engine_version
  instance_class          = var.instance_class
  allocated_storage       = var.allocated_storage
  db_name                 = var.db_name
  username                = var.username
  password                = var.password
  db_subnet_group_name    = aws_db_subnet_group.this.name
  vpc_security_group_ids  = var.security_group_ids
  skip_final_snapshot     = var.skip_final_snapshot
  publicly_accessible     = false
  deletion_protection     = var.deletion_protection
  backup_retention_period = var.backup_retention_period

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-postgres"
  })
}

# TODO: add parameter groups, storage encryption tuning, monitoring, and
# Secrets Manager integration instead of direct username and password input.
