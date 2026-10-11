"""Client for the SwyfTech CRM's Pitch API (see swyftech-crm/src/pitch-api.js).

Looks up companies to start proposals from, pulls their latest assessment, and reports
proposal status back so the CRM deal follows along."""

import re
from typing import Dict, List, Optional

import httpx

from .runtime_settings import get_settings


class CRMError(Exception):
    pass


def crm_configured(cfg=None) -> bool:
    cfg = cfg or get_settings()
    return bool(cfg.CRM_URL and cfg.CRM_API_TOKEN)


async def _request(method: str, path: str, *, url: str = "", token: str = "", **kwargs) -> Dict:
    cfg = get_settings()
    base = (url or cfg.CRM_URL).rstrip("/")
    token = token or cfg.CRM_API_TOKEN
    if not base or not token:
        raise CRMError("The CRM link isn't set up. Add the CRM URL and API token under Settings.")
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
            r = await client.request(method, f"{base}{path}", headers={"Authorization": f"Bearer {token}"}, **kwargs)
    except httpx.HTTPError as e:
        raise CRMError(f"Could not reach the CRM at {base}: {e}") from e
    try:
        data = r.json()
    except ValueError:
        data = {}
    if r.status_code == 401:
        raise CRMError("The CRM rejected the API token. Check it matches PITCH_API_TOKEN on the CRM.")
    if r.status_code == 503:
        raise CRMError(data.get("error") or "The CRM's Pitch API is turned off (PITCH_API_TOKEN is empty on the CRM).")
    if r.status_code == 404 and not data:
        raise CRMError(f"{base} doesn't have the Pitch API. Is this the CRM's URL, and is the CRM up to date?")
    if r.status_code != 200 or not data.get("ok"):
        raise CRMError(data.get("error") or f"The CRM returned HTTP {r.status_code}.")
    return data


async def search_companies(q: str = "", *, url: str = "", token: str = "") -> List[Dict]:
    return (await _request("GET", "/api/pitch/companies", params={"q": q}, url=url, token=token))["companies"]


async def company_detail(company_id: int) -> Dict:
    return await _request("GET", f"/api/pitch/companies/{company_id}")


async def record_proposal(company_id: int, payload: Dict) -> Dict:
    return await _request("POST", f"/api/pitch/companies/{company_id}/proposal", json=payload)


def parse_count(value) -> Optional[int]:
    """CRM sizes are free text ("12", "6–15", "about 20"). Only a single number is used;
    a range is too vague to price from."""
    text = str(value or "").strip()
    nums = re.findall(r"\d+", text)
    if len(nums) == 1 and not re.search(r"[–—-]|to\b", text):
        return int(nums[0])
    return None


def counts_from(detail: Dict) -> Dict[str, Optional[int]]:
    """Users/endpoints for the prospect: the assessment's environment (counted on the visit)
    wins over the company record (often a range from the website form)."""
    env = {e["label"]: e["value"] for e in ((detail.get("assessment") or {}).get("environment") or [])}
    company = detail.get("company") or {}
    users = parse_count(env.get("Users")) or parse_count(company.get("users"))
    endpoints = parse_count(env.get("Computers")) or parse_count(company.get("devices"))
    return {"users": users, "endpoints": endpoints}


def open_deal(detail: Dict) -> Optional[Dict]:
    open_stages = ("new", "contacted", "assessment", "proposal")
    return next((d for d in detail.get("deals") or [] if d["stage"] in open_stages), None)
