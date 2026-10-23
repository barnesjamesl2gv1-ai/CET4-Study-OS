"""Search GitHub repository metadata; never clone, install, or execute projects.

Example:
  python .agents/skills/github-first-reuse/scripts/github_candidates.py "audio segmentation" --language Python --limit 6

Search metadata is unverified: inspect README, actual LICENSE, source and releases.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API = "https://api.github.com/search/repositories"


def build_url(query: str, language: str | None, limit: int) -> str:
    if not query.strip():
        raise ValueError("query must not be empty")
    if not 1 <= limit <= 20:
        raise ValueError("limit must be between 1 and 20")
    terms = query.strip()
    if language:
        terms += f" language:{language.strip()}"
    return API + "?" + urlencode({"q": terms, "per_page": limit})


def extract_candidates(payload: dict) -> list[dict]:
    if not isinstance(payload.get("items"), list):
        raise ValueError("GitHub response has no items array")
    candidates = []
    for item in payload["items"]:
        if not isinstance(item, dict) or not item.get("full_name") or not item.get("html_url"):
            continue
        candidates.append({
            "repo": item["full_name"],
            "url": item["html_url"],
            "description": item.get("description"),
            "stars": item.get("stargazers_count"),
            "updated_at": item.get("updated_at"),
            "archived": item.get("archived", False),
            "license": "UNVERIFIED: inspect actual LICENSE and third-party notices",
        })
    return candidates


def search(query: str, language: str | None = None, limit: int = 6, opener=urlopen) -> list[dict]:
    url = build_url(query, language, limit)
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "cet4-github-first-reuse"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    request = Request(url, headers=headers)
    with opener(request, timeout=15) as response:
        payload = json.load(response)
    return extract_candidates(payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Search GitHub for candidate repositories (read-only)")
    parser.add_argument("query", help="search terms, preferably capability + technology")
    parser.add_argument("--language", help="GitHub language filter, e.g. Python or TypeScript")
    parser.add_argument("--limit", type=int, default=6)
    args = parser.parse_args(argv)
    try:
        repos = search(args.query, args.language, args.limit)
    except (ValueError, HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        print(f"GitHub search failed; no results verified: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"query": args.query, "candidates": repos, "warning": "Search metadata only; verify LICENSE, security, compatibility and code before reuse."}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
