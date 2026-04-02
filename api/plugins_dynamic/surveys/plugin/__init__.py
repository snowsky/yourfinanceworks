"""
Plugin package — re-exports register_plugin for the YFW plugin loader.
"""

from .api import register_plugin  # noqa: F401

__all__ = ["register_plugin"]
