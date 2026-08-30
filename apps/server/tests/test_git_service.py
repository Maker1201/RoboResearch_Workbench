from app.git_service import is_blocked_file, list_candidate_files, parse_status


def test_parse_status_handles_modified_and_untracked_files():
    changes = parse_status(" M src/policy.py\n?? scripts/eval.py\n")
    assert changes == [
        {"status": "M", "path": "src/policy.py"},
        {"status": "??", "path": "scripts/eval.py"},
    ]


def test_blocked_files_protect_secrets_and_large_research_outputs():
    assert is_blocked_file(".env")
    assert is_blocked_file("checkpoints/model.ckpt")
    assert is_blocked_file("datasets/raw/file.txt")
    assert not is_blocked_file("src/policy.py")


def test_candidate_files_include_staged_changes(tmp_path):
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@local"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
    tracked = repo / "tracked.py"
    tracked.write_text("original\n")
    subprocess.run(["git", "-C", str(repo), "add", "tracked.py"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "init", "-q"], check=True)

    # 已暂存的修改：工作区与暂存区一致，ls-files --modified 不会列出，但必须可提交
    tracked.write_text("staged change\n")
    subprocess.run(["git", "-C", str(repo), "add", "tracked.py"], check=True)
    (repo / "new_dir").mkdir()
    (repo / "new_dir" / "feature.py").write_text("new\n")

    candidates = list_candidate_files(str(repo))
    assert "tracked.py" in candidates
    assert "new_dir/feature.py" in candidates


