import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import PLUGINS_ROOT, REPO_ROOT, sample_scene  # noqa: E402
from dungeon_core.arbiter import GPUArbiter  # noqa: E402
from dungeon_core.cache import SceneCache, compute_state_hash  # noqa: E402
from dungeon_core.contracts import NarrationRequest  # noqa: E402
from dungeon_core.loader import load_plugin_by_id  # noqa: E402

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class TestMockImagePlugin(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.plugin = load_plugin_by_id(PLUGINS_ROOT, "mock-placeholder")
        self.plugin.output_dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_generates_valid_png(self):
        result = self.plugin.generate(sample_scene())
        data = Path(result.image).read_bytes()
        self.assertTrue(data.startswith(PNG_MAGIC))
        self.assertEqual(result.actual_seed, 882134)
        self.assertEqual(result.plugin_id, "mock-placeholder")

    def test_deterministic_for_same_seed_and_scene(self):
        first = Path(self.plugin.generate(sample_scene()).image).read_bytes()
        second = Path(self.plugin.generate(sample_scene()).image).read_bytes()
        self.assertEqual(first, second)

    def test_different_seed_changes_image(self):
        first = Path(self.plugin.generate(sample_scene()).image).read_bytes()
        other = Path(
            self.plugin.generate(sample_scene(seed=1234)).image
        ).read_bytes()
        self.assertNotEqual(first, other)


class TestMockTextPlugin(unittest.TestCase):
    def test_narrates_from_structured_request(self):
        plugin = load_plugin_by_id(PLUGINS_ROOT, "mock-echo")
        result = plugin.narrate(
            NarrationRequest(
                event={"action": "enter", "location": "the vault"},
                game_state={"hp": 20},
                scene_id="dungeon1/vault",
            )
        )
        self.assertIn("the vault", result.text)
        self.assertIn("20 HP", result.text)
        self.assertEqual(result.plugin_id, "mock-echo")


class TestSceneCache(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = SceneCache(self.tmp.name)
        self.image = Path(self.tmp.name) / "img.png"
        self.image.write_bytes(PNG_MAGIC + b"fake")
        self.state = {"entities": [{"kind": "chest", "state": "closed"}]}

    def tearDown(self):
        self.tmp.cleanup()

    def test_put_then_get_hits(self):
        self.cache.put("dungeon1/vault", self.state, str(self.image))
        self.assertEqual(self.cache.get("dungeon1/vault", self.state), str(self.image))

    def test_state_change_is_a_different_key_and_misses(self):
        self.cache.put("dungeon1/vault", self.state, str(self.image))
        changed = {"entities": [{"kind": "chest", "state": "open, empty"}]}
        self.assertNotEqual(
            compute_state_hash(self.state), compute_state_hash(changed)
        )
        self.assertIsNone(self.cache.get("dungeon1/vault", changed))

    def test_missing_scene_misses(self):
        self.assertIsNone(self.cache.get("dungeon1/nowhere", self.state))

    def test_index_persists_to_disk(self):
        self.cache.put("dungeon1/vault", self.state, str(self.image))
        reloaded = SceneCache(self.tmp.name)
        self.assertEqual(
            reloaded.get("dungeon1/vault", self.state), str(self.image)
        )


class TestArbiter(unittest.TestCase):
    def test_only_one_plugin_loaded_at_a_time(self):
        text = load_plugin_by_id(PLUGINS_ROOT, "mock-echo")
        image = load_plugin_by_id(PLUGINS_ROOT, "mock-placeholder")
        arbiter = GPUArbiter()
        arbiter.load(text)
        self.assertTrue(text.loaded)
        arbiter.load(image)
        self.assertFalse(text.loaded)  # evicted
        self.assertTrue(image.loaded)
        self.assertEqual(arbiter.current_id, "mock-placeholder")
        arbiter.unload_current()
        self.assertFalse(image.loaded)
        self.assertIsNone(arbiter.current_id)


class TestConformancePack(unittest.TestCase):
    def test_pack_shape(self):
        pack = json.loads(
            (REPO_ROOT / "conformance" / "pack.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(pack["scenes"]), 10)
        self.assertEqual(len(pack["character_consistency"]["scenes"]), 3)
        self.assertIn("scene", pack["room_revisit"])
        self.assertIn("changed_scene", pack["room_revisit"])
        ids = [s["id"] for s in pack["scenes"]]
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
