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


import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".github" / "tools"))
from config import Config, load_config  # noqa: E402


def test_load_config_returns_dataclass(tmp_repo, request):
    src = Path(request.config.rootpath) / ".github" / "config.yaml"
    (tmp_repo / ".github" / "config.yaml").write_text(src.read_text())
    cfg = load_config(tmp_repo / ".github" / "config.yaml")
    assert isinstance(cfg, Config)
    assert cfg.profile == "auto"
    assert cfg.models["thinking"] == "claude-opus-4-6"
    assert cfg.memory_budgets["checkpoint"]["soft"] == 2000


def test_load_config_missing_file_raises(tmp_repo):
    with __import__("pytest").raises(FileNotFoundError):
        load_config(tmp_repo / ".github" / "config.yaml")


from config import resolve_profile, resolve_feature  # noqa: E402


def test_resolve_profile_tiny():
    thresholds = {
        "tiny":   {"max_files": 50,    "max_loc": 2000},
        "small":  {"max_files": 500,   "max_loc": 20000},
        "medium": {"max_files": 5000,  "max_loc": 200000},
        "large":  {"max_files": 50000, "max_loc": 2000000},
    }
    assert resolve_profile(files=10, loc=500, thresholds=thresholds) == "tiny"
    assert resolve_profile(files=200, loc=10000, thresholds=thresholds) == "small"
    assert resolve_profile(files=2000, loc=100000, thresholds=thresholds) == "medium"
    assert resolve_profile(files=20000, loc=500000, thresholds=thresholds) == "large"
    assert resolve_profile(files=100000, loc=5000000, thresholds=thresholds) == "xlarge"


def test_resolve_profile_files_alone_can_force_higher_tier():
    thresholds = {
        "tiny":   {"max_files": 50,    "max_loc": 2000},
        "small":  {"max_files": 500,   "max_loc": 20000},
        "medium": {"max_files": 5000,  "max_loc": 200000},
        "large":  {"max_files": 50000, "max_loc": 2000000},
    }
    assert resolve_profile(files=2000, loc=500, thresholds=thresholds) == "medium"


def test_resolve_feature_auto_uses_profile_default():
    assert resolve_feature("code_graph", "auto", profile="tiny") == "off"
    assert resolve_feature("code_graph", "auto", profile="small") == "symbols-only"
    assert resolve_feature("code_graph", "auto", profile="medium") == "full"


def test_resolve_feature_explicit_overrides_profile():
    assert resolve_feature("code_graph", "full", profile="tiny") == "full"
    assert resolve_feature("validator_gate", "off", profile="large") == "off"
