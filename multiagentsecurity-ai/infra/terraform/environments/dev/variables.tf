variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "name_prefix" {
  type    = string
  default = "multiagentsecurity-dev"
}

variable "db_name" {
  type    = string
  default = "multiagentsecurity"
}

variable "db_username" {
  type    = string
  default = "postgres"
}

variable "db_password" {
  type      = string
  sensitive = true
}

variable "ingestion_schedule_expression" {
  type    = string
  default = "rate(6 hours)"
}
