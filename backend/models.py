from __future__ import annotations

from datetime import datetime
from sqlalchemy import (
    String,
    Integer,
    DateTime,
    Boolean,
    ForeignKey,
    UniqueConstraint,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

class User(Base):
    """
    Users include:
      - admin
      - parent
    (Workers are out of scope for Sprint 1 prototype, but can be added later.)
    """
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)  # "admin" | "parent"
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # Parent-owned campers
    parent_links: Mapped[list["ParentCamper"]] = relationship(
        back_populates="parent",
        cascade="all, delete-orphan",
        foreign_keys="ParentCamper.parent_user_id",
    )

    tokens: Mapped[list["SessionToken"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

class SessionToken(Base):
    __tablename__ = "session_tokens"
    __table_args__ = (UniqueConstraint("token", name="uq_session_token"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(String(128), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped["User"] = relationship(back_populates="tokens")

class Camper(Base):
    __tablename__ = "campers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    first_name: Mapped[str] = mapped_column(String(120), nullable=False)
    last_name: Mapped[str] = mapped_column(String(120), nullable=False)
    date_of_birth: Mapped[str] = mapped_column(String(20), nullable=True)  # simple string for prototype
    emergency_info: Mapped[str] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    parent_links: Mapped[list["ParentCamper"]] = relationship(back_populates="camper", cascade="all, delete-orphan")
    enrollments: Mapped[list["Enrollment"]] = relationship(back_populates="camper", cascade="all, delete-orphan")
    group_memberships: Mapped[list["GroupMembership"]] = relationship(back_populates="camper", cascade="all, delete-orphan")

class ParentCamper(Base):
    __tablename__ = "parent_campers"
    __table_args__ = (UniqueConstraint("parent_user_id", "camper_id", name="uq_parent_camper"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    camper_id: Mapped[int] = mapped_column(ForeignKey("campers.id", ondelete="CASCADE"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    parent: Mapped["User"] = relationship(back_populates="parent_links", foreign_keys=[parent_user_id])
    camper: Mapped["Camper"] = relationship(back_populates="parent_links")

class CampYear(Base):
    __tablename__ = "camp_years"
    __table_args__ = (UniqueConstraint("year", name="uq_camp_year"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    enrollments: Mapped[list["Enrollment"]] = relationship(back_populates="camp_year", cascade="all, delete-orphan")
    groups: Mapped[list["Group"]] = relationship(back_populates="camp_year", cascade="all, delete-orphan")

class Enrollment(Base):
    """
    Represents "enrolled children to the camp year" and their status (pending/admitted/withdrawn).
    """
    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("camp_year_id", "camper_id", name="uq_year_camper"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camp_year_id: Mapped[int] = mapped_column(ForeignKey("camp_years.id", ondelete="CASCADE"), nullable=False)
    camper_id: Mapped[int] = mapped_column(ForeignKey("campers.id", ondelete="CASCADE"), nullable=False)

    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")  # pending|admitted|withdrawn
    notes: Mapped[str] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    camp_year: Mapped["CampYear"] = relationship(back_populates="enrollments")
    camper: Mapped["Camper"] = relationship(back_populates="enrollments")

class Group(Base):
    __tablename__ = "groups"
    __table_args__ = (UniqueConstraint("camp_year_id", "name", name="uq_group_year_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camp_year_id: Mapped[int] = mapped_column(ForeignKey("camp_years.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    camp_year: Mapped["CampYear"] = relationship(back_populates="groups")
    memberships: Mapped[list["GroupMembership"]] = relationship(back_populates="group", cascade="all, delete-orphan")
    events: Mapped[list["GroupEvent"]] = relationship(back_populates="group", cascade="all, delete-orphan")

class GroupMembership(Base):
    __tablename__ = "group_memberships"
    __table_args__ = (UniqueConstraint("group_id", "camper_id", name="uq_group_camper"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    camper_id: Mapped[int] = mapped_column(ForeignKey("campers.id", ondelete="CASCADE"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    group: Mapped["Group"] = relationship(back_populates="memberships")
    camper: Mapped["Camper"] = relationship(back_populates="group_memberships")

class GroupEvent(Base):
    """
    Scheduling tasks/activities for a camp group.
    """
    __tablename__ = "group_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    location: Mapped[str] = mapped_column(String(255), nullable=True)

    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    group: Mapped["Group"] = relationship(back_populates="events")
