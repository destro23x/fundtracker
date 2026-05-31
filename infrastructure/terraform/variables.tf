# ── AWS ───────────────────────────────────────────────────────────────────────

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-west-1"
}

variable "project_name" {
  description = "Project name prefix for all resources"
  type        = string
  default     = "fund-tracker"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "prod"
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

# ── Network ───────────────────────────────────────────────────────────────────

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

# ── Database ──────────────────────────────────────────────────────────────────

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t4g.micro"
}

variable "db_name" {
  description = "PostgreSQL database name"
  type        = string
  default     = "fund_tracker"
}

variable "db_username" {
  description = "PostgreSQL master username"
  type        = string
  default     = "fundtracker"
}

variable "db_multi_az" {
  description = "Enable RDS Multi-AZ (recommended for prod)"
  type        = bool
  default     = false
}

# ── ECS ───────────────────────────────────────────────────────────────────────

variable "backend_cpu" {
  description = "Backend task CPU units (256 / 512 / 1024 / 2048 / 4096)"
  type        = number
  default     = 512
}

variable "backend_memory" {
  description = "Backend task memory (MB)"
  type        = number
  default     = 1024
}

variable "frontend_cpu" {
  description = "Frontend task CPU units"
  type        = number
  default     = 256
}

variable "frontend_memory" {
  description = "Frontend task memory (MB)"
  type        = number
  default     = 512
}

variable "backend_desired_count" {
  description = "Desired number of backend tasks"
  type        = number
  default     = 1
}

variable "frontend_desired_count" {
  description = "Desired number of frontend tasks"
  type        = number
  default     = 1
}

# ── Application ───────────────────────────────────────────────────────────────

variable "api_url" {
  description = <<-EOT
    Base URL used by the frontend to reach the API.
    Defaults to the ALB URL. Override with a custom domain once DNS is set up,
    e.g. "https://api.yourdomain.com". Also rebuild the frontend image with
    NEXT_PUBLIC_API_URL set to this value.
  EOT
  type        = string
  default     = ""
}

variable "supabase_url" {
  description = "Supabase project URL (e.g. https://xxx.supabase.co)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "supabase_anon_key" {
  description = "Supabase anon/public key (used by frontend)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "supabase_service_role_key" {
  description = "Supabase service role key (backend only)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "openai_api_key" {
  description = "OpenAI API key (optional — used for AI-based file parsing)"
  type        = string
  default     = ""
  sensitive   = true
}
