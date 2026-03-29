"""Handlers package — imports all handler modules to trigger @register decorators."""

from backend.handlers import code  # noqa: F401
from backend.handlers import (
    ai_langchain,
    apps,
    data_transform,
    databases,
    fallback,
    flow_control,
    http,
    triggers,
)

# Sentinel used by pipeline to confirm registration side-effects have run.
_ensure_all_registered = True
