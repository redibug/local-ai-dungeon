"""Shared test helpers: locate the repo and build a sample scene."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
PLUGINS_ROOT = REPO_ROOT / "plugins"

from dungeon_core.contracts import (  # noqa: E402
    CharacterInScene,
    EntityInScene,
    SceneRequest,
)


def sample_scene(**overrides) -> SceneRequest:
    scene = SceneRequest(
        scene_id="dungeon1/vault",
        seed=882134,
        location={
            "type": "treasure vault",
            "materials": ["wet stone"],
            "features": ["stone pillars", "iron torches"],
        },
        entities=[EntityInScene(kind="chest", state="open, empty")],
        characters=[
            CharacterInScene(
                char_id="player",
                action="kneeling by the chest",
                ref_image="refs/player.png",
                description="woman, red braided hair, scar on left cheek",
            )
        ],
        mood="tension",
        lighting="torchlight",
        aspect="16:9",
    )
    for key, value in overrides.items():
        setattr(scene, key, value)
    return scene
