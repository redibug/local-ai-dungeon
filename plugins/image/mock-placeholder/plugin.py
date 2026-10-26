"""Mock image plugin — a TEST DOUBLE, not a model.

It implements the image plugin contract (load/unload/generate) with
zero dependencies so core, the demo, the conformance runner and the
test suite can run on any machine, GPU or not. generate() writes a
deterministic PNG using only the stdlib (a hand-rolled zlib/struct
PNG encoder): the base palette comes from seed + scene_id (so the
same room keeps the same colours), and a block pattern is derived
from the full request — entities, change, mood — so a changed room
visibly differs while staying recognisably the same place.

Do not mistake its output for image generation. Real plugins live in
the sibling folders.
"""

from __future__ import annotations

import hashlib
import json
import struct
import time
import zlib
from dataclasses import asdict, is_dataclass
from pathlib import Path

from dungeon_core.contracts import SceneResult, field_of

WIDTH, HEIGHT = 320, 180
BLOCK = 20  # px per block in the pattern grid


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def encode_png(width: int, height: int, rows: list[bytes]) -> bytes:
    """Minimal truecolour PNG encoder. ``rows`` are raw RGB scanlines."""
    raw = b"".join(b"\x00" + row for row in rows)  # filter type 0 per row
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(raw))
        + _chunk(b"IEND", b"")
    )


def _request_fingerprint(req) -> str:
    payload = {
        "scene_id": req.scene_id,
        "seed": req.seed,
        "location": req.location,
        "entities": [
            {"kind": field_of(e, "kind"), "state": field_of(e, "state")}
            for e in req.entities
        ],
        "characters": [field_of(c, "char_id") for c in req.characters],
        "change": req.change,
        "mood": req.mood,
        "lighting": req.lighting,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def render_placeholder_png(req) -> bytes:
    """Deterministic placeholder image bytes for a SceneRequest."""
    base = hashlib.sha256(f"{req.seed}:{req.scene_id}".encode("utf-8")).digest()
    fingerprint = _request_fingerprint(req)
    # Palette: three colours derived from seed+scene (stable per room).
    palette = [
        (base[0], base[1], base[2]),
        (base[3], base[4], base[5]),
        (base[6], base[7], base[8]),
        (230, 220, 200),
    ]
    rows: list[bytes] = []
    cols = WIDTH // BLOCK
    for by in range(HEIGHT // BLOCK):
        row_bytes = bytearray()
        for bx in range(cols):
            block_hash = hashlib.sha256(
                f"{fingerprint}:{by}:{bx}".encode("utf-8")
            ).digest()
            pick = block_hash[0] % len(palette)
            # Re-visiting with a change still uses the same palette, but
            # the fingerprint — and therefore the pattern — moves.
            row_bytes.extend(bytes(palette[pick]) * BLOCK)
        row = bytes(row_bytes)
        rows.extend([row] * BLOCK)
    return encode_png(WIDTH, HEIGHT, rows)


class MockPlaceholderImagePlugin:
    def __init__(self, manifest=None, plugin_dir=None, output_dir=None):
        self.manifest = manifest
        self.plugin_dir = Path(plugin_dir) if plugin_dir else None
        self.output_dir = Path(output_dir) if output_dir else Path("outputs")
        self.loaded = False
        self.generate_calls = 0

    # -- lifecycle -----------------------------------------------------
    def install(self) -> None:
        return None  # nothing to fetch: there is no model

    def health(self) -> dict:
        return {"ok": True, "backend": "mock", "detail": "test double, always healthy"}

    def load(self) -> None:
        self.loaded = True

    def unload(self) -> None:
        self.loaded = False

    def estimate(self, req) -> dict:
        return {"seconds": 0.01, "peak_vram_gb": 0.0}

    # -- generation ----------------------------------------------------
    def generate(self, req, strategy: str = "txt2img") -> SceneResult:
        started = time.perf_counter()
        self.generate_calls += 1
        self.output_dir.mkdir(parents=True, exist_ok=True)
        safe_scene = req.scene_id.replace("/", "_").replace(",", "-")
        # Include the request fingerprint: a changed room must not
        # overwrite the cached image of the unchanged room.
        fingerprint = _request_fingerprint(req)[:8]
        out_path = self.output_dir / f"{safe_scene}-{req.seed}-{fingerprint}.png"
        out_path.write_bytes(render_placeholder_png(req))
        return SceneResult(
            image=str(out_path),
            actual_seed=req.seed,
            seconds=time.perf_counter() - started,
            compiled_prompt=f"[mock] {req.scene_id} seed={req.seed}",
            plugin_id=self.manifest.id if self.manifest else "mock-placeholder",
            plugin_version=self.manifest.version if self.manifest else "0.1.0",
            negative_prompt=None,
            strategy=strategy,
        )


def create_plugin(manifest, plugin_dir):
    return MockPlaceholderImagePlugin(manifest=manifest, plugin_dir=plugin_dir)
