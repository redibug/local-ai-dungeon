# Local AI Dungeon Crawler

A fully local AI dungeon crawler: real RPG stats and game logic in code,
an LLM that only narrates, and an image model that re-renders the scene
every move — no API keys, no daily limits, nothing leaves the player's
machine.

## The plugin idea

Core never knows a model. Everything model-specific lives in a **plugin
folder**: the model files (or a pointer to them) + the glue code that
integrates it + a `plugin.yaml` manifest that honestly declares its
requirements and capabilities.

- Core sends **structured** requests (a `SceneRequest`: location,
  entities, characters, previous image, what changed, a seed) — never a
  prompt string. Each image plugin compiles that into its own model's
  dialect (SDXL wants tags and a negative prompt; Z-Image Turbo wants
  natural language and must *not* get a negative prompt; FLUX.2 Klein
  takes native reference images). See
  [docs/PLUGIN_ARCHITECTURE.md](docs/PLUGIN_ARCHITECTURE.md).
- Core plans around the manifest: a changed room is served by native
  edit, inpaint, img2img, or txt2img depending on what the plugin
  declares; characters use native references, IP-Adapter, or a prompt
  description when the plugin has nothing better — and the player is
  told when it degrades.
- Text plugins are deliberately boring: usually just a manifest
  pointing at a local endpoint (Ollama / LM Studio / llama.cpp) plus a
  narration template. The text model narrates a state diff; stats,
  inventory and damage always stay in core code.
- Players can swap plugins to find what runs best on *their* computer.
  A conformance pack (see `conformance/`) gives every image plugin the
  same scenes, the same recurring character, and the same
  revisited-with-a-change room, and reports seconds-per-move and fit.

Writing your own plugin: [docs/WRITING_A_PLUGIN.md](docs/WRITING_A_PLUGIN.md).

## Quickstart

Requires Python 3.11+ and PyYAML. No other dependencies, no build step
beyond the package metadata in `pyproject.toml`.

```bash
pip install -e .            # or: export PYTHONPATH=src

# End-to-end demo with the two mock plugins (no GPU, no models):
python -m dungeon_core.demo

# Test suite (stdlib unittest):
python -m unittest discover -s tests -v

# Conformance pack against the mock placeholder plugin:
python -m dungeon_core.conformance
```

The demo narrates a move, renders a scene, revisits it unchanged
(cache hit — no render), then revisits it changed (fallback strategy),
printing what happened at each step.

## Repo layout

```
src/dungeon_core/     core: contracts, manifest loading, plugin loader,
                      fallback strategies, GPU arbiter, scene cache, demo
plugins/image/        image plugins (mock, SDXL, Z-Image, FLUX.2 Klein)
plugins/text/         text plugins (mock echo, Qwen3 via Ollama)
conformance/          the shared benchmark pack + scoring guide
tests/                stdlib unittest suite
docs/                 architecture + plugin authoring guide
```

Model weights are never committed (see `.gitignore`); a plugin's
manifest lists the files it needs.

## Status

**Scaffold v0.1.** Real and runnable: core contracts, manifest
validation, plugin discovery/loading, fallback planning, scene cache,
the mock plugins, all three real plugins' manifests and prompt
compilers, and the conformance pack.

Honestly not done yet: the SDXL plugin's ComfyUI workflow has not been
run against a live server; the Z-Image and FLUX.2 Klein backends raise
`PluginNotReady` (compilers and manifests are complete, the runners
are not wired up); there is no game loop, UI, or model downloader yet.

## License

TBD — no license has been chosen yet, so no license file is included.
Individual model weights carry their own licenses; each plugin's
manifest states the one that applies to it.
