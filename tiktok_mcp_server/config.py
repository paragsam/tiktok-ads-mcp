"""
Configuration management for the TikTok Ads MCP server.

This module is intentionally small and easy to read. It exposes a single
`TikTokConfig` dataclass and a helper to load it from environment variables.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Optional


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


@dataclass(slots=True)
class TikTokConfig:
    """Configuration for connecting to the TikTok Marketing API."""

    access_token: str
    api_base_url: str = "https://business-api.tiktok.com/open_api/"
    api_version: str = "v1.3"

    @property
    def api_root(self) -> str:
        """
        Full root URL including API version, e.g.:
        https://business-api.tiktok.com/open_api/v1.3
        """
        base = self.api_base_url.rstrip("/")
        version = self.api_version.lstrip("/")
        return f"{base}/{version}"


_CONFIG_CACHE: Optional[TikTokConfig] = None


def _read_env(name: str, *, default: Optional[str] = None) -> Optional[str]:
    """Tiny helper around os.getenv for readability."""
    value = os.getenv(name, default)
    if value is None:
        return None
    value = value.strip()
    return value or None


def load_config_from_env() -> TikTokConfig:
    """
    Load TikTok configuration from environment variables.

    Required:
      - TIKTOK_ADS_ACCESS_TOKEN

    Optional:
      - TIKTOK_ADS_API_BASE_URL  (defaults to https://business-api.tiktok.com/open_api/)
      - TIKTOK_ADS_API_VERSION   (defaults to v1.3)

    This function only validates that required values are present; it does not
    call the TikTok API.
    """
    access_token = _read_env("TIKTOK_ADS_ACCESS_TOKEN")

    if not access_token:
        raise ConfigError(
            "Missing TIKTOK_ADS_ACCESS_TOKEN. "
            "Set a long-lived TikTok Marketing API access token in your environment."
        )

    api_base_url = _read_env(
        "TIKTOK_ADS_API_BASE_URL", default="https://business-api.tiktok.com/open_api/"
    )
    api_version = _read_env("TIKTOK_ADS_API_VERSION", default="v1.3")

    return TikTokConfig(
        access_token=access_token,
        api_base_url=api_base_url or "https://business-api.tiktok.com/open_api/",
        api_version=api_version or "v1.3",
    )


def get_config() -> TikTokConfig:
    """
    Return a cached TikTokConfig instance.

    The config is loaded lazily the first time this function is called. This
    keeps module import side effects minimal and makes it easier to test.
    """
    global _CONFIG_CACHE
    if _CONFIG_CACHE is None:
        _CONFIG_CACHE = load_config_from_env()
    return _CONFIG_CACHE

