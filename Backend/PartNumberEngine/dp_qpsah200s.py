from typing import Any, Dict

from .base_engine import PartNumberEngine
from qp_dpt_engine import quote_dp_part_number, PartNumberError


class QPSAH200SEngine(PartNumberEngine):
    model = "QPSAH200S"

    def quote(self, part_number: str) -> Dict[str, Any]:
        try:
            result = quote_dp_part_number(part_number)
            result.setdefault("model", self.model)
            return result
        except PartNumberError as exc:
            raise exc
