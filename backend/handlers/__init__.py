"""Handlers package — imports all handler modules to trigger @register decorators."""

from backend.handlers import ai_langchain as ai_langchain
from backend.handlers import apps as apps
from backend.handlers import code  # noqa: F401
from backend.handlers import data_transform as data_transform
from backend.handlers import databases as databases
from backend.handlers import fallback as fallback
from backend.handlers import flow_control as flow_control
from backend.handlers import http as http
from backend.handlers import triggers as triggers

# Sentinel used by pipeline to confirm registration side-effects have run.
_ensure_all_registered = True
