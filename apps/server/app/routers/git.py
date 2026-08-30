from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud, git_service, github_service, models, schemas
from ..database import get_db
from ..services.projects_service import project_or_404
from ..services.settings_service import github_config

router = APIRouter()


@router.post("/projects/{project_id}/git/init")
def project_git_init(project_id: int, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id)
    result = git_service.init_repo(project.path, project.default_branch or "main")
    return result


@router.get("/projects/{project_id}/git/status")
def project_git_status(project_id: int, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id)
    try:
        return git_service.status(project.path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/projects/{project_id}/git/diff")
def project_git_diff(project_id: int, file: str | None = None, staged: bool = False, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id)
    return git_service.diff(project.path, file, staged)


@router.post("/projects/{project_id}/git/stage")
def project_git_stage(project_id: int, payload: schemas.GitStageRequest, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id)
    return git_service.stage(project.path, payload.files)


@router.post("/projects/{project_id}/git/unstage")
def project_git_unstage(project_id: int, payload: schemas.GitStageRequest, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id)
    return git_service.unstage(project.path, payload.files)


@router.post("/projects/{project_id}/git/commit")
def project_git_commit(project_id: int, payload: schemas.GitCommitRequest, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id)
    return git_service.commit(project.path, payload.files, payload.message)


@router.post("/projects/{project_id}/git/push")
def project_git_push(project_id: int, payload: schemas.GitPushRequest, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id)
    return git_service.push(project.path, payload.remote, payload.branch, payload.confirm)


@router.post("/projects/{project_id}/git/pull")
def project_git_pull(project_id: int, payload: schemas.GitPullRequest, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id)
    return git_service.pull(project.path, payload.remote, payload.branch)


@router.get("/projects/{project_id}/git/pre-push-check")
def project_pre_push_check(project_id: int, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id)
    return git_service.pre_push_check(project.path)


@router.post("/projects/{project_id}/publish-github")
def publish_github(project_id: int, payload: schemas.ProjectPublishRequest, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id)
    config = github_config(db)
    token = config.get("token")
    if not token:
        raise HTTPException(status_code=400, detail="GitHub token is not configured in Settings")
    if not git_service.is_git_repo(project.path):
        init_result = git_service.init_repo(project.path, payload.default_branch)
        if not init_result["ok"]:
            return init_result
    git_service.ensure_gitignore(project.path)
    scan = git_service.pre_push_check(project.path)
    if (scan["blocked_files"] or scan["secret_matches"]) and not payload.confirm_risks:
        return {"ok": False, "requires_confirmation": True, "scan": scan, "stderr": "Security check found risky files. Review before publishing."}
    if scan["safe_files"]:
        add_result = git_service.stage(project.path, scan["safe_files"])
        if not add_result["ok"]:
            return add_result
        commit_result = git_service.run_git(project.path, ["commit", "-m", payload.initial_commit_message], timeout=60)
        if not commit_result["ok"] and "nothing to commit" not in commit_result.get("stdout", "") + commit_result.get("stderr", ""):
            return commit_result
    owner = config.get("default_owner") or config.get("username")
    try:
        repo = github_service.create_repository(str(token), owner, payload.repository_name, payload.description, payload.visibility == "private", payload.default_branch)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    remote_url = repo.get("ssh_url") or repo.get("clone_url")
    if not git_service.status(project.path).get("remote_url") and remote_url:
        remote_result = git_service.run_git(project.path, ["remote", "add", "origin", remote_url])
        if not remote_result["ok"]:
            return remote_result
    push_result = git_service.push(project.path, "origin", payload.default_branch, True)
    if push_result["ok"]:
        project.remote_url = remote_url
        project.branch = payload.default_branch
        project.default_branch = payload.default_branch
        db.commit()
    return {"ok": push_result["ok"], "repo": repo, "remote_url": remote_url, "push": push_result, "scan": scan}


@router.get("/projects/{project_id}/versions")
def project_versions(project_id: int, db: Session = Depends(get_db)) -> list[dict]:
    project = project_or_404(db, project_id)
    return git_service.history(project.path)


@router.get("/projects/{project_id}/versions/{commit_hash}")
def project_version_detail(project_id: int, commit_hash: str, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id)
    return git_service.commit_detail(project.path, commit_hash)


@router.post("/projects/{project_id}/versions/{commit_hash}/open")
def project_open_version(project_id: int, commit_hash: str, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id)
    return git_service.open_version(project.path, commit_hash)


@router.post("/projects/{project_id}/versions/{commit_hash}/branch")
def project_branch_from_version(project_id: int, commit_hash: str, payload: schemas.BranchCreateRequest, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id)
    return git_service.create_branch_from(project.path, payload.name, commit_hash)


@router.post("/projects/{project_id}/versions/{commit_hash}/restore")
def project_restore_version(project_id: int, commit_hash: str, payload: schemas.VersionRestoreRequest, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id)
    return git_service.restore_to(project.path, commit_hash, payload.confirm, payload.create_backup_branch)


@router.get("/projects/{project_id}/branches")
def project_branches(project_id: int, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id)
    return git_service.branches(project.path)


@router.post("/projects/{project_id}/branches")
def project_create_branch(project_id: int, payload: schemas.BranchCreateRequest, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id)
    return git_service.create_branch_from(project.path, payload.name, payload.commit_hash)


@router.post("/projects/{project_id}/checkpoints", response_model=schemas.ProjectCheckpointOut)
def create_checkpoint(project_id: int, payload: schemas.ProjectCheckpointCreate, db: Session = Depends(get_db)):
    if payload.project_id != project_id:
        raise HTTPException(status_code=400, detail="Checkpoint project_id does not match URL")
    return crud.create_item(db, models.ProjectCheckpoint, payload)
