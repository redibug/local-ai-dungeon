"""Conformance runner: run the shared pack against one image plugin.

    python -m dungeon_core.conformance [--plugin mock-placeholder]
                                       [--vram-gb 8]

Loads conformance/pack.json, builds a SceneRequest for every scene
(10 standard + the character-consistency set + the room-revisit pair),
times generate(), and prints a plain verdict. Scoring bands and the
full rationale live in conformance/README.md.

Peak VRAM is taken from the plugin's estimate() for now — real
measurement needs a GPU-side sampler and is TODO. Verdicts therefore
use declared requirements vs. the --vram-gb you pass (default 8).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .contracts import CharacterInScene, EntityInScene, SceneRequest, derive_seed
from .demo import find_repo_root
from .fallback import choose_character_strategy, choose_room_strategy
from .loader import instantiate_plugin, find_manifest


def verdict_for(avg_seconds: float, min_vram_gb: float, available_vram_gb: float) -> str:
    if min_vram_gb > available_vram_gb:
        return f"Won't fit (needs {min_vram_gb:g}GB, you have {available_vram_gb:g}GB)"
    if avg_seconds <= 8:
        return f"Playable (~{avg_seconds:.1f}s/move)"
    if avg_seconds <= 20:
        return f"Slow (~{avg_seconds:.1f}s/move)"
    return f"Too slow for per-move play (~{avg_seconds:.1f}s/move)"


def scene_request_from_pack(scene: dict, save_id: str = "conformance") -> SceneRequest:
    body = scene.get("scene", scene)
    characters = [
        CharacterInScene(
            char_id=c.get("char_id", "player"),
            action=c.get("action", ""),
            ref_image=c.get("ref_image"),
            description=c.get("description", ""),
        )
        for c in body.get("characters", [])
    ]
    return SceneRequest(
        scene_id=scene["id"],
        seed=derive_seed(save_id, scene["id"]),
        location=body.get("location", {}),
        entities=[EntityInScene(**e) for e in body.get("entities", [])],
        characters=characters,
        previous_image=body.get("previous_image"),
        change=body.get("change"),
        mood=body.get("mood", ""),
        lighting=body.get("lighting", ""),
        aspect=body.get("aspect", "16:9"),
    )


def iter_pack_requests(pack: dict):
    for scene in pack["scenes"]:
        yield "standard", scene_request_from_pack(scene)
    char_pack = pack["character_consistency"]
    char = char_pack["character"]
    for scene in char_pack["scenes"]:
        merged = dict(scene)
        body = dict(merged.get("scene", merged))
        body["characters"] = [{**char, "action": body.get("action", "")}]
        merged["scene"] = body
        yield "character", scene_request_from_pack(merged)
    revisit = pack["room_revisit"]
    yield "revisit:first", scene_request_from_pack(revisit["scene"])
    yield "revisit:changed", scene_request_from_pack(revisit["changed_scene"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dungeon_core.conformance")
    parser.add_argument("--plugin", default="mock-placeholder")
    parser.add_argument("--vram-gb", type=float, default=8.0)
    args = parser.parse_args(argv)

    root = find_repo_root()
    pack_path = root / "conformance" / "pack.json"
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    manifest = find_manifest(root / "plugins", args.plugin)
    if manifest is None:
        print(f"no such plugin: {args.plugin}", file=sys.stderr)
        return 2
    plugin = instantiate_plugin(manifest)
    out_dir = root / "outputs" / "conformance" / args.plugin
    if hasattr(plugin, "output_dir"):
        plugin.output_dir = out_dir

    print(f"=== Conformance: {manifest.id} ===")
    print(f"character consistency (declared): {manifest.capabilities.character_consistency}; "
          f"character strategy with ref: "
          f"{choose_character_strategy(manifest, has_ref=True)}")
    print(f"changed-room strategy: "
          f"{choose_room_strategy(manifest, revisited=True, changed=True)}")

    times: list[float] = []
    failures = 0
    if hasattr(plugin, "load"):
        plugin.load()
    try:
        for label, req in iter_pack_requests(pack):
            started = time.perf_counter()
            try:
                result = plugin.generate(req)
                elapsed = time.perf_counter() - started
                times.append(elapsed)
                print(f"  [{label}] {req.scene_id}: {elapsed:.3f}s -> {result.image}")
            except Exception as exc:  # a plugin that cannot run scores as failed, not fatal
                failures += 1
                print(f"  [{label}] {req.scene_id}: FAILED — {type(exc).__name__}: {exc}")
    finally:
        if hasattr(plugin, "unload"):
            plugin.unload()

    if times:
        avg = sum(times) / len(times)
        verdict = verdict_for(avg, manifest.requirements.min_vram_gb, args.vram_gb)
    else:
        avg = 0.0
        verdict = "Won't run (every generation failed — see plugin status)"
    est = plugin.estimate(next(iter_pack_requests(pack))[1]) if hasattr(plugin, "estimate") else {}
    print(f"\nscenes run: {len(times)} ok, {failures} failed")
    print(f"average: {avg:.2f}s/move; estimated peak VRAM: {est.get('peak_vram_gb', 'unknown')}GB "
          f"(from plugin estimate(), not measured)")
    print(f"verdict for a {args.vram_gb:g}GB card: {verdict}")
    print("character consistency: judge the 3 character scenes by eye — "
          "open the outputs side by side (see conformance/README.md).")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
