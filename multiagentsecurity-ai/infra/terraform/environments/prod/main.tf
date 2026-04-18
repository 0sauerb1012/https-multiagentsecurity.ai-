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

# TODO: promote the validated staging or dev topology here once production
# requirements are confirmed. Keep domain cutover optional until then.
