from __future__ import annotations

import subprocess
from pathlib import Path


BLOCKED_PATTERNS = (
    ".env",
    "checkpoint",
    "checkpoints",
    "dataset",
    "datasets",
    "wandb",
    "runs/",
    "outputs/",
    ".pt",
    ".pth",
    ".ckpt",
    ".onnx",
)


def run_git(repo_path: str, args: list[str], timeout: int = 30) -> dict:
    path = Path(repo_path).expanduser().resolve()
    if not path.exists():
        raise ValueError(f"Path does not exist: {repo_path}")
    command = ["git", "-C", str(path), *args]
    completed = subprocess.run(command, text=True, capture_output=True, timeout=timeout, check=False)
    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def is_git_repo(repo_path: str) -> bool:
    result = run_git(repo_path, ["rev-parse", "--is-inside-work-tree"])
    return result["ok"] and result["stdout"] == "true"


def status(repo_path: str) -> dict:
    branch = run_git(repo_path, ["branch", "--show-current"])
    remote = run_git(repo_path, ["remote", "get-url", "origin"])
    porcelain = run_git(repo_path, ["status", "--short"])
    log = run_git(repo_path, ["log", "--oneline", "-8"])
    return {
        "is_repo": is_git_repo(repo_path),
        "branch": branch["stdout"] if branch["ok"] else None,
        "remote_url": remote["stdout"] if remote["ok"] else None,
        "changes": parse_status(porcelain["stdout"]),
        "recent_commits": log["stdout"].splitlines() if log["ok"] and log["stdout"] else [],
    }


def diff(repo_path: str, file_path: str | None = None) -> dict:
    args = ["diff", "--"]
    if file_path:
        args.append(file_path)
    return run_git(repo_path, args, timeout=60)


def commit(repo_path: str, files: list[str], message: str) -> dict:
    blocked = [file for file in files if is_blocked_file(file)]
    if blocked:
        return {"ok": False, "stderr": f"Refusing to stage risky files: {', '.join(blocked)}", "stdout": ""}
    add_result = run_git(repo_path, ["add", "--", *files])
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
    return run_git(repo_path, args, timeout=120)


def parse_status(output: str) -> list[dict[str, str]]:
    changes = []
    for line in output.splitlines():
        if not line:
            continue
        changes.append({"status": line[:2].strip() or "?", "path": line[3:].strip()})
    return changes


def is_blocked_file(file_path: str) -> bool:
    clean = file_path.lower()
    return any(pattern in clean for pattern in BLOCKED_PATTERNS)

