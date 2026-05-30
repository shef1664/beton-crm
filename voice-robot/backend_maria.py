"""Compatibility entrypoint for Render/uvicorn.

Use:
    uvicorn backend_maria:app --host 0.0.0.0 --port $PORT

The main implementation lives in backend-maria.py for continuity with the
existing task files.
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


_source = Path(__file__).with_name("backend-maria.py")
_spec = spec_from_file_location("backend_maria_source", _source)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Cannot load {_source}")

_module = module_from_spec(_spec)
_spec.loader.exec_module(_module)

app = _module.app
