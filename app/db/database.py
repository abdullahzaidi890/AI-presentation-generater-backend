import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Boolean, DateTime, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from ..config import get_settings


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Presentation(Base):
    __tablename__ = "presentations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(200))
    content_json: Mapped[str] = mapped_column(Text)
    settings_json: Mapped[str] = mapped_column(Text, default="{}")
    theme: Mapped[str] = mapped_column(String(50), default="minimal_academic")
    provider: Mapped[str] = mapped_column(String(50), default="")
    model: Mapped[str] = mapped_column(String(100), default="")
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    def to_dict(self, with_content: bool = True) -> dict:
        content = json.loads(self.content_json)
        d = {
            "id": self.id,
            "title": self.title,
            "theme": self.theme,
            "provider": self.provider,
            "model": self.model,
            "fallback_used": self.fallback_used,
            "slide_count": len(content.get("slides", [])),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        if with_content:
            d["content"] = content
            d["settings"] = json.loads(self.settings_json or "{}")
        else:
            slides = content.get("slides", [])
            d["cover"] = slides[0] if slides else None  # used for dashboard thumbnails
        return d


_engine = None
_SessionLocal = None


def init_db(url: str | None = None):
    """Create engine + tables. Auto-creates the sqlite folder/file on first run."""
    global _engine, _SessionLocal
    url = url or get_settings().database_url
    if url.startswith("sqlite:///") and ":memory:" not in url:
        Path(url.replace("sqlite:///", "", 1)).parent.mkdir(parents=True, exist_ok=True)
    kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
    _engine = create_engine(url, **kwargs)
    Base.metadata.create_all(_engine)
    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def get_db():
    if _SessionLocal is None:
        init_db()
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()
