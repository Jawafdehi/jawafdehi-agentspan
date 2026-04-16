from __future__ import annotations

from pathlib import Path

import httpx

from jawafdehi_agentspan.settings import get_settings

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
)


class RemoteDocumentFetcher:
    def __init__(self, *, timeout: float = 60.0) -> None:
        self.timeout = timeout

    @staticmethod
    def guess_extension(url: str, content_type: str | None) -> str:
        normalized = url.lower().split("?")[0]
        for extension in (
            ".pdf",
            ".docx",
            ".doc",
            ".html",
            ".htm",
            ".txt",
            ".jpg",
            ".jpeg",
        ):
            if normalized.endswith(extension):
                return extension
        if content_type:
            lowered = content_type.lower()
            if "pdf" in lowered:
                return ".pdf"
            if "wordprocessingml" in lowered:
                return ".docx"
            if "msword" in lowered:
                return ".doc"
            if "html" in lowered:
                return ".html"
            if "jpeg" in lowered:
                return ".jpg"
            if "text/plain" in lowered:
                return ".txt"
        return ".bin"

    async def download(self, url: str, output_path: Path) -> Path:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=self.timeout
        ) as client:
            response = await client.get(url, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.content)
        return output_path

    async def download_with_detected_extension(
        self, url: str, output_stem: Path
    ) -> Path:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=self.timeout
        ) as client:
            response = await client.get(url, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        extension = self.guess_extension(url, response.headers.get("content-type"))
        output_path = output_stem.with_suffix(extension)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.content)
        return output_path

    async def fetch_text(self, url: str) -> str:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=self.timeout
        ) as client:
            response = await client.get(url, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        return response.text


class BraveSearchClient:
    def __init__(self, *, timeout: float = 30.0) -> None:
        self.timeout = timeout

    async def search(self, query: str, *, count: int = 10) -> list[dict[str, str]]:
        settings = get_settings()
        if not settings.brave_search_api_key:
            raise RuntimeError("BRAVE_SEARCH_API_KEY is required for Brave search.")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": count},
                headers={
                    "X-Subscription-Token": settings.brave_search_api_key,
                    "Accept": "application/json",
                },
            )
        response.raise_for_status()
        payload = response.json()
        results = payload.get("web", {}).get("results", [])
        normalized: list[dict[str, str]] = []
        for result in results:
            url = (result.get("url") or "").strip()
            title = (result.get("title") or "").strip()
            if not url or not title:
                continue
            normalized.append(
                {
                    "url": url,
                    "title": title,
                    "description": (result.get("description") or "").strip(),
                }
            )
        return normalized
