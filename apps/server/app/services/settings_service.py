from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from .. import models

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
        "ai": {"provider": "none", "api_base": "", "api_key": "", "model": "", "output_language": "zh", "research_interests": "", "max_pdf_chars": 60000},
    },
}

DEFAULT_FLAT_SETTINGS: dict[str, str] = {
    "general.language": "zh-CN",
    "paths.projects_root": "/home/robot",
    "paths.knowledge_root": "/home/robot/文档/Obsidian Vault",
    "paths.obsidian_vault": "/home/robot/文档/Obsidian Vault",
    "paths.dataset_root": "/home/robot/datasets",
    "paths.experiment_root": "/home/robot/experiments",
    "integrations.obsidian.enabled": "false",
    "integrations.obsidian.vault_path": "",
    "integrations.obsidian.knowledge_root": "Knowledge",
    "integrations.obsidian.use_obsidian_uri": "true",
    "integrations.zotero.enabled": "false",
    "integrations.zotero.connection_mode": "web_api",
    "integrations.zotero.user_id": "",
    "integrations.zotero.library": "My Library",
    "integrations.zotero.data_dir": "",
    "integrations.ai.provider": "none",
    "integrations.ai.api_base": "",
    "integrations.ai.model": "",
    "integrations.ai.output_language": "zh",
    "integrations.ai.research_interests": "",
    "integrations.ai.max_pdf_chars": "60000",
    "integrations.github.enabled": "false",
    "integrations.github.username": "",
    "integrations.github.default_owner": "",
    "integrations.github.default_branch": "main",
}

SECRET_KEYS = {
    "integrations.zotero.api_key",
    "integrations.github.token",
    "integrations.github.personal_access_token",
    "integrations.ai.api_key",
}


def get_settings(db: Session, mask_secrets: bool = True) -> dict[str, Any]:
    settings = json.loads(json.dumps(DEFAULT_SETTINGS))
    for row in db.query(models.SystemSetting).all():
        if row.key in SECRET_KEYS:
            continue
        _assign(settings, row.key.split("."), row.value)
    for key in SECRET_KEYS:
        value = secret_value(db, key)
        if value:
            _assign(settings, key.split("."), value)
    if mask_secrets:
        _mask(settings, ["integrations", "github", "token"])
        _mask(settings, ["integrations", "github", "personal_access_token"])
        _mask(settings, ["integrations", "zotero", "api_key"])
        _mask(settings, ["integrations", "ai", "api_key"])
    return settings


def get_secret(db: Session, dotted_key: str) -> str | None:
    row = db.get(models.SystemSetting, dotted_key)
    return row.value if row and row.value else None


def update_settings(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    flat = _flatten(payload)
    for key, value in flat.items():
        if key in SECRET_KEYS:
            if value:
                put_secret(db, key, str(value))
            continue
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
        or secret_value(db, "integrations.github.token")
        or secret_value(db, "integrations.github.personal_access_token")
    )
    return {
        "enabled": github.get("enabled"),
        "token": token,
        "username": github.get("username"),
        "default_owner": github.get("default_owner") or github.get("username"),
        "default_branch": github.get("default_branch") or "main",
    }


def parse_bool(value: str) -> bool:
    return value.lower() in {"1", "true", "yes", "on"}


def bool_to_setting(value: bool) -> str:
    return "true" if value else "false"


def mask_secret(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}{'*' * 6}{value[-4:]}"


def setting_value(db: Session, key: str) -> str:
    item = db.get(models.SystemSetting, key)
    return item.value if item and item.value is not None else DEFAULT_FLAT_SETTINGS.get(key, "")


def secret_value(db: Session, key: str) -> str:
    item = db.get(models.SecretSetting, key)
    return item.value if item else ""


def all_settings_by_prefix(db: Session, prefix: str) -> dict[str, str]:
    rows = db.query(models.SecretSetting).filter(models.SecretSetting.key.like(f"{prefix}%")).all()
    return {row.key: row.value for row in rows if row.value}


def delete_setting(db: Session, key: str) -> None:
    item = db.get(models.SecretSetting, key)
    if item:
        db.delete(item)


def put_setting(db: Session, key: str, value: str) -> None:
    item = db.get(models.SystemSetting, key)
    if not item:
        item = models.SystemSetting(key=key, value=value)
        db.add(item)
    else:
        item.value = value


def put_secret(db: Session, key: str, value: str | None) -> None:
    if value is None or value == "":
        return
    item = db.get(models.SecretSetting, key)
    if not item:
        item = models.SecretSetting(key=key, value=value)
        db.add(item)
    else:
        item.value = value


