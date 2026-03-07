"""
MCP tools for TikTok Ads analytics and reporting.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from .models import DateRange, InsightResponse, InsightRow
from .tiktok_client import TikTokApiError, get_client


def _build_common_report_params(
    date_range: DateRange,
    metrics: Optional[List[str]],
    time_granularity: str,
) -> Dict[str, Any]:
    params: Dict[str, Any] = {
        "start_date": date_range.start_date,
        "end_date": date_range.end_date,
        "time_granularity": time_granularity,
    }
    if metrics:
        params["metrics"] = metrics
    return params


def _insights_from_raw(raw: Any) -> InsightResponse:
    """
    Convert TikTok's integrated report payload into our InsightResponse model.
    """
    if not isinstance(raw, dict):
        return InsightResponse(rows=[], raw={"unexpected": raw})

    list_data = raw.get("list") or raw.get("data") or []
    rows: List[InsightRow] = []
    for item in list_data:
        if not isinstance(item, dict):
            continue
        row = InsightRow(
            stat_time_day=item.get("stat_time_day"),
            campaign_id=item.get("campaign_id"),
            adgroup_id=item.get("adgroup_id"),
            ad_id=item.get("ad_id"),
            spend=_safe_float(item.get("spend")),
            impressions=_safe_int(item.get("impressions")),
            clicks=_safe_int(item.get("clicks")),
            conversions=_safe_int(
                item.get("conversions") or item.get("conversion"),
            ),
            ctr=_safe_float(item.get("ctr")),
            cpc=_safe_float(item.get("cpc")),
            cpa=_safe_float(item.get("cpa")),
            raw=item,
        )
        rows.append(row)

    return InsightResponse(rows=rows, raw=raw)


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def register_tools(mcp: FastMCP) -> None:
    """
    Register analytics-related tools on the given FastMCP instance.
    """

    @mcp.tool()
    def get_account_insights(
        advertiser_id: str,
        date_range: DateRange,
        metrics: Optional[List[str]] = None,
        time_granularity: str = "DAY",
    ) -> Dict[str, Any]:
        """
        Get basic account-level performance metrics over a date range.

        This uses TikTok's /report/integrated/get/ endpoint with a BASIC
        report_type and data_level=AUCTION_ADVERTISER.

        Args:
            advertiser_id: TikTok advertiser (account) ID to get insights for.
        """
        client = get_client()
        params = _build_common_report_params(date_range, metrics, time_granularity)
        params["report_type"] = "BASIC"
        params["data_level"] = "AUCTION_ADVERTISER"

        try:
            raw = client.get_integrated_report(advertiser_id, params)
        except TikTokApiError as exc:
            raise RuntimeError(f"Failed to fetch account insights: {exc}") from exc

        parsed = _insights_from_raw(raw)
        return {"rows": [r.model_dump() for r in parsed.rows], "raw": parsed.raw}

    @mcp.tool()
    def get_campaign_insights(
        advertiser_id: str,
        date_range: DateRange,
        metrics: Optional[List[str]] = None,
        time_granularity: str = "DAY",
        campaign_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Get performance metrics per campaign.

        Args:
            advertiser_id: TikTok advertiser (account) ID to get insights for.
        """
        client = get_client()
        params = _build_common_report_params(date_range, metrics, time_granularity)
        params["report_type"] = "BASIC"
        params["data_level"] = "AUCTION_CAMPAIGN"
        if campaign_ids:
            params["filtering"] = {"campaign_ids": campaign_ids}

        try:
            raw = client.get_integrated_report(advertiser_id, params)
        except TikTokApiError as exc:
            raise RuntimeError(f"Failed to fetch campaign insights: {exc}") from exc

        parsed = _insights_from_raw(raw)
        return {"rows": [r.model_dump() for r in parsed.rows], "raw": parsed.raw}

    @mcp.tool()
    def get_adgroup_insights(
        advertiser_id: str,
        date_range: DateRange,
        metrics: Optional[List[str]] = None,
        time_granularity: str = "DAY",
        adgroup_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Get performance metrics per ad group.

        Args:
            advertiser_id: TikTok advertiser (account) ID to get insights for.
        """
        client = get_client()
        params = _build_common_report_params(date_range, metrics, time_granularity)
        params["report_type"] = "BASIC"
        params["data_level"] = "AUCTION_ADGROUP"
        if adgroup_ids:
            params["filtering"] = {"adgroup_ids": adgroup_ids}

        try:
            raw = client.get_integrated_report(advertiser_id, params)
        except TikTokApiError as exc:
            raise RuntimeError(f"Failed to fetch ad group insights: {exc}") from exc

        parsed = _insights_from_raw(raw)
        return {"rows": [r.model_dump() for r in parsed.rows], "raw": parsed.raw}

    @mcp.tool()
    def get_ad_insights(
        advertiser_id: str,
        date_range: DateRange,
        metrics: Optional[List[str]] = None,
        time_granularity: str = "DAY",
        ad_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Get performance metrics per ad.

        Args:
            advertiser_id: TikTok advertiser (account) ID to get insights for.
        """
        client = get_client()
        params = _build_common_report_params(date_range, metrics, time_granularity)
        params["report_type"] = "BASIC"
        params["data_level"] = "AUCTION_AD"
        if ad_ids:
            params["filtering"] = {"ad_ids": ad_ids}

        try:
            raw = client.get_integrated_report(advertiser_id, params)
        except TikTokApiError as exc:
            raise RuntimeError(f"Failed to fetch ad insights: {exc}") from exc

        parsed = _insights_from_raw(raw)
        return {"rows": [r.model_dump() for r in parsed.rows], "raw": parsed.raw}

