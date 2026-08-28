from __future__ import annotations

import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

BLOCKED_PATTERNS = (
    ".env",
    "id_rsa",
    "id_ed25519",
    "credentials",
    "secret",
    "token",
    "checkpoint",
    "checkpoints",
    "dataset",
    "datasets",
    "rosbag",
    "wandb",
    "runs/",
    "outputs/",
    "results/",
    ".pt",
    ".pth",
    ".ckpt",
    ".onnx",
    ".bag",
    ".mcap",
)
SECRET_REGEXES = (
    re.compile(r"(?i)(api[_-]?key|access[_-]?token|secret|password)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
)
MAX_SAFE_FILE_BYTES = 50 * 1024 * 1024


def run_git(repo_path: str, args: list[str], timeout: int = 30) -> dict:
    path = Path(repo_path).expanduser().resolve()
    if not path.exists():
        raise ValueError(f"Path does not exist: {repo_path}")
    command = ["git", "-C", str(path), *args]
    completed = subprocess.run(command, text=True, capture_output=True, timeout=timeout, check=False)
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout.rstrip("\r\n"),
        "stderr": completed.stderr.strip(),
    }


def is_git_repo(repo_path: str) -> bool:
    result = run_git(repo_path, ["rev-parse", "--is-inside-work-tree"])
    return result["ok"] and result["stdout"] == "true"


def init_repo(repo_path: str, default_branch: str = "main") -> dict:
    result = run_git(repo_path, ["init", "-b", default_branch])
    if not result["ok"] and "unknown switch" in result.get("stderr", ""):
        result = run_git(repo_path, ["init"])
        if result["ok"]:
            run_git(repo_path, ["checkout", "-B", default_branch])
    return result


def status(repo_path: str) -> dict:
    repo = is_git_repo(repo_path)
    if not repo:
        return {
            "is_repo": False,
            "branch": None,
            "remote_url": None,
            "changes": [],
            "modified": 0,
            "untracked": 0,
            "conflicts": 0,
            "unpushed_commits": 0,
            "last_commit": None,
            "recent_commits": [],
        }
    branch = run_git(repo_path, ["branch", "--show-current"])
    remote = run_git(repo_path, ["remote", "get-url", "origin"])
    porcelain = run_git(repo_path, ["status", "--short"])
    log = run_git(repo_path, ["log", "--oneline", "-8"])
    last = run_git(repo_path, ["log", "-1", "--pretty=format:%h %s"])
    current_branch = branch["stdout"] if branch["ok"] and branch["stdout"] else None
    upstream_count = {"stdout": "0"}
    if current_branch:
        upstream_count = run_git(repo_path, ["rev-list", "--count", "@{u}..HEAD"])
    changes = parse_status(porcelain["stdout"])
    return {
        "is_repo": True,
        "branch": current_branch,
        "remote_url": remote["stdout"] if remote["ok"] else None,
        "changes": changes,
        "modified": len([item for item in changes if item["status"] != "??"]),
        "untracked": len([item for item in changes if item["status"] == "??"]),
        "conflicts": len([item for item in changes if "U" in item["status"] or item["status"] in {"AA", "DD"}]),
        "unpushed_commits": int(upstream_count["stdout"] or 0) if upstream_count.get("ok") and str(upstream_count.get("stdout", "")).isdigit() else 0,
        "last_commit": last["stdout"] if last["ok"] else None,
        "recent_commits": log["stdout"].splitlines() if log["ok"] and log["stdout"] else [],
    }


def diff(repo_path: str, file_path: str | None = None, staged: bool = False) -> dict:
    args = ["diff"]
    if staged:
        args.append("--cached")
    args.append("--")
    if file_path:
        args.append(file_path)
    return run_git(repo_path, args, timeout=60)


def stage(repo_path: str, files: list[str]) -> dict:
    blocked = [file for file in files if is_blocked_file(file)]
    if blocked:
        return {"ok": False, "stderr": f"Refusing to stage risky files: {', '.join(blocked)}", "stdout": ""}
    return run_git(repo_path, ["add", "--", *files], timeout=60)


