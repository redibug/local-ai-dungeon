# Mock Placeholder Image Plugin

**Status: test double.** There is no model here. It implements the
image plugin contract with a deterministic stdlib-only PNG writer so
core, the demo, conformance and the tests run anywhere.

- Palette derives from seed + scene_id; the block pattern derives
  from the full request, so a changed room differs but keeps its
  colours.
- Capabilities are declared honestly: txt2img + img2img, no inpaint,
  no reference images, weak character consistency, 0 VRAM.

Use it to develop against the contract. Do not ship it as a renderer.
