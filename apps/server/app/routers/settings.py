from __future__ import annotations

from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import schemas
from ..database import get_db
from ..paper_integrations.zotero import zotero_status
from ..services import settings_service

router = APIRouter()


@router.get("/settings", response_model=schemas.SystemSettingsOut)
def get_settings(db: Session = Depends(get_db)) -> dict:
    return {"settings": settings_service.get_settings(db)}


@router.put("/settings", response_model=schemas.SystemSettingsOut)
def put_settings(payload: schemas.SystemSettingsIn, db: Session = Depends(get_db)) -> dict:
    return {"settings": settings_service.update_settings(db, payload.settings)}


@router.get("/api/settings")
def api_get_settings(db: Session = Depends(get_db)) -> dict:
    return settings_service.build_settings_payload(db)


@router.patch("/api/settings")
def api_update_settings(payload: dict, db: Session = Depends(get_db)) -> dict:
    return settings_service.store_settings_payload(db, payload)


@router.post("/api/settings/test/{integration}")
async def test_integration(integration: str, payload: dict | None = None, db: Session = Depends(get_db)) -> dict:
    payload = payload or {}
    if integration == "paths":
        saved_paths = {key: settings_service.setting_value(db, f"paths.{key}") for key in ["projects_root", "knowledge_root", "obsidian_vault", "dataset_root", "experiment_root"]}
        paths = {**saved_paths, **(payload.get("paths") or {})}
        missing = [name for name, value in paths.items() if not value or not Path(str(value)).expanduser().exists()]
        if missing:
            return {"ok": False, "message": f"以下路径不存在：{', '.join(missing)}"}
        return {"ok": True, "message": "所有存储路径均可访问。"}
    if integration == "obsidian":
        obsidian = (payload.get("integrations") or {}).get("obsidian") or {}
        vault_path = obsidian.get("vault_path") or settings_service.setting_value(db, "integrations.obsidian.vault_path")
        if not vault_path:
            return {"ok": False, "message": "尚未配置 Obsidian Vault 路径。"}
        expanded = Path(str(vault_path)).expanduser()
        if not expanded.exists():
            return {"ok": False, "message": f"Vault 路径不存在：{vault_path}"}
        return {"ok": True, "message": f"Obsidian Vault 可访问：{vault_path}"}
    if integration == "zotero":
        status = await zotero_status()
        if not status.get("available"):
            return {"ok": False, "message": f"无法连接 Zotero 本地服务：{status.get('error', '未知错误')}"}
        if not status.get("authorized"):
            return {"ok": False, "message": "Zotero 已启动，但尚未完成写入授权（首次导入时会自动弹出授权）。"}
        return {"ok": True, "message": f"Zotero 本地服务正常（v{status.get('version') or '?'}，已授权）。"}
    if integration == "github":
        github = (payload.get("integrations") or {}).get("github") or {}
        token = github.get("personal_access_token") or settings_service.secret_value(db, "integrations.github.personal_access_token")
        if not token:
            return {"ok": False, "message": "尚未配置 GitHub Token，请填写后保存。"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    "https://api.github.com/user",
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
                )
        except httpx.HTTPError as exc:
            return {"ok": False, "message": f"无法访问 GitHub API：{exc}"}
        if response.status_code == 401:
            return {"ok": False, "message": "GitHub Token 无效或已过期。"}
        if response.status_code != 200:
            return {"ok": False, "message": f"GitHub API 返回 {response.status_code}。"}
        login = response.json().get("login", "?")
        return {"ok": True, "message": f"GitHub Token 有效，当前用户：{login}。"}
    raise HTTPException(status_code=404, detail=f"Unknown integration: {integration}")
