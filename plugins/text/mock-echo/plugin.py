"""Mock text plugin — a TEST DOUBLE, not a model.

Produces deterministic narration from a NarrationRequest's structured
event + game-state snapshot, so the demo and tests can exercise the
text path with no LLM, no server and no GPU. The output is templated
on purpose: it proves the plumbing, and its dullness is the point —
a real text plugin swaps in by manifest, not by core changes.
"""

from __future__ import annotations

import time
from pathlib import Path

from dungeon_core.contracts import NarrationResult


class MockEchoTextPlugin:
    def __init__(self, manifest=None, plugin_dir=None):
        self.manifest = manifest
        self.plugin_dir = Path(plugin_dir) if plugin_dir else None
        self.loaded = False
        self.narrate_calls = 0

    def load(self) -> None:
        self.loaded = True

    def unload(self) -> None:
        self.loaded = False

    def health(self) -> dict:
        return {"ok": True, "backend": "mock", "detail": "test double, always healthy"}

    def narrate(self, req) -> NarrationResult:
        started = time.perf_counter()
        self.narrate_calls += 1
        event = req.event or {}
        state = req.game_state or {}
        action = event.get("action", "look around")
        place = event.get("location") or req.scene_id or "an unknown place"
        detail = event.get("detail", "")
        hp = state.get("hp")
        hp_text = f" You feel steady ({hp} HP)." if hp is not None else ""
        detail_text = f" {detail}" if detail else ""
        text = (
            f"[mock narration] You {action} — {place}.{detail_text}{hp_text} "
            f"The air is cold, and somewhere ahead something waits."
        )
        return NarrationResult(
            text=text,
            plugin_id=self.manifest.id if self.manifest else "mock-echo",
            plugin_version=self.manifest.version if self.manifest else "0.1.0",
            seconds=time.perf_counter() - started,
        )


def create_plugin(manifest, plugin_dir):
    return MockEchoTextPlugin(manifest=manifest, plugin_dir=plugin_dir)
