"""Handlers package — imports all handler modules to trigger @register decorators."""

from backend.handlers import code  # noqa: F401
from backend.handlers import (
    ai_langchain as ai_langchain,
    apps as apps,
    data_transform as data_transform,
    databases as databases,
    fallback as fallback,
    flow_control as flow_control,
    http as http,
    triggers as triggers,
)

# Sentinel used by pipeline to confirm registration side-effects have run.
_ensure_all_registered = True
