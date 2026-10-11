# ExpenseIQ — Personal Expense Tracker

A desktop expense tracker built with **Kivy + SQLite**, with a separated service layer, input validation, analytics, filtering, CSV export, monthly budget alerts, and automated tests.

## Features
- Create, edit, and delete expenses.
- Amounts stored as integer cents to avoid floating-point currency errors.
- Categories, ISO dates (`YYYY-MM-DD`), optional descriptions.
- Filter by category and inclusive date range.
- Analytics: filtered total/count, highest expense, category totals, top 3 categories.
- SQLite persistence with indexes and transactional writes.
- Monthly budget saved in the database, with warnings when current-month spending exceeds it.
- CSV export of the current filtered view.
- Missing database is initialized automatically.
- If the SQLite database is detected as damaged, the app preserves a timestamped copy and warns the user before starting a new database. The original damaged records are not silently discarded.

## Requirements
- Python 3.10+
- Kivy 2.3+

## Run on Windows
```powershell
py -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

## Run tests
```powershell
python -m unittest discover -s tests -v
```

The tests do not require Kivy because they exercise the backend only.

## Data location
By default the database is stored at:
- Windows: `%USERPROFILE%\\.expenseiq\\expenseiq.sqlite3`
- Linux/macOS: `~/.expenseiq/expenseiq.sqlite3`

To use another data directory, set `EXPENSEIQ_DATA_DIR` before launching the app.

PowerShell example:
```powershell
$env:EXPENSEIQ_DATA_DIR = "D:\\ExpenseIQData"
python main.py
```

## Architecture
- `expenseiq/database.py`: SQLite repository, schema setup, recovery handling.
- `expenseiq/service.py`: business rules, validation, analytics, budgets.
- `expenseiq/models.py`: domain dataclasses.
- `expenseiq/ui.py`: Kivy UI only; delegates all business logic to the service.
- `tests/test_service.py`: backend unit tests.

## Design decisions
- SQLite is used instead of JSON because it supports transactions, indexes, and consistent CRUD operations.
- Currency is stored in integer paise/cents (`amount_cents`) and converted to decimal for display.
- Queries use parameters rather than string interpolation.
- Database writes use SQLite transactions.
- The app does not need an internet connection or a cloud account.
