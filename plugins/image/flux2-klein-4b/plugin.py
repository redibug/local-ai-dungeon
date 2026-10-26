"""FLUX.2 Klein 4B image plugin.

WHAT IS REAL HERE
- The manifest: Apache-2.0 4B, multi-reference capable, native edit.
- The prompt compiler: natural-language prompt PLUS the character
  reference image list (up to the manifest's max of 10) carried
  alongside it — Klein takes references natively, so unlike the
  SDXL plugin there is no adapter to bolt on, and unlike Z-Image
  the references are a first-class part of the compiled output.
  Unit-tested.

WHAT IS NOT DONE
- generate() raises PluginNotReady: no ComfyUI workflow / diffusers
  runner is wired yet. Note the honest capability grading: character
  consistency is declared ``medium``, not ``strong`` — Klein is the
  fast sibling of FLUX.2 and holds identity more weakly than the big
  FLUX.2 dev / FLUX.1 Kontext models. Its strength here is the native
  edit path for changed rooms plus speed (4 distilled steps).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dungeon_core.contracts import field_of
from dungeon_core.errors import PluginNotReady

NOT_READY_MESSAGE = (
    "FLUX.2 Klein 4B backend is not wired up yet: the manifest and "
    "prompt compiler (including the native multi-reference list) are "
    "complete, but there is no runner. Missing: a ComfyUI workflow for "
    "the FLUX.2 Klein family (or a diffusers integration) and the "
    "weights listed in plugin.yaml. Until then, use mock-placeholder "
    "or sdxl-lightning-ipadapter to play."
)


@dataclass
class CompiledPrompt:
    positive: str
    negative: Optional[str] = None  # FLUX-family: no negative prompt
    references: list[str] = field(default_factory=list)
    steps: int = 4
    cfg: float = 1.0
    resolution: list[int] = field(default_factory=lambda: [1024, 1024])
    seed: int = 0


class KleinPromptCompiler:
    """SceneRequest -> natural language + native reference list."""

    def __init__(self, config: Optional[dict] = None, manifest=None):
        native = getattr(manifest, "native", None)
        self.steps = int(getattr(native, "steps", None) or 4)
        self.cfg = float(getattr(native, "cfg", None) or 1.0)
        self.resolution = list(getattr(native, "resolution", None) or [1024, 1024])
        caps = getattr(manifest, "capabilities", None)
        self.max_refs = int(getattr(caps, "max_reference_images", 10) or 10)

    def compile(self, req) -> CompiledPrompt:
        loc = req.location or {}
        sentences: list[str] = []
        loc_type = field_of(loc, "type") or "dungeon room"
        materials = field_of(loc, "materials", []) or []
        features = field_of(loc, "features", []) or []
        opening = f"A dark fantasy scene in a {loc_type}"
        if materials:
            opening += f" of {', '.join(str(m) for m in materials)}"
        if features:
            opening += f", featuring {', '.join(str(f) for f in features)}"
        sentences.append(opening + ".")
        for entity in req.entities or []:
            kind = field_of(entity, "kind")
            state = field_of(entity, "state")
            sentences.append(f"A {kind}" + (f" that is {state}." if state else "."))
        references: list[str] = []
        for char in req.characters or []:
            desc = field_of(char, "description") or f"the character {field_of(char, 'char_id')}"
            action = field_of(char, "action")
            sentences.append(
                f"Show {desc} (from the reference image)"
                + (f", {action}." if action else ".")
            )
            ref = field_of(char, "ref_image")
            if ref:
                references.append(str(ref))
        if req.previous_image:
            references.append(str(req.previous_image))
        if req.change:
            sentences.append(
                f"Edit the previous scene: {req.change}. "
                "Keep the room, lighting and composition the same."
            )
        mood_light = ", ".join(p for p in [req.mood, req.lighting] if p)
        if mood_light:
            sentences.append(f"Atmosphere: {mood_light}.")
        return CompiledPrompt(
            positive=" ".join(sentences),
            negative=None,
            references=references[: self.max_refs],
            steps=self.steps,
            cfg=self.cfg,
            resolution=self.resolution,
            seed=int(req.seed),
        )


class Flux2KleinPlugin:
    def __init__(self, manifest=None, plugin_dir=None, config: Optional[dict] = None):
        self.manifest = manifest
        self.plugin_dir = Path(plugin_dir) if plugin_dir else None
        self.config = config or {}
        self.compiler = KleinPromptCompiler(self.config, manifest)
        self.loaded = False

    def install(self) -> None:
        raise PluginNotReady(NOT_READY_MESSAGE)

    def health(self) -> dict:
        return {"ok": False, "backend": "comfyui", "detail": NOT_READY_MESSAGE}

    def load(self) -> None:
        self.loaded = True

    def unload(self) -> None:
        self.loaded = False

    def estimate(self, req) -> dict:
        return {"seconds": 3.0, "peak_vram_gb": 13.0}

    def compile_prompt(self, req) -> CompiledPrompt:
        return self.compiler.compile(req)

    def generate(self, req, strategy: str = "txt2img"):
        raise PluginNotReady(NOT_READY_MESSAGE)


Plugin = Flux2KleinPlugin


def create_plugin(manifest, plugin_dir):
    return Flux2KleinPlugin(manifest=manifest, plugin_dir=plugin_dir)
