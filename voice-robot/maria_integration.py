"""Compatibility import for maria-integration.py.

The original file uses a hyphen in its name, but Python imports require a valid
module identifier. Render and local tests import this underscore module.
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


_source = Path(__file__).with_name("maria-integration.py")
_spec = spec_from_file_location("maria_integration_source", _source)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Cannot load {_source}")

_module = module_from_spec(_spec)
_spec.loader.exec_module(_module)

MariaBotHandler = _module.MariaBotHandler
handle_incoming_call = _module.handle_incoming_call
synthesize_with_eleven_labs = _module.synthesize_with_eleven_labs
voximplant_handler = _module.voximplant_handler
