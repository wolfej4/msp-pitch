from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


# ---------- Prospect ----------
class ProspectBase(BaseModel):
    company_name: str
    contact_name: str = ""
    email: str = ""
    phone: str = ""
    industry: str = ""
    headcount: str = ""
    notes: str = ""


class ProspectCreate(ProspectBase):
    pass


class ProspectUpdate(BaseModel):
    company_name: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    industry: Optional[str] = None
    headcount: Optional[str] = None
    notes: Optional[str] = None


class ProspectOut(ProspectBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------- Service ----------
class ServiceBase(BaseModel):
    name: str
    category: str = "General"
    description: str = ""
    default_price: float = 0.0
    price_unit: str = "flat"
    billing_cycle: str = "monthly"
    is_active: int = 1


class ServiceCreate(ServiceBase):
    pass


class ServiceUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    default_price: Optional[float] = None
    price_unit: Optional[str] = None
    billing_cycle: Optional[str] = None
    is_active: Optional[int] = None


class ServiceOut(ServiceBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


# ---------- Proposal Items ----------
class ProposalItemBase(BaseModel):
    name: str
    description: str = ""
    quantity: float = 1.0
    price: float = 0.0
    price_unit: str = "flat"
    billing_cycle: str = "monthly"
    notes: str = ""
    service_id: Optional[int] = None


class ProposalItemCreate(ProposalItemBase):
    pass


class ProposalItemUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    quantity: Optional[float] = None
    price: Optional[float] = None
    price_unit: Optional[str] = None
    billing_cycle: Optional[str] = None
    notes: Optional[str] = None


class ProposalItemOut(ProposalItemBase):
    id: int
    prospect_id: int
    model_config = ConfigDict(from_attributes=True)


# ---------- Chat ----------
class ChatMessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ChatRequest(BaseModel):
    message: str


# ---------- Email ----------
class EmailRequest(BaseModel):
    to: str
    subject: Optional[str] = None
    body: Optional[str] = None
