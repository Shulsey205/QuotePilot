from abc import ABC, abstractmethod
from typing import Any, Dict


class PartNumberError(Exception):
    """
    Structured error for invalid part numbers.
    Carries segment, invalid code, and list of valid codes.
    """
    def __init__(self, message: str,
                 segment: str | None = None,
                 invalid_code: str | None = None,
                 valid_codes: list[str] | None = None):
        super().__init__(message)
        self.segment = segment
        self.invalid_code = invalid_code
        self.valid_codes = valid_codes or []


class PartNumberEngine(ABC):
    """
    Base class for all QuotePilot product engines.
    Each specific instrument will subclass this and implement quote.
    """

    model: str  # example "QPSAH200S"

    @abstractmethod
    def quote(self, part_number: str) -> Dict[str, Any]:
        """
        Return a full quote result for a part number.

        Expected result pattern:
          {
            "model": str,
            "input_part_number": str,
            "normalized_part_number": str,
            "segments": {...},
            "base_price": float,
            "adders_total": float,
            "final_price": float,
            "segments": [ ... ]
          }

        The method can raise PartNumberError when validation fails.
        """
        raise NotImplementedError
