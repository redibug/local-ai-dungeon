"""SDXL Lightning + IP-Adapter image plugin (ComfyUI backend).

WHAT IS REAL HERE
- The prompt compiler (SDXLPromptCompiler): SceneRequest -> SDXL
  tag-style positive prompt + negative prompt, style/LoRA prefix,
  and IP-Adapter reference handling. Unit-tested.
- generate(): builds a ComfyUI workflow from the embedded template
  and talks to a local ComfyUI server via urllib (POST /prompt, poll
  /history, fetch /view).

WHAT IS NOT VERIFIED
- The workflow has NOT been run against a live ComfyUI server yet.
  Node class names target ComfyUI core + the ComfyUI_IPAdapter_plus
  custom nodes; expect to adjust node ids/inputs on first real run.
- CHECKPOINT FILENAMES MUST BE SET: DEFAULT_CONFIG["checkpoint"]
  (or plugin config / config.schema.json) contains an obvious
  SET_ME placeholder. Set it to a Lightning-distilled SDXL checkpoint
  actually installed in your ComfyUI models/checkpoints folder, plus
  the IP-Adapter + CLIP vision filenames, before generating.

Lightning checkpoints are distilled: few steps, low CFG. Feeding one
CFG 7 / 30 steps (normal SDXL habits) ruins output — the manifest's
native steps/cfg exist precisely to stop core or users doing that.
"""

from __future__ import annotations

import copy
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dungeon_core.contracts import SceneResult, field_of
from dungeon_core.errors import PluginNotReady

STYLE_PREFIX = "dark fantasy illustration, detailed digital painting"
DEFAULT_LORA_TRIGGER = "<lora:dungeon-fantasy-style:0.7>"
DEFAULT_NEGATIVE = (
    "blurry, low quality, worst quality, deformed, disfigured, "
    "bad anatomy, extra fingers, watermark, text, logo, "
    "modern, sci-fi, photograph, bright daylight, cheerful"
)

# !!! SET THESE to files actually installed in ComfyUI before use !!!
DEFAULT_CONFIG = {
    "comfy_url": "http://127.0.0.1:8188",
    "checkpoint": "SET_ME_lightning_checkpoint.safetensors",
    "ip_adapter_model": "ip-adapter-plus_sdxl_vit-h.safetensors",
    "clip_vision_model": "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors",
    "ip_adapter_weight": 0.7,
    "style_lora": DEFAULT_LORA_TRIGGER,
    "poll_timeout_seconds": 120,
}


@dataclass
class CompiledPrompt:
    positive: str
    negative: Optional[str]
    references: list[str] = field(default_factory=list)
    steps: int = 6
    cfg: float = 1.5
    resolution: list[int] = field(default_factory=lambda: [1024, 1024])
    seed: int = 0


def _join(parts: list[str]) -> str:
    return ", ".join(p.strip() for p in parts if p and str(p).strip())


class SDXLPromptCompiler:
    """SceneRequest -> SDXL dialect. Pure and unit-testable."""

    def __init__(self, config: Optional[dict] = None, manifest=None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        native = getattr(manifest, "native", None)
        self.steps = int(getattr(native, "steps", None) or 6)
        self.cfg = float(getattr(native, "cfg", None) or 1.5)
        self.resolution = list(getattr(native, "resolution", None) or [1024, 1024])
        caps = getattr(manifest, "capabilities", None)
        self.max_refs = int(getattr(caps, "max_reference_images", 2) or 2)
        self.supports_negative = bool(getattr(caps, "negative_prompt", True))

    def compile(self, req) -> CompiledPrompt:
        loc = req.location or {}
        parts: list[str] = [STYLE_PREFIX]
        if self.config.get("style_lora"):
            parts.append(str(self.config["style_lora"]))
        loc_type = field_of(loc, "type")
        if loc_type:
            parts.append(str(loc_type))
        for material in field_of(loc, "materials", []) or []:
            parts.append(str(material))
        for feature in field_of(loc, "features", []) or []:
            parts.append(str(feature))
        for entity in req.entities or []:
            kind = field_of(entity, "kind")
            state = field_of(entity, "state")
            parts.append(_join([str(kind), str(state)]) if state else str(kind))
        for char in req.characters or []:
            desc = field_of(char, "description")
            action = field_of(char, "action")
            label = desc or f"character {field_of(char, 'char_id')}"
            parts.append(_join([str(label), str(action)]) if action else str(label))
        if req.change:
            parts.append(str(req.change))
        if req.lighting:
            parts.append(f"{req.lighting} lighting")
        if req.mood:
            parts.append(f"{req.mood} mood")
        parts.append("atmospheric, rich detail")

        references = [
            str(field_of(c, "ref_image"))
            for c in (req.characters or [])
            if field_of(c, "ref_image")
        ][: self.max_refs]

        return CompiledPrompt(
            positive=_join(parts),
            negative=DEFAULT_NEGATIVE if self.supports_negative else None,
            references=references,
            steps=self.steps,
            cfg=self.cfg,
            resolution=self.resolution,
            seed=int(req.seed),
        )


def build_workflow(compiled: CompiledPrompt, config: dict) -> dict:
    """Fill the embedded ComfyUI workflow template.

    Without references this is a plain txt2img graph. With references,
    IP-Adapter nodes (from ComfyUI_IPAdapter_plus) are inserted between
    the checkpoint loader and the KSampler — their exact node contract
    is the part to verify on first live run.
    """
    width, height = compiled.resolution
    workflow: dict = {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": config["checkpoint"]},
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": compiled.positive, "clip": ["1", 1]},
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": compiled.negative or "", "clip": ["1", 1]},
        },
        "4": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
                "seed": compiled.seed,
                "steps": compiled.steps,
                "cfg": compiled.cfg,
                "sampler_name": "euler",
                "scheduler": "sgm_uniform",
                "denoise": 1.0,
            },
        },
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "dungeon"}},
    }
    if compiled.references:
        workflow["8"] = {
            "class_type": "IPAdapterUnifiedLoader",
            "inputs": {"model": ["1", 0], "preset": "PLUS (high strength)"},
        }
        workflow["9"] = {
            "class_type": "LoadImage",
            "inputs": {"image": Path(compiled.references[0]).name},
        }
        workflow["10"] = {
            "class_type": "IPAdapterAdvanced",
            "inputs": {
                "model": ["8", 0],
                "ipadapter": ["8", 1],
                "image": ["9", 0],
                "weight": float(config.get("ip_adapter_weight", 0.7)),
                "start_at": 0.0,
                "end_at": 1.0,
                "weight_type": "linear",
            },
        }
        workflow["5"]["inputs"]["model"] = ["10", 0]
    return workflow


