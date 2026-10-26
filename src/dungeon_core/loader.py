"""Plugin discovery and loading.

A plugin is a folder under ``plugins/<kind>/<id>/`` containing a
``plugin.yaml`` and, for code plugins, a ``plugin.py``. Declarative
(text) plugins may have no code at all — discovery still finds them via
their manifest.

A code plugin's ``plugin.py`` must provide ONE of:
  - ``create_plugin(manifest, plugin_dir)``  (preferred factory), or
  - ``PLUGIN_CLASS`` naming a class, or
  - a class named ``Plugin``.
Plugin classes are constructed as ``Cls(manifest=..., plugin_dir=...)``
when the factory route is not used.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from typing import Any, Optional

from .errors import PluginLoadError
from .manifest import PluginManifest, load_manifest


def discover_manifests(
    plugins_root: str | Path, kind: Optional[str] = None
) -> list[PluginManifest]:
    """Find every plugin.yaml under plugins_root/<kind>/<id>/."""
    root = Path(plugins_root)
    manifests: list[PluginManifest] = []
    if not root.is_dir():
        return manifests
    kind_dirs = [root / kind] if kind else sorted(p for p in root.iterdir() if p.is_dir())
    for kind_dir in kind_dirs:
        if not kind_dir.is_dir():
            continue
        for plugin_dir in sorted(p for p in kind_dir.iterdir() if p.is_dir()):
            yaml_path = plugin_dir / "plugin.yaml"
            if yaml_path.is_file():
                manifests.append(load_manifest(yaml_path))
    return manifests


def find_manifest(
    plugins_root: str | Path, plugin_id: str
) -> Optional[PluginManifest]:
    for manifest in discover_manifests(plugins_root):
        if manifest.id == plugin_id:
            return manifest
    return None


def load_plugin_module(manifest: PluginManifest) -> Any:
    """Import a plugin folder's plugin.py as a standalone module."""
    plugin_dir = manifest.plugin_dir
    if plugin_dir is None:
        raise PluginLoadError(f"plugin {manifest.id!r}: manifest has no source path")
    plugin_py = plugin_dir / "plugin.py"
    if not plugin_py.is_file():
        raise PluginLoadError(
            f"plugin {manifest.id!r}: no plugin.py in {plugin_dir} "
            "(declarative plugins cannot be instantiated as code)"
        )
    module_name = "dungeon_plugin_" + re.sub(r"[^0-9a-zA-Z_]", "_", manifest.id)
    spec = importlib.util.spec_from_file_location(module_name, plugin_py)
    if spec is None or spec.loader is None:
        raise PluginLoadError(f"plugin {manifest.id!r}: cannot import {plugin_py}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # surface the real cause, wrapped once
        raise PluginLoadError(
            f"plugin {manifest.id!r}: importing plugin.py failed: {exc}"
        ) from exc
    return module


def instantiate_plugin(manifest: PluginManifest) -> Any:
    """Import plugin.py and create the plugin instance."""
    module = load_plugin_module(manifest)
    plugin_dir = manifest.plugin_dir
    factory = getattr(module, "create_plugin", None)
    if callable(factory):
        return factory(manifest, plugin_dir)
    cls = None
    class_name = getattr(module, "PLUGIN_CLASS", None)
    if class_name:
        cls = getattr(module, class_name, None)
    if cls is None:
        cls = getattr(module, "Plugin", None)
    if cls is None:
        raise PluginLoadError(
            f"plugin {manifest.id!r}: plugin.py defines neither "
            "create_plugin(), PLUGIN_CLASS, nor a Plugin class"
        )
    return cls(manifest=manifest, plugin_dir=plugin_dir)


def load_plugin_by_id(plugins_root: str | Path, plugin_id: str) -> Any:
    manifest = find_manifest(plugins_root, plugin_id)
    if manifest is None:
        raise PluginLoadError(
            f"no plugin with id {plugin_id!r} under {plugins_root}"
        )
    return instantiate_plugin(manifest)
