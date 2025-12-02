from typing import Any, Dict, Callable, Type


# ---------------------------------------------------------------------------
# Error type used by all engines
# ---------------------------------------------------------------------------


class PartNumberError(Exception):
    """
    Structured error raised when a part-number segment or code is invalid.

    Attributes:
        segment:      Human-readable segment name (e.g. "Output signal type")
        invalid_code: The bad code that was supplied (e.g. "Z")
        valid_codes:  List of valid codes for this segment (e.g. ["A", "B", "C"])
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


# ---------------------------------------------------------------------------
# Base engine + registry
# ---------------------------------------------------------------------------


class PartNumberEngine:
    """
    Minimal base class for all QuotePilot engines.
    Engines must implement quote(part_number) -> dict.
    """

    model: str = ""

    def quote(self, part_number: str) -> Dict[str, Any]:  # type: ignore[override]
        raise NotImplementedError("Engines must implement quote(part_number)")


ENGINE_REGISTRY: Dict[str, PartNumberEngine] = {}


def register_engine(model: str) -> Callable[[Type[PartNumberEngine]], Type[PartNumberEngine]]:
    """
    Class decorator used by engine implementations to register themselves.

    Example:
        @register_engine("QPSAH200S")
        class QPSAH200SEngine(PartNumberEngine):
            ...
    """

    def decorator(cls: Type[PartNumberEngine]) -> Type[PartNumberEngine]:
        ENGINE_REGISTRY[model] = cls()
        return cls

    return decorator


def get_engine(model: str) -> PartNumberEngine:
    """
    Look up an engine instance by model code (e.g. "QPSAH200S", "QPMAG").
    """
    if model not in ENGINE_REGISTRY:
        raise KeyError(
            f"Unknown model '{model}'. Available: {sorted(list(ENGINE_REGISTRY.keys()))}"
        )
    return ENGINE_REGISTRY[model]
