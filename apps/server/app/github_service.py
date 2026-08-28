from __future__ import annotations

from typing import Any

import httpx


def create_repository(token: str, owner: str | None, repository_name: str, description: str | None, private: bool, default_branch: str) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    payload = {"name": repository_name, "description": description or "", "private": private, "auto_init": False}
    url = "https://api.github.com/user/repos" if not owner else f"https://api.github.com/orgs/{owner}/repos"
    with httpx.Client(timeout=30) as client:
        response = client.post(url, headers=headers, json=payload)
        if response.status_code == 404 and owner:
            response = client.post("https://api.github.com/user/repos", headers=headers, json=payload)
        if response.status_code >= 400:
            raise RuntimeError(f"GitHub repository creation failed: {response.status_code} {response.text}")
        data = response.json()
        if default_branch and default_branch != data.get("default_branch"):
            # GitHub applies the real default branch after the first push; the local push command sets it upstream.
            data["requested_default_branch"] = default_branch
        return data