def unstage(repo_path: str, files: list[str]) -> dict:
    return run_git(repo_path, ["restore", "--staged", "--", *files], timeout=60)


def commit(repo_path: str, files: list[str], message: str) -> dict:
    scan = pre_push_check(repo_path, files=files)
    if scan["blocked_files"] or scan["secret_matches"]:
        return {"ok": False, "stderr": "Security check blocked commit.", "stdout": "", "scan": scan}
    add_result = stage(repo_path, files)
    if not add_result["ok"]:
        return add_result
    return run_git(repo_path, ["commit", "-m", message], timeout=60)


def push(repo_path: str, remote: str, branch: str | None, confirm: bool) -> dict:
    if not confirm:
        return {"ok": False, "stdout": "", "stderr": "Push requires explicit confirmation."}
    target_branch = branch or status(repo_path).get("branch")
    args = ["push", remote]
    if target_branch:
        args.append(target_branch)
    return run_git(repo_path, args, timeout=180)


def pull(repo_path: str, remote: str = "origin", branch: str | None = None) -> dict:
    args = ["pull", remote]
    if branch:
        args.append(branch)
    return run_git(repo_path, args, timeout=180)


def parse_status(output: str) -> list[dict[str, str]]:
    changes = []
    for line in output.splitlines():
        if not line:
            continue
        changes.append({"status": line[:2].strip() or "?", "path": line[3:].strip()})
    return changes


def is_blocked_file(file_path: str) -> bool:
    clean = file_path.lower().replace(os.sep, "/")
    return any(pattern in clean for pattern in BLOCKED_PATTERNS)


def list_candidate_files(repo_path: str) -> list[str]:
    if is_git_repo(repo_path):
        result = run_git(repo_path, ["ls-files", "--modified", "--others", "--exclude-standard"], timeout=60)
        return result["stdout"].splitlines() if result["ok"] and result["stdout"] else []
    root = Path(repo_path).expanduser().resolve()
    ignored_dirs = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"}
    files = []
    for item in root.rglob("*"):
        if item.is_dir() or any(part in ignored_dirs for part in item.relative_to(root).parts):
            continue
        files.append(str(item.relative_to(root)))
        if len(files) > 5000:
            break
    return files


def pre_push_check(repo_path: str, files: list[str] | None = None) -> dict[str, Any]:
    root = Path(repo_path).expanduser().resolve()
    candidates = files or list_candidate_files(repo_path)
    blocked_files: list[str] = []
    large_files: list[dict[str, Any]] = []
    secret_matches: list[dict[str, Any]] = []
    safe_files: list[str] = []
    for rel in candidates:
        rel = rel.strip()
        if not rel:
            continue
        full = (root / rel).resolve()
        if not str(full).startswith(str(root)) or not full.exists() or full.is_dir():
            continue
        risky = is_blocked_file(rel)
        size = full.stat().st_size
        if size > MAX_SAFE_FILE_BYTES:
            large_files.append({"path": rel, "size": size})
            risky = True
        if _file_has_secret(full):
            secret_matches.append({"path": rel, "reason": "possible secret/token pattern"})
            risky = True
        if risky:
            blocked_files.append(rel)
        else:
            safe_files.append(rel)
    return {
        "ok": not blocked_files and not secret_matches,
        "safe_files": safe_files,
        "blocked_files": sorted(set(blocked_files)),
        "large_files": large_files,
        "secret_matches": secret_matches,
    }


def ensure_gitignore(repo_path: str) -> dict:
    root = Path(repo_path).expanduser().resolve()
    gitignore = root / ".gitignore"
    required = [".env", "*.pt", "*.pth", "*.ckpt", "*.onnx", "*.bag", "*.mcap", "checkpoints/", "datasets/", "wandb/", "runs/", "outputs/", "results/"]
    existing = gitignore.read_text(encoding="utf-8", errors="ignore") if gitignore.exists() else ""
    missing = [item for item in required if item not in existing]
    if missing:
        with gitignore.open("a", encoding="utf-8") as handle:
            if existing and not existing.endswith("\n"):
                handle.write("\n")
            handle.write("\n# RoboResearch Workbench safety defaults\n")
            handle.write("\n".join(missing) + "\n")
    return {"ok": True, "path": str(gitignore), "added": missing}


