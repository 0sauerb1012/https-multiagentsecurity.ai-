output "record_fqdn" {
  value = try(aws_route53_record.frontend[0].fqdn, null)
}
