# Z-Image Turbo (GGUF)

**Status: manifest + compiler complete, backend pending.**
`generate()` raises `PluginNotReady` explaining what's missing.

Requirements (declared): 6GB VRAM minimum via GGUF (~Q4), 8GB
recommended; Apache-2.0 weights; 8 steps at CFG 1.0.

Implemented:
- Natural-language prompt compiler — **no negative prompt, ever**
  (`negative=None`). Passing one, or a normal CFG, breaks distilled
  Turbo models; hiding that from core is this plugin's whole job.
- Honest capabilities: txt2img + img2img, no inpaint, no reference
  images, weak character consistency (core compensates with seed +
  cache + img2img).

TODO:
- Wire a runner: ComfyUI-GGUF workflow or diffusers ZImagePipeline.
- Pin the exact GGUF quant, text encoder and VAE files + hashes in
  `plugin.yaml`.
- Run the conformance pack and record real seconds/move on an 8GB card.
