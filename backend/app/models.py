import uuid
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import String, ForeignKey, DateTime, Date, Numeric, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class TFI(Base):
    __tablename__ = "tfi"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    funds: Mapped[list["Fund"]] = relationship(back_populates="tfi", cascade="all, delete-orphan")
    subfunds: Mapped[list["Subfund"]] = relationship(back_populates="tfi", cascade="all, delete-orphan")


class Fund(Base):
    """Fundusz parasolowy / umbrella (poziom pomiędzy TFI a subfunduszami)."""
    __tablename__ = "funds"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    tfi_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tfi.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    tfi: Mapped["TFI | None"] = relationship(back_populates="funds")
    subfunds: Mapped[list["Subfund"]] = relationship(back_populates="fund")


class Subfund(Base):
    """Subfundusz (liść hierarchii: TFI → Fundusz → Subfundusz)."""
    __tablename__ = "subfunds"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    tfi_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tfi.id", ondelete="SET NULL"), nullable=True)
    fund_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("funds.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    ticker: Mapped[str | None] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    tfi: Mapped["TFI | None"] = relationship(back_populates="subfunds")
    fund: Mapped["Fund | None"] = relationship(back_populates="subfunds")


class PortfolioComposition(Base):
    """
    Tabela przechowująca znormalizowane pozycje portfeli wczytane przez moduł 'Dane'.
    Każdy rekord odpowiada jednej pozycji z przetworzonego pliku.
    """
    __tablename__ = "portfolio_composition"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_filename: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    parsed_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    snapshot_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Identyfikacja funduszu
    umbrella_name: Mapped[str | None] = mapped_column(String(500))   # Nazwa funduszu
    subfund_name: Mapped[str | None] = mapped_column(String(500))    # Nazwa subfunduszu
    fund_type: Mapped[str | None] = mapped_column(String(50))        # Typ funduszu (SFIO, FIO…)
    fund_id: Mapped[str | None] = mapped_column(String(50))          # Identyfikator funduszu (KNF/IZFIA)
    izfia_id: Mapped[str | None] = mapped_column(String(20))         # Kod IZFiA (np. PZU001, ALR010)

    # Pozycja
    company_name: Mapped[str] = mapped_column(String(500), nullable=False)  # Emitent
    country: Mapped[str | None] = mapped_column(String(100))                # Kraj emitenta
    isin: Mapped[str | None] = mapped_column(String(20))
    asset_type: Mapped[str | None] = mapped_column(String(200))             # Typ instrumentu
    shares: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))          # Ilość
    currency_fund: Mapped[str] = mapped_column(String(20), default="PLN")   # Waluta wyceny funduszu
    currency_instrument: Mapped[str] = mapped_column(String(20), default="PLN")  # Waluta instrumentu
    value: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))           # Wartość w PLN
    weight_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))      # Udział %

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class User(Base):
    """Lokalny użytkownik — email + zahashowane hasło."""
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Article(Base):
    """Artykuł w dziale Aktualności."""
    __tablename__ = "articles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Which event types to track
    track_new: Mapped[bool] = mapped_column(Boolean, default=True)
    track_closed: Mapped[bool] = mapped_column(Boolean, default=True)
    track_increases: Mapped[bool] = mapped_column(Boolean, default=True)
    track_decreases: Mapped[bool] = mapped_column(Boolean, default=True)
    # Thresholds for increase/decrease (OR logic: trigger if EITHER condition met)
    min_weight_pp: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("2.0"))
    min_rel_pct: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("20.0"))
    # Optional: apply only to a specific fund (null = all funds)
    fund_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subfunds.id", ondelete="CASCADE"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
