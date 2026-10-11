"""LLM client supporting Anthropic (cloud) and Ollama (self-hosted)."""

import json
from typing import AsyncIterator, Dict, List

import httpx
from anthropic import AsyncAnthropic

from .config import Settings
from .runtime_settings import get_settings


def build_system_prompt(prospect: Dict, services: List[Dict], company: Dict) -> str:
    """Compose a system prompt that grounds the model in this MSP's catalog
    and the active prospect's context."""
    catalog_lines = []
    by_cat: Dict[str, List[Dict]] = {}
    for s in services:
        by_cat.setdefault(s["category"], []).append(s)

    for cat in sorted(by_cat.keys()):
        catalog_lines.append(f"\n### {cat}")
        for s in by_cat[cat]:
            unit = s["price_unit"]
            cycle = s["billing_cycle"]
            price_str = f"${s['default_price']:.2f}"
            if unit != "flat":
                price_str += f" {unit.replace('_', ' ')}"
            price_str += f" / {cycle.replace('_', '-')}"
            catalog_lines.append(f"- **{s['name']}** ({price_str}): {s['description']}")

    catalog_block = "\n".join(catalog_lines) if catalog_lines else "(no services configured yet)"

    prospect_block = (
        f"Company: {prospect.get('company_name', 'Unknown')}\n"
        f"Contact: {prospect.get('contact_name') or '—'}\n"
        f"Industry: {prospect.get('industry') or '—'}\n"
        f"Headcount: {prospect.get('headcount') or '—'}\n"
        f"Notes: {prospect.get('notes') or '—'}\n"
    )

    return f"""You are an expert MSP (Managed Service Provider) sales consultant working for **{company['name']}** ({company.get('tagline', '')}).

You have two jobs in this conversation:

1. **Discovery & Sales** — When chatting about a prospect, run a consultative discovery: ask sharp questions about their business size, industry, current IT pain points, security posture, compliance requirements, growth plans, and budget. Then recommend specific services from the catalog below that solve their actual problems. Reference services by their **exact name** so the user can one-click add them to the proposal panel.

2. **Strategic Advisor** — When the user asks for help deciding what services to offer or how to position something (e.g., "what should I offer to a 12-person law firm?" or "should I bundle backup with managed IT?"), give pragmatic, MSP-industry-specific advice grounded in the catalog and the local market context (NW Florida / Crestview area, SMB-focused).

## Style
- Be conversational, direct, and brief. No corporate fluff.
- Ask one or two questions at a time, not five.
- Tie every recommendation to a specific pain point the prospect mentioned.
- Be honest when something isn't a fit; suggest alternatives.
- When suggesting bundles, call them out clearly (e.g., "I'd recommend the Foundation tier plus EDR and DNS Filtering").

## Active Prospect
{prospect_block}

## Service Catalog
{catalog_block}

When you mention a service from the catalog, use its **exact name** in **bold** so the user can quickly add it to the proposal."""


class LLMError(Exception):
    pass


# ---------- Anthropic ----------
async def _stream_anthropic(messages: List[Dict], system: str, cfg: Settings) -> AsyncIterator[str]:
    if not cfg.ANTHROPIC_API_KEY:
        raise LLMError("ANTHROPIC_API_KEY is not set.")
    client = AsyncAnthropic(api_key=cfg.ANTHROPIC_API_KEY)
    async with client.messages.stream(
        model=cfg.ANTHROPIC_MODEL,
        max_tokens=2048,
        system=system,
        messages=messages,
    ) as stream:
        async for text in stream.text_stream:
            yield text


# ---------- Ollama ----------
async def _stream_ollama(messages: List[Dict], system: str, cfg: Settings) -> AsyncIterator[str]:
    payload = {
        "model": cfg.OLLAMA_MODEL,
        "messages": [{"role": "system", "content": system}] + messages,
        "stream": True,
    }
    url = f"{cfg.OLLAMA_BASE_URL.rstrip('/')}/api/chat"
    timeout = httpx.Timeout(120.0, connect=10.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, json=payload) as r:
                if r.status_code != 200:
                    body = await r.aread()
                    raise LLMError(f"Ollama error {r.status_code}: {body.decode(errors='ignore')}")
                async for line in r.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    msg = chunk.get("message") or {}
                    if (content := msg.get("content")):
                        yield content
                    if chunk.get("done"):
                        return
    except httpx.HTTPError as e:
        raise LLMError(f"Could not reach Ollama at {url}: {e}") from e


# ---------- Model discovery ----------
async def list_ollama_models(base_url: str) -> List[str]:
    url = f"{base_url.rstrip('/')}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            r = await client.get(url)
    except httpx.HTTPError as e:
        raise LLMError(f"Could not reach Ollama at {base_url}: {e}") from e
    if r.status_code != 200:
        raise LLMError(f"Ollama returned HTTP {r.status_code} from {url}")
    try:
        return sorted(m["name"] for m in r.json().get("models", []))
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        raise LLMError(f"Unexpected response from {url} — is this an Ollama server?") from e


async def list_anthropic_models(api_key: str) -> List[str]:
    if not api_key:
        raise LLMError("ANTHROPIC_API_KEY is not set.")
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            r = await client.get(
                "https://api.anthropic.com/v1/models",
                params={"limit": 100},
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
            )
    except httpx.HTTPError as e:
        raise LLMError(f"Could not reach the Anthropic API: {e}") from e
    if r.status_code == 401:
        raise LLMError("Anthropic rejected the API key (HTTP 401).")
    if r.status_code != 200:
        raise LLMError(f"Anthropic API returned HTTP {r.status_code}")
    return [m["id"] for m in r.json().get("data", [])]


# ---------- Public ----------
async def stream_chat(messages: List[Dict], system: str) -> AsyncIterator[str]:
    cfg = get_settings()
    provider = cfg.LLM_PROVIDER.lower()
    if provider == "anthropic":
        async for tok in _stream_anthropic(messages, system, cfg):
            yield tok
    elif provider == "ollama":
        async for tok in _stream_ollama(messages, system, cfg):
            yield tok
    else:
        raise LLMError(f"Unknown LLM_PROVIDER: {cfg.LLM_PROVIDER}")
