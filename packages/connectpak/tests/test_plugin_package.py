"""The generated plugin and the OpenAI Plugins Directory package."""

from __future__ import annotations

import importlib.util
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _gen():
    spec = importlib.util.spec_from_file_location("gen_plugins", ROOT / "scripts" / "gen_plugins.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_plugin_pins_the_published_package_version() -> None:
    gen = _gen()
    manifest = json.loads((ROOT / "plugins/connectpak/.claude-plugin/plugin.json").read_text())
    args = manifest["mcpServers"]["connectpak"]["args"]
    assert args == ["--from", f"connectpak=={gen._version()}", "connectpak"]


def test_directory_zip_ships_skills_without_local_mcp(tmp_path: Path) -> None:
    gen = _gen()
    out = tmp_path / "connectpak.zip"
    gen.build_codex_directory_zip(out)
    with zipfile.ZipFile(out) as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read(".codex-plugin/plugin.json"))
    assert "codex.mcp.json" not in names and ".mcp.json" not in names
    assert not any(n.startswith(".claude-plugin/") for n in names)
    assert "mcpServers" not in manifest
    assert {f"skills/{d}/SKILL.md" for d in gen.SKILL_DIRS.values()} <= names
    ui = manifest["interface"]
    assert len(ui["shortDescription"]) <= 30
    for key in ("websiteURL", "supportURL", "privacyPolicyURL", "termsOfServiceURL"):
        assert ui[key].startswith("https://")
    for key in ("logo", "composerIcon"):
        assert ui[key].removeprefix("./") in names
    assert "codex mcp add connectpak" in ui["longDescription"]
