from abc import ABC, abstractmethod
from typing import Any, Dict, Type


class PartNumberError(Exception):
    """
    Structured error for invalid part numbers.
    Carries:
      - segment: which logical segment failed (e.g. "output_signal")
      - invalid_code: the code the user provided (e.g. "Z")
      - valid_codes: list of valid codes for that segment (e.g. ["A", "B", "C"])
    """

    def __init__(
        self,
        message: str,
        segment: str | None = None,
        invalid_code: str | None = None,
        valid_codes: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.segment = segment
        self.invalid_code = invalid_code
        self.valid_codes = valid_codes or []


class PartNumberEngine(ABC):
    """
    Base class for all QuotePilot product engines.

    Each specific instrument (QPSAH200S, QPMAG, etc.)
    will subclass this and implement quote().
    """

    # Example: "QPSAH200S" or "QPMAG"
    model: str

    @abstractmethod
    def quote(self, part_number: str) -> Dict[str, Any]:
        """
        Return a full quote result for a part number.

        Expected general result pattern (you can add more fields if needed):

        {
          "model": str,
          "input_part_number": str,
          "normalized_part_number": str,
          "segments": {...},          # or a list, depending on engine
          "base_price": float,
          "adders_total": float,
          "final_price": float,
        }

        Implementations may raise PartNumberError when validation fails.
        """
        raise NotImplementedError


# ----------------------------------------------------------------------
# Engine registry helpers
# ----------------------------------------------------------------------

# Holds a mapping of model name -> engine class
# Example: "QPSAH200S" -> QPSAH200SEngine
ENGINE_REGISTRY: Dict[str, Type[PartNumberEngine]] = {}


def register_engine(engine_cls: Type[PartNumberEngine]) -> Type[PartNumberEngine]:
    """
    Class decorator to register a concrete engine in ENGINE_REGISTRY.

    Usage:

      @register_engine
      class QPSAH200SEngine(PartNumberEngine):
          model = "QPSAH200S"
          ...

    When Python imports the module containing that class, the decorator runs
    and adds the class to ENGINE_REGISTRY under its .model name.
    """
    model = getattr(engine_cls, "model", None)
    if not model:
        raise ValueError("Engine classes must define a class attribute 'model'.")

    ENGINE_REGISTRY[model] = engine_cls
    return engine_cls


def get_engine(model: str) -> PartNumberEngine:
    """
    Look up an engine by model name and return an instance.

    Example:
      engine = get_engine("QPSAH200S")
      result = engine.quote("QPSAH200S-A-M-G-3-C-3-1-1-C-1-02")
    """
    try:
        engine_cls = ENGINE_REGISTRY[model]
    except KeyError:
        raise ValueError(f"Unknown model: {model!r}")
    return engine_cls()
