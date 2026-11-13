"""The generated plugin and the OpenAI Plugins Directory package."""

from __future__ import annotations

import importlib.util
import json
import sys
import tomllib
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


def test_claude_directory_default_is_skills_only() -> None:
    """Without a Verified org, the directory refuses local servers and code files."""
    gen = _gen()
    files = gen.render_claude_directory()
    manifest = json.loads(files[".claude-plugin/plugin.json"])
    assert "mcpServers" not in manifest and "userConfig" not in manifest
    allowed = (".md", ".json", ".png")
    assert all(n.endswith(allowed) or n == "LICENSE" for n in files), sorted(files)
    assert {f"skills/{d}/SKILL.md" for d in gen.SKILL_DIRS.values()} <= set(files)
    readme = files["README.md"].decode()
    assert f"uvx --from connectpak=={gen._version()} connectpak" in readme
    assert len(readme.split()) >= 40
    for skill in gen.SKILL_DIRS.values():
        assert "claude mcp add connectpak" in files[f"skills/{skill}/SKILL.md"].decode()


def test_claude_directory_bundle_with_server_is_self_contained() -> None:
    gen = _gen()
    files = gen.render_claude_directory(with_server=True)
    manifest = json.loads(files[".claude-plugin/plugin.json"])
    server = manifest["mcpServers"]["connectpak"]
    assert server["args"] == ["--from", "${CLAUDE_PLUGIN_ROOT}/vendor/connectpak", "connectpak"]
    assert set(server["env"]) == {"CLAUDE_PLUGIN_OPTION_CONNECTION",
                                  "CLAUDE_PLUGIN_OPTION_ENGINE"}

    # Only the vendored package has a pyproject, and it redirects nothing.
    assert [n for n in files if n.endswith("pyproject.toml")] == [
        "vendor/connectpak/pyproject.toml"
    ]
    vendored = tomllib.loads(files["vendor/connectpak/pyproject.toml"].decode())
    assert "uv" not in vendored.get("tool", {})
    assert all("==" in r for r in vendored["build-system"]["requires"])

    # Claude-only: no Codex files, which forward credential env vars.
    assert not any("codex" in n for n in files)

    src = "vendor/connectpak/src/connectpak"
    assert f"{src}/core/server.py" in files and f"{src}/launcher/__main__.py" in files
    for e in gen.ENGINES:
        track, name = e.package.split("-", 1)
        assert f"{src}/{track}/{name}/connector.py" in files
    assert not any("__pycache__" in n for n in files)
