# Backend/PartNumberEngine/base_engine.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Type


# --------------------------------------------------------------------------------------
# Error type for part-number issues
# --------------------------------------------------------------------------------------


@dataclass
class PartNumberError(Exception):
    """
    Error raised when a part number cannot be parsed or validated.

    Fields are structured so the API can return clean JSON describing:
    - which segment failed
    - what code was invalid
    - which codes are valid
    """

    message: str
    segment: Optional[str] = None
    invalid_code: Optional[str] = None
    valid_codes: Optional[List[str]] = None

    def __post_init__(self) -> None:
        super().__init__(self.message)
        if self.valid_codes is None:
            self.valid_codes = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message": self.message,
            "segment": self.segment,
            "invalid_code": self.invalid_code,
            "valid_codes": self.valid_codes,
        }


# --------------------------------------------------------------------------------------
# Engine registry and helpers
# --------------------------------------------------------------------------------------


ENGINE_REGISTRY: Dict[str, Type["PartNumberEngine"]] = {}


def register_engine(model_name: str):
    """
    Class decorator to register a PartNumberEngine implementation.

    Usage:

        @register_engine("QPSAH200S")
        class QPSAH200SEngine(PartNumberEngine):
            ...
    """

    def decorator(cls: Type["PartNumberEngine"]) -> Type["PartNumberEngine"]:
        ENGINE_REGISTRY[model_name] = cls
        return cls

    return decorator


def get_engine(model_name: str) -> "PartNumberEngine":
    """
    Look up an engine by its model name and return an instance.

    Raises PartNumberError if the model is unknown.
    """
    try:
        engine_cls = ENGINE_REGISTRY[model_name]
    except KeyError:
        available = sorted(ENGINE_REGISTRY.keys())
        raise PartNumberError(
            message=f"Unknown model '{model_name}'. Available: {available}"
        )

    return engine_cls()


# --------------------------------------------------------------------------------------
# Base implementation for all engines
# --------------------------------------------------------------------------------------


class PartNumberEngine:
    """
    Base class for all QuotePilot engines.

    Concrete subclasses must define:

        MODEL: str
        BASE_PRICE: float
        MASTER_SEGMENTS: List[Dict[str, Any]]

    MASTER_SEGMENTS is a list of segment definitions in order, each of which looks like:

        {
            "key": "line_size",
            "label": "Line size",
            "position": 1,
            "codes": {
                "04": {"description": '1\" (DN25)', "adder": 0.0},
                "06": {"description": '1.5\" (DN40)', "adder": 50.0},
                ...
            },
        }
    """

    MODEL: str = ""
    BASE_PRICE: float = 0.0
    MASTER_SEGMENTS: List[Dict[str, Any]] = []
    BASELINE_PART_NUMBER: Optional[str] = None

    # -------------------------- core public API -------------------------------------

    def quote(self, part_number: str) -> Dict[str, Any]:
        """
        Parse and price a part number.

        Returns a structured dict with:

            {
                "model": ...,
                "part_number": ...,
                "base_price": ...,
                "segments": [...],
                "total_adders": ...,
                "final_price": ...,
            }

        Raises PartNumberError if any segment code is invalid.
        """
        parsed_segments, total_adders = self._parse_and_price_segments(part_number)

        base_price = float(self.BASE_PRICE)
        final_price = base_price + total_adders

        return {
            "model": self.MODEL,
            "part_number": part_number,
            "base_price": base_price,
            "segments": parsed_segments,
            "total_adders": total_adders,
            "final_price": final_price,
        }

    # -------------------------- internal helpers ------------------------------------

    def _parse_and_price_segments(
        self, part_number: str
    ) -> (List[Dict[str, Any]], float):
        """
        Internal helper used by quote().

        Splits the part number, validates all segment codes against MASTER_SEGMENTS,
        and calculates the total adder.
        """
        if not part_number:
            raise PartNumberError("Empty part number")

        parts = part_number.split("-")

        if len(parts) < 2:
            raise PartNumberError(
                message="Part number must include model and at least one segment"
            )

        model = parts[0].upper()

        if model != self.MODEL:
            raise PartNumberError(
                message=f"Model prefix '{model}' does not match engine model '{self.MODEL}'",
                segment="model",
                invalid_code=model,
                valid_codes=[self.MODEL],
            )

        tokens = parts[1:]

        if len(tokens) != len(self.MASTER_SEGMENTS):
            raise PartNumberError(
                message=(
                    f"Expected {len(self.MASTER_SEGMENTS)} segments for model "
                    f"{self.MODEL} but got {len(tokens)}"
                )
            )

        parsed_segments: List[Dict[str, Any]] = []
        total_adders: float = 0.0

        for index, seg_def in enumerate(self.MASTER_SEGMENTS):
            try:
                code = tokens[index]
            except IndexError:
                raise PartNumberError(
                    message=f"Missing segment at position {index + 1}",
                    segment=seg_def.get("key"),
                )

            codes_dict: Dict[str, Dict[str, Any]] = seg_def.get("codes", {})
            if code not in codes_dict:
                valid = sorted(codes_dict.keys())
                raise PartNumberError(
                    message=(
                        f"Invalid code [{code}] for segment "
                        f"[{seg_def.get('label', seg_def.get('key'))}]. "
                        f"Valid options are: {', '.join(valid)}"
                    ),
                    segment=seg_def.get("key"),
                    invalid_code=code,
                    valid_codes=valid,
                )

            code_info = codes_dict[code]
            description = code_info.get("description", "")
            adder = float(code_info.get("adder", 0.0))

            parsed_segments.append(
                {
                    "key": seg_def.get("key"),
                    "label": seg_def.get("label"),
                    "code": code,
                    "description": description,
                    "adder": adder,
                }
            )

            total_adders += adder

        return parsed_segments, total_adders


# --------------------------------------------------------------------------------------
# Import concrete engines so they register themselves
# --------------------------------------------------------------------------------------

# These imports are intentionally at the bottom to avoid circular import issues.
# Each module defines an engine class decorated with @register_engine(...),
# which populates ENGINE_REGISTRY when the module is imported.

from . import dp_qpsah200s  # noqa: F401
from . import qpmag_engine  # noqa: F401
