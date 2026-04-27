from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .database import Base


class Prospect(Base):
    __tablename__ = "prospects"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String, nullable=False)
    contact_name = Column(String, default="")
    email = Column(String, default="")
    phone = Column(String, default="")
    industry = Column(String, default="")
    headcount = Column(String, default="")
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship("Message", back_populates="prospect", cascade="all, delete-orphan")
    items = relationship("ProposalItem", back_populates="prospect", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    prospect_id = Column(Integer, ForeignKey("prospects.id", ondelete="CASCADE"))
    role = Column(String, nullable=False)  # user | assistant | system
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    prospect = relationship("Prospect", back_populates="messages")


class Service(Base):
    """Master catalog of services this MSP offers."""

    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    category = Column(String, default="General")
    description = Column(Text, default="")
    default_price = Column(Float, default=0.0)
    price_unit = Column(String, default="flat")  # flat | per_user | per_device | per_endpoint
    billing_cycle = Column(String, default="monthly")  # monthly | annual | one_time
    is_active = Column(Integer, default=1)


class Category(Base):
    """User-managed list of service categories. Service.category stores the name as a string."""

    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)


class ProposalItem(Base):
    """A line item attached to a specific prospect's proposal."""

    __tablename__ = "proposal_items"

    id = Column(Integer, primary_key=True, index=True)
    prospect_id = Column(Integer, ForeignKey("prospects.id", ondelete="CASCADE"))
    service_id = Column(Integer, ForeignKey("services.id", ondelete="SET NULL"), nullable=True)
    name = Column(String, nullable=False)
    description = Column(Text, default="")
    quantity = Column(Float, default=1.0)
    price = Column(Float, default=0.0)
    price_unit = Column(String, default="flat")
    billing_cycle = Column(String, default="monthly")
    notes = Column(Text, default="")

    prospect = relationship("Prospect", back_populates="items")
