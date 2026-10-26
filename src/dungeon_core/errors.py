"""Errors raised by core and plugins.

These are deliberately plain: a player (or a test) should be able to
tell *what* is missing or invalid from the message alone.
"""


class ManifestError(ValueError):
    """A plugin.yaml is missing required fields or has invalid values."""


class PluginLoadError(RuntimeError):
    """A plugin folder could not be imported or instantiated."""


class PluginNotReady(RuntimeError):
    """The plugin is real but something it needs is not available yet.

    Raised for unfinished backends and for missing local services
    (e.g. no ComfyUI server answering). The message must say what is
    missing and what to do about it.
    """
