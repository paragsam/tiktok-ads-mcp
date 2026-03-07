"""
MCP tools related to TikTok campaigns.

Each tool is registered from `server.py` via `register_tools(mcp)`.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from .models import CampaignSummary
from .tiktok_client import TikTokApiError, get_client


def _summarise_campaigns(raw_data: Any) -> List[CampaignSummary]:
    """
    Convert TikTok's campaign list payload to simple summaries.

    TikTok typically returns:
      { "list": [ { "campaign_id": "...", ... }, ... ], "page_info": {...} }
    We only care about the list here and expose a trimmed-down view.
    """
    items = raw_data.get("list", []) if isinstance(raw_data, dict) else []
    summaries: List[CampaignSummary] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        summary = CampaignSummary(
            campaign_id=item.get("campaign_id", ""),
            campaign_name=item.get("campaign_name"),
            objective=item.get("objective_type") or item.get("objective"),
            campaign_status=item.get("campaign_status"),
            raw=item,
        )
        summaries.append(summary)
    return summaries


def register_tools(mcp: FastMCP) -> None:
    """
    Register campaign-related tools on the given FastMCP instance.
    """

    @mcp.tool()
    def list_campaigns(
        advertiser_id: str,
        status: Optional[List[str]] = None,
        search_term: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List campaigns for the given TikTok advertiser.

        Args:
            advertiser_id: TikTok advertiser (account) ID to list campaigns for.
            status: Optional list of campaign statuses to filter by.
            search_term: Optional case-insensitive substring match on campaign name.

        Returns:
            A dict containing:
              - campaigns: list of CampaignSummary objects (as plain dicts)
              - raw: the raw TikTok response data
        """
        client = get_client()
        try:
            raw = client.list_campaigns(advertiser_id, status=status, search_term=search_term)
        except TikTokApiError as exc:
            # Re-raise with a friendly message for the MCP client.
            raise RuntimeError(f"Failed to list campaigns: {exc}") from exc

        campaigns = [c.model_dump() for c in _summarise_campaigns(raw)]
        return {"campaigns": campaigns, "raw": raw}

    @mcp.tool()
    def create_campaign(
        advertiser_id: str,
        name: str,
        objective: str,
        budget: float,
        budget_mode: str = "BUDGET_MODE_TOTAL",
        operation_status: str = "ENABLE",
    ) -> Dict[str, Any]:
        """
        Create a basic campaign.

        This is a thin wrapper over TikTok's /campaign/create/ endpoint. It only
        exposes a small set of fields commonly needed for a first version.

        Args:
            advertiser_id: TikTok advertiser (account) ID to create the campaign under.
            name: Campaign name.
            objective: Objective type (for example: TRAFFIC, CONVERSIONS).
            budget: Budget amount in the account's currency.
            budget_mode: TikTok budget mode (e.g. BUDGET_MODE_TOTAL).
            operation_status: Initial status, usually ENABLE or DISABLE.
        """
        client = get_client()

        payload: Dict[str, Any] = {
            "campaign_name": name,
            "objective_type": objective,
            "budget": budget,
            "budget_mode": budget_mode,
            "operation_status": operation_status,
        }

        try:
            raw = client.create_campaign(advertiser_id, payload)
        except TikTokApiError as exc:
            raise RuntimeError(f"Failed to create campaign: {exc}") from exc

        return raw

    @mcp.tool()
    def update_campaign(
        advertiser_id: str,
        campaign_id: str,
        name: Optional[str] = None,
        budget: Optional[float] = None,
        operation_status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update simple properties of a campaign.

        Args:
            advertiser_id: TikTok advertiser (account) ID that owns the campaign.
            campaign_id: ID of the campaign to update.
            name: Optional new name.
            budget: Optional new budget.
            operation_status: Optional new status (ENABLE / DISABLE).
        """
        client = get_client()
        data: Dict[str, Any] = {"campaign_id": campaign_id}
        if name is not None:
            data["campaign_name"] = name
        if budget is not None:
            data["budget"] = budget

        try:
            raw = client.update_campaign(advertiser_id, data)
            if operation_status is not None:
                status_payload = {
                    "campaign_ids": [campaign_id],
                    "operation_status": operation_status,
                }
                status_raw = client.update_campaign_status(advertiser_id, status_payload)
                return {"update": raw, "status_update": status_raw}
        except TikTokApiError as exc:
            raise RuntimeError(f"Failed to update campaign: {exc}") from exc

        return raw

