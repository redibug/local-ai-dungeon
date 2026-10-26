"""Z-Image Turbo (GGUF) image plugin.

WHAT IS REAL HERE
- The manifest (Apache-2.0, 6B, 8 steps, GGUF fits ~6GB VRAM).
- The prompt compiler: natural-language sentences, NO negative prompt
  (``negative is None``), CFG 1.0, 8 steps. Z-Image Turbo is a
  distilled model — a negative prompt or a normal CFG actively breaks
  it, which is exactly the dialect difference this plugin exists to
  hide from core. Unit-tested.

WHAT IS NOT DONE
- generate() raises PluginNotReady. The runner — a ComfyUI-GGUF
  workflow or a diffusers ZImagePipeline integration — has not been
  wired up yet. Character references are declared ``none`` honestly:
  consistency for this plugin comes from core's seed + cache +
  img2img path, not from reference images.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dungeon_core.contracts import field_of
from dungeon_core.errors import PluginNotReady

NOT_READY_MESSAGE = (
    "Z-Image Turbo backend is not wired up yet: the manifest and prompt "
    "compiler are complete, but there is no runner. Missing: a "
    "ComfyUI-GGUF workflow (ComfyUI-GGUF custom node + the GGUF weights "
    "listed in plugin.yaml) or a diffusers ZImagePipeline integration. "
    "Until then, use the mock-placeholder or sdxl-lightning-ipadapter "
    "plugin to play."
)


@dataclass
class CompiledPrompt:
    positive: str
    negative: Optional[str] = None  # always None for this model — by design
    references: list[str] = field(default_factory=list)  # always empty: no ref support
    steps: int = 8
    cfg: float = 1.0
    resolution: list[int] = field(default_factory=lambda: [1024, 1024])
    seed: int = 0


class ZImagePromptCompiler:
    """SceneRequest -> natural-language description. Pure, unit-tested."""

    def __init__(self, config: Optional[dict] = None, manifest=None):
        native = getattr(manifest, "native", None)
        self.steps = int(getattr(native, "steps", None) or 8)
        self.cfg = float(getattr(native, "cfg", None) or 1.0)
        self.resolution = list(getattr(native, "resolution", None) or [1024, 1024])

    def compile(self, req) -> CompiledPrompt:
        loc = req.location or {}
        sentences: list[str] = []
        loc_type = field_of(loc, "type") or "dungeon room"
        materials = field_of(loc, "materials", []) or []
        features = field_of(loc, "features", []) or []
        opening = f"A dark fantasy illustration of a {loc_type}"
        if materials:
            opening += f" built of {', '.join(str(m) for m in materials)}"
        if features:
            opening += f", with {', '.join(str(f) for f in features)}"
        sentences.append(opening + ".")
        for entity in req.entities or []:
            kind = field_of(entity, "kind")
            state = field_of(entity, "state")
            sentences.append(f"There is a {kind}" + (f", {state}." if state else "."))
        for char in req.characters or []:
            desc = field_of(char, "description") or f"a character ({field_of(char, 'char_id')})"
            action = field_of(char, "action")
            sentences.append(f"{desc}" + (f" is {action}." if action else " is present."))
        if req.change:
            sentences.append(f"Change from before: {req.change}.")
        mood_light = ", ".join(p for p in [req.mood, req.lighting] if p)
        if mood_light:
            sentences.append(f"The mood is {mood_light}.")
        return CompiledPrompt(
            positive=" ".join(sentences),
            negative=None,
            references=[],
            steps=self.steps,
            cfg=self.cfg,
            resolution=self.resolution,
            seed=int(req.seed),
        )


class ZImageTurboPlugin:
    def __init__(self, manifest=None, plugin_dir=None, config: Optional[dict] = None):
        self.manifest = manifest
        self.plugin_dir = Path(plugin_dir) if plugin_dir else None
        self.config = config or {}
        self.compiler = ZImagePromptCompiler(self.config, manifest)
        self.loaded = False

    def install(self) -> None:
        raise PluginNotReady(NOT_READY_MESSAGE)

    def health(self) -> dict:
        return {"ok": False, "backend": "gguf", "detail": NOT_READY_MESSAGE}

    def load(self) -> None:
        self.loaded = True

    def unload(self) -> None:
        self.loaded = False

    def estimate(self, req) -> dict:
        return {"seconds": 5.0, "peak_vram_gb": 6.0}

    def compile_prompt(self, req) -> CompiledPrompt:
        return self.compiler.compile(req)

    def generate(self, req, strategy: str = "txt2img"):
        raise PluginNotReady(NOT_READY_MESSAGE)


Plugin = ZImageTurboPlugin


def create_plugin(manifest, plugin_dir):
    return ZImageTurboPlugin(manifest=manifest, plugin_dir=plugin_dir)
