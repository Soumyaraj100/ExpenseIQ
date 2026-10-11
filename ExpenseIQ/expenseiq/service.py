"""Business rules and analytics, independent of the GUI."""
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from .database import ExpenseDatabase, DatabaseError
from .models import Expense, Analytics

CATEGORIES = [
    "Food", "Transport", "Shopping", "Bills", "Health",
    "Education", "Entertainment", "Groceries", "Other"
]

class ValidationError(ValueError):
    pass

def money_to_cents(raw) -> int:
    try:
        value = Decimal(str(raw).strip())
    except (InvalidOperation, ValueError, AttributeError):
        raise ValidationError("Enter a valid amount, for example 125.50.")
    if not value.is_finite() or value <= 0:
        raise ValidationError("Amount must be a positive number.")
    rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if rounded != value:
        raise ValidationError("Amount can have at most two decimal places.")
    cents = int(rounded * 100)
    if cents > 999_999_999_999:
        raise ValidationError("Amount is too large.")
    return cents

def parse_date(raw) -> str:
    try:
        return datetime.strptime(str(raw).strip(), "%Y-%m-%d").date().isoformat()
    except (ValueError, TypeError):
        raise ValidationError("Date must use YYYY-MM-DD format, e.g. 2026-10-11.")

class ExpenseService:
    def __init__(self, db: ExpenseDatabase):
        self.db = db

    def add(self, amount, category, spent_on, description=""):
        cents = money_to_cents(amount)
        category = str(category).strip()
        if not category:
            raise ValidationError("Choose a category.")
        day = parse_date(spent_on)
        description = str(description).strip()
        if len(description) > 500:
            raise ValidationError("Description must be 500 characters or fewer.")
        return self.db.add_expense(cents, category, day, description)

    def update(self, expense_id, amount, category, spent_on, description=""):
        cents = money_to_cents(amount)
        category = str(category).strip()
        if not category: raise ValidationError("Choose a category.")
        day = parse_date(spent_on)
        description = str(description).strip()
        if len(description) > 500: raise ValidationError("Description must be 500 characters or fewer.")
        self.db.update_expense(int(expense_id), cents, category, day, description)

    def delete(self, expense_id):
        self.db.delete_expense(int(expense_id))

    def expenses(self, category=None, start_date=None, end_date=None):
        start = parse_date(start_date) if start_date else None
        end = parse_date(end_date) if end_date else None
        if start and end and start > end:
            raise ValidationError("Start date cannot be after end date.")
        rows = self.db.list_expenses(category, start, end)
        return [Expense(
            id=r["id"], amount=Decimal(r["amount_cents"]) / 100,
            category=r["category"], spent_on=date.fromisoformat(r["spent_on"]),
            description=r["description"] or ""
        ) for r in rows]

    def analytics(self, expenses=None):
        expenses = self.expenses() if expenses is None else expenses
        total = sum((e.amount for e in expenses), Decimal("0.00"))
        by_category = defaultdict(lambda: Decimal("0.00"))
        for e in expenses: by_category[e.category] += e.amount
        highest = max(expenses, key=lambda e: e.amount, default=None)
        top = sorted(by_category.items(), key=lambda pair: (-pair[1], pair[0]))[:3]
        return Analytics(total, len(expenses), highest, dict(by_category), top)

    def set_monthly_budget(self, amount):
        cents = money_to_cents(amount)
        self.db.set_setting("monthly_budget_cents", cents)

    def monthly_budget(self):
        raw = self.db.get_setting("monthly_budget_cents", "")
        return Decimal(raw) / 100 if raw else None

    def current_month_total(self, today=None):
        today = today or date.today()
        start = today.replace(day=1).isoformat()
        # ISO date string ordering handles month end without calculating it.
        rows = self.expenses(start_date=start, end_date=today.isoformat())
        return sum((e.amount for e in rows), Decimal("0.00"))
