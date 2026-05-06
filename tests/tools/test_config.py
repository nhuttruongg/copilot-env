def test_skeleton_exists(tmp_repo):
    assert (tmp_repo / ".github" / "tools").is_dir()
    assert (tmp_repo / ".github" / ".cache" / "memory" / "decisions").is_dir()


import yaml
from pathlib import Path


def test_config_yaml_exists_and_has_profile_field(tmp_repo, request):
    src = Path(request.config.rootpath) / ".github" / "config.yaml"
    dst = tmp_repo / ".github" / "config.yaml"
    dst.write_text(src.read_text())
    data = yaml.safe_load(dst.read_text())
    assert data["profile"] == "auto"
    assert "profile_thresholds" in data
    assert "features" in data
    assert data["features"]["code_graph"] == "auto"
    assert "memory" in data
    assert data["memory"]["budgets"]["checkpoint"]["soft"] == 2000
    assert "models" in data
    assert data["models"]["thinking"] == "claude-opus-4-6"
