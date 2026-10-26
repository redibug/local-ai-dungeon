"""Runnable end-to-end demo using the two mock plugins.

    python -m dungeon_core.demo

No GPU, no models, no servers: the mock text plugin narrates from a
template and the mock image plugin writes a deterministic placeholder
PNG. What the demo actually proves is the *core* flow:

  1. narrate a move (text plugin loaded via the GPU arbiter),
  2. render a first-visit scene (image plugin loaded, text unloaded),
  3. revisit the room unchanged  -> scene cache hit, NO render,
  4. revisit the room changed    -> fallback strategy renders an update.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from .arbiter import GPUArbiter
from .cache import SceneCache
from .contracts import (
    CharacterInScene,
    EntityInScene,
    NarrationRequest,
    SceneRequest,
    derive_seed,
)
from .fallback import choose_character_strategy, choose_room_strategy
from .loader import load_plugin_by_id


def find_repo_root() -> Path:
    env = os.environ.get("LOCAL_AI_DUNGEON_ROOT")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    # src/dungeon_core/demo.py -> repo root is two levels up, when
    # running from a source checkout / editable install.
    candidate = here.parents[2]
    if (candidate / "plugins").is_dir():
        return candidate
    cwd = Path.cwd()
    if (cwd / "plugins").is_dir():
        return cwd
    return candidate


def room_state(chest_state: str) -> dict:
    """Serializable room state used as the cache key's state part."""
    return {
        "location": {"type": "entrance hall", "materials": ["wet stone"]},
        "entities": [{"kind": "chest", "state": chest_state}],
        "mood": "dread",
        "lighting": "torchlight",
    }


def build_scene(save_id: str, chest_state: str, change=None, previous=None) -> SceneRequest:
    return SceneRequest(
        scene_id="dungeon1/entrance",
        seed=derive_seed(save_id, "dungeon1/entrance"),
        location={"type": "entrance hall", "materials": ["wet stone"],
                  "features": ["iron torches", "flooded floor"]},
        entities=[EntityInScene(kind="chest", state=chest_state)],
        characters=[CharacterInScene(char_id="player", action="entering, sword drawn")],
        previous_image=previous,
        change=change,
        mood="dread",
        lighting="torchlight",
        aspect="16:9",
    )


def main() -> int:
    root = find_repo_root()
    plugins_root = root / "plugins"
    out_root = root / "outputs" / "demo"
    if out_root.exists():
        shutil.rmtree(out_root)
    image_out = out_root / "images"
    cache = SceneCache(out_root / "cache")
    arbiter = GPUArbiter()
    save_id = "demo-save"
    game_state = {"hp": 20, "max_hp": 20, "gold": 0, "depth": 1}

    print("=== Local AI Dungeon — mock demo ===")
    print(f"plugins: {plugins_root}")

    text_plugin = load_plugin_by_id(plugins_root, "mock-echo")
    image_plugin = load_plugin_by_id(plugins_root, "mock-placeholder")
    image_plugin.output_dir = image_out
    print(f"text plugin:  {text_plugin.manifest.id} (backend: mock — test double)")
    print(f"image plugin: {image_plugin.manifest.id} (backend: mock — test double)")

    # 1) Narrate a move -------------------------------------------------
    arbiter.load(text_plugin)
    narration = text_plugin.narrate(
        NarrationRequest(
            event={"action": "enter", "location": "the entrance hall",
                   "detail": "A chest sits against the far wall."},
            game_state=game_state,
            scene_id="dungeon1/entrance",
        )
    )
    print(f"\n[1] narration (arbiter loaded: {arbiter.current_id})")
    print(f"    {narration.text}")
    arbiter.unload_current()

    # 2) First visit: render -------------------------------------------
    state_v1 = room_state("closed")
    strategy = choose_room_strategy(image_plugin.manifest, revisited=False, changed=False)
    char_strategy = choose_character_strategy(image_plugin.manifest, has_ref=False)
    arbiter.load(image_plugin)
    scene = build_scene(save_id, "closed")
    result = image_plugin.generate(scene, strategy=strategy)
    cache.put(scene.scene_id, state_v1, result.image)
    print(f"\n[2] first visit -> strategy={strategy}, character strategy={char_strategy}")
    print(f"    rendered {result.image} in {result.seconds:.3f}s "
          f"(generate calls: {image_plugin.generate_calls})")

    # 3) Revisit unchanged: cache hit ----------------------------------
    strategy = choose_room_strategy(image_plugin.manifest, revisited=True, changed=False)
    cached = cache.get(scene.scene_id, state_v1)
    print(f"\n[3] revisit unchanged -> strategy={strategy}")
    print(f"    cache hit: {cached} (generate calls still: {image_plugin.generate_calls})")

    # 4) Revisit changed: fallback strategy ----------------------------
    game_state["gold"] = 15
    state_v2 = room_state("open, empty")
    strategy = choose_room_strategy(image_plugin.manifest, revisited=True, changed=True)
    scene_changed = build_scene(save_id, "open, empty",
                                change="the chest is now open and empty",
                                previous=cached)
    result2 = image_plugin.generate(scene_changed, strategy=strategy)
    cache.put(scene_changed.scene_id, state_v2, result2.image)
    arbiter.unload_current()
    print(f"\n[4] revisit changed (chest opened) -> strategy={strategy}")
    print(f"    re-rendered via {strategy}: {result2.image} "
          f"(generate calls: {image_plugin.generate_calls})")
    print(f"    cache now holds {len(cache)} room states")

    print("\nDemo OK: narrate -> render -> cache hit -> changed revisit, "
          "all with mock plugins.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
