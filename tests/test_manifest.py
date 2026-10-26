import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import PLUGINS_ROOT  # noqa: E402
from dungeon_core.errors import ManifestError  # noqa: E402
from dungeon_core.loader import discover_manifests  # noqa: E402
from dungeon_core.manifest import load_manifest  # noqa: E402

EXPECTED_IDS = {
    "mock-placeholder",
    "sdxl-lightning-ipadapter",
    "z-image-turbo-gguf",
    "flux2-klein-4b",
    "mock-echo",
    "qwen3-8b-ollama",
}


class TestShippedManifests(unittest.TestCase):
    def test_all_shipped_plugins_load_and_validate(self):
        manifests = discover_manifests(PLUGINS_ROOT)
        self.assertEqual({m.id for m in manifests}, EXPECTED_IDS)
        for m in manifests:
            self.assertIn(m.kind, ("image", "text"))
            self.assertTrue(m.display_name)
            self.assertTrue(m.version)
            self.assertTrue(m.backend)

    def test_discovery_filters_by_kind(self):
        images = discover_manifests(PLUGINS_ROOT, kind="image")
        texts = discover_manifests(PLUGINS_ROOT, kind="text")
        self.assertEqual(len(images), 4)
        self.assertEqual(len(texts), 2)

    def test_sdxl_manifest_values(self):
        m = load_manifest(
            PLUGINS_ROOT / "image" / "sdxl-lightning-ipadapter" / "plugin.yaml"
        )
        self.assertEqual(m.capabilities.reference_images, "ip_adapter")
        self.assertEqual(m.capabilities.max_reference_images, 2)
        self.assertTrue(m.capabilities.negative_prompt)
        self.assertTrue(m.capabilities.inpaint)
        self.assertEqual(m.native.steps, 6)
        self.assertEqual(m.requirements.min_vram_gb, 6)

    def test_klein_manifest_values(self):
        m = load_manifest(PLUGINS_ROOT / "image" / "flux2-klein-4b" / "plugin.yaml")
        self.assertEqual(m.capabilities.reference_images, "native_multi_ref")
        self.assertEqual(m.capabilities.max_reference_images, 10)
        self.assertTrue(m.capabilities.native_edit)

    def test_qwen_manifest_is_declarative(self):
        m = load_manifest(PLUGINS_ROOT / "text" / "qwen3-8b-ollama" / "plugin.yaml")
        self.assertEqual(m.backend, "openai_compatible")
        self.assertEqual(m.endpoint, "http://127.0.0.1:11434/v1")
        self.assertEqual(m.model, "qwen3:8b-q4_K_M")
        self.assertEqual(m.template, "narrate.jinja")
        # Declarative: no plugin.py in that folder.
        self.assertFalse((m.plugin_dir / "plugin.py").exists())


class TestManifestValidation(unittest.TestCase):
    def _write(self, text: str) -> Path:
        tmp = tempfile.NamedTemporaryFile(
            "w", suffix=".yaml", delete=False, encoding="utf-8"
        )
        tmp.write(text)
        tmp.close()
        return Path(tmp.name)

    def test_missing_required_field_raises_clear_error(self):
        path = self._write("id: x\nkind: image\n")
        with self.assertRaises(ManifestError) as ctx:
            load_manifest(path)
        self.assertIn("display_name", str(ctx.exception))

    def test_bad_reference_mode_raises(self):
        path = self._write(
            "id: x\nkind: image\ndisplay_name: X\nversion: 0.1.0\n"
            "backend: mock\ncapabilities:\n  reference_images: telepathy\n"
        )
        with self.assertRaises(ManifestError) as ctx:
            load_manifest(path)
        self.assertIn("reference_images", str(ctx.exception))

    def test_bad_kind_raises(self):
        path = self._write(
            "id: x\nkind: audio\ndisplay_name: X\nversion: 0.1.0\nbackend: mock\n"
        )
        with self.assertRaises(ManifestError):
            load_manifest(path)


if __name__ == "__main__":
    unittest.main()
