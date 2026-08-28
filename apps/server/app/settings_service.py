from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from . import models

DEFAULT_SETTINGS: dict[str, Any] = {
    "general": {"language": "zh-CN"},
    "paths": {
        "projects_root": "/home/robot",
        "knowledge_root": "/home/robot/文档/Obsidian Vault",
        "obsidian_vault": "/home/robot/文档/Obsidian Vault",
        "dataset_root": "/home/robot/datasets",
        "experiment_root": "/home/robot/experiments",
    },
    "integrations": {
        "github": {"enabled": False, "username": "", "token": "", "personal_access_token": "", "default_owner": "", "default_branch": "main"},
        "obsidian": {"enabled": False, "vault_path": "", "knowledge_root": "Knowledge", "use_obsidian_uri": True},
        "zotero": {"enabled": False, "connection_mode": "web_api", "user_id": "", "api_key": "", "library": "My Library"},
    },
}


def get_settings(db: Session, mask_secrets: bool = True) -> dict[str, Any]:
    settings = json.loads(json.dumps(DEFAULT_SETTINGS))
    for row in db.query(models.SystemSetting).all():
        _assign(settings, row.key.split("."), row.value)
    if mask_secrets:
        _mask(settings, ["integrations", "github", "token"])
        _mask(settings, ["integrations", "zotero", "api_key"])
    return settings


def get_secret(db: Session, dotted_key: str) -> str | None:
    row = db.get(models.SystemSetting, dotted_key)
    return row.value if row and row.value else None


def update_settings(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    flat = _flatten(payload)
    for key, value in flat.items():
        row = db.get(models.SystemSetting, key)
        if not row:
            row = models.SystemSetting(key=key)
            db.add(row)
        row.value = json.dumps(value) if isinstance(value, (dict, list, bool, int, float)) else value
    db.commit()
    return get_settings(db)


def github_config(db: Session) -> dict[str, str | None]:
    settings = get_settings(db, mask_secrets=False)
    github = settings.get("integrations", {}).get("github", {})
    token = (
        github.get("token")
        or github.get("personal_access_token")
        or get_secret(db, "integrations.github.token")
        or get_secret(db, "integrations.github.personal_access_token")
    )
    return {
        "enabled": github.get("enabled"),
        "token": token,
        "username": github.get("username"),
        "default_owner": github.get("default_owner") or github.get("username"),
        "default_branch": github.get("default_branch") or "main",
    }


def _assign(target: dict[str, Any], parts: list[str], value: str | None) -> None:
    cursor = target
    for part in parts[:-1]:
        cursor = cursor.setdefault(part, {})
    cursor[parts[-1]] = _parse(value)


def _parse(value: str | None) -> Any:
    if value is None:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _flatten(value: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, item in value.items():
        full = f"{prefix}.{key}" if prefix else key
        if isinstance(item, dict):
            result.update(_flatten(item, full))
        else:
            result[full] = item
    return result


def _mask(settings: dict[str, Any], parts: list[str]) -> None:
    cursor = settings
    for part in parts[:-1]:
        cursor = cursor.get(part, {})
    key = parts[-1]
    value = cursor.get(key)
    if value:
        cursor[key] = f"{str(value)[:4]}...{str(value)[-4:]}" if len(str(value)) > 8 else "********"
