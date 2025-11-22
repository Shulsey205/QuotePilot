# PartNumberEngine/__init__.py

from .base_engine import (
    PartNumberEngine,
    PartNumberError,
    register_engine,
    get_engine,
    ENGINE_REGISTRY,
)

# Import concrete engines so their @register_engine decorators run
from .dp_qpsah200s import QPSAH200SEngine
from .qpmag_engine import QPMAGEngine

__all__ = [
    "PartNumberEngine",
    "PartNumberError",
    "register_engine",
    "get_engine",
    "ENGINE_REGISTRY",
    "QPSAH200SEngine",
    "QPMAGEngine",
]
