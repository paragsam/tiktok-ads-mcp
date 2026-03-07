"""
Entrypoint for the TikTok Ads MCP server.

This module wires together:
  - the FastMCP server
  - campaign / ad group / ad / reporting tools

Run with:
    python -m tiktok_mcp_server.server
"""

from __future__ import annotations

import logging
import os

from mcp.server.fastmcp import FastMCP

from . import tools_ads, tools_adgroups, tools_campaigns, tools_reporting


def _configure_http_logging() -> None:
    """
    Configure logging for TikTok API HTTP request/response debugging.
    Logs go to stderr so they do not interfere with MCP stdio protocol.
    Set TIKTOK_ADS_HTTP_DEBUG=1 for DEBUG level (e.g. request body).
    """
    http_logger = logging.getLogger("tiktok_mcp_server.http")
    if not http_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        http_logger.addHandler(handler)
    level = logging.DEBUG if os.getenv("TIKTOK_ADS_HTTP_DEBUG") else logging.INFO
    http_logger.setLevel(level)


def create_app() -> FastMCP:
    """
    Create and configure the FastMCP server instance.
    """
    mcp = FastMCP("tiktok-ads-mcp")

    tools_campaigns.register_tools(mcp)
    tools_adgroups.register_tools(mcp)
    tools_ads.register_tools(mcp)
    tools_reporting.register_tools(mcp)

    return mcp


def main() -> None:
    """
    Start the MCP server.

    The default transport is stdio, which is what most MCP clients expect.
    HTTP request/response logging (headers) goes to stderr for debugging.
    """
    _configure_http_logging()
    app = create_app()
    app.run()


if __name__ == "__main__":
    main()

