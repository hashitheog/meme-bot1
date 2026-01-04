from sqlalchemy.ext.asyncio import AsyncAttrs, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Float, Integer, JSON, Boolean, DateTime
from datetime import datetime
from app.config import settings

# For MVP, we use SQLite. In production, switch connection string to PostgreSQL.
# SQLite async URL needs 4 slashes for absolute path or 3 for relative.
# Using a local file 'meme_bot.db'
DATABASE_URL = "sqlite+aiosqlite:///meme_bot.db"

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(AsyncAttrs, DeclarativeBase):
    pass

class Token(Base):
    __tablename__ = "tokens"

    address: Mapped[str] = mapped_column(String, primary_key=True)
    chain: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    symbol: Mapped[str] = mapped_column(String)
    
    # Metadata at discovery
    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    launch_age_minutes: Mapped[int] = mapped_column(Integer)
    
    # Analysis results
    final_score: Mapped[float] = mapped_column(Float, nullable=True)
    ai_risk_score: Mapped[float] = mapped_column(Float, nullable=True)
    is_alerted: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Storing full analysis report as JSON for debugging/audit
    analysis_data: Mapped[dict] = mapped_column(JSON, nullable=True)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
