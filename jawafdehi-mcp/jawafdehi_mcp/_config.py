"""Configuration helpers for jawafdehi-mcp.

Settings are read from environment variables (matching the jawafdehi-agentspan
.env file) so that the MCP package does not require a separate config file.
"""

from __future__ import annotations

import os


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def jawafdehi_api_base_url() -> str:
    return _env("JAWAFDEHI_API_BASE_URL", "https://portal.jawafdehi.org")


def jawafdehi_api_token() -> str:
    return _env("JAWAFDEHI_API_TOKEN", "")


def nes_api_base_url() -> str:
    return _env("NES_API_BASE_URL", "https://nes.jawafdehi.org")
