# Local AI Dungeon Crawler — Plugin Architecture v0.1
Date: 2026-10-26 · Status: design draft (Mel's direction: fully modular, plugin = model + glue)

## Principle

Core never knows a model. A plugin is a self-contained folder:

    plugin = model files (or a pointer to them) + glue code + manifest

Core speaks ONE canonical language (structured game/scene state).
Each plugin translates that language into its own model's dialect,
runs it, and translates the result back. Swapping a plugin changes
nothing in core, saves, or the other plugin type.

Two plugin kinds, independent of each other:
- `image` — hard, code + assets. One active at a time.
- `text`  — easy, usually manifest-only (endpoint + template). One active at a time.
Any image plugin works with any text plugin.

## Folder layout

    plugins/
      image/
        sdxl-lightning-ipadapter/
          plugin.yaml        # manifest (below)
          plugin.py          # glue: implements the image contract
          workflow.json      # e.g. its ComfyUI graph — private to the plugin
          config.schema.json # its own settings, core renders UI from this
        z-image-turbo-gguf/
          plugin.yaml
          plugin.py
          ...
        flux2-klein-4b/
          plugin.yaml
          plugin.py
          ...
      text/
        qwen3-8b-ollama/
          plugin.yaml        # no code needed — declarative only
        llama31-8b-lmstudio/
          plugin.yaml

## 1. The manifest — capabilities, not promises

Core makes every decision (fallbacks, warnings, GPU scheduling) from
the manifest. It never probes a model directly.

```yaml
id: sdxl-lightning-ipadapter
kind: image
display_name: "SDXL Lightning + IP-Adapter (fantasy)"
version: 1.0.0
backend: comfyui            # comfyui | diffusers | gguf | api-local
license: "CreativeML Open RAIL++-M (checkpoint-dependent)"

requirements:
  min_vram_gb: 6
  recommended_vram_gb: 8
  system_ram_gb: 16
  download_gb: 7.5
  files:                    # core downloads/verifies; plugin never fetches ad-hoc
    - { path: "checkpoints/juggernautXL_lightning.safetensors", sha256: "...", url: "..." }
    - { path: "ipadapter/ip-adapter-plus_sdxl.bin", sha256: "...", url: "..." }

capabilities:
  txt2img: true
  img2img: true
  inpaint: true
  reference_images: ip_adapter     # none | img2img_only | ip_adapter | face_id | native_multi_ref | native_edit
  max_reference_images: 2
  character_consistency: strong    # strong | medium | weak — shown to player in settings
  room_edit_consistency: strong    # can it change a room without redrawing it?
  controlnet: [depth, canny]
  negative_prompt: true
  seed_reproducible: true

native:
  resolution: [1024, 1024]         # plugin is free to render here and downscale
  steps: 6
  cfg: 1.5
```

Why capabilities matter — the same feature, four dialects:

| Need | SDXL plugin | Z-Image Turbo plugin | FLUX.2 Klein plugin |
|---|---|---|---|
| Character ref | IP-Adapter nodes in its workflow | none → falls back to prompt block + img2img | native multi-ref inputs |
| Room, changed | inpaint masked region | img2img, denoise 0.35 | native edit instruction |
| Prompt style | tags + negative prompt, LoRA triggers | natural language, NO negative, CFG ~1 | natural language / structured |
| Broken if… | CFG 7 + 30 steps on a Lightning ckpt | you pass a negative prompt | you expect hard face-lock |

Core does not care which row it's talking to. It asks the manifest,
picks a strategy, and the plugin executes its own version of it:

    revisit, unchanged  -> core serves cached image (no plugin call at all)
    revisit, changed    -> edit if room_edit supported, else img2img, else txt2img+seed
    character appears   -> native ref > ip_adapter/face_id > prompt-block only
                           (core warns the player when it degrades:
                            "this plugin has weak character consistency")

## 2. Canonical requests — core sends meaning, not prompts

The single most important rule: **core never builds a prompt string.**
Prompt dialect is the leakiest part of every model — if core writes
SDXL tags, the FLUX plugin is broken by design. Core sends a
structured scene; each plugin compiles it.

```jsonc
// SceneRequest — the only thing core ever sends an image plugin
{
  "scene_id": "dungeon1/3,4",
  "seed": 882134,                       // derived: hash(save_id + scene_id)
  "location":  { "type": "corridor", "materials": ["wet stone"],
                 "features": ["iron torches", "flooded floor"] },
  "entities":  [{ "kind": "chest", "state": "open, empty" }],
  "characters":[{ "char_id": "player", "action": "entering, sword drawn",
                  "ref_image": "saves/.../refs/player.png" }],
  "previous_image": "saves/.../scenes/dungeon1_3,4.png",  // may be null
  "change": "the chest is now open",    // null for a first visit
  "mood": "dread", "lighting": "torchlight",
  "aspect": "16:9"
}
// -> SceneResult
{
  "image": "....png", "actual_seed": 882134, "seconds": 4.1,
  "compiled_prompt": "...",             // for debug/repro, never for logic
  "plugin_id": "sdxl-lightning-ipadapter", "plugin_version": "1.0.0"
}
```

Saves store the SceneRequest + the resulting image, never plugin
internals (no workflow IDs, no sampler names). Switching plugins
mid-game therefore cannot corrupt a save: old scenes stay as-is,
new scenes render in the new plugin, core shows a one-time
"style may change" note.

## 3. Image plugin contract (the glue code)

```python
class ImagePlugin:
    def install(self) -> None: ...        # fetch/verify manifest files
    def health(self) -> Health: ...       # backend up? files present?
    def load(self) -> None: ...           # take the GPU
    def unload(self) -> None: ...         # actually free VRAM, not "probably"
    def estimate(self, req) -> Estimate: ...  # seconds + peak VRAM, for the arbiter
    def generate(self, req: SceneRequest) -> SceneResult: ...
```

Everything model-specific lives behind this: sampler, steps, CFG,
resolution, workflow graph, quant level, prompt compiler,
negative-prompt handling (including "this model must NOT get one").

## 4. Text plugin contract — deliberately boring

Narration is text-in/text-out, so most text plugins need **no code**:

```yaml
id: qwen3-8b-ollama
kind: text
backend: openai_compatible        # ollama | lmstudio | llamacpp | openai_compatible
endpoint: "http://127.0.0.1:11434/v1"
model: "qwen3:8b-q4_K_M"
context_tokens: 8192
supports_json_mode: true
template: narrate.jinja           # the plugin's one real asset
requirements: { min_vram_gb: 5, download_gb: 4.7 }
```

Core sends a NarrationRequest (structured event + full game-state
snapshot + tone/length targets) — never raw history — and requires
a validated shape back: narration text, separately from any
scene tags. Game logic, stats, inventory, and damage stay in core
code, always. The LLM narrates a state diff; it never owns state.
A weak local model can then only write a dull paragraph, it cannot
break the game.

## 5. Core's jobs (the only non-plugin code)

- **GPU arbiter.** Only one GPU plugin is loaded at a time.
  Per move: text loads → narrate → unload → image loads → render.
  Plugins report footprint via `estimate()`; the arbiter, not the
  plugins, decides load order and eviction.
- **Scene cache + speculative pre-gen.** While the player reads,
  generate adjacent rooms in the background. Cache is keyed by
  scene_id + state_hash, so "changed" is detectable.
- **Settings UI from schemas.** Each plugin ships
  `config.schema.json` (checkpoint choice, quant, LoRA, endpoint…).
  Core renders it generically — adding a plugin adds its own
  settings page with zero core changes.
- **Conformance / benchmark kit — this is how players "find what
  works on their computer."** Every image plugin must pass the
  same test pack: 10 standard scenes, 1 character appearing
  3 times, 1 room revisited-with-a-change. Core times it, measures
  peak VRAM, and shows a plain verdict in settings:
  `Playable (~4s/move)` / `Slow (~18s/move)` / `Won't fit (needs 12GB, you have 8GB)`
  plus the three character shots side by side so consistency is
  judged by eye, not by a manifest claim.

## 6. Rules that keep it modular in practice

1. No model name, sampler, or prompt fragment in core. Ever.
   If core needs to know it, it belongs in the manifest.
2. Plugins are folders. Install = drop in folder (+ file download
   via manifest). Uninstall = delete folder. No registry edits.
3. A plugin may degrade (weak consistency, slow) but must declare
   it. Silent quality differences are what make swapping feel broken.
4. Plugin API is versioned (`api: 1`). Core supports api 1 and 2
   side by side so old community plugins don't die on an update.
5. Community plugins are the point: someone else's weird model
   becomes playable by writing one folder, not forking the game.

## First three plugins to build

1. `sdxl-lightning-ipadapter` — the 8GB reference implementation.
2. `z-image-turbo-gguf` — proves the contract survives a model with
   no negative prompt, no IP-Adapter, distilled sampler settings.
3. `flux2-klein-4b` — proves native multi-ref / native edit fit the
   same SceneRequest without special-casing in core.
If all three pass the same conformance pack, the abstraction is real.
