"""
MCP tools related to TikTok ads.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from .entity_cache import get_entity_cache
from .models import AdSummary
from .tiktok_client import TikTokApiError, get_client
from .tools_adgroups import _resolve_campaign_automation_type


def _creative_info_from_item(item: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    """Extract creative_info from ad item; ensure it's a list of dicts or None."""
    raw_ci = item.get("creative_info")
    if raw_ci is None:
        return None
    if isinstance(raw_ci, list):
        return raw_ci if all(isinstance(x, dict) for x in raw_ci) else None
    if isinstance(raw_ci, dict):
        return [raw_ci]
    return None


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
            creative_info=_creative_info_from_item(item),
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

        items = raw.get("list", []) if isinstance(raw, dict) else []
        get_entity_cache().feed_ads(items)

        ads = [a.model_dump() for a in _summarise_ads(raw)]
        return {"ads": ads, "raw": raw}

    @mcp.tool()
    def get_ad(advertiser_id: str, ad_id: str) -> Dict[str, Any]:
        """
        Get a single ad by ID. Returns ad details including creative_info.

        Args:
            advertiser_id: TikTok advertiser (account) ID that owns the ad.
            ad_id: ID of the ad to fetch.
        """
        client = get_client()
        try:
            raw = client.get_ad(advertiser_id, ad_id)
        except TikTokApiError as exc:
            raise RuntimeError(f"Failed to get ad: {exc}") from exc
        items = raw.get("list", []) if isinstance(raw, dict) else []
        summaries = _summarise_ads({"list": items})
        ad = summaries[0].model_dump() if summaries else {}
        return {"ad": ad, "raw": raw}

    @mcp.tool()
    def create_ad(
        advertiser_id: str,
        adgroup_id: str,
        name: str,
        creative_id: str,
        operation_status: str = "ENABLE",
        creative_list: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create an ad in the given ad group.

        For manual campaigns, creative_id is used. For Smart+ / Upgraded Smart+,
        the API requires creative_list: a list of items, each with creative_info
        (and optionally ad_material_id, material_operation_status). Pass creative_list
        as a JSON array. See https://business-api.tiktok.com/portal/docs?id=1843317390059522

        Sample create body (Smart+):
        {
          "adgroup_id": "0000000000000000",
          "ad_name": "example_ad_name",
          "creative_id": "1111111111111111",
          "operation_status": "ENABLE",
          "advertiser_id": "2222222222222222",
          "ad_configuration": {
            "call_to_action_id": "3333333333333333"
          },
          "landing_page_url_list": [
            {
              "landing_page_url": "https://example.com/page?utm_source=source&utm_medium=medium"
            }
          ],
          "creative_list": [
            {
              "ad_material_id": "4444444444444444",
              "creative_info": {
                "ad_format": "SINGLE_VIDEO",
                "identity_authorized_bc_id": "5555555555555555",
                "identity_id": "00000000-0000-0000-0000-000000000000",
                "identity_type": "IDENTITY_TYPE_HERE",
                "tiktok_item_id": "6666666666666666"
              },
              "material_operation_status": "ENABLE"
            }
          ]
        }

        Args:
            advertiser_id: TikTok advertiser (account) ID to create the ad under.
            adgroup_id: Ad group ID to attach the ad to.
            creative_id: Existing creative ID (used for manual; fallback for Smart+).
            creative_list: Optional JSON array of creative_list items for Smart+. Each item
                can include ad_material_id, creative_info (object), material_operation_status.
        """
        client = get_client()
        campaign_automation_type = _resolve_campaign_automation_type(advertiser_id, adgroup_id)

        payload: Dict[str, Any] = {
            "adgroup_id": adgroup_id,
            "ad_name": name,
            "creative_id": creative_id,
            "operation_status": operation_status,
        }

        if creative_list is not None and creative_list.strip():
            try:
                parsed = json.loads(creative_list)
                # Handle double- or multi-encoded JSON (e.g. MCP client sends string with escaped JSON)
                while isinstance(parsed, str):
                    parsed = json.loads(parsed)
                if isinstance(parsed, list) and len(parsed) > 0:
                    payload["creative_list"] = parsed
                elif isinstance(parsed, dict):
                    payload["creative_list"] = [parsed]
                else:
                    payload["creative_list"] = [
                        {
                            "creative_info": {"creative_id": creative_id},
                            "material_operation_status": operation_status,
                        }
                    ]
            except json.JSONDecodeError:
                payload["creative_list"] = [
                    {
                        "creative_info": {"creative_id": creative_id},
                        "material_operation_status": operation_status,
                    }
                ]
        else:
            at = (campaign_automation_type or "").strip().upper()
            if at in ("SMART_PLUS", "UPGRADED_SMART_PLUS"):
                payload["creative_list"] = [
                    {
                        "creative_info": {"creative_id": creative_id},
                        "material_operation_status": operation_status,
                    }
                ]

        try:
            raw = client.create_ad(advertiser_id, payload, campaign_automation_type=campaign_automation_type)
        except TikTokApiError as exc:
            raise RuntimeError(f"Failed to create ad: {exc}") from exc

        return raw

    def _resolve_campaign_automation_type_for_ad(advertiser_id: str, ad_id: str) -> str:
        """Resolve campaign_automation_type for an ad: ad_id -> adgroup_id -> campaign_id -> automation_type (from cache or fetch)."""
        client = get_client()
        cache = get_entity_cache()
        adgroup_id = cache.get_ad_adgroup(ad_id)
        if adgroup_id is None:
            raw = client.get_ad(advertiser_id, ad_id)
            items = raw.get("list", []) if isinstance(raw, dict) else []
            cache.feed_ads(items)
            adgroup_id = cache.get_ad_adgroup(ad_id)
            if adgroup_id is None and items and isinstance(items[0], dict):
                adgroup_id = items[0].get("adgroup_id")
            if adgroup_id is None:
                return "MANUAL"
        campaign_id = cache.get_adgroup_campaign(adgroup_id)
        if campaign_id is None:
            raw = client.get_adgroup(advertiser_id, str(adgroup_id))
            items = raw.get("list", []) if isinstance(raw, dict) else []
            cache.feed_adgroups(items)
            campaign_id = cache.get_adgroup_campaign(adgroup_id)
            if campaign_id is None and items and isinstance(items[0], dict):
                campaign_id = items[0].get("campaign_id")
            if campaign_id is None:
                return "MANUAL"
        automation_type = cache.get_campaign_automation_type(campaign_id)
        if automation_type is None:
            raw = client.get_campaign(advertiser_id, str(campaign_id))
            items = raw.get("list", []) if isinstance(raw, dict) else []
            cache.feed_campaigns(items)
            automation_type = cache.get_campaign_automation_type(campaign_id)
        return automation_type if automation_type is not None else "MANUAL"

    @mcp.tool()
    def update_ad(
        advertiser_id: str,
        ad_id: str,
        name: Optional[str] = None,
        operation_status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update simple properties of an ad.

        Endpoint is chosen by the campaign's campaign_automation_type (MANUAL,
        SMART_PLUS, or UPGRADED_SMART_PLUS), resolved from the ad's ad group and
        campaign (cache or fetch).

        Args:
            advertiser_id: TikTok advertiser (account) ID that owns the ad.
            ad_id: ID of the ad to update.
        """
        client = get_client()
        campaign_automation_type = _resolve_campaign_automation_type_for_ad(advertiser_id, ad_id)
        data: Dict[str, Any] = {"ad_id": ad_id}
        if name is not None:
            data["ad_name"] = name

        try:
            raw = client.update_ad(advertiser_id, data, campaign_automation_type=campaign_automation_type)
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