def history(repo_path: str, limit: int = 80) -> list[dict[str, Any]]:
    fmt = "%H%x1f%h%x1f%an%x1f%ad%x1f%s"
    result = run_git(repo_path, ["log", f"--max-count={limit}", f"--pretty=format:{fmt}", "--date=iso", "--shortstat"], timeout=60)
    if not result["ok"] or not result["stdout"]:
        return []
    commits: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in result["stdout"].splitlines():
        if "\x1f" in line:
            parts = line.split("\x1f")
            current = {"hash": parts[0], "short_hash": parts[1], "author": parts[2], "date": parts[3], "message": parts[4], "stats": ""}
            commits.append(current)
        elif current and line.strip():
            current["stats"] = line.strip()
    return commits


def commit_detail(repo_path: str, commit_hash: str) -> dict[str, Any]:
    meta = run_git(repo_path, ["show", "--quiet", "--pretty=format:%H%x1f%h%x1f%an%x1f%ad%x1f%s", "--date=iso", commit_hash])
    files = run_git(repo_path, ["show", "--name-status", "--pretty=format:", commit_hash], timeout=60)
    patch = run_git(repo_path, ["show", "--format=", "--find-renames", commit_hash], timeout=60)
    parts = meta["stdout"].split("\x1f") if meta["ok"] else []
    return {
        "hash": parts[0] if len(parts) > 0 else commit_hash,
        "short_hash": parts[1] if len(parts) > 1 else commit_hash[:7],
        "author": parts[2] if len(parts) > 2 else None,
        "date": parts[3] if len(parts) > 3 else None,
        "message": parts[4] if len(parts) > 4 else None,
        "files": files["stdout"].splitlines() if files["ok"] and files["stdout"] else [],
        "diff": patch["stdout"] if patch["ok"] else patch.get("stderr", ""),
    }


def open_version(repo_path: str, commit_hash: str) -> dict[str, Any]:
    root = Path(repo_path).expanduser().resolve()
    short = commit_hash[:12]
    target = root / ".workbench" / "versions" / short
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return {"ok": True, "path": str(target), "message": "Version worktree already exists."}
    result = run_git(str(root), ["worktree", "add", "--detach", str(target), commit_hash], timeout=120)
    if result["ok"]:
        return {"ok": True, "path": str(target), "message": result["stdout"]}
    return result


def create_branch_from(repo_path: str, name: str, commit_hash: str | None = None) -> dict:
    args = ["branch", name]
    if commit_hash:
        args.append(commit_hash)
    return run_git(repo_path, args)


def branches(repo_path: str) -> dict[str, Any]:
    branch_result = run_git(repo_path, ["branch", "--format=%(refname:short)"])
    current = status(repo_path).get("branch")
    return {"current": current, "branches": branch_result["stdout"].splitlines() if branch_result["ok"] else []}


def switch_branch(repo_path: str, name: str) -> dict:
    if status(repo_path)["changes"]:
        return {"ok": False, "stderr": "Refusing to switch branches with uncommitted changes.", "stdout": ""}
    return run_git(repo_path, ["switch", name])


def restore_to(repo_path: str, commit_hash: str, confirm: bool, create_backup_branch: bool = True) -> dict[str, Any]:
    current_status = status(repo_path)
    if current_status["changes"]:
        return {"ok": False, "stderr": "Restore blocked: working tree has uncommitted changes.", "changes": current_status["changes"]}
    if not confirm:
        return {"ok": False, "stderr": "Restore requires explicit confirmation."}
    backup = None
    if create_backup_branch:
        backup = f"backup/workbench-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        backup_result = run_git(repo_path, ["branch", backup])
        if not backup_result["ok"]:
            return backup_result
    result = run_git(repo_path, ["reset", "--hard", commit_hash], timeout=120)
    result["backup_branch"] = backup
    return result


def _file_has_secret(path: Path) -> bool:
    if path.stat().st_size > 1024 * 1024:
        return False
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")[:200000]
    except OSError:
        return False
    return any(pattern.search(text) for pattern in SECRET_REGEXES)
