"""Handlers package — imports all handler modules to trigger @register decorators."""

from backend.handlers import (  # noqa: F401
    triggers,
    http,
    flow_control,
    data_transform,
    databases,
    apps,
    ai_langchain,
    code,
    fallback,
)

# Sentinel used by pipeline to confirm registration side-effects have run.
_ensure_all_registered = True
