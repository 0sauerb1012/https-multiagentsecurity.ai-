variable "name_prefix" {
  type = string
}

variable "role_arn" {
  type = string
}

variable "handler" {
  type    = string
  default = "handler.lambda_handler"
}

variable "runtime" {
  type    = string
  default = "python3.11"
}

variable "timeout" {
  type    = number
  default = 60
}

variable "memory_size" {
  type    = number
  default = 512
}

variable "package_file" {
  type = string
}

variable "environment_variables" {
  type    = map(string)
  default = {}
}

variable "tags" {
  type    = map(string)
  default = {}
}
