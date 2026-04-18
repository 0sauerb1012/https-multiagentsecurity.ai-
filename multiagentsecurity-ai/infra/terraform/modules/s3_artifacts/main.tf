resource "aws_s3_bucket" "this" {
  bucket = var.bucket_name

  tags = merge(var.tags, {
    Name = var.bucket_name
  })
}

# TODO: add encryption, lifecycle policies, versioning, and access control.
