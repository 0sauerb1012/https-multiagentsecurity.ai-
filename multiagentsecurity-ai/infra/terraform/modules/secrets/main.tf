resource "aws_secretsmanager_secret" "db" {
  name = "${var.name_prefix}/database"

  tags = var.tags
}

resource "aws_secretsmanager_secret_version" "db" {
  secret_id     = aws_secretsmanager_secret.db.id
  secret_string = jsonencode(var.secret_values)
}

# TODO: split secrets by concern and rotate credentials automatically.
