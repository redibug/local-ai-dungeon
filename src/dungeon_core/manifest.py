"""Plugin manifests: the plugin.yaml loader and validator.

Core makes every planning decision (fallbacks, GPU scheduling, player
warnings) from the manifest. It never probes a model directly, so a
manifest must be honest — and must at least be *complete*. Validation
here checks completeness and value sanity, raising ManifestError with
a message that names the plugin file and the offending field.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from .errors import ManifestError

REFERENCE_MODES = (
    "none",
    "img2img_only",
    "ip_adapter",
    "face_id",
    "native_multi_ref",
    "native_edit",
)
CONSISTENCY_LEVELS = ("strong", "medium", "weak")
PLUGIN_KINDS = ("image", "text")
REQUIRED_FIELDS = ("id", "kind", "display_name", "version", "backend")


@dataclass
class Requirements:
    min_vram_gb: float = 0.0
    recommended_vram_gb: float = 0.0
    system_ram_gb: float = 0.0
    download_gb: float = 0.0
    files: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Capabilities:
    txt2img: bool = False
    img2img: bool = False
    inpaint: bool = False
    native_edit: bool = False
    reference_images: str = "none"
    max_reference_images: int = 0
    character_consistency: str = "weak"
    room_edit_consistency: str = "weak"
    controlnet: list[str] = field(default_factory=list)
    negative_prompt: bool = False
    seed_reproducible: bool = False


@dataclass
class NativeSettings:
    resolution: list[int] = field(default_factory=lambda: [1024, 1024])
    steps: Optional[int] = None
    cfg: Optional[float] = None


@dataclass
class PluginManifest:
    id: str
    kind: str
    display_name: str
    version: str
    backend: str
    license: Optional[str] = None
    requirements: Requirements = field(default_factory=Requirements)
    capabilities: Capabilities = field(default_factory=Capabilities)
    native: NativeSettings = field(default_factory=NativeSettings)
    # Text-plugin fields (declared in the manifest, unused for image):
    endpoint: Optional[str] = None
    model: Optional[str] = None
    context_tokens: Optional[int] = None
    supports_json_mode: bool = False
    template: Optional[str] = None
    # Bookkeeping:
    source_path: Optional[Path] = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def plugin_dir(self) -> Optional[Path]:
        return self.source_path.parent if self.source_path else None


def _fail(path: Path, message: str) -> ManifestError:
    return ManifestError(f"{path}: {message}")


def load_manifest(path: str | Path) -> PluginManifest:
    """Load and validate one plugin.yaml."""
    path = Path(path)
    if not path.is_file():
        raise _fail(path, "manifest file not found")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise _fail(path, f"invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise _fail(path, "manifest must be a YAML mapping")

    for name in REQUIRED_FIELDS:
        if not data.get(name):
            raise _fail(path, f"missing required field: {name!r}")

    kind = str(data["kind"])
    if kind not in PLUGIN_KINDS:
        raise _fail(path, f"kind must be one of {PLUGIN_KINDS}, got {kind!r}")

    caps_raw = data.get("capabilities") or {}
    if not isinstance(caps_raw, dict):
        raise _fail(path, "capabilities must be a mapping")
    ref_mode = str(caps_raw.get("reference_images", "none"))
    if ref_mode not in REFERENCE_MODES:
        raise _fail(
            path,
            f"capabilities.reference_images must be one of {REFERENCE_MODES}, "
            f"got {ref_mode!r}",
        )
    char_cons = str(caps_raw.get("character_consistency", "weak"))
    if char_cons not in CONSISTENCY_LEVELS:
        raise _fail(
            path,
            f"capabilities.character_consistency must be one of "
            f"{CONSISTENCY_LEVELS}, got {char_cons!r}",
        )
    room_cons = str(caps_raw.get("room_edit_consistency", "weak"))
    if room_cons not in CONSISTENCY_LEVELS:
        raise _fail(
            path,
            f"capabilities.room_edit_consistency must be one of "
            f"{CONSISTENCY_LEVELS}, got {room_cons!r}",
        )

    req_raw = data.get("requirements") or {}
    native_raw = data.get("native") or {}

    manifest = PluginManifest(
        id=str(data["id"]),
        kind=kind,
        display_name=str(data["display_name"]),
        version=str(data["version"]),
        backend=str(data["backend"]),
        license=data.get("license"),
        requirements=Requirements(
            min_vram_gb=float(req_raw.get("min_vram_gb", 0) or 0),
            recommended_vram_gb=float(req_raw.get("recommended_vram_gb", 0) or 0),
            system_ram_gb=float(req_raw.get("system_ram_gb", 0) or 0),
            download_gb=float(req_raw.get("download_gb", 0) or 0),
            files=list(req_raw.get("files") or []),
        ),
        capabilities=Capabilities(
            txt2img=bool(caps_raw.get("txt2img", False)),
            img2img=bool(caps_raw.get("img2img", False)),
            inpaint=bool(caps_raw.get("inpaint", False)),
            native_edit=bool(caps_raw.get("native_edit", False)),
            reference_images=ref_mode,
            max_reference_images=int(caps_raw.get("max_reference_images", 0) or 0),
            character_consistency=char_cons,
            room_edit_consistency=room_cons,
            controlnet=list(caps_raw.get("controlnet") or []),
            negative_prompt=bool(caps_raw.get("negative_prompt", False)),
            seed_reproducible=bool(caps_raw.get("seed_reproducible", False)),
        ),
        native=NativeSettings(
            resolution=list(native_raw.get("resolution") or [1024, 1024]),
            steps=native_raw.get("steps"),
            cfg=native_raw.get("cfg"),
        ),
        endpoint=data.get("endpoint"),
        model=data.get("model"),
        context_tokens=data.get("context_tokens"),
        supports_json_mode=bool(data.get("supports_json_mode", False)),
        template=data.get("template"),
        source_path=path,
        raw=data,
    )
    return manifest
