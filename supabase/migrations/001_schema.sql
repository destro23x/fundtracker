-- ============================================================
-- Fund Portfolio Tracker — pełny schemat bazy danych
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- TFI (Towarzystwo Funduszy Inwestycyjnych)
-- ============================================================
CREATE TABLE IF NOT EXISTS tfi (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    VARCHAR(255) NOT NULL,
    name       VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_tfi_user_id ON tfi(user_id);

-- ============================================================
-- Funds (fundusze parasolowe / umbrella level)
-- ============================================================
CREATE TABLE IF NOT EXISTS funds (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    VARCHAR(255) NOT NULL,
    name       VARCHAR(255) NOT NULL,
    tfi_id     UUID REFERENCES tfi(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_funds_user_id ON funds(user_id);
CREATE INDEX IF NOT EXISTS idx_funds_tfi_id  ON funds(tfi_id);

-- ============================================================
-- Subfunds (subfundusze / leaf level)
-- ============================================================
CREATE TABLE IF NOT EXISTS subfunds (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     VARCHAR(255) NOT NULL,
    tfi_id      UUID REFERENCES tfi(id)   ON DELETE SET NULL,
    fund_id     UUID REFERENCES funds(id) ON DELETE SET NULL,
    name        VARCHAR(255) NOT NULL,
    ticker      VARCHAR(50),
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_subfunds_user_id ON subfunds(user_id);
CREATE INDEX IF NOT EXISTS idx_subfunds_fund_id ON subfunds(fund_id);

-- ============================================================
-- Portfolio Snapshots
-- ============================================================
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fund_id         UUID NOT NULL REFERENCES subfunds(id) ON DELETE CASCADE,
    snapshot_date   DATE NOT NULL,
    total_value     NUMERIC(20, 2),
    currency        VARCHAR(10) NOT NULL DEFAULT 'PLN',
    upload_filename VARCHAR(500),
    raw_data        JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (fund_id, snapshot_date)
);
CREATE INDEX IF NOT EXISTS idx_snapshots_fund_date ON portfolio_snapshots(fund_id, snapshot_date DESC);

-- ============================================================
-- Portfolio Positions (legacy — pozycje powiązane ze snapshotami)
-- ============================================================
CREATE TABLE IF NOT EXISTS portfolio_positions (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_id  UUID NOT NULL REFERENCES portfolio_snapshots(id) ON DELETE CASCADE,
    company_name VARCHAR(500) NOT NULL,
    ticker       VARCHAR(255),
    isin         VARCHAR(20),
    shares       NUMERIC(20, 4),
    value        NUMERIC(20, 2),
    weight_pct   NUMERIC(10, 4),
    currency     VARCHAR(50)  NOT NULL DEFAULT 'PLN',
    asset_type   VARCHAR(200),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_positions_snapshot ON portfolio_positions(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_positions_isin     ON portfolio_positions(isin) WHERE isin IS NOT NULL;

-- ============================================================
-- Alerts
-- ============================================================
CREATE TABLE IF NOT EXISTS alerts (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fund_id          UUID NOT NULL REFERENCES subfunds(id) ON DELETE CASCADE,
    user_id          VARCHAR(255) NOT NULL,
    alert_type       VARCHAR(100) NOT NULL,
    company_name     VARCHAR(500),
    ticker           VARCHAR(255),
    change_pct       NUMERIC(10, 4),
    old_weight       NUMERIC(10, 4),
    new_weight       NUMERIC(10, 4),
    old_value        NUMERIC(20, 2),
    new_value        NUMERIC(20, 2),
    old_shares       NUMERIC(20, 4),
    new_shares       NUMERIC(20, 4),
    message          TEXT NOT NULL,
    is_read          BOOLEAN NOT NULL DEFAULT FALSE,
    snapshot_from_id UUID REFERENCES portfolio_snapshots(id),
    snapshot_to_id   UUID REFERENCES portfolio_snapshots(id),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_alerts_user_id ON alerts(user_id, is_read, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_fund_id ON alerts(fund_id);

-- ============================================================
-- Alert Rules
-- ============================================================
CREATE TABLE IF NOT EXISTS alert_rules (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         VARCHAR(255) NOT NULL,
    name            VARCHAR(255) NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    track_new       BOOLEAN NOT NULL DEFAULT TRUE,
    track_closed    BOOLEAN NOT NULL DEFAULT TRUE,
    track_increases BOOLEAN NOT NULL DEFAULT TRUE,
    track_decreases BOOLEAN NOT NULL DEFAULT TRUE,
    min_weight_pp   NUMERIC(10, 4) NOT NULL DEFAULT 2.0,
    min_rel_pct     NUMERIC(10, 4) NOT NULL DEFAULT 20.0,
    fund_id         UUID REFERENCES subfunds(id) ON DELETE CASCADE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_alert_rules_user_id ON alert_rules(user_id);

-- ============================================================
-- Portfolio Composition (znormalizowane pozycje portfeli — moduł Dane)
-- ============================================================
CREATE TABLE IF NOT EXISTS portfolio_composition (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             VARCHAR(255) NOT NULL,
    source_filename     VARCHAR(500) NOT NULL,
    parsed_filename     VARCHAR(500) NOT NULL,
    snapshot_date       DATE,

    -- Identyfikacja funduszu
    umbrella_name       VARCHAR(500),
    subfund_name        VARCHAR(500),
    fund_type           VARCHAR(50),
    fund_id             VARCHAR(50),   -- ISIN funduszu (np. PLFIO000141)
    izfia_id            VARCHAR(20),   -- Kod IZFiA    (np. PZU001, ALR010, AXA002)

    -- Pozycja
    company_name        VARCHAR(500) NOT NULL,
    country             VARCHAR(100),
    isin                VARCHAR(20),
    asset_type          VARCHAR(200),
    shares              NUMERIC(20, 4),
    currency_fund       VARCHAR(20)  NOT NULL DEFAULT 'PLN',
    currency_instrument VARCHAR(20)  NOT NULL DEFAULT 'PLN',
    value               NUMERIC(20, 2),
    weight_pct          NUMERIC(10, 4),

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_portfolio_composition_user_id   ON portfolio_composition(user_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_composition_source    ON portfolio_composition(source_filename);
CREATE INDEX IF NOT EXISTS idx_portfolio_composition_date      ON portfolio_composition(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_pc_user_subfund_date            ON portfolio_composition(user_id, subfund_name, snapshot_date DESC);

-- ============================================================
-- Users (lokalna autoryzacja — email + bcrypt hasło)
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- ============================================================
-- Domyślny admin
--   email:    admin@fundtracker.local
--   hasło:    admin123
-- ============================================================
INSERT INTO users (id, email, hashed_password)
VALUES (
    'a0000000-0000-0000-0000-000000000001',
    'admin@fundtracker.local',
    '$2b$12$UPJUxuMPEJcgTI8PwGa1buctbCzQI7OK0q6wtp5vXl35imkzy.Irm'
)
ON CONFLICT (email) DO NOTHING;

-- ============================================================
-- Articles (Aktualności)
-- ============================================================
CREATE TABLE IF NOT EXISTS articles (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title        VARCHAR(500) NOT NULL,
    content      TEXT NOT NULL,
    author       VARCHAR(255),
    published_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at DESC);
