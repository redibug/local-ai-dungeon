# Writing a plugin

A plugin is one folder. Everything your model needs — glue code,
workflow files, settings schema, the honest list of what it can and
can't do — lives in that folder, and nothing about your model leaks
into core. If core would need to change to support your model, the
contract is missing something; open an issue instead of forking core.

## 1. Copy a folder

Image plugin: copy `plugins/image/mock-placeholder/` (the smallest
complete contract implementation) or the real plugin closest to yours.
Text plugin: copy `plugins/text/qwen3-8b-ollama/` — most text plugins
need **no code at all**, just a manifest and a template.

```
plugins/image/my-model/
  plugin.yaml          # required
  plugin.py            # required for image plugins
  config.schema.json   # your settings; core renders UI from this
  README.md            # status, honestly
```

## 2. Fill in the manifest — honestly

`plugin.yaml` must declare: `id`, `kind`, `display_name`, `version`,
`backend`, plus `requirements` (min/recommended VRAM, download size,
the model files needed) and `capabilities`.

Declare what the model *actually* does:

- No reference-image support? `reference_images: none`, and core will
  fall back to the character's description block and tell the player
  consistency is weak. That's a fine plugin. Claiming `ip_adapter`
  you don't wire up is a broken one.
- Distilled model that breaks with a negative prompt or normal CFG?
  `negative_prompt: false` and your real steps/CFG under `native:` —
  core trusts those numbers instead of imposing defaults.
- Can't inpaint? Say so. Core will route changed rooms through
  img2img or txt2img+seed for you.

Validation is strict about fields existing and values being sane
(`dungeon_core.manifest.load_manifest` raises `ManifestError` naming
the field). It cannot check honesty. The conformance pack can.

## 3. Implement the contract (image plugins)

Your `plugin.py` exposes `create_plugin(manifest, plugin_dir)`
returning an object with:

```python
install()   # fetch/verify the manifest's files, or raise PluginNotReady
health()    # {"ok": bool, "backend": ..., "detail": ...}
load()      # take the GPU (or note that your server holds the model)
unload()    # actually free it — the arbiter swaps models per move
estimate(req) -> {"seconds": ..., "peak_vram_gb": ...}
generate(req, strategy="txt2img") -> SceneResult
compile_prompt(req)   # your dialect compiler; keep it pure & testable
```

The heart is the compiler: `SceneRequest` in (structured scene —
location, entities, characters, previous image, change, seed), your
model's prompt dialect out. Tag-style + negative for SDXL, natural
language + *no* negative for distilled Turbo models, reference lists
for native multi-ref models. Look at the three shipped compilers;
each is deliberately different, and core doesn't care.

Unfinished is allowed. Not-ready is a first-class state: raise
`PluginNotReady` with a message that says what's missing and what the
player can do instead. Silent stubs that return junk images are the
one unacceptable failure mode.

For text plugins with code, the contract is just `load()`,
`unload()` and `narrate(NarrationRequest) -> NarrationResult`.
Remember: narration only. Stats and state belong to core; a text
plugin that tries to own them is breaking the game's rules, not
extending them.

## 4. Run conformance

```bash
python -m dungeon_core.conformance --plugin my-model --vram-gb 8
python -m unittest discover -s tests
```

Ship the numbers in your plugin's README: seconds-per-move on a named
card, the verdict band, and the character-consistency outputs judged
by eye. Then write your README's status line the way the shipped
plugins do — what's implemented, what's TODO, no adjectives doing the
work of benchmarks.
