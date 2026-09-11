import os
import importlib


def test_agents_md_exists():
    assert os.path.exists("AGENTS.md"), "AGENTS.md must exist at repo root"


def test_access_test_exists():
    assert os.path.exists("AGENT_ACCESS_TEST.md"), "AGENT_ACCESS_TEST.md must exist at repo root"


def test_adapters_gitkeep_exists():
    assert os.path.exists(os.path.join("src", "adapters", ".gitkeep")), "src/adapters/.gitkeep must exist"


def test_adapter_class_importable():
    module = importlib.import_module("src.platform.adapter")
    assert hasattr(module, "Adapter"), "Adapter class must be defined in src.platform.adapter"
