"""
MCP tools related to TikTok ads.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from .models import AdSummary
from .tiktok_client import TikTokApiError, get_client


def _summarise_ads(raw_data: Any) -> List[AdSummary]:
    items = raw_data.get("list", []) if isinstance(raw_data, dict) else []
    summaries: List[AdSummary] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        summary = AdSummary(
            ad_id=item.get("ad_id", ""),
            ad_name=item.get("ad_name"),
            ad_status=item.get("ad_status"),
            campaign_id=item.get("campaign_id"),
            adgroup_id=item.get("adgroup_id"),
            raw=item,
        )
        summaries.append(summary)
    return summaries


def register_tools(mcp: FastMCP) -> None:
    """
    Register ad-related tools on the given FastMCP instance.
    """

    @mcp.tool()
    def list_ads(
        advertiser_id: str,
        campaign_id: Optional[str] = None,
        adgroup_id: Optional[str] = None,
        status: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        List ads for the given TikTok advertiser.

        Args:
            advertiser_id: TikTok advertiser (account) ID to list ads for.
            campaign_id: Optional campaign ID to filter by.
            adgroup_id: Optional ad group ID to filter by.
            status: Optional list of ad statuses to filter by.
        """
        client = get_client()
        try:
            raw = client.list_ads(advertiser_id, campaign_id=campaign_id, adgroup_id=adgroup_id, status=status)
        except TikTokApiError as exc:
            raise RuntimeError(f"Failed to list ads: {exc}") from exc

        ads = [a.model_dump() for a in _summarise_ads(raw)]
        return {"ads": ads, "raw": raw}

    @mcp.tool()
    def create_ad(
        advertiser_id: str,
        adgroup_id: str,
        name: str,
        creative_id: str,
        operation_status: str = "ENABLE",
    ) -> Dict[str, Any]:
        """
        Create a basic ad in the given ad group.

        This wrapper assumes you already have a creative ID. TikTok supports
        many creative types; modelling them all is out of scope here, so this
        function focuses on the common case of referencing an existing creative.

        Args:
            advertiser_id: TikTok advertiser (account) ID to create the ad under.
            adgroup_id: Ad group ID to attach the ad to.
        """
        client = get_client()

        payload: Dict[str, Any] = {
            "adgroup_id": adgroup_id,
            "ad_name": name,
            "creative_id": creative_id,
            "operation_status": operation_status,
        }

        try:
            raw = client.create_ad(advertiser_id, payload)
        except TikTokApiError as exc:
            raise RuntimeError(f"Failed to create ad: {exc}") from exc

        return raw

    @mcp.tool()
    def update_ad(
        advertiser_id: str,
        ad_id: str,
        name: Optional[str] = None,
        operation_status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update simple properties of an ad.

        Args:
            advertiser_id: TikTok advertiser (account) ID that owns the ad.
            ad_id: ID of the ad to update.
        """
        client = get_client()
        data: Dict[str, Any] = {"ad_id": ad_id}
        if name is not None:
            data["ad_name"] = name

        try:
            raw = client.update_ad(advertiser_id, data)
            if operation_status is not None:
                status_payload = {
                    "ad_ids": [ad_id],
                    "operation_status": operation_status,
                }
                status_raw = client.update_ad_status(advertiser_id, status_payload)
                return {"update": raw, "status_update": status_raw}
        except TikTokApiError as exc:
            raise RuntimeError(f"Failed to update ad: {exc}") from exc

        return raw

