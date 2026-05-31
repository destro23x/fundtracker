# Fund Portfolio Tracker

Professional tool for tracking investment fund portfolio composition changes over time.

## Features

- Upload Excel files with fund portfolio data
- AI-powered parser for flexible Excel format support
- Track portfolio changes across dates
- Alerts: "Fund X increased NVIDIA position by 40%"
- Multi-user with Supabase Auth
- Interactive charts and comparison views
- Fund history timeline

## Stack

| Layer     | Technology                        |
|-----------|-----------------------------------|
| Frontend  | Next.js 14, TypeScript, Tailwind, shadcn/ui, Recharts |
| Backend   | FastAPI, SQLAlchemy, Alembic      |
| Database  | PostgreSQL (via Supabase)         |
| Auth      | Supabase Auth                     |
| AI Parser | OpenAI GPT-4o                     |
| Storage   | Supabase Storage (Excel files)    |

## Project Structure

```
fund-portfolio-tracker/
├── frontend/        # Next.js application
├── backend/         # FastAPI application
├── supabase/        # DB migrations
└── docker-compose.yml
```

## Uruchomienie aplikacji

### Wymagania

- Docker & Docker Compose (zalecane)
- lub: Node.js 20+ i Python 3.11+ (uruchomienie lokalne)

---

### Opcja A — Docker Compose (najszybciej)

```bash
# 1. Skopiuj plik konfiguracyjny i uzupełnij dane
cp .env.example .env

# 2. Zbuduj i uruchom
docker-compose up --build
```

Aplikacja dostępna pod:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/docs (Swagger UI)
- PostgreSQL: localhost:5432

Zatrzymanie:

```bash
docker-compose down        # zatrzymaj kontenery
docker-compose down -v     # zatrzymaj i usuń woluminy (baza danych)
```

---

### Opcja B — Uruchomienie lokalne

#### Krok 1 — Konfiguracja

```bash
cp .env.example .env
# Uzupełnij .env:
#   DATABASE_URL       — np. postgresql+asyncpg://user:pass@localhost/fund_tracker
#   SUPABASE_URL       — opcjonalne (jeśli używasz Supabase Auth)
#   SUPABASE_KEY       — opcjonalne
#   OPENAI_API_KEY     — wymagane do AI parsera
#   SECRET_KEY         — dowolny losowy ciąg znaków
```

#### Krok 2 — Backend (FastAPI)

```bash
cd backend

# Utwórz i aktywuj środowisko wirtualne
python3 -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate         # Windows

# Zainstaluj zależności
pip install -r requirements.txt

# Uruchom migracje bazy danych
alembic upgrade head

# Uruchom serwer API
uvicorn app.main:app --reload --port 8000
```

API dostępne pod: http://localhost:8000/docs

#### Krok 3 — Frontend (Next.js)

```bash
cd frontend

npm install
npm run dev
```

Frontend dostępny pod: http://localhost:3000

---

### Zmienne środowiskowe

| Zmienna | Opis | Wymagana |
|---|---|---|
| `DATABASE_URL` | Connection string PostgreSQL | tak |
| `SECRET_KEY` | Klucz JWT do sesji | tak |
| `OPENAI_API_KEY` | Klucz OpenAI (AI parser) | tak |
| `SUPABASE_URL` | URL projektu Supabase | opcjonalna |
| `SUPABASE_KEY` | Anon key Supabase | opcjonalna |
| `NEXT_PUBLIC_API_URL` | URL backendu (domyślnie `http://localhost:8000`) | opcjonalna |

> Bez `SUPABASE_URL` aplikacja działa w trybie dev (auth wyłączony, wszyscy użytkownicy mają dostęp).

---

## Quick Start

### Prerequisites
- Node.js 20+
- Python 3.11+
- Docker & Docker Compose
- Supabase account (or local Supabase)

### 1. Clone & configure
```bash
cp .env.example .env
# Fill in your Supabase credentials and OpenAI API key
```

### 2. Start with Docker
```bash
docker-compose up --build
```

Or run locally:

### 3a. Backend
```bash
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### 3b. Frontend
```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## How It Works

1. **Create a Fund** — give it a name (e.g. "PKO Akcji Plus")
2. **Upload Excel** — upload the monthly portfolio report
3. **AI parsing** — the parser auto-detects column layouts (company, ticker, ISIN, shares, value, weight%)
4. **Compare** — select two dates and see what changed
5. **Alerts** — automatic notifications when positions change significantly

## Excel Format Support

The AI parser handles most common formats including:
- Standard Polish TFI reports
- ING, PKO, Pekao fund reports
- Any tabular format with company + position data


