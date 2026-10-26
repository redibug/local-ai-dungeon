"""Fallback planning: pure functions over a manifest's capabilities.

Core asks these *before* calling a plugin, so the same game logic
works for every plugin and degradation is explicit, never silent:

    room revisited, unchanged -> "cache"   (no plugin call at all)
    room revisited, changed   -> "edit" | "inpaint" | "img2img" | "txt2img"
    character with a ref      -> "native_ref" | "ip_adapter" | "prompt_only"

These functions look at capabilities only. They never import a plugin.
"""

from __future__ import annotations

from .manifest import PluginManifest


def choose_room_strategy(
    manifest: PluginManifest, revisited: bool, changed: bool
) -> str:
    """How should this scene be produced?

    Returns one of: "cache", "edit", "inpaint", "img2img", "txt2img".
    """
    if not revisited:
        return "txt2img"
    if not changed:
        return "cache"
    caps = manifest.capabilities
    if caps.native_edit:
        return "edit"
    if caps.inpaint:
        return "inpaint"
    if caps.img2img:
        return "img2img"
    return "txt2img"


def choose_character_strategy(manifest: PluginManifest, has_ref: bool) -> str:
    """How will a character's appearance be anchored in this scene?

    Returns one of: "native_ref", "ip_adapter", "prompt_only".
    "prompt_only" is the honest weak path: the character's fixed
    description block is all the plugin gets, and core should warn the
    player that consistency will drift with this plugin.
    """
    if not has_ref:
        return "prompt_only"
    mode = manifest.capabilities.reference_images
    if mode in ("native_multi_ref", "native_edit"):
        return "native_ref"
    if mode in ("ip_adapter", "face_id"):
        return "ip_adapter"
    return "prompt_only"
