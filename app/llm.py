"""LLM client supporting Anthropic and Google Gemini (cloud) and Ollama (self-hosted)."""

import json
import re
from typing import AsyncIterator, Dict, List, Optional, Tuple

import httpx
from anthropic import AsyncAnthropic

from .config import Settings
from .runtime_settings import get_settings


def _count(n) -> str:
    return "—" if n is None else str(n)


# The model ends a reply with this line to put services on the proposal (when auto-add is on).
# Lenient about decoration (bold, bullets, backticks) since smaller models add it.
PROPOSAL_ADD_RE = re.compile(r"^[\s*_`>#-]*PROPOSAL_ADD[\s*_`]*[:：](.*)$", re.IGNORECASE | re.MULTILINE)


def extract_proposal_adds(text: str) -> Tuple[str, List[str]]:
    """Split a reply into (text without PROPOSAL_ADD lines, service names they listed)."""
    names: List[str] = []
    for m in PROPOSAL_ADD_RE.finditer(text):
        for name in re.split(r"[|;]", m.group(1)):
            name = name.strip(" \t*_`\"'")
            if name:
                names.append(name)
    return PROPOSAL_ADD_RE.sub("", text).strip(), names


AUTO_ADD_INSTRUCTIONS = """

## Adding services to the proposal
When you recommend that specific catalog services go on this prospect's proposal, end your reply with one final line in exactly this format. It is hidden from the user and adds those services to the proposal automatically:
PROPOSAL_ADD: Exact Service Name | Another Exact Service Name
Rules:
- List only services you are actively recommending in this reply, using their exact catalog names.
- Leave out services already on the Current Proposal and any you said aren't a fit.
- If you're still asking discovery questions and not recommending anything yet, leave the line out entirely."""


def assessment_block(a: Optional[Dict], limit: int = 15) -> str:
    """The CRM assessment as plain text for a prompt: score, then findings most severe first."""
    if not a:
        return ""
    draft = "" if a.get("status") == "complete" else ", draft (not finished)"
    score = f"score {a['score']}/100 ({a['rating']})" if a.get("score") is not None else "not scored"
    lines = [f"Assessed {a.get('assessed_on', '')}, {score}{draft}."]
    findings = a.get("findings") or []
    if findings:
        lines.append("Findings, most severe first:")
        for f in findings[:limit]:
            line = f"- [{f['status_label']} · {f['severity']}] {f['title']} ({f['category']}). Recommended fix: {f['fix']}"
            if f.get("note"):
                line += f" Visit note: {f['note']}"
            lines.append(line)
        if len(findings) > limit:
            lines.append(f"- …and {len(findings) - limit} lower-priority findings.")
    else:
        lines.append("No problems found on the items checked.")
    if a.get("unverified"):
        lines.append(f"{a['unverified']} checklist items weren't verified on the visit.")
    if a.get("environment"):
        lines.append("Environment: " + "; ".join(f"{e['label']}: {e['value']}" for e in a["environment"]))
    if a.get("summary"):
        lines.append(f"Assessor's summary: {a['summary']}")
    return "\n".join(lines)


