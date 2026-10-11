"""SQLite persistence layer. Uses transactions and preserves damaged databases."""
from __future__ import annotations
import sqlite3
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

class DatabaseError(RuntimeError):
    pass

class ExpenseDatabase:
    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.recovery_message = ""
        self._initialize_safely()

    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 10000")
        return conn

    def _initialize_safely(self):
        existed = self.path.exists() and self.path.stat().st_size > 0
        try:
            with self._connect() as conn:
                check = conn.execute("PRAGMA quick_check").fetchone()
                if not check or check[0] != "ok":
                    raise sqlite3.DatabaseError(f"SQLite integrity check failed: {check[0] if check else 'no result'}")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS expenses (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
                        category TEXT NOT NULL CHECK(length(trim(category)) > 0),
                        spent_on TEXT NOT NULL,
                        description TEXT NOT NULL DEFAULT '',
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(spent_on)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category)")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS settings (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    )
                """)
        except sqlite3.DatabaseError as exc:
            if not existed:
                raise DatabaseError(f"Could not initialize the database: {exc}") from exc
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            preserved = self.path.with_name(f"{self.path.stem}.corrupt_{stamp}{self.path.suffix}")
            try:
                shutil.copy2(self.path, preserved)
            except OSError as copy_exc:
                raise DatabaseError(
                    f"Database is damaged and could not be backed up. Original left untouched at {self.path}. "
                    f"Backup error: {copy_exc}"
                ) from exc
            self.path.unlink()
            self.recovery_message = (
                f"The saved database was damaged. A copy was preserved at:\\n{preserved}\\n"
                "A new database has been created; the preserved copy was not deleted."
            )
            with self._connect() as conn:
                self._create_schema(conn)

    @staticmethod
    def _create_schema(conn):
        conn.execute("""CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
            category TEXT NOT NULL CHECK(length(trim(category)) > 0),
            spent_on TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(spent_on)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category)")
        conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")

    def list_expenses(self, category=None, start_date=None, end_date=None):
        sql = "SELECT * FROM expenses WHERE 1=1"
        params: list[Any] = []
        if category and category != "All":
            sql += " AND category = ?"; params.append(category)
        if start_date:
            sql += " AND spent_on >= ?"; params.append(start_date)
        if end_date:
            sql += " AND spent_on <= ?"; params.append(end_date)
        sql += " ORDER BY spent_on DESC, id DESC"
        try:
            with self._connect() as conn:
                return [dict(r) for r in conn.execute(sql, params).fetchall()]
        except sqlite3.DatabaseError as exc:
            raise DatabaseError(f"Could not read expenses: {exc}") from exc

    def add_expense(self, amount_cents, category, spent_on, description):
        try:
            with self._connect() as conn:
                cur = conn.execute(
                    "INSERT INTO expenses(amount_cents, category, spent_on, description) VALUES(?,?,?,?)",
                    (amount_cents, category, spent_on, description))
                return cur.lastrowid
        except sqlite3.DatabaseError as exc:
            raise DatabaseError(f"Could not save expense: {exc}") from exc

    def update_expense(self, expense_id, amount_cents, category, spent_on, description):
        try:
            with self._connect() as conn:
                cur = conn.execute("""UPDATE expenses SET amount_cents=?, category=?, spent_on=?,
                    description=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                    (amount_cents, category, spent_on, description, expense_id))
                if cur.rowcount == 0:
                    raise DatabaseError("That expense no longer exists.")
        except sqlite3.DatabaseError as exc:
            if isinstance(exc, DatabaseError): raise
            raise DatabaseError(f"Could not update expense: {exc}") from exc

    def delete_expense(self, expense_id):
        try:
            with self._connect() as conn:
                cur = conn.execute("DELETE FROM expenses WHERE id=?", (expense_id,))
                if cur.rowcount == 0:
                    raise DatabaseError("That expense no longer exists.")
        except sqlite3.DatabaseError as exc:
            if isinstance(exc, DatabaseError): raise
            raise DatabaseError(f"Could not delete expense: {exc}") from exc

    def get_setting(self, key, default=""):
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            return row["value"] if row else default

    def set_setting(self, key, value):
        with self._connect() as conn:
            conn.execute("""INSERT INTO settings(key,value) VALUES(?,?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value""", (key, str(value)))
