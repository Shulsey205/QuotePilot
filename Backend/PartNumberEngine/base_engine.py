from abc import ABC, abstractmethod
from typing import Any, Dict


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
            "adders": [...],
            "total_price": float
          }

        The method can raise PartNumberError when validation fails.
        """
        raise NotImplementedError
