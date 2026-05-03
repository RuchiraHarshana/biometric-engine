import json
from typing import Any, Dict, List, Optional

import httpx
from urllib.parse import quote

from app.core import config


class SupabaseClient:
    def __init__(self, url: str = config.SUPABASE_URL, key: str = config.SUPABASE_SERVICE_KEY):
        clean_url = (url or "").lstrip("\ufeff").strip()
        clean_key = (key or "").lstrip("\ufeff").strip()
        self.base = clean_url.rstrip("/") + "/rest/v1"
        self.key = clean_key
        self._client: Optional[httpx.AsyncClient] = None

    def _headers(self) -> Dict[str, str]:
        return {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
            "Accept": "application/json",
        }

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30)
        return self._client

    async def close(self) -> None:
        """Close the underlying httpx client if open."""
        if self._client is not None:
            try:
                await self._client.aclose()
            finally:
                self._client = None

    def _build_qs(self, filters: Optional[Dict[str, Any]] = None, select: str = "*") -> str:
        qs = f"?select={select}"
        if not filters:
            return qs
        parts = []
        for k, v in filters.items():
            # simple equality filter
            parts.append(f"{k}=eq.{quote(str(v), safe='')}")
        return qs + "&" + "&".join(parts)

    async def get(self, table: str, filters: Optional[Dict[str, Any]] = None, select: str = "*") -> List[Dict[str, Any]]:
        client = await self._get_client()
        url = f"{self.base}/{table}{self._build_qs(filters, select)}"
        resp = await client.get(url, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def insert(self, table: str, payload: Any, returning: str = "representation") -> Any:
        client = await self._get_client()
        url = f"{self.base}/{table}"
        resp = await client.post(url, headers=self._headers(), json=payload)
        if resp.is_error:
            # if duplicate primary key (sequence out of sync), try to repair by picking a new id
            if resp.status_code == 409:
                # attempt to compute max(id) and retry with id = max+1
                try:
                    rows = await self.get(table, select="id")
                    max_id = 0
                    for r in rows:
                        try:
                            v = int(r.get("id", 0))
                            if v > max_id:
                                max_id = v
                        except Exception:
                            continue
                    payload_with_id = dict(payload)
                    payload_with_id["id"] = max_id + 1
                    resp2 = await client.post(url, headers=self._headers(), json=payload_with_id)
                    if resp2.is_error:
                        raise httpx.HTTPStatusError(f"POST {url} returned {resp2.status_code}: {resp2.text}", request=resp2.request, response=resp2)
                    return resp2.json()
                except Exception:
                    raise httpx.HTTPStatusError(f"POST {url} returned {resp.status_code}: {resp.text}", request=resp.request, response=resp)
            # include body for easier debugging
            raise httpx.HTTPStatusError(f"POST {url} returned {resp.status_code}: {resp.text}", request=resp.request, response=resp)
        return resp.json()

    async def update(self, table: str, filters: Dict[str, Any], payload: Any, returning: str = "representation") -> Any:
        client = await self._get_client()
        url = f"{self.base}/{table}{self._build_qs(filters)}"
        resp = await client.patch(url, headers=self._headers(), json=payload)
        if resp.is_error:
            raise httpx.HTTPStatusError(f"PATCH {url} returned {resp.status_code}: {resp.text}", request=resp.request, response=resp)
        return resp.json()

    async def delete(self, table: str, filters: Dict[str, Any]) -> None:
        client = await self._get_client()
        url = f"{self.base}/{table}{self._build_qs(filters)}"
        resp = await client.delete(url, headers=self._headers())
        if resp.is_error:
            raise httpx.HTTPStatusError(f"DELETE {url} returned {resp.status_code}: {resp.text}", request=resp.request, response=resp)


# module-level client for convenience
client = SupabaseClient()
