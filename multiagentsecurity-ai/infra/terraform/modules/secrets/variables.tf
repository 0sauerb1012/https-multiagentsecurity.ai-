variable "name_prefix" {
  type = string
}

variable "secret_values" {
  type      = map(string)
  sensitive = true
}

variable "tags" {
  type    = map(string)
  default = {}
}
