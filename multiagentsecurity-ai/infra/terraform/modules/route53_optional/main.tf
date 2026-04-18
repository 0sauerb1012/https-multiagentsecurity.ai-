# Intentionally left light. Route 53 is optional until domain cutover work begins.

resource "aws_route53_record" "frontend" {
  count   = var.enabled ? 1 : 0
  zone_id = var.zone_id
  name    = var.record_name
  type    = "CNAME"
  ttl     = 300
  records = [var.target]
}
