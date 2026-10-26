# FLUX.2 Klein 4B

**Status: manifest + compiler complete, backend pending.**
`generate()` raises `PluginNotReady` explaining what's missing.

Requirements (declared): 8GB VRAM minimum (GGUF/offload territory),
13GB recommended at FP8; ~11GB download; Apache-2.0 for the 4B.

Implemented:
- Prompt compiler producing natural language **plus** the native
  multi-reference list (characters first, then the previous scene) —
  up to 10 references, carried in the compiled output.
- Native edit declared: changed rooms go down core's "edit" strategy
  for this plugin instead of inpaint/img2img.
- Honest grading: character consistency `medium` — Klein is fast and
  reference-native, but holds identity more weakly than the large
  FLUX.2 dev / FLUX.1 Kontext models.

TODO:
- Wire the runner (ComfyUI FLUX.2 workflow or diffusers).
- Pin exact weights/text-encoder/VAE files + hashes in `plugin.yaml`.
- Verify multi-ref behaviour and seconds/move in the conformance pack
  on a 13GB and an 8GB card.
