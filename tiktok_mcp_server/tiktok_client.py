"""
Small HTTP client for the TikTok Marketing API.

The goal of this module is clarity:
  - one place that knows how to talk to TikTok
  - simple, well-named methods per operation
  - minimal magic
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

from .config import TikTokConfig, get_config

# Logger for HTTP request/response. Level can be set via
# logging.getLogger("tiktok_mcp_server.http").setLevel(logging.DEBUG)
logger = logging.getLogger("tiktok_mcp_server.http")

_BODY_TRUNCATE = 200


def _truncate(body: bytes) -> bytes:
    if len(body) <= _BODY_TRUNCATE:
        return body
    return body[:_BODY_TRUNCATE] + b"..."

def _log_request(request: httpx.Request) -> None:
    """Event hook: log method, URL, and request body (truncated)."""
    body = request.content or b""
    logger.info(
        "TikTok API request: %s %s  body=%s",
        request.method,
        request.url,
        _truncate(body),
    )


def _log_response(response: httpx.Response) -> None:
    """Event hook: log response body only (truncated)."""
    try:
        response.read()  # consume stream so content is available for logging and later .json()
    except Exception:
        pass
    body = response.content or b""
    logger.info(
        "TikTok API response: %s %s -> %d  body=%s",
        response.request.method,
        response.request.url,
        response.status_code,
        _truncate(body),
    )


class TikTokApiError(RuntimeError):
    """Raised when the TikTok API returns an error response."""

    def __init__(self, message: str, *, code: Optional[int] = None, data: Any | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.data = data


@dataclass(slots=True)
class TikTokClient:
    """
    Tiny wrapper around httpx.Client for TikTok Marketing API calls.

    Methods in this class are intentionally straightforward. They accept simple
    Python types and return decoded JSON (dicts and lists).
    """

    config: TikTokConfig
    _client: httpx.Client

    def __init__(self, config: TikTokConfig, *, timeout: float = 10.0) -> None:
        self.config = config
        self._client = httpx.Client(
            base_url=config.api_root,
            headers={
                "Access-Token": config.access_token,
                "Content-Type": "application/json",
            },
            timeout=timeout,
            event_hooks={
                "request": [_log_request],
                "response": [_log_response],
            },
        )

    # ---- internal helpers -------------------------------------------------

    def _with_advertiser(self, advertiser_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = dict(params or {})
        params.setdefault("advertiser_id", advertiser_id)
        return params

    def _handle_response(self, response: httpx.Response) -> Any:
        """
        Decode JSON and raise TikTokApiError on non-success.

        TikTok Business API responses generally look like:
          { "code": 0, "message": "OK", "data": { ... } }
        """
        try:
            payload = response.json()
        except ValueError as exc:  # invalid JSON
            raise TikTokApiError(
                f"TikTok API returned non-JSON response (status {response.status_code})"
            ) from exc

        if response.status_code != 200:
            raise TikTokApiError(
                f"TikTok API HTTP {response.status_code}: {payload}",
                data=payload,
            )

        code = payload.get("code")
        message = payload.get("message", "")
        if code not in (0, "0", None):
            raise TikTokApiError(
                f"TikTok API error {code}: {message or 'Unknown error'}",
                code=int(code) if isinstance(code, (int, str)) and str(code).isdigit() else None,
                data=payload,
            )

        return payload.get("data", payload)

    # ---- campaigns --------------------------------------------------------

    def list_campaigns(
        self,
        advertiser_id: str,
        *,
        status: Optional[List[str]] = None,
        search_term: Optional[str] = None,
    ) -> Any:
        """
        List campaigns for the given advertiser.

        Maps to GET /campaign/get/
        """
        params: Dict[str, Any] = {}
        filtering: Dict[str, Any] = {}
        if status:
            filtering["campaign_status"] = status
        if search_term:
            filtering["campaign_name"] = search_term
        if filtering:
            params["filtering"] = json.dumps(filtering)

        response = self._client.get("/campaign/get/", params=self._with_advertiser(advertiser_id, params))
        return self._handle_response(response)

    def get_campaign(self, advertiser_id: str, campaign_id: str) -> Any:
        """
        Get a single campaign by ID. Returns same shape as list_campaigns (data with list, page_info).
        Maps to GET /campaign/get/ with filtering campaign_ids.
        """
        params: Dict[str, Any] = {"filtering": json.dumps({"campaign_ids": [campaign_id]})}
        response = self._client.get("/campaign/get/", params=self._with_advertiser(advertiser_id, params))
        return self._handle_response(response)

    def create_campaign(self, advertiser_id: str, payload: Dict[str, Any]) -> Any:
        """
        Create a campaign.

        Maps to POST /campaign/create/
        """
        body = dict(payload)
        body.setdefault("advertiser_id", advertiser_id)
        response = self._client.post("/campaign/create/", json=body)
        return self._handle_response(response)

    def update_campaign(self, advertiser_id: str, payload: Dict[str, Any]) -> Any:
        """
        Update a campaign.

        Maps to POST /campaign/update/
        """
        body = dict(payload)
        body.setdefault("advertiser_id", advertiser_id)
        response = self._client.post("/campaign/update/", json=body)
        return self._handle_response(response)

    def update_campaign_status(self, advertiser_id: str, payload: Dict[str, Any]) -> Any:
        """
        Update campaign status.

        Maps to POST /campaign/status/update/
        """
        body = dict(payload)
        body.setdefault("advertiser_id", advertiser_id)
        response = self._client.post("/campaign/status/update/", json=body)
        return self._handle_response(response)

    # ---- ad groups --------------------------------------------------------

    def list_adgroups(
        self,
        advertiser_id: str,
        *,
        campaign_id: Optional[str] = None,
        status: Optional[List[str]] = None,
    ) -> Any:
        """
        List ad groups for the advertiser, optionally filtered by campaign.

        Maps to GET /adgroup/get/
        """
        filtering: Dict[str, Any] = {}
        if campaign_id:
            filtering["campaign_ids"] = [campaign_id]
        if status:
            filtering["adgroup_status"] = status

        params: Dict[str, Any] = {}
        if filtering:
            params["filtering"] = json.dumps(filtering)

        response = self._client.get("/adgroup/get/", params=self._with_advertiser(advertiser_id, params))
        return self._handle_response(response)

    def get_adgroup(self, advertiser_id: str, adgroup_id: str) -> Any:
        """
        Get a single ad group by ID. Returns same shape as list_adgroups (data with list, page_info).
        Maps to GET /adgroup/get/ with filtering adgroup_ids.
        """
        params: Dict[str, Any] = {"filtering": json.dumps({"adgroup_ids": [adgroup_id]})}
        response = self._client.get("/adgroup/get/", params=self._with_advertiser(advertiser_id, params))
        return self._handle_response(response)

    def create_adgroup(self, advertiser_id: str, payload: Dict[str, Any]) -> Any:
        """
        Create an ad group.

        Maps to POST /adgroup/create/
        """
        body = dict(payload)
        body.setdefault("advertiser_id", advertiser_id)
        response = self._client.post("/adgroup/create/", json=body)
        return self._handle_response(response)

    def update_adgroup(
        self,
        advertiser_id: str,
        payload: Dict[str, Any],
        *,
        campaign_automation_type: str = "MANUAL",
    ) -> Any:
        """
        Update an ad group.

        Endpoint is chosen by campaign_automation_type:
        - MANUAL: POST /adgroup/update/
        - SMART_PLUS: POST /spc/adgroup/update/
        - UPGRADED_SMART_PLUS: POST /smart_plus/adgroup/update/
        See: https://business-api.tiktok.com/portal/docs?id=1843314894279682
        """
        body = dict(payload)
        body.setdefault("advertiser_id", advertiser_id)
        at = (campaign_automation_type or "").strip().upper()
        if at == "MANUAL":
            path = "/adgroup/update/"
        elif at in ("SMART_PLUS", "UPGRADED_SMART_PLUS"):
            path = "/smart_plus/adgroup/update/"
        else:
            path = "/adgroup/update/"
        logger.info(
            "update_adgroup called with campaign_automation_type=%r (endpoint=%s)",
            campaign_automation_type,
            path,
        )
        response = self._client.post(path, json=body)
        return self._handle_response(response)

    def update_adgroup_status(self, advertiser_id: str, payload: Dict[str, Any]) -> Any:
        """
        Update an ad group status.

        Maps to POST /adgroup/status/update/
        """
        body = dict(payload)
        body.setdefault("advertiser_id", advertiser_id)
        response = self._client.post("/adgroup/status/update/", json=body)
        return self._handle_response(response)

    # ---- ads --------------------------------------------------------------

    def list_ads(
        self,
        advertiser_id: str,
        *,
        campaign_id: Optional[str] = None,
        adgroup_id: Optional[str] = None,
        status: Optional[List[str]] = None,
    ) -> Any:
        """
        List ads for the advertiser.

        Maps to GET /ad/get/
        """
        filtering: Dict[str, Any] = {}
        if campaign_id:
            filtering["campaign_ids"] = [campaign_id]
        if adgroup_id:
            filtering["adgroup_ids"] = [adgroup_id]
        if status:
            filtering["ad_status"] = status

        params: Dict[str, Any] = {}
        if filtering:
            params["filtering"] = json.dumps(filtering)

        response = self._client.get("/ad/get/", params=self._with_advertiser(advertiser_id, params))
        return self._handle_response(response)

    def create_ad(self, advertiser_id: str, payload: Dict[str, Any]) -> Any:
        """
        Create an ad.

        Maps to POST /ad/create/
        """
        body = dict(payload)
        body.setdefault("advertiser_id", advertiser_id)
        response = self._client.post("/ad/create/", json=body)
        return self._handle_response(response)

    def update_ad(self, advertiser_id: str, payload: Dict[str, Any]) -> Any:
        """
        Update an ad.

        Maps to POST /ad/update/
        """
        body = dict(payload)
        body.setdefault("advertiser_id", advertiser_id)
        response = self._client.post("/ad/update/", json=body)
        return self._handle_response(response)

    def update_ad_status(self, advertiser_id: str, payload: Dict[str, Any]) -> Any:
        """
        Update ad status.

        Maps to POST /ad/status/update/
        """
        body = dict(payload)
        body.setdefault("advertiser_id", advertiser_id)
        response = self._client.post("/ad/status/update/", json=body)
        return self._handle_response(response)

    # ---- reporting / analytics -------------------------------------------

    def get_integrated_report(self, advertiser_id: str, payload: Dict[str, Any]) -> Any:
        """
        General-purpose reporting helper.

        Maps to GET /report/integrated/get/
        """
        params = dict(payload)
        params.setdefault("advertiser_id", advertiser_id)
        response = self._client.get("/report/integrated/get/", params=params)
        return self._handle_response(response)


_CLIENT: Optional[TikTokClient] = None


def get_client() -> TikTokClient:
    """
    Return a shared TikTokClient instance.

    The underlying httpx.Client is reused across calls for efficiency, but the
    interface here stays very simple.
    """
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = TikTokClient(get_config())
    return _CLIENT

