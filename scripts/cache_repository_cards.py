#!/usr/bin/env python3
"""Cache GitHub repository card SVGs for stable static-site rendering."""

from __future__ import annotations

import argparse
import html
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable


DEFAULT_DATA_FILE = Path("_data/repositories.yml")
DEFAULT_OUTPUT_DIR = Path("assets/img/repositories")
DEFAULT_STATS_URL = "https://github-readme-stats.vercel.app"
CARD_THEMES = {
    "light": "default",
    "dark": "dark",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cache GitHub repository card SVGs.")
    parser.add_argument("--data-file", default=str(DEFAULT_DATA_FILE))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--stats-url", default=DEFAULT_STATS_URL)
    return parser.parse_args()


def read_github_repositories(data_file: Path) -> list[str]:
    repos: list[str] = []
    in_repos = False

    for line in data_file.read_text(encoding="utf-8").splitlines():
        if line.strip() == "github_repos:":
            in_repos = True
            continue

        if in_repos and line and not line.startswith((" ", "\t", "-")):
            break

        if in_repos:
            stripped = line.strip()
            if stripped.startswith("- "):
                repos.append(stripped[2:].strip())

    return repos


def cache_filename(repository: str, mode: str) -> str:
    return f"{repository.replace('/', '__')}--{mode}.svg"


def card_url(stats_url: str, repository: str, theme: str) -> str:
    owner, repo = repository.split("/", 1)
    query = urllib.parse.urlencode(
        {
            "username": owner,
            "repo": repo,
            "theme": theme,
            "locale": "en",
            "show_owner": "false",
            "description_lines_count": "2",
        }
    )
    return f"{stats_url.rstrip('/')}/api/pin/?{query}"


def fetch_url(url: str) -> bytes:
    headers = {"User-Agent": "al-folio-svg-cache"}
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = f"Bearer {token}"
        headers["Accept"] = "application/vnd.github+json"

    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def repository_api_url(repository: str) -> str:
    return f"https://api.github.com/repos/{urllib.parse.quote(repository, safe='/')}"


def fetch_repository_metadata(repository: str, fetch: Callable[[str], bytes]) -> dict:
    try:
        return json.loads(fetch(repository_api_url(repository)).decode("utf-8"))
    except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError):
        return {}


def ellipsize(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    return value[: max_length - 1].rstrip() + "..."


def fallback_svg(repository: str, mode: str, metadata: dict | None = None) -> bytes:
    metadata = metadata or {}
    background = "#ffffff" if mode == "light" else "#151515"
    border = "#e4e2e2" if mode == "light" else "#30363d"
    title = "#b509ac" if mode == "light" else "#58a6ff"
    text = "#586069" if mode == "light" else "#8b949e"
    muted = "#6a737d" if mode == "light" else "#8b949e"
    safe_repository = html.escape(repository)
    name = metadata.get("name") or repository.split("/", 1)[1]
    description = metadata.get("description") or repository
    stars = metadata.get("stargazers_count") or 0
    forks = metadata.get("forks_count") or 0
    language = metadata.get("language") or ""
    safe_name = html.escape(ellipsize(str(name), 34))
    safe_description = html.escape(ellipsize(str(description), 56))
    safe_language = html.escape(str(language))
    language_text = f"   {safe_language}" if safe_language else ""
    icon = "#24292f" if mode == "light" else "#c9d1d9"
    svg = f"""<svg width="400" height="140" viewBox="0 0 400 140" fill="none" xmlns="http://www.w3.org/2000/svg">
<rect x="0.5" y="0.5" width="399" height="139" rx="4.5" fill="{background}" stroke="{border}"/>
<text x="24" y="42" fill="{title}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="22" font-weight="600">{safe_name}</text>
<text x="24" y="72" fill="{text}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="13">{safe_repository}</text>
<text x="24" y="96" fill="{muted}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="13">{safe_description}</text>
<path fill="{icon}" d="M33 110.2l2.5 5.1 5.6.8-4 3.9.9 5.5-5-2.6-5 2.6.9-5.5-4-3.9 5.6-.8 2.5-5.1z"/>
<text x="48" y="123" fill="{text}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="14">{stars}</text>
<circle cx="88" cy="113" r="2.8" fill="{icon}"/>
<circle cx="88" cy="123" r="2.8" fill="{icon}"/>
<circle cx="102" cy="113" r="2.8" fill="{icon}"/>
<path d="M88 116v4m0-4c0 4.5 14 2.5 14-3" stroke="{icon}" stroke-width="2" stroke-linecap="round"/>
<text x="112" y="123" fill="{text}" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="14">{forks}{language_text}</text>
</svg>
"""
    return svg.encode("utf-8")


def valid_svg(content: bytes) -> bool:
    return b"<svg" in content[:500].lower()


def cache_repository_cards(
    data_file: Path = DEFAULT_DATA_FILE,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    stats_url: str = DEFAULT_STATS_URL,
    fetch: Callable[[str], bytes] = fetch_url,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    for repository in read_github_repositories(data_file):
        metadata: dict | None = None
        for mode, theme in CARD_THEMES.items():
            output_path = output_dir / cache_filename(repository, mode)
            url = card_url(stats_url, repository, theme)
            try:
                content = fetch(url)
                if not valid_svg(content):
                    raise ValueError(f"Response is not SVG: {url}")
            except (OSError, ValueError, urllib.error.URLError) as error:
                if output_path.exists():
                    print(f"Keeping existing {output_path}: {error}")
                    continue
                if metadata is None:
                    metadata = fetch_repository_metadata(repository, fetch)
                content = fallback_svg(repository, mode, metadata)
                print(f"Writing fallback {output_path}: {error}")

            output_path.write_bytes(content)
            print(f"Cached {output_path}")


def main() -> int:
    args = parse_args()
    cache_repository_cards(
        data_file=Path(args.data_file),
        output_dir=Path(args.output_dir),
        stats_url=args.stats_url,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
