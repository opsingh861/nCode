"""Node handler registry with @register decorator."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.handlers.base import NodeHandler

# Registry: n8n node type string (lowercase, canonical) → handler instance.
_REGISTRY: dict[str, "NodeHandler"] = {}


def register(*node_types: str):
    """Class decorator that registers a handler for one or more n8n node types.

    Usage::

        @register("n8n-nodes-base.httpRequest")
        class HttpRequestHandler:
            def generate(self, node, ctx): ...
            def supported_operations(self): return [...]
            def required_packages(self): return [...]
    """

    def decorator(cls):
        instance = cls()
        for node_type in node_types:
            _REGISTRY[node_type.lower()] = instance
        return cls

    return decorator


def get_handler(node_type: str) -> "NodeHandler | None":
    """Return the registered handler for the given n8n node type, or None."""
    return _REGISTRY.get(node_type.lower())


def get_supported_types() -> list[str]:
    """Return all registered n8n node type strings."""
    return list(_REGISTRY.keys())


def is_supported(node_type: str) -> bool:
    return node_type.lower() in _REGISTRY
