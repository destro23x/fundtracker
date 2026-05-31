output "app_url" {
  description = "Application URL (frontend)"
  value       = "http://${aws_lb.main.dns_name}"
}

output "alb_dns_name" {
  description = "ALB DNS name (set in DNS / var.api_url)"
  value       = aws_lb.main.dns_name
}

output "backend_ecr_url" {
  description = "ECR URL — push backend image here"
  value       = aws_ecr_repository.backend.repository_url
}

output "frontend_ecr_url" {
  description = "ECR URL — push frontend image here"
  value       = aws_ecr_repository.frontend.repository_url
}

output "rds_endpoint" {
  description = "RDS PostgreSQL host"
  value       = aws_db_instance.main.address
  sensitive   = true
}

output "uploads_bucket" {
  description = "S3 bucket for uploaded Excel/PDF files"
  value       = aws_s3_bucket.uploads.bucket
}

output "tf_state_bucket" {
  description = "S3 bucket for Terraform remote state (use in backend config)"
  value       = aws_s3_bucket.tf_state.bucket
}

output "tf_lock_table" {
  description = "DynamoDB table for Terraform state locking"
  value       = aws_dynamodb_table.tf_lock.name
}

output "ecr_login_command" {
  description = "Authenticate Docker with ECR"
  value       = "aws ecr get-login-password --region ${var.aws_region} | docker login --username AWS --password-stdin ${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com"
}

output "db_secret_arn" {
  description = "Secrets Manager ARN for DB credentials"
  value       = aws_secretsmanager_secret.db_credentials.arn
  sensitive   = true
}
