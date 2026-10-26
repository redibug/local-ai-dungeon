"""GPU arbiter: exactly one plugin holds the GPU at a time.

On an 8GB card the text model and the image model cannot co-exist, so
per move core does: load text -> narrate -> unload -> load image ->
render -> (optionally unload). Plugins implement load()/unload();
the arbiter, not the plugins, decides load order and eviction.
"""

from __future__ import annotations

from typing import Any, Optional


class GPUArbiter:
    def __init__(self) -> None:
        self._current: Any = None
        self._current_id: Optional[str] = None

    @property
    def current_id(self) -> Optional[str]:
        return self._current_id

    @property
    def loaded_plugin(self) -> Any:
        return self._current

    def load(self, plugin: Any) -> Any:
        """Make ``plugin`` the loaded one, unloading whatever was there.

        Plugins are identified by their manifest id when they carry a
        manifest, else by object identity. Loading the already-loaded
        plugin is a no-op.
        """
        plugin_id = getattr(getattr(plugin, "manifest", None), "id", None) or str(
            id(plugin)
        )
        if self._current is plugin:
            return plugin
        self.unload_current()
        load_fn = getattr(plugin, "load", None)
        if callable(load_fn):
            load_fn()
        self._current = plugin
        self._current_id = plugin_id
        return plugin

    def unload_current(self) -> None:
        if self._current is None:
            return
        unload_fn = getattr(self._current, "unload", None)
        if callable(unload_fn):
            unload_fn()
        self._current = None
        self._current_id = None
