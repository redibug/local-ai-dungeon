import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import PLUGINS_ROOT, sample_scene  # noqa: E402
from dungeon_core.errors import PluginNotReady  # noqa: E402
from dungeon_core.loader import instantiate_plugin, find_manifest  # noqa: E402


def load(plugin_id):
    return instantiate_plugin(find_manifest(PLUGINS_ROOT, plugin_id))


class TestSDXLCompiler(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin = load("sdxl-lightning-ipadapter")

    def test_produces_negative_prompt(self):
        compiled = self.plugin.compile_prompt(sample_scene())
        self.assertIsNotNone(compiled.negative)
        self.assertIn("blurry", compiled.negative)

    def test_positive_is_tag_style_with_scene_content(self):
        compiled = self.plugin.compile_prompt(sample_scene())
        self.assertIn("treasure vault", compiled.positive)
        self.assertIn("wet stone", compiled.positive)
        self.assertIn("chest", compiled.positive)
        self.assertIn("red braided hair", compiled.positive)

    def test_ip_adapter_references_collected(self):
        compiled = self.plugin.compile_prompt(sample_scene())
        self.assertEqual(compiled.references, ["refs/player.png"])

    def test_lightning_native_settings(self):
        compiled = self.plugin.compile_prompt(sample_scene())
        self.assertEqual(compiled.steps, 6)
        self.assertEqual(compiled.cfg, 1.5)

    def test_generate_without_configured_checkpoint_says_so(self):
        with self.assertRaises(PluginNotReady) as ctx:
            self.plugin.generate(sample_scene())
        self.assertIn("checkpoint", str(ctx.exception).lower())


class TestZImageCompiler(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin = load("z-image-turbo-gguf")

    def test_negative_prompt_is_none(self):
        compiled = self.plugin.compile_prompt(sample_scene())
        self.assertIsNone(compiled.negative)

    def test_distilled_settings(self):
        compiled = self.plugin.compile_prompt(sample_scene())
        self.assertEqual(compiled.cfg, 1.0)
        self.assertEqual(compiled.steps, 8)

    def test_natural_language_prompt(self):
        compiled = self.plugin.compile_prompt(sample_scene())
        self.assertIn("treasure vault", compiled.positive)
        self.assertTrue(compiled.positive.endswith("."))

    def test_generate_raises_not_ready(self):
        with self.assertRaises(PluginNotReady):
            self.plugin.generate(sample_scene())


class TestKleinCompiler(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin = load("flux2-klein-4b")

    def test_references_included(self):
        compiled = self.plugin.compile_prompt(sample_scene())
        self.assertIn("refs/player.png", compiled.references)

    def test_prompt_mentions_reference_image(self):
        compiled = self.plugin.compile_prompt(sample_scene())
        self.assertIn("reference image", compiled.positive)

    def test_previous_image_added_to_references_for_edits(self):
        scene = sample_scene(previous_image="scenes/vault.png",
                             change="the chest is now closed")
        compiled = self.plugin.compile_prompt(scene)
        self.assertIn("scenes/vault.png", compiled.references)
        self.assertIn("Edit the previous scene", compiled.positive)

    def test_generate_raises_not_ready(self):
        with self.assertRaises(PluginNotReady):
            self.plugin.generate(sample_scene())


if __name__ == "__main__":
    unittest.main()
