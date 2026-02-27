"""
Lightweight data models used by the MCP tools.

These models are intentionally minimal: they provide structure and type hints
without trying to mirror every field in the TikTok API.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class DateRange(BaseModel):
    """Simple YYYY-MM-DD date range."""

    start_date: str = Field(description="Start date in YYYY-MM-DD format.")
    end_date: str = Field(description="End date in YYYY-MM-DD format.")


class CampaignSummary(BaseModel):
    """Short view of a TikTok campaign."""

    id: str = Field(alias="campaign_id")
    name: Optional[str] = Field(default=None, alias="campaign_name")
    objective: Optional[str] = None
    status: Optional[str] = Field(default=None, alias="campaign_status")
    raw: Dict = Field(default_factory=dict, description="Raw TikTok campaign payload.")


class AdGroupSummary(BaseModel):
    """Short view of a TikTok ad group."""

    id: str = Field(alias="adgroup_id")
    name: Optional[str] = Field(default=None, alias="adgroup_name")
    status: Optional[str] = Field(default=None, alias="adgroup_status")
    campaign_id: Optional[str] = None
    raw: Dict = Field(default_factory=dict, description="Raw TikTok ad group payload.")


class AdSummary(BaseModel):
    """Short view of a TikTok ad."""

    id: str = Field(alias="ad_id")
    name: Optional[str] = Field(default=None, alias="ad_name")
    status: Optional[str] = Field(default=None, alias="ad_status")
    campaign_id: Optional[str] = None
    adgroup_id: Optional[str] = None
    raw: Dict = Field(default_factory=dict, description="Raw TikTok ad payload.")


class InsightRow(BaseModel):
    """
    A single row of basic performance metrics.

    The exact keys depend on the requested dimensions and metrics; this model
    focuses on the commonly used numbers and also carries the full raw dict.
    """

    date: Optional[str] = Field(default=None, alias="stat_time_day")
    campaign_id: Optional[str] = None
    adgroup_id: Optional[str] = None
    ad_id: Optional[str] = None

    # Common metrics (all are optional; TikTok controls what is returned)
    spend: Optional[float] = None
    impressions: Optional[int] = None
    clicks: Optional[int] = None
    conversions: Optional[int] = None
    ctr: Optional[float] = None
    cpc: Optional[float] = None
    cpa: Optional[float] = None

    raw: Dict = Field(default_factory=dict, description="Raw TikTok insight row.")


class InsightResponse(BaseModel):
    """Wrapper for a list of insight rows."""

    rows: List[InsightRow]
    raw: Dict = Field(default_factory=dict, description="Raw TikTok report payload.")

