def test_skeleton_exists(tmp_repo):
    assert (tmp_repo / ".github" / "tools").is_dir()
    assert (tmp_repo / ".github" / ".cache" / "memory" / "decisions").is_dir()
