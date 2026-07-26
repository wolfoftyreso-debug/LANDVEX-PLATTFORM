# Optional Route 53 records — only when the zone lives in this account.
# Both hostnames point at the node's EIP; Caddy terminates TLS per host.

resource "aws_route53_record" "app" {
  count   = var.route53_zone_id != "" && var.app_domain != "" ? 1 : 0
  zone_id = var.route53_zone_id
  name    = var.app_domain
  type    = "A"
  ttl     = 300
  records = [aws_eip.node.public_ip]
}

resource "aws_route53_record" "files" {
  count   = var.route53_zone_id != "" && var.files_domain != "" ? 1 : 0
  zone_id = var.route53_zone_id
  name    = var.files_domain
  type    = "A"
  ttl     = 300
  records = [aws_eip.node.public_ip]
}
