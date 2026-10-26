"""dungeon_core — the model-agnostic core of the local AI dungeon crawler.

Core never knows a model. It speaks in contracts (SceneRequest /
NarrationRequest), reads plugin manifests, plans fallbacks from
declared capabilities, arbitrates the GPU, and caches scenes.
Everything model-specific lives in a plugin folder.
"""

from .arbiter import GPUArbiter
from .cache import SceneCache, cache_key, compute_state_hash
from .contracts import (
    CharacterInScene,
    EntityInScene,
    NarrationRequest,
    NarrationResult,
    SceneRequest,
    SceneResult,
    derive_seed,
)
from .errors import ManifestError, PluginLoadError, PluginNotReady
from .fallback import choose_character_strategy, choose_room_strategy
from .loader import (
    discover_manifests,
    find_manifest,
    instantiate_plugin,
    load_plugin_by_id,
)
from .manifest import (
    Capabilities,
    NativeSettings,
    PluginManifest,
    Requirements,
    load_manifest,
)

__version__ = "0.1.0"

__all__ = [
    "GPUArbiter",
    "SceneCache",
    "cache_key",
    "compute_state_hash",
    "CharacterInScene",
    "EntityInScene",
    "NarrationRequest",
    "NarrationResult",
    "SceneRequest",
    "SceneResult",
    "derive_seed",
    "ManifestError",
    "PluginLoadError",
    "PluginNotReady",
    "choose_character_strategy",
    "choose_room_strategy",
    "discover_manifests",
    "find_manifest",
    "instantiate_plugin",
    "load_plugin_by_id",
    "Capabilities",
    "NativeSettings",
    "PluginManifest",
    "Requirements",
    "load_manifest",
]
