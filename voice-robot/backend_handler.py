#!/usr/bin/env python3
"""Import-safe wrapper for backend-handler.py."""

import importlib.util
from pathlib import Path

_path = Path(__file__).with_name("backend-handler.py")
_spec = importlib.util.spec_from_file_location("backend_handler_impl", _path)
if _spec is None or _spec.loader is None:
    raise RuntimeError("cannot load backend-handler.py")
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

app = _module.app
