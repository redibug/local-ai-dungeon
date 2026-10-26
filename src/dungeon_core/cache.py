"""Scene cache: rendered rooms on disk, keyed by scene + state.

A room is identified by its ``scene_id`` plus a hash of its state
(entities, characters, mood, ...). Revisiting a room whose state has
not changed is a cache hit — the stored image is served and no plugin
is called at all. Any state change produces a different key, which is
how core knows a revisit needs the fallback strategy instead.

The index is a single JSON file next to the cached images. Saves store
SceneRequests + image paths, never plugin internals, so a cache built
by one plugin stays valid after a plugin swap.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Optional


def compute_state_hash(state: Any) -> str:
    """Stable hash of a room state (dict, dataclass, or string)."""
    if is_dataclass(state) and not isinstance(state, type):
        state = asdict(state)
    payload = json.dumps(state, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def cache_key(scene_id: str, state: Any) -> str:
    return f"{scene_id}:{compute_state_hash(state)}"


class SceneCache:
    def __init__(self, cache_dir: str | Path) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.cache_dir / "index.json"
        self._index: dict[str, dict[str, Any]] = {}
        if self.index_path.is_file():
            try:
                self._index = json.loads(self.index_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._index = {}

    def _save(self) -> None:
        self.index_path.write_text(
            json.dumps(self._index, indent=2, sort_keys=True), encoding="utf-8"
        )

    def get(self, scene_id: str, state: Any) -> Optional[str]:
        """Return the cached image path for this exact room state, or None."""
        entry = self._index.get(cache_key(scene_id, state))
        if not entry:
            return None
        image = entry.get("image")
        if image and Path(image).is_file():
            return image
        return None

    def put(self, scene_id: str, state: Any, image_path: str) -> str:
        key = cache_key(scene_id, state)
        self._index[key] = {
            "scene_id": scene_id,
            "state_hash": compute_state_hash(state),
            "image": str(image_path),
        }
        self._save()
        return key

    def __len__(self) -> int:
        return len(self._index)
