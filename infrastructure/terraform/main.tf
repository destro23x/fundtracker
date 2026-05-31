terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Uncomment after the first apply creates the S3 state bucket:
  # backend "s3" {
  #   bucket         = "<tf_state_bucket output>"
  #   key            = "fund-tracker/terraform.tfstate"
  #   region         = "eu-west-1"
  #   dynamodb_table = "<tf_lock_table output>"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# ── Data sources ──────────────────────────────────────────────────────────────

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

# ── Locals ────────────────────────────────────────────────────────────────────

locals {
  azs     = slice(data.aws_availability_zones.available.names, 0, 2)
  prefix  = "${var.project_name}-${var.environment}"
  alb_url = "http://${aws_lb.main.dns_name}"
}
