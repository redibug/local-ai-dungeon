"""Canonical contracts between core and plugins.

Core speaks ONLY in these structures. A SceneRequest describes a scene
semantically — location, entities, characters, what changed — and never
contains a prompt string. Compiling this into a model's prompt dialect
(tags + negative for SDXL, natural language for Z-Image / FLUX, ...) is
each plugin's private job. See docs/PLUGIN_ARCHITECTURE.md.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class CharacterInScene:
    """A character appearing in a scene.

    ``description`` is a fixed, verbatim appearance block owned by core's
    character record (e.g. "woman, red braided hair, scar on left
    cheek"). Plugins may use it as prompt text, as an IP-Adapter /
    multi-reference input via ``ref_image``, or both.
    """

    char_id: str
    action: str = ""
    ref_image: Optional[str] = None
    description: str = ""


@dataclass
class EntityInScene:
    """A thing in the room whose state matters (chest, door, torch...)."""

    kind: str
    state: str = ""


@dataclass
class SceneRequest:
    """The only thing core ever sends an image plugin."""

    scene_id: str
    seed: int
    location: dict[str, Any] = field(default_factory=dict)
    entities: list[EntityInScene] = field(default_factory=list)
    characters: list[CharacterInScene] = field(default_factory=list)
    previous_image: Optional[str] = None
    change: Optional[str] = None
    mood: str = ""
    lighting: str = ""
    aspect: str = "16:9"


@dataclass
class SceneResult:
    image: str
    actual_seed: int
    seconds: float
    compiled_prompt: str
    plugin_id: str
    plugin_version: str
    negative_prompt: Optional[str] = None
    strategy: str = "txt2img"


@dataclass
class NarrationRequest:
    """What core sends a text plugin: a structured event + a snapshot
    of game state (owned by core code, never by the model)."""

    event: dict[str, Any] = field(default_factory=dict)
    game_state: dict[str, Any] = field(default_factory=dict)
    scene_id: Optional[str] = None
    tone: str = "dark fantasy"
    target_length: str = "one short paragraph"


@dataclass
class NarrationResult:
    text: str
    plugin_id: str
    plugin_version: str
    seconds: float = 0.0


def derive_seed(save_id: str, scene_id: str) -> int:
    """Deterministic per-room seed: the same save + room always derives
    the same seed, so a room can be reproduced (and, combined with the
    scene cache, recognised) across sessions and plugin swaps.

    Returns a non-negative 31-bit int, safe for every sampler we know.
    """
    digest = hashlib.sha256(f"{save_id}:{scene_id}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) & 0x7FFFFFFF


def field_of(obj: Any, name: str, default: Any = "") -> Any:
    """Read ``name`` from a dataclass instance or a plain dict.

    Scene data crosses the core/plugin boundary in both shapes (core
    builds dataclasses; JSON packs and saves use dicts), so compilers
    use this instead of caring which one they got.
    """
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)
