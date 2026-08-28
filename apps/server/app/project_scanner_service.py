from __future__ import annotations

from pathlib import Path
from typing import Any

from . import git_service


def scan_project(path_value: str) -> dict[str, Any]:
    path = Path(path_value).expanduser().resolve()
    if not path.exists() or not path.is_dir():
        raise ValueError(f"Project folder does not exist: {path_value}")

    files = {child.name for child in path.iterdir()}
    recursive_names = _sample_recursive_names(path)
    git_status = git_service.status(str(path)) if (path / ".git").exists() else {"is_repo": False, "branch": None, "remote_url": None, "changes": []}
    tags: list[str] = []
    detections: dict[str, bool] = {
        "git_repository": (path / ".git").exists(),
        "github_remote": _is_github_remote(git_status.get("remote_url")),
        "github_config": (path / ".github").exists(),
        "ros2": "package.xml" in files or any(name.endswith(".launch.py") for name in recursive_names),
        "robotics_assets": any(name.endswith((".urdf", ".xacro")) for name in recursive_names),
        "python": bool({"pyproject.toml", "requirements.txt", "setup.py", "setup.cfg"} & files),
        "node": "package.json" in files,
        "cpp": "CMakeLists.txt" in files,
        "docker": "Dockerfile" in files or any(name.startswith("docker-compose") for name in files),
        "readme": any(name.lower().startswith("readme") for name in files),
    }
    if detections["ros2"]:
        tags.append("ROS2")
    if detections["robotics_assets"]:
        tags.append("Robotics")
    if detections["python"]:
        tags.append("Python")
    if detections["node"]:
        tags.append("Node")
    if detections["cpp"]:
        tags.append("C/C++")
    if detections["docker"]:
        tags.append("Docker")

    readme = next((child.name for child in path.iterdir() if child.is_file() and child.name.lower().startswith("readme")), None)
    project_type = infer_project_type(tags, detections)
    registration_case = infer_registration_case(detections["git_repository"], detections["github_remote"])

    return {
        "name": path.name,
        "path": str(path),
        "description": _description_from_readme(path / readme) if readme else None,
        "project_type": project_type,
        "tags": tags,
        "detections": detections,
        "git": git_status,
        "branch": git_status.get("branch"),
        "remote_url": git_status.get("remote_url"),
        "readme": readme,
        "registration_case": registration_case,
        "suggested_stages": default_stages(project_type),
    }


def list_directories(path_value: str | None = None) -> dict[str, Any]:
    path = Path(path_value or str(Path.home())).expanduser().resolve()
    if not path.exists() or not path.is_dir():
        raise ValueError(f"Folder does not exist: {path}")
    items = []
    for child in sorted(path.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
        if child.name.startswith("."):
            continue
        if child.is_dir():
            items.append({"name": child.name, "path": str(child), "is_dir": True})
    parent = str(path.parent) if path.parent != path else None
    return {"path": str(path), "parent": parent, "items": items}


def infer_project_type(tags: list[str], detections: dict[str, bool]) -> str:
    if detections.get("ros2"):
        return "ROS2 / Robotics"
    if detections.get("robotics_assets"):
        return "Robotics"
    if detections.get("python"):
        return "Python Research"
    if detections.get("node"):
        return "Web / Node"
    if detections.get("cpp"):
        return "C/C++"
    return "Research Project"


def infer_registration_case(has_git: bool, has_github: bool) -> str:
    if has_git and has_github:
        return "Local + Git + GitHub"
    if has_git:
        return "Local + Git"
    return "Local Only"


def default_stages(project_type: str) -> list[dict[str, Any]]:
    base = ["Literature", "Environment", "Baseline", "Development", "Experiments", "Evaluation", "Documentation"]
    if "ROS2" in project_type or "Robotics" in project_type:
        base = ["Literature", "Environment", "Simulation", "Development", "Real Robot", "Evaluation", "Documentation"]
    return [{"title": title, "status": "pending", "weight": 1, "progress": 0, "order_index": index} for index, title in enumerate(base)]


def _is_github_remote(remote_url: str | None) -> bool:
    return bool(remote_url and "github.com" in remote_url.lower())


def _sample_recursive_names(path: Path, limit: int = 1200) -> list[str]:
    names: list[str] = []
    ignored = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"}
    for child in path.rglob("*"):
        if len(names) >= limit:
            break
        if any(part in ignored for part in child.parts):
            continue
        names.append(child.name)
    return names


def _description_from_readme(readme: Path) -> str | None:
    try:
        for line in readme.read_text(encoding="utf-8", errors="ignore").splitlines():
            clean = line.strip().strip("#").strip()
            if clean:
                return clean[:300]
    except OSError:
        return None
    return None
