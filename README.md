# TikTok Ads MCP Server

Python-based MCP server that exposes TikTok Ads Manager (Marketing API) operations as tools.

The server is designed to be **easy to read**, with clear separation between configuration, the TikTok API client, and MCP tools for campaigns, ad groups, ads, and analytics.

## Features

- Management tools for:
  - Campaigns (list, get, create, update)
  - Ad groups (list, create, update)
  - Ads (list, create, update)
- Analytics tools for:
  - Account
  - Campaigns
  - Ad groups
  - Ads
- Environment-driven configuration (no secrets in code)

## Requirements

- Python 3.10+
- TikTok Business account and access to the TikTok Marketing API
- A **long-lived access token** for the TikTok Marketing API (advertiser ID is passed per tool request)

## Installation

From the project root:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

Or, if you prefer `pyproject.toml`, you can use a tool like `pipx`, `uv`, or `pip` with editable installs.

## Configuration

The server reads configuration from environment variables:

- `TIKTOK_ADS_ACCESS_TOKEN` – long-lived access token for the TikTok Ads account (required)
- `TIKTOK_ADS_API_BASE_URL` – optional; defaults to `https://business-api.tiktok.com/open_api/`
- `TIKTOK_ADS_API_VERSION` – optional; defaults to `v1.3`

**Advertiser ID** is not a startup setting. Each tool takes an `advertiser_id` argument so you can operate on different TikTok Ads accounts in the same session.

You can export these in your shell, or create a `.env` file and load it before starting the server.

### HTTP logging (debugging)

Every TikTok API request and response is logged to **stderr** with full HTTP headers (sensitive headers like `Access-Token` are redacted). This does not interfere with the MCP stdio protocol.

- By default: **INFO** – request method/URL and full request/response headers.
- Set `TIKTOK_ADS_HTTP_DEBUG=1` for **DEBUG** – also logs request body (truncated). Useful when debugging payloads.

When running under Claude Desktop, check the app’s logs or terminal for this output.

## Running the MCP server

After installing dependencies and setting environment variables:

```bash
python -m tiktok_mcp_server.server
```

This starts the MCP server using the default transport (configured in `server.py`). Refer to your MCP client (such as an editor or AI tool) for how to register the server.

## Using with an MCP client

In your MCP-compatible client, register a new server pointing to this project. A typical configuration (exact syntax varies by client) will:

- Point to `python -m tiktok_mcp_server.server`
- Run it from the project root
- Pass no extra arguments (the server reads everything from environment variables)

Once registered, you should see tools like:

- `list_campaigns`
- `create_campaign`
- `get_campaign_insights`
- and others defined in the `tools_*.py` modules.

## TikTok API notes

The TikTok Marketing API is versioned. This project defaults to API version `v1.3` and uses endpoints under:

```text
https://business-api.tiktok.com/open_api/v1.3/
```

If TikTok changes versions or endpoints, you can update:

- The `TIKTOK_ADS_API_VERSION` environment variable, or
- The constants in `tiktok_client.py`.

## Contributing and GitHub

This project is structured so it can live in a public GitHub repository:

- All configuration is done via environment variables
- No secrets are stored in the codebase

To publish it on GitHub:

1. Initialize git in the project directory
2. Create a GitHub repository
3. Push this project so others can clone and use it

