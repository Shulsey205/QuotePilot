from typing import Dict

from .base_engine import PartNumberEngine
from .dp_qpsah200s import QPSAH200SEngine
from .mag_qpmag import QPMAGEngine


_qpsah200s_engine = QPSAH200SEngine()
_qpmag_engine = QPMAGEngine()

ENGINE_REGISTRY: Dict[str, PartNumberEngine] = {
    "QPSAH200S": _qpsah200s_engine,
    "QPMAG": _qpmag_engine,
}


def get_engine(model: str) -> PartNumberEngine:
    try:
        return ENGINE_REGISTRY[model]
    except KeyError:
        raise ValueError(f"Unsupported model [{model}]")
