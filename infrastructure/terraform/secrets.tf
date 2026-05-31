resource "random_password" "db" {
  length  = 32
  special = false # No URL-encoding issues in DATABASE_URL
}

resource "random_password" "secret_key" {
  length  = 64
  special = false
}

# ── DB credentials ────────────────────────────────────────────────────────────

resource "aws_secretsmanager_secret" "db_credentials" {
  name                    = "${local.prefix}/db-credentials"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    username     = var.db_username
    password     = random_password.db.result
    host         = aws_db_instance.main.address
    port         = 5432
    dbname       = var.db_name
    DATABASE_URL = "postgresql+asyncpg://${var.db_username}:${random_password.db.result}@${aws_db_instance.main.address}:5432/${var.db_name}"
  })
}

# ── Application secrets ───────────────────────────────────────────────────────

resource "aws_secretsmanager_secret" "app" {
  name                    = "${local.prefix}/app-secrets"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id
  secret_string = jsonencode({
    SECRET_KEY                = random_password.secret_key.result
    SUPABASE_URL              = var.supabase_url
    SUPABASE_SERVICE_ROLE_KEY = var.supabase_service_role_key
    OPENAI_API_KEY            = var.openai_api_key
  })
}
