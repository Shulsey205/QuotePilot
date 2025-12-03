# Backend/PartNumberEngine/__init__.py

"""
Package init for PartNumberEngine.

This file's job is to import all concrete engine modules so that their
@register_engine decorators run at import time and populate ENGINE_REGISTRY
in base_engine.py.

Any new engine module should be imported here.
"""

# Import engine modules solely for their side effects (registration).
# Each module defines an engine class decorated with @register_engine(...).

from . import dp_qpsah200s  # noqa: F401
from . import nl_qpsah200s  # noqa: F401
from . import qpmag_engine  # noqa: F401
