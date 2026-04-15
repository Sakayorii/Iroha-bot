"""Web tools: URL fetcher, GitHub repo analyzer, image generator."""
from __future__ import annotations

import re
from typing import Optional

import aiohttp

GITHUB_REPO_PATTERN = re.compile(r"github\.com/([^/\s]+)/([^/\s#?]+)")


async def fetch_url_text(url: str, max_chars: int = 8000) -> Optional[str]:
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.get(url, headers={"User-Agent": "Mozilla/5.0"}) as resp:
                if resp.status != 200:
                    return None
                ct = resp.content_type or ""
                if "html" not in ct and "text" not in ct:
                    return None
                html = await resp.text(errors="replace")
                html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
                html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
                html = re.sub(r"<[^>]+>", " ", html)
                html = re.sub(r"\s+", " ", html).strip()
                return html[:max_chars] if html else None
    except Exception:
        return None


async def fetch_github_repo(url: str) -> Optional[str]:
    """Fetch GitHub repo info, file tree, and README."""
    m = GITHUB_REPO_PATTERN.search(url)
    if not m:
        return None
    owner, repo = m.group(1), m.group(2).rstrip("/")
    base = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "IrohaBot"}

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
            parts = []

            # repo info
            async with session.get(base, headers=headers) as resp:
                if resp.status != 200:
                    return None
                info = await resp.json()
                parts.append(f"repo: {info.get('full_name', '?')}")
                parts.append(f"description: {info.get('description', 'none')}")
                parts.append(f"stars: {info.get('stargazers_count', 0)} | forks: {info.get('forks_count', 0)}")
                parts.append(f"language: {info.get('language', '?')}")
                topics = info.get("topics", [])
                if topics:
                    parts.append(f"topics: {', '.join(topics)}")

            # file tree (root level)
            async with session.get(f"{base}/contents", headers=headers) as resp:
                if resp.status == 200:
                    files = await resp.json()
                    if isinstance(files, list):
                        tree = []
                        for f in files[:50]:
                            icon = "\U0001f4c1" if f.get("type") == "dir" else "\U0001f4c4"
                            tree.append(f"  {icon} {f['name']}")
                        parts.append(f"\nfile tree:\n" + "\n".join(tree))

            # README
            readme_headers = {**headers, "Accept": "application/vnd.github.raw"}
            async with session.get(f"{base}/readme", headers=readme_headers) as resp:
                if resp.status == 200:
                    readme = await resp.text()
                    parts.append(f"\nREADME (first 3000 chars):\n{readme[:3000]}")

            # key files: check for common config files
            for fname in ["package.json", "pyproject.toml", "requirements.txt", "Cargo.toml", "go.mod"]:
                try:
                    async with session.get(f"{base}/contents/{fname}", headers=readme_headers) as resp:
                        if resp.status == 200:
                            content = await resp.text()
                            parts.append(f"\n{fname}:\n{content[:1500]}")
                except Exception:
                    pass

            return "\n".join(parts) if parts else None
    except Exception:
        return None