class SDXLPlugin:
    def __init__(self, manifest=None, plugin_dir=None, config: Optional[dict] = None,
                 output_dir=None):
        self.manifest = manifest
        self.plugin_dir = Path(plugin_dir) if plugin_dir else None
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.output_dir = Path(output_dir) if output_dir else Path("outputs")
        self.compiler = SDXLPromptCompiler(self.config, manifest)
        self.loaded = False

    # -- lifecycle -----------------------------------------------------
    def install(self) -> None:
        raise PluginNotReady(
            "Automatic model download is not implemented yet. Place the "
            "checkpoint, IP-Adapter and CLIP vision files listed in "
            "plugin.yaml into your ComfyUI models folders manually."
        )

    def health(self) -> dict:
        url = self.config["comfy_url"].rstrip("/") + "/system_stats"
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                return {"ok": resp.status == 200, "backend": "comfyui", "detail": url}
        except Exception as exc:
            return {"ok": False, "backend": "comfyui", "detail": f"{url}: {exc}"}

    def load(self) -> None:
        self.loaded = True  # the model itself lives in the ComfyUI server

    def unload(self) -> None:
        self.loaded = False

    def estimate(self, req) -> dict:
        return {"seconds": 6.0, "peak_vram_gb": 8.0}

    # -- generation ----------------------------------------------------
    def compile_prompt(self, req) -> CompiledPrompt:
        return self.compiler.compile(req)

    def generate(self, req, strategy: str = "txt2img") -> SceneResult:
        if self.config["checkpoint"].startswith("SET_ME"):
            raise PluginNotReady(
                "SDXL plugin checkpoint is not configured: set 'checkpoint' "
                "in this plugin's config (see config.schema.json) to a "
                "Lightning SDXL checkpoint installed in ComfyUI. The "
                "shipped value is an intentional SET_ME placeholder."
            )
        compiled = self.compiler.compile(req)
        workflow = build_workflow(compiled, self.config)
        started = time.perf_counter()
        image_path = self._run_workflow(workflow, req)
        return SceneResult(
            image=str(image_path),
            actual_seed=compiled.seed,
            seconds=time.perf_counter() - started,
            compiled_prompt=compiled.positive,
            plugin_id=self.manifest.id if self.manifest else "sdxl-lightning-ipadapter",
            plugin_version=self.manifest.version if self.manifest else "1.0.0",
            negative_prompt=compiled.negative,
            strategy=strategy,
        )

    def _run_workflow(self, workflow: dict, req) -> Path:
        base = self.config["comfy_url"].rstrip("/")
        payload = json.dumps({"prompt": workflow}).encode("utf-8")
        request = urllib.request.Request(
            base + "/prompt", data=payload,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as resp:
                prompt_id = json.loads(resp.read())["prompt_id"]
        except (urllib.error.URLError, OSError, KeyError, ValueError) as exc:
            raise PluginNotReady(
                f"ComfyUI server not reachable at {base} ({exc}). Start "
                "ComfyUI locally, or set comfy_url in this plugin's config."
            ) from exc

        deadline = time.time() + float(self.config.get("poll_timeout_seconds", 120))
        filename = None
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(
                    f"{base}/history/{prompt_id}", timeout=10
                ) as resp:
                    history = json.loads(resp.read())
            except (urllib.error.URLError, OSError, ValueError):
                history = {}
            entry = history.get(prompt_id) or {}
            for node_out in (entry.get("outputs") or {}).values():
                for img in node_out.get("images") or []:
                    filename = img.get("filename")
            if filename:
                break
            time.sleep(1.0)
        if not filename:
            raise PluginNotReady(
                f"ComfyUI prompt {prompt_id} produced no image within "
                f"{self.config.get('poll_timeout_seconds')}s — check the "
                "ComfyUI console (the embedded workflow is unverified "
                "against a live server; see this plugin's README)."
            )

        query = urllib.parse.urlencode({"filename": filename, "type": "output"})
        self.output_dir.mkdir(parents=True, exist_ok=True)
        safe_scene = req.scene_id.replace("/", "_").replace(",", "-")
        out_path = self.output_dir / f"{safe_scene}-{req.seed}.png"
        try:
            with urllib.request.urlopen(f"{base}/view?{query}", timeout=30) as resp:
                out_path.write_bytes(resp.read())
        except (urllib.error.URLError, OSError) as exc:
            raise PluginNotReady(
                f"ComfyUI finished but the image could not be fetched: {exc}"
            ) from exc
        return out_path


# Backwards-friendly alias + factory used by the core loader.
Plugin = SDXLPlugin


def create_plugin(manifest, plugin_dir):
    return SDXLPlugin(manifest=manifest, plugin_dir=plugin_dir)
