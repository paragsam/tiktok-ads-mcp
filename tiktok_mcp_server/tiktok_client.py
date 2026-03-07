"""
Small HTTP client for the TikTok Marketing API.

The goal of this module is clarity:
  - one place that knows how to talk to TikTok
  - simple, well-named methods per operation
  - minimal magic
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

from .config import TikTokConfig, get_config

# Logger for HTTP request/response debugging. Level can be set via
# logging.getLogger("tiktok_mcp_server.http").setLevel(logging.DEBUG)
logger = logging.getLogger("tiktok_mcp_server.http")

# Header names (case-insensitive) whose values should be redacted in logs
_REDACT_HEADERS = frozenset({"access-token", "authorization", "cookie"})


def _redact_headers(headers: httpx.Headers) -> Dict[str, str]:
    """Return a dict of header name -> value, with sensitive values redacted."""
    out: Dict[str, str] = {}
    for name, value in headers.items():
        key = name.lower()
        if key in _REDACT_HEADERS and value:
            out[name] = "***REDACTED***"
        else:
            out[name] = value
    return out


def _format_headers_for_log(headers: Dict[str, str]) -> str:
    """Format headers as multi-line string for logging."""
    return "\n    ".join(f"{k}: {v}" for k, v in sorted(headers.items()))


def _log_request(request: httpx.Request) -> None:
    """Event hook: log outgoing request method, URL, and full headers."""
    safe_headers = _redact_headers(request.headers)
    logger.info(
        "TikTok API request: %s %s\n  Request headers:\n    %s",
        request.method,
        request.url,
        _format_headers_for_log(safe_headers),
    )
    if request.content:
        logger.debug("  Request body: %s", request.content[:2000] if len(request.content) > 2000 else request.content)


def _log_response(response: httpx.Response) -> None:
    """Event hook: log response status and full response headers."""
    safe_headers = _redact_headers(response.headers)
    logger.info(
        "TikTok API response: %s %s -> %d %s\n  Response headers:\n    %s",
        response.request.method,
        response.request.url,
        response.status_code,
        response.reason_phrase or "",
        _format_headers_for_log(safe_headers),
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
        if status:
            params["filtering"] = {"campaign_status": status}
        if search_term:
            filtering = params.setdefault("filtering", {})
            filtering["campaign_name"] = search_term

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
            params["filtering"] = filtering

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

    def update_adgroup(self, advertiser_id: str, payload: Dict[str, Any]) -> Any:
        """
        Update an ad group.

        Maps to POST /adgroup/update/
        """
        body = dict(payload)
        body.setdefault("advertiser_id", advertiser_id)
        response = self._client.post("/adgroup/update/", json=body)
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
            params["filtering"] = filtering

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

