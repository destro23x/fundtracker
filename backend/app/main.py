from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.database import engine, Base
from app.api import subfunds, alerts, upload_all, positions, alert_rules, stats, rankings, movers, tfi, funds, upload_history, dane, articles
from app.api import auth as auth_router

settings = get_settings()

app = FastAPI(
    title="Fund Portfolio Tracker API",
    version="1.0.0",
    description="Track investment fund portfolio composition changes over time.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(subfunds.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(alert_rules.router, prefix="/api/v1")
app.include_router(stats.router, prefix="/api/v1")
app.include_router(rankings.router, prefix="/api/v1")
app.include_router(movers.router, prefix="/api/v1")
app.include_router(tfi.router)
app.include_router(funds.router)
app.include_router(upload_all.router)
app.include_router(positions.router)
app.include_router(upload_history.router)
app.include_router(dane.router)
app.include_router(articles.router)


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)



@app.get("/health")
async def health():
    return {"status": "ok"}
