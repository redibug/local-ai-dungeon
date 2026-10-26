import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import PLUGINS_ROOT  # noqa: E402
from dungeon_core.contracts import derive_seed  # noqa: E402
from dungeon_core.fallback import (  # noqa: E402
    choose_character_strategy,
    choose_room_strategy,
)
from dungeon_core.loader import find_manifest  # noqa: E402


class TestDeriveSeed(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(
            derive_seed("save1", "dungeon1/3,4"), derive_seed("save1", "dungeon1/3,4")
        )

    def test_differs_by_scene_and_save(self):
        base = derive_seed("save1", "dungeon1/3,4")
        self.assertNotEqual(base, derive_seed("save1", "dungeon1/3,5"))
        self.assertNotEqual(base, derive_seed("save2", "dungeon1/3,4"))

    def test_in_sampler_safe_range(self):
        seed = derive_seed("save", "scene")
        self.assertGreaterEqual(seed, 0)
        self.assertLessEqual(seed, 2**31 - 1)


class TestFallback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sdxl = find_manifest(PLUGINS_ROOT, "sdxl-lightning-ipadapter")
        cls.zimage = find_manifest(PLUGINS_ROOT, "z-image-turbo-gguf")
        cls.klein = find_manifest(PLUGINS_ROOT, "flux2-klein-4b")
        cls.mock = find_manifest(PLUGINS_ROOT, "mock-placeholder")

    def test_first_visit_is_txt2img(self):
        for m in (self.sdxl, self.zimage, self.klein, self.mock):
            self.assertEqual(choose_room_strategy(m, False, False), "txt2img")

    def test_revisit_unchanged_is_cache_for_everyone(self):
        for m in (self.sdxl, self.zimage, self.klein, self.mock):
            self.assertEqual(choose_room_strategy(m, True, False), "cache")

    def test_klein_changed_room_uses_native_edit(self):
        self.assertEqual(choose_room_strategy(self.klein, True, True), "edit")

    def test_sdxl_changed_room_uses_inpaint(self):
        self.assertEqual(choose_room_strategy(self.sdxl, True, True), "inpaint")

    def test_zimage_changed_room_uses_img2img_not_inpaint(self):
        # Z-Image declares no inpaint; core must not ask for it.
        self.assertEqual(choose_room_strategy(self.zimage, True, True), "img2img")

    def test_klein_character_uses_native_ref(self):
        self.assertEqual(choose_character_strategy(self.klein, True), "native_ref")

    def test_sdxl_character_uses_ip_adapter(self):
        self.assertEqual(choose_character_strategy(self.sdxl, True), "ip_adapter")

    def test_mock_and_zimage_characters_are_prompt_only(self):
        self.assertEqual(choose_character_strategy(self.mock, True), "prompt_only")
        self.assertEqual(choose_character_strategy(self.zimage, True), "prompt_only")

    def test_no_ref_is_prompt_only_for_everyone(self):
        for m in (self.sdxl, self.zimage, self.klein, self.mock):
            self.assertEqual(choose_character_strategy(m, False), "prompt_only")


if __name__ == "__main__":
    unittest.main()