Pokazywanie 10 największych pozycji dla funduszu
Alokacja sektorowa
Ekspozycja geograficzna
Liczba pozycji
Obrót portfela policz jak był obrót portfela
Jak zmianił się skład funduszu w ciągu ostatniego roku.

terraforma uaktualnij


Czy baza danych jest znormalizowana?

Tak, portfolio_composition jest celowo zdenormalizowane. Konkretne naruszenia:

1NF — OK (atomowe wartości, brak powtarzających się grup)

2NF — naruszenie — kolumny zależą tylko od części klucza:

umbrella_name, subfund_name, fund_type, izfia_id — opisują fundusz, nie pozycję
source_filename, parsed_filename — opisują upload, nie pozycję
3NF — naruszenie — zależności przechodnie:

subfund_name → umbrella_name (nazwa subfunduszu determinuje TFI)
isin → company_name, isin → country (ISIN determinuje emitenta i kraj)
source_filename → snapshot_date (plik determinuje datę)

Znormalizowana wersja wyglądałaby tak:

tfi            (id, name)
subfunds       (id, tfi_id FK, name, fund_type, izfia_id)  ← już istnieje
instruments    (isin PK, company_name, country)
uploads        (id, user_id, source_filename, snapshot_date)
portfolio_positions (upload_id FK, subfund_id FK, isin FK,
                     asset_type, shares, value, weight_pct,
                     currency_fund, currency_instrument)


Dlaczego zdenormalizowanie jest tu OK:

Dane są read-heavy, write-once — uploady są rzadkie, odczytów jest dużo
Brak aktualizacji częściowych — cały snapshot jest zastępowany naraz
Upraszcza parsery (każdy parser pisze jeden flat dict per pozycja)
11 700 wierszy — żaden problem wydajnościowy
company_name w danych funduszowych bywa niespójny między datami (ten sam ISIN, różna nazwa) — denormalizacja to zachowuje

Jedyna realna wada: subfund_name jako string zamiast FK do subfunds.id — stąd potrzeba mapowania subfund_name → uuid w każdym endpoincie.


a gdy będzie wierszy 10 milionów w portfolio_composition to czy nadal nie będzie to problem wydajnościowy ?

10 milionów wierszy to granica, gdzie zaczyna mieć znaczenie — ale PostgreSQL da radę jeśli masz właściwe indeksy.

Obecny stan — brak indeksów na kluczowych kolumnach:
Masz 3 indeksy na osobne kolumny, ale brakuje kluczowego composite index. Na 10M wierszach to będzie ból, ale z większym problemem — całe przetwarzanie jest w Pythonie.

Aktualne query pattern vs 10M wierszy:

# movers, rankings, alerts — WSZYSTKIE robią to:
all_rows = SELECT * FROM portfolio_composition WHERE user_id = X
# → ładuje do Pythona np. 500 000 wierszy dla jednego usera
# → grupowanie, diffowanie, agregacje — w pamięci RAM aplikacji

Gdzie to padnie:

Zapytanie	Teraz (11k)	10M wierszy
WHERE user_id = X	~1ms	~200ms (index scan, ale duże I/O)
Python groupby + diff	~5ms	~30s (OOM lub timeout)
ILIKE company_name	~2ms	~10s (seq scan na user's rows)
Pairwise Jaccard (45×45)	~50ms	nieprzewidywalny

Brakuje composite index:

-- Większość zapytań filtruje user + date + subfund
CREATE INDEX idx_pc_user_subfund_date 
ON portfolio_composition (user_id, subfund_name, snapshot_date);

-- Wyszukiwanie tekstowe
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_pc_company_trgm 
ON portfolio_composition USING GIN (company_name gin_trgm_ops);

Prawdziwe rozwiązanie na 10M — przenieść logikę do SQL:

Zamiast ładować wszystko do Pythona, np. dla /activity:

-- Zamiast obecnego SELECT * → Python groupby
SELECT subfund_name,
       COUNT(DISTINCT snapshot_date) AS snap_count,
       MAX(snapshot_date)            AS latest_date
FROM portfolio_composition
WHERE user_id = 'dev-user'
GROUP BY subfund_name;
-- → 1 zapytanie, 45 wierszy zwrotnych zamiast 11 000

Ocena realistyczna:

< 1M wierszy — obecne podejście działa bez zmian
1–10M wierszy — potrzeba composite index + agregacje w SQL
> 10M wierszy — rozważyć partycjonowanie tabeli po (user_id, snapshot_date) lub materialized views dla często czytanych agregatów
Przy Twoim obecnym use case (jedna instancja, kilka TFI kwartalnie) raczej nigdy nie dojdziesz do 10M — to byłoby ~850 uploadów tej samej skali.