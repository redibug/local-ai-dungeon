# SDXL Lightning + IP-Adapter

**Status: compiler real, backend unverified.** The prompt compiler is
implemented and unit-tested; `generate()` builds a ComfyUI workflow and
talks to a local server via `/prompt`, but that workflow has **not**
been run against a live ComfyUI yet.

Requirements: 6GB VRAM minimum / 8GB recommended, a local ComfyUI
install, a Lightning-distilled SDXL checkpoint, the IP-Adapter Plus
SDXL model + CLIP Vision H, and the ComfyUI_IPAdapter_plus custom
nodes if you use character references.

Implemented:
- Manifest with real requirements/capabilities for an 8GB card.
- SDXL prompt compiler: tag-style positive prompt, proper negative
  prompt, style LoRA prefix, IP-Adapter reference list (max 2).
- Native sampler settings from the manifest (6 steps, CFG 1.5 —
  Lightning settings; normal SDXL settings would ruin it).
- ComfyUI submission/poll/fetch in `generate()`.

TODO before first real run:
- **Set the checkpoint filenames.** `DEFAULT_CONFIG` in `plugin.py`
  and `config.schema.json` carry an intentional
  `SET_ME_lightning_checkpoint.safetensors` placeholder — point them
  at files actually installed in ComfyUI.
- Pin real file hashes/URLs in `plugin.yaml` (currently null).
- Verify IP-Adapter node names/inputs against a live server.
- img2img / inpaint strategies for changed rooms (the workflow here
  is txt2img; core's fallback planner already asks correctly).
