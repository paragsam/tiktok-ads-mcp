"""
MCP tools related to TikTok ad groups.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from .models import AdGroupSummary
from .tiktok_client import TikTokApiError, get_client


def _summarise_adgroups(raw_data: Any) -> List[AdGroupSummary]:
    items = raw_data.get("list", []) if isinstance(raw_data, dict) else []
    summaries: List[AdGroupSummary] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        summary = AdGroupSummary(
            adgroup_id=item.get("adgroup_id", ""),
            adgroup_name=item.get("adgroup_name"),
            adgroup_status=item.get("adgroup_status"),
            campaign_id=item.get("campaign_id"),
            raw=item,
        )
        summaries.append(summary)
    return summaries


def register_tools(mcp: FastMCP) -> None:
    """
    Register adgroup-related tools on the given FastMCP instance.
    """

    @mcp.tool()
    def list_adgroups(
        advertiser_id: str,
        campaign_id: Optional[str] = None,
        status: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        List ad groups for the given TikTok advertiser.

        Args:
            advertiser_id: TikTok advertiser (account) ID to list ad groups for.
            campaign_id: Optional campaign ID to filter by.
            status: Optional list of ad group statuses to filter by.
        """
        client = get_client()
        try:
            raw = client.list_adgroups(advertiser_id, campaign_id=campaign_id, status=status)
        except TikTokApiError as exc:
            raise RuntimeError(f"Failed to list ad groups: {exc}") from exc

        adgroups = [g.model_dump() for g in _summarise_adgroups(raw)]
        return {"adgroups": adgroups, "raw": raw}

    @mcp.tool()
    def create_adgroup(
        advertiser_id: str,
        campaign_id: str,
        name: str,
        optimization_goal: str,
        billing_event: str,
        bid: float,
        budget: float,
        operation_status: str = "ENABLE",
    ) -> Dict[str, Any]:
        """
        Create a basic ad group under the given campaign.

        This wrapper only exposes the most common bidding and budget fields.
        Targeting is intentionally left as a simple preset-free payload.

        Args:
            advertiser_id: TikTok advertiser (account) ID to create the ad group under.
            campaign_id: Campaign ID to attach the ad group to.
        """
        client = get_client()

        payload: Dict[str, Any] = {
            "campaign_id": campaign_id,
            "adgroup_name": name,
            "optimization_goal": optimization_goal,
            "billing_event": billing_event,
            "bid": bid,
            "budget": budget,
            "operation_status": operation_status,
        }

        try:
            raw = client.create_adgroup(advertiser_id, payload)
        except TikTokApiError as exc:
            raise RuntimeError(f"Failed to create ad group: {exc}") from exc

        return raw

    @mcp.tool()
    def update_adgroup(
        advertiser_id: str,
        adgroup_id: str,
        name: Optional[str] = None,
        bid: Optional[float] = None,
        budget: Optional[float] = None,
        operation_status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update simple properties of an ad group.

        Args:
            advertiser_id: TikTok advertiser (account) ID that owns the ad group.
            adgroup_id: ID of the ad group to update.
        """
        client = get_client()
        data: Dict[str, Any] = {"adgroup_id": adgroup_id}
        if name is not None:
            data["adgroup_name"] = name
        if bid is not None:
            data["bid"] = bid
        if budget is not None:
            data["budget"] = budget

        try:
            raw = client.update_adgroup(advertiser_id, data)
            if operation_status is not None:
                status_payload = {
                    "adgroup_ids": [adgroup_id],
                    "operation_status": operation_status,
                }
                status_raw = client.update_adgroup_status(advertiser_id, status_payload)
                return {"update": raw, "status_update": status_raw}
        except TikTokApiError as exc:
            raise RuntimeError(f"Failed to update ad group: {exc}") from exc

        return raw

