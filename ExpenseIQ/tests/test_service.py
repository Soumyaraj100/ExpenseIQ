import tempfile
import unittest
from pathlib import Path
from datetime import date
from decimal import Decimal

from expenseiq.database import ExpenseDatabase
from expenseiq.service import ExpenseService, ValidationError, money_to_cents

class ExpenseServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = ExpenseDatabase(Path(self.temp.name) / "test.sqlite3")
        self.service = ExpenseService(self.db)

    def tearDown(self):
        self.temp.cleanup()

    def test_money_validation(self):
        self.assertEqual(money_to_cents("12.34"), 1234)
        for invalid in ("0", "-1", "abc", "", "1.999"):
            with self.assertRaises(ValidationError):
                money_to_cents(invalid)

    def test_crud_and_persistence(self):
        eid = self.service.add("100.50", "Food", "2026-10-10", "Lunch")
        self.assertEqual(len(self.service.expenses()), 1)
        self.service.update(eid, "125.00", "Food", "2026-10-11", "Dinner")
        row = self.service.expenses()[0]
        self.assertEqual(row.amount, Decimal("125"))
        self.assertEqual(row.description, "Dinner")
        self.service.delete(eid)
        self.assertEqual(self.service.expenses(), [])

    def test_analytics_and_filters(self):
        self.service.add("100", "Food", "2026-10-01")
        self.service.add("200", "Transport", "2026-10-02")
        self.service.add("300", "Food", "2026-10-03")
        filtered = self.service.expenses(category="Food", start_date="2026-10-01", end_date="2026-10-02")
        self.assertEqual(len(filtered), 1)
        analytics = self.service.analytics()
        self.assertEqual(analytics.total, Decimal("600"))
        self.assertEqual(analytics.highest.amount, Decimal("300"))
        self.assertEqual(analytics.top_categories[0], ("Food", Decimal("400")))

    def test_budget_persists(self):
        self.service.set_monthly_budget("5000")
        self.assertEqual(self.service.monthly_budget(), Decimal("5000"))

if __name__ == "__main__":
    unittest.main()
