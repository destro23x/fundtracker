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

Funkcjonalności:
TFI mają pokazywać z listy rozwijalnej jakie mają Fundusze
Fundusze mają pokazywać jakie podfundusze mają

Pokazywanie 10 największych pozycji dla funduszu
Alokacja sektorowa
Ekspozycja geograficzna
Liczba pozycji
Obrót portfela


Wydzielic parsery aby do jakiegos wspolnego formatu sprowadzały wszystkie raporty i dopiero wtedy raport mozna byłoby wczytać do systemu. Uzytkownik moglby przejrze przegenerowany raport i zaakceptować do 

Wspólny format, zaakceptowanie raportu


Nazwa funduszu
Nazwa subsunduszu
Identyfikator funduszu lub subfunduszu
Typ Funduszu
Nazwa emitenta
Kraj emitenta
Kod ISIN instrumentu 
Typ instrumentu (Akcje, instrumenty pochodne)
Ilość instrumnetów w portfelu
Waluta instumentu
Waluta wyceny instumentu
Wartość instrumentu w walucie wyceny
Procentowy udział w wartości ogółem

# fundtracker
