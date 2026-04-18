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

# TODO: mirror the dev environment once the staging stack becomes necessary.
# For now this file exists to establish a clear environment boundary.
