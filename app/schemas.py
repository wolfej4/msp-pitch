import re
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .config import normalize_url


# ---------- Prospect ----------
class ProspectBase(BaseModel):
    company_name: str
    contact_name: str = ""
    email: str = ""
    phone: str = ""
    industry: str = ""
    users: Optional[int] = Field(None, ge=0)
    endpoints: Optional[int] = Field(None, ge=0)
    notes: str = ""


class ProspectCreate(ProspectBase):
    pass


class ProspectUpdate(BaseModel):
    company_name: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    industry: Optional[str] = None
    users: Optional[int] = Field(None, ge=0)
    endpoints: Optional[int] = Field(None, ge=0)
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


# ---------- Category ----------
class CategoryCreate(BaseModel):
    name: str


class CategoryUpdate(BaseModel):
    name: str


class CategoryOut(BaseModel):
    id: int
    name: str
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


# ---------- App settings ----------
class AppSettingsUpdate(BaseModel):
    company_name: Optional[str] = Field(None, min_length=1)
    company_tagline: Optional[str] = None
    company_email: Optional[str] = None
    company_phone: Optional[str] = None
    company_website: Optional[str] = None
    llm_provider: Optional[str] = None
    anthropic_model: Optional[str] = Field(None, min_length=1)
    gemini_model: Optional[str] = Field(None, min_length=1)
    ollama_base_url: Optional[str] = None
    ollama_model: Optional[str] = Field(None, min_length=1)
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = Field(None, ge=1, le=65535)
    smtp_user: Optional[str] = None
    smtp_from: Optional[str] = None
    smtp_tls: Optional[bool] = None
    # Write-only secrets; "" removes the saved value (falling back to the env var).
    smtp_pass: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None


    @field_validator("llm_provider")
    @classmethod
    def _provider(cls, v):
        if v is None:
            return v
        v = v.strip().lower()
        if v not in ("ollama", "anthropic", "gemini"):
            raise ValueError("must be 'ollama', 'anthropic' or 'gemini'")
        return v

    @field_validator("ollama_base_url")
    @classmethod
    def _ollama_url(cls, v):
        if v is None:
            return v
        v = normalize_url(v)
        if not re.match(r"^https?://\S+$", v):
            raise ValueError("must be a URL like http://192.168.1.50:11434")
        return v


class LLMTestRequest(BaseModel):
    provider: Literal["ollama", "anthropic", "gemini"]
    api_key: str = ""  # an unsaved key typed into the form; blank uses the saved one
    ollama_base_url: str = ""
    model: str = ""
