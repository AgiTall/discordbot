"""SQLAlchemy models for Gangs (Банды / Отряды)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, String, Integer, Float, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

class Gang(Base):
    __tablename__ = "gangs"

    id: Mapped[int] = mapped_column(primary_key=True)
    guild_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    balance: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Store camp upgrades or stats in JSONB to allow dynamic fields
    # Example: {"camp_fire": 1, "dog": 0, "fast_travel": 1}
    camp_upgrades: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    members: Mapped[list["GangMember"]] = relationship(
        "GangMember",
        back_populates="gang",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Gang {self.name} (ID: {self.id})>"


class GangMember(Base):
    __tablename__ = "gang_members"

    id: Mapped[int] = mapped_column(primary_key=True)
    gang_id: Mapped[int] = mapped_column(ForeignKey("gangs.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    guild_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    
    # "leader" or "member"
    role: Mapped[str] = mapped_column(String, default="member")
    
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    gang: Mapped["Gang"] = relationship("Gang", back_populates="members")

    def __repr__(self) -> str:
        return f"<GangMember User: {self.user_id} Role: {self.role} Gang: {self.gang_id}>"
