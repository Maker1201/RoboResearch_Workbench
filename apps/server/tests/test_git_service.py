from app.git_service import is_blocked_file, parse_status


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