def build_system_prompt(
    prospect: Dict,
    services: List[Dict],
    company: Dict,
    proposal_items: List[str] = (),
    auto_add: bool = False,
    assessment: Optional[Dict] = None,
) -> str:
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
    proposal_block = "\n".join(f"- {n}" for n in proposal_items) if proposal_items else "(nothing yet)"

    prospect_block = (
        f"Company: {prospect.get('company_name', 'Unknown')}\n"
        f"Contact: {prospect.get('contact_name') or '—'}\n"
        f"Industry: {prospect.get('industry') or '—'}\n"
        f"Users: {_count(prospect.get('users'))}\n"
        f"Endpoints: {_count(prospect.get('endpoints'))}\n"
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

{f"""## IT Assessment (from the CRM)
{assessment_block(assessment)}

These are real gaps found at this prospect. Recommend services that close the most severe findings first, and say which finding each recommendation addresses.

""" if assessment else ""}## Current Proposal
{proposal_block}

## Service Catalog
{catalog_block}

When you mention a service from the catalog, use its **exact name** in **bold** so the user can quickly add it to the proposal.{AUTO_ADD_INSTRUCTIONS if auto_add else ""}"""


class LLMError(Exception):
    pass


def _money(n: float) -> str:
    return f"${n:,.2f}"


def build_summary_prompt(prospect: Dict, company: Dict, items: List[Dict], totals: Dict,
                         assessment: Optional[Dict], transcript: List[Dict]) -> Tuple[str, List[Dict]]:
    """System prompt + single user message asking for the proposal's executive summary."""
    item_lines = "\n".join(
        f"- {it['name']}: {it['description'] or ''}".rstrip(": ") for it in items
    ) or "(no services on the proposal yet)"
    convo = "\n\n".join(
        f"{'Salesperson' if m['role'] == 'user' else 'Assistant'}: {m['content']}" for m in transcript[-30:]
    ) or "(no conversation)"
    system = f"""You write the executive summary at the top of a managed IT services proposal from {company['name']} to {prospect.get('company_name')}. The client reads it first, so it must be clear, specific and persuasive without hype.

Write 2–3 short paragraphs (120–220 words total), addressed to the client as "you":
1. What we heard: their situation and main concerns, in their terms.
2. What we recommend and why: tie the proposed services to those concerns{' and to the most serious assessment findings' if assessment else ''}.
3. What happens next (a short onboarding / next-step sentence).

Rules: plain text only, no headings, bullet lists or markdown. Don't list prices; the proposal shows them. Use only facts from the material below; never invent numbers, names or incidents. Don't mention AI, the assistant, or this conversation."""
    parts = [
        f"Client: {prospect.get('company_name')}"
        + (f", contact {prospect['contact_name']}" if prospect.get("contact_name") else "")
        + (f", industry {prospect['industry']}" if prospect.get("industry") else "")
        + (f", {prospect['users']} users" if prospect.get("users") is not None else "")
        + (f", {prospect['endpoints']} endpoints" if prospect.get("endpoints") is not None else ""),
        f"Salesperson's notes: {prospect.get('notes') or '(none)'}",
        f"Proposed services:\n{item_lines}",
        f"Totals: {_money(totals['monthly'])}/month recurring, {_money(totals['annual'])}/year, {_money(totals['one_time'])} one-time.",
    ]
    if assessment:
        parts.append("IT assessment:\n" + assessment_block(assessment, limit=8))
    parts.append(f"Discovery conversation (internal):\n{convo}")
    return system, [{"role": "user", "content": "\n\n".join(parts) + "\n\nWrite the executive summary now."}]


def clean_summary(text: str) -> str:
    """Strip markdown the model may add anyway, and any stray PROPOSAL_ADD line."""
    text, _ = extract_proposal_adds(text)
    text = re.sub(r"^#+\s*", "", text, flags=re.M)
    text = re.sub(r"\*\*(.+?)\*\*|__(.+?)__", lambda m: m.group(1) or m.group(2), text)
    text = re.sub(r"^(executive summary|summary)\s*:?\s*\n", "", text.strip(), flags=re.I)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


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


# ---------- Gemini ----------
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


def _gemini_model_path(model: str) -> str:
    # The models API lists names as "models/gemini-..."; accept either form.
    return model if model.startswith("models/") else f"models/{model}"


def _gemini_error(status: int, body: bytes) -> str:
    try:
        detail = json.loads(body)["error"]["message"]
    except (ValueError, KeyError, TypeError):
        detail = body.decode(errors="ignore")[:300]
    if status in (400, 403) and "API key" in detail:
        return f"Gemini rejected the API key: {detail}"
    return f"Gemini error {status}: {detail}"


async def _stream_gemini(messages: List[Dict], system: str, cfg: Settings) -> AsyncIterator[str]:
    if not cfg.GEMINI_API_KEY:
        raise LLMError("GEMINI_API_KEY is not set.")
    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        # Gemini calls the assistant role "model".
        "contents": [
            {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
            for m in messages
        ],
    }
    url = f"{GEMINI_API_BASE}/{_gemini_model_path(cfg.GEMINI_MODEL)}:streamGenerateContent"
    timeout = httpx.Timeout(120.0, connect=10.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST", url, params={"alt": "sse"}, json=payload,
                headers={"x-goog-api-key": cfg.GEMINI_API_KEY},
            ) as r:
                if r.status_code != 200:
                    raise LLMError(_gemini_error(r.status_code, await r.aread()))
                async for line in r.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    try:
                        chunk = json.loads(line[5:])
                    except json.JSONDecodeError:
                        continue
                    if (blocked := (chunk.get("promptFeedback") or {}).get("blockReason")):
                        raise LLMError(f"Gemini blocked the request ({blocked}).")
                    for cand in (chunk.get("candidates") or [])[:1]:
                        for part in (cand.get("content") or {}).get("parts") or []:
                            if part.get("text") and not part.get("thought"):
                                yield part["text"]
    except httpx.HTTPError as e:
        raise LLMError(f"Could not reach the Gemini API: {e}") from e


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


async def list_gemini_models(api_key: str) -> List[str]:
    if not api_key:
        raise LLMError("GEMINI_API_KEY is not set.")
    names: List[str] = []
    page_token = None
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            for _ in range(10):  # paginated; a handful of pages at most
                params = {"pageSize": 1000}
                if page_token:
                    params["pageToken"] = page_token
                r = await client.get(f"{GEMINI_API_BASE}/models", params=params, headers={"x-goog-api-key": api_key})
                if r.status_code != 200:
                    raise LLMError(_gemini_error(r.status_code, r.content))
                data = r.json()
                for m in data.get("models", []):
                    if "generateContent" in m.get("supportedGenerationMethods", []):
                        names.append(m["name"].removeprefix("models/"))
                page_token = data.get("nextPageToken")
                if not page_token:
                    break
    except httpx.HTTPError as e:
        raise LLMError(f"Could not reach the Gemini API: {e}") from e
    return sorted(names)


# ---------- Public ----------
async def complete(messages: List[Dict], system: str) -> str:
    """Whole reply as one string (for drafting text rather than chatting)."""
    return "".join([tok async for tok in stream_chat(messages, system)])


async def stream_chat(messages: List[Dict], system: str) -> AsyncIterator[str]:
    cfg = get_settings()
    provider = cfg.LLM_PROVIDER.lower()
    if provider == "anthropic":
        async for tok in _stream_anthropic(messages, system, cfg):
            yield tok
    elif provider == "ollama":
        async for tok in _stream_ollama(messages, system, cfg):
            yield tok
    elif provider == "gemini":
        async for tok in _stream_gemini(messages, system, cfg):
            yield tok
    else:
        raise LLMError(f"Unknown LLM_PROVIDER: {cfg.LLM_PROVIDER}")
