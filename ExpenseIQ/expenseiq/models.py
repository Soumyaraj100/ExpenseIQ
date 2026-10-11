from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

@dataclass(frozen=True)
class Expense:
    id: int
    amount: Decimal
    category: str
    spent_on: date
    description: str = ""

@dataclass(frozen=True)
class Analytics:
    total: Decimal
    count: int
    highest: Optional[Expense]
    by_category: dict[str, Decimal]
    top_categories: list[tuple[str, Decimal]]
