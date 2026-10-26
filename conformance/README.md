# Conformance pack

The conformance pack is how a player finds out what works on *their*
computer, and how a plugin author proves a plugin behaves. Every
image plugin runs the **same** pack; core times it and reports a
plain verdict. A plugin that only works on its author's machine has
not finished.

Run it:

```bash
python -m dungeon_core.conformance                      # mock plugin, 8GB assumed
python -m dungeon_core.conformance --plugin flux2-klein-4b --vram-gb 13
```

## What's in pack.json

- **10 standard scenes** — the spread of rooms a dungeon actually
  needs: entrance, corridors, vault, cavern, throne room, library,
  prison, shrine, chasm bridge, boss antechamber. Each is a structured
  scene description (the same shape as a `SceneRequest`), not a prompt.
- **character_consistency** — one character (fixed description block,
  fixed char_id) in 3 different scenes. There is no way to score this
  honestly with a number: the 3 outputs are judged **by eye**, side by
  side. Same person, or not?
- **room_revisit** — one room, then the same room with a stated change
  (chest opened, a torch out). Judged by eye too: is it recognisably
  the same room with that change, or a new room wearing its name?

## How a plugin is scored

- **Time per move** — wall-clock average of `generate()` over the
  standard scenes (plus the rest of the pack). Per-move play means an
  image every few seconds; a 40-second render is a loading screen,
  not a move.
- **Peak VRAM** — currently taken from the plugin's `estimate()`
  (declared, not measured; a real GPU sampler is TODO and reports
  must say which one a number is).
- **Fit** — the manifest's `min_vram_gb` vs. the card being scored
  for. Quantised builds declare the VRAM of the quant, not the
  full-precision model.

## Verdict bands

| Verdict | Meaning |
|---|---|
| `Playable (~Xs/move)` | average ≤ 8s/move and it fits the card |
| `Slow (~Xs/move)` | 8–20s/move — playable if the player tolerates pauses |
| `Too slow for per-move play` | > 20s/move |
| `Won't fit (needs A GB, you have B GB)` | declared minimum VRAM exceeds the card |

Qualitative results (character sameness, room-revisit sameness) are
reported next to the verdict, never folded into it — a fast plugin
that redraws your character every room is not "Playable", it's fast
and inconsistent, and the player deserves to see both facts.
