"""
In-memory cache, 24-hour TTL. Stores only:

  - adgroup_id (int) -> campaign_id (int)
  - ad_id (int) -> adgroup_id (int)
  - campaign_id (int) -> campaign_automation_type ("MANUAL" | "SMART_PLUS" | "UPGRADED_SMART_PLUS")
"""

from __future__ import annotations

import logging
import time
from threading import RLock
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger("tiktok_mcp_server.entity_cache")

# 24 hours in seconds
TTL_SECONDS = 24 * 3600

CampaignAutomationType = str  # "MANUAL" | "SMART_PLUS" | "UPGRADED_SMART_PLUS"

_VALID_AUTOMATION_TYPES = frozenset({"MANUAL", "SMART_PLUS", "UPGRADED_SMART_PLUS"})


def _to_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _normalize_campaign_automation_type(raw: Any) -> CampaignAutomationType:
    """Normalize API value to MANUAL, SMART_PLUS, or UPGRADED_SMART_PLUS."""
    if raw is None:
        return "MANUAL"
    s = (raw if isinstance(raw, str) else str(raw)).strip().upper().replace("-", "_")
    return s if s in _VALID_AUTOMATION_TYPES else "MANUAL"


def _expiry() -> float:
    return time.monotonic() + TTL_SECONDS


class EntityCache:
    """
    Thread-safe cache:
      - adgroup_id (int) -> campaign_id (int)
      - ad_id (int) -> adgroup_id (int)
      - campaign_id (int) -> campaign_automation_type (MANUAL | SMART_PLUS | UPGRADED_SMART_PLUS)
    24h TTL per entry.
    """

    __slots__ = ("_adgroup_to_campaign", "_ad_to_adgroup", "_campaign_to_automation_type", "_lock")

    def __init__(self) -> None:
        # (value, expiry_monotonic)
        self._adgroup_to_campaign: Dict[int, tuple[int, float]] = {}
        self._ad_to_adgroup: Dict[int, tuple[int, float]] = {}
        self._campaign_to_automation_type: Dict[int, tuple[CampaignAutomationType, float]] = {}
        self._lock = RLock()

    def _expired(self, expiry: float) -> bool:
        return time.monotonic() > expiry

    def get_adgroup_campaign(self, adgroup_id: Union[int, str]) -> Optional[int]:
        """adgroup_id -> campaign_id (int)."""
        key = _to_int(adgroup_id)
        if key is None:
            return None
        with self._lock:
            entry = self._adgroup_to_campaign.get(key)
            if entry is None:
                return None
            campaign_id, exp = entry
            if self._expired(exp):
                del self._adgroup_to_campaign[key]
                return None
            return campaign_id

    def get_ad_adgroup(self, ad_id: Union[int, str]) -> Optional[int]:
        """ad_id -> adgroup_id (int)."""
        key = _to_int(ad_id)
        if key is None:
            return None
        with self._lock:
            entry = self._ad_to_adgroup.get(key)
            if entry is None:
                return None
            adgroup_id, exp = entry
            if self._expired(exp):
                del self._ad_to_adgroup[key]
                return None
            return adgroup_id

    def get_campaign_automation_type(self, campaign_id: Union[int, str]) -> Optional[CampaignAutomationType]:
        """campaign_id -> campaign_automation_type (MANUAL | SMART_PLUS | UPGRADED_SMART_PLUS)."""
        key = _to_int(campaign_id)
        if key is None:
            return None
        with self._lock:
            entry = self._campaign_to_automation_type.get(key)
            if entry is None:
                return None
            automation_type, exp = entry
            if self._expired(exp):
                del self._campaign_to_automation_type[key]
                return None
            return automation_type

    def feed_adgroups(self, items: List[Dict[str, Any]]) -> None:
        """adgroup_id -> campaign_id (int map only)."""
        if not items:
            return
        exp = _expiry()
        with self._lock:
            for item in items:
                if not isinstance(item, dict):
                    continue
                ag_id = _to_int(item.get("adgroup_id"))
                camp_id = _to_int(item.get("campaign_id"))
                if ag_id is not None and camp_id is not None:
                    self._adgroup_to_campaign[ag_id] = (camp_id, exp)

    def feed_ads(self, items: List[Dict[str, Any]]) -> None:
        """ad_id -> adgroup_id (int map only)."""
        if not items:
            return
        exp = _expiry()
        with self._lock:
            for item in items:
                if not isinstance(item, dict):
                    continue
                ad_id = _to_int(item.get("ad_id"))
                ag_id = _to_int(item.get("adgroup_id"))
                if ad_id is not None and ag_id is not None:
                    self._ad_to_adgroup[ad_id] = (ag_id, exp)

    def feed_campaigns(self, items: List[Dict[str, Any]]) -> None:
        """campaign_id -> campaign_automation_type (int to MANUAL | SMART_PLUS | UPGRADED_SMART_PLUS)."""
        if not items:
            return
        exp = _expiry()
        with self._lock:
            for item in items:
                if not isinstance(item, dict):
                    continue
                camp_id = _to_int(item.get("campaign_id"))
                if camp_id is None:
                    continue
                raw = item.get("campaign_automation_type") or item.get("campaign_type") or item.get("campaign_app_type") or item.get("objective_type")
                automation_type = _normalize_campaign_automation_type(raw)
                self._campaign_to_automation_type[camp_id] = (automation_type, exp)
                logger.info("entity_cache: campaign_id=%s -> campaign_automation_type=%s", camp_id, automation_type)


_cache: Optional[EntityCache] = None


def get_entity_cache() -> EntityCache:
    global _cache
    if _cache is None:
        _cache = EntityCache()
    return _cache
