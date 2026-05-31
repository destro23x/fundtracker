"""
Endpoints dla Aktualności (artykuły).

GET    /api/v1/articles/       – lista artykułów (publiczne, limit=20)
POST   /api/v1/articles/       – utwórz artykuł (wymaga auth)
GET    /api/v1/articles/{id}   – pobierz artykuł (publiczne)
DELETE /api/v1/articles/{id}   – usuń artykuł (wymaga auth)
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Article, User
from app.schemas import ArticleCreate, ArticleOut
from app.dependencies import get_current_user_id

router = APIRouter(prefix="/api/v1/articles", tags=["articles"])


@router.get("/", response_model=list[ArticleOut])
async def list_articles(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Article).order_by(Article.published_at.desc()).limit(limit)
    )
    return result.scalars().all()


@router.post("/", response_model=ArticleOut, status_code=201)
async def create_article(
    body: ArticleCreate,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    # Pobierz email autora jeśli dostępny
    author: str | None = None
    if user_id != "dev-user":
        user_result = await db.execute(
            select(User).where(User.id == uuid.UUID(user_id))
        )
        user = user_result.scalar_one_or_none()
        if user:
            author = user.email

    article = Article(
        title=body.title,
        content=body.content,
        author=author,
        published_at=body.published_at or datetime.utcnow(),
    )
    db.add(article)
    await db.commit()
    await db.refresh(article)
    return article


@router.get("/{article_id}", response_model=ArticleOut)
async def get_article(
    article_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Artykuł nie istnieje")
    return article


@router.delete("/{article_id}", status_code=204)
async def delete_article(
    article_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Artykuł nie istnieje")
    await db.delete(article)
    await db.commit()