def build_settings_payload(db: Session) -> dict[str, Any]:
    zotero_key = secret_value(db, "integrations.zotero.api_key")
    github_token = secret_value(db, "integrations.github.personal_access_token")
    return {
        "general": {"language": setting_value(db, "general.language")},
        "paths": {
            "projects_root": setting_value(db, "paths.projects_root"),
            "knowledge_root": setting_value(db, "paths.knowledge_root"),
            "obsidian_vault": setting_value(db, "paths.obsidian_vault"),
            "dataset_root": setting_value(db, "paths.dataset_root"),
            "experiment_root": setting_value(db, "paths.experiment_root"),
        },
        "integrations": {
            "obsidian": {
                "enabled": parse_bool(setting_value(db, "integrations.obsidian.enabled")),
                "vault_path": setting_value(db, "integrations.obsidian.vault_path"),
                "knowledge_root": setting_value(db, "integrations.obsidian.knowledge_root"),
                "use_obsidian_uri": parse_bool(setting_value(db, "integrations.obsidian.use_obsidian_uri")),
            },
            "zotero": {
                "enabled": parse_bool(setting_value(db, "integrations.zotero.enabled")),
                "connection_mode": setting_value(db, "integrations.zotero.connection_mode"),
                "user_id": setting_value(db, "integrations.zotero.user_id"),
                "api_key": None,
                "api_key_masked": mask_secret(zotero_key),
                "library": setting_value(db, "integrations.zotero.library"),
                "data_dir": setting_value(db, "integrations.zotero.data_dir"),
            },
            "ai": {
                "provider": setting_value(db, "integrations.ai.provider"),
                "api_base": setting_value(db, "integrations.ai.api_base"),
                "api_key": None,
                "api_key_masked": mask_secret(secret_value(db, "integrations.ai.api_key")),
                "model": setting_value(db, "integrations.ai.model"),
                "output_language": setting_value(db, "integrations.ai.output_language"),
                "research_interests": setting_value(db, "integrations.ai.research_interests"),
                "max_pdf_chars": int(setting_value(db, "integrations.ai.max_pdf_chars") or 60000),
            },
            "github": {
                "enabled": parse_bool(setting_value(db, "integrations.github.enabled")),
                "username": setting_value(db, "integrations.github.username"),
                "personal_access_token": None,
                "personal_access_token_masked": mask_secret(github_token),
                "default_owner": setting_value(db, "integrations.github.default_owner"),
                "default_branch": setting_value(db, "integrations.github.default_branch"),
            },
        },
    }


def store_settings_payload(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    general = payload.get("general") or {}
    if "language" in general:
        put_setting(db, "general.language", str(general["language"]))
    for key, value in (payload.get("paths") or {}).items():
        put_setting(db, f"paths.{key}", str(value))
    integrations = payload.get("integrations") or {}
    obsidian = integrations.get("obsidian") or {}
    for key in ["vault_path", "knowledge_root"]:
        if key in obsidian:
            put_setting(db, f"integrations.obsidian.{key}", str(obsidian[key]))
    for key in ["enabled", "use_obsidian_uri"]:
        if key in obsidian:
            put_setting(db, f"integrations.obsidian.{key}", bool_to_setting(bool(obsidian[key])))
    zotero = integrations.get("zotero") or {}
    for key in ["connection_mode", "user_id", "library", "data_dir"]:
        if key in zotero:
            put_setting(db, f"integrations.zotero.{key}", str(zotero[key]))
    if "enabled" in zotero:
        put_setting(db, "integrations.zotero.enabled", bool_to_setting(bool(zotero["enabled"])))
    put_secret(db, "integrations.zotero.api_key", zotero.get("api_key"))
    ai = integrations.get("ai") or {}
    for key in ["provider", "api_base", "model", "output_language", "research_interests"]:
        if key in ai:
            put_setting(db, f"integrations.ai.{key}", str(ai[key]))
    if "max_pdf_chars" in ai:
        put_setting(db, "integrations.ai.max_pdf_chars", str(int(ai["max_pdf_chars"] or 60000)))
    put_secret(db, "integrations.ai.api_key", ai.get("api_key"))
    github = integrations.get("github") or {}
    for key in ["username", "default_owner", "default_branch"]:
        if key in github:
            put_setting(db, f"integrations.github.{key}", str(github[key]))
    if "enabled" in github:
        put_setting(db, "integrations.github.enabled", bool_to_setting(bool(github["enabled"])))
    put_secret(db, "integrations.github.personal_access_token", github.get("personal_access_token"))
    db.commit()
    return build_settings_payload(db)


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
