from datetime import date
from decimal import Decimal
from pathlib import Path
import os

from kivy.app import App
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivy.core.window import Window

from .database import ExpenseDatabase, DatabaseError
from .service import ExpenseService, ValidationError, CATEGORIES

Window.minimum_width, Window.minimum_height = 760, 620
Window.size = (1100, 760)

BG = (0.055, 0.075, 0.11, 1)
PANEL = (0.09, 0.12, 0.17, 1)
ACCENT = (0.25, 0.78, 0.60, 1)
TEXT = (0.92, 0.95, 0.98, 1)
MUTED = (0.63, 0.69, 0.77, 1)
DANGER = (0.88, 0.32, 0.34, 1)

def label(text, size=14, color=TEXT, **kwargs):
    return Label(text=str(text), font_size=size, color=color, halign="left",
                 valign="middle", **kwargs)

def btn(text, callback, color=ACCENT, fg=(0.03,0.08,0.08,1), height=dp(40)):
    b = Button(text=text, size_hint_y=None, height=height, background_normal="",
               background_color=color, color=fg, bold=True)
    b.bind(on_release=lambda *_: callback())
    return b

class ExpenseIQApp(App):
    title = "ExpenseIQ — Personal Expense Tracker"

    def build(self):
        self.data_path = Path(os.environ.get(
            "EXPENSEIQ_DATA_DIR", str(Path.home() / ".expenseiq"))) / "expenseiq.sqlite3"
        self.db = ExpenseDatabase(self.data_path)
        self.service = ExpenseService(self.db)
        self.selected_id = None
        self.root_box = BoxLayout(orientation="vertical", padding=dp(18), spacing=dp(12))
        self.root_box.canvas.before.clear()
        with self.root_box.canvas.before:
            from kivy.graphics import Color, Rectangle
            Color(*BG); self.bg_rect = Rectangle(pos=self.root_box.pos, size=self.root_box.size)
        self.root_box.bind(pos=self._update_bg, size=self._update_bg)
        self._build_ui()
        self.refresh()
        if self.db.recovery_message:
            self.message("Saved data recovery", self.db.recovery_message)
        return self.root_box

    def _update_bg(self, *_):
        self.bg_rect.pos = self.root_box.pos
        self.bg_rect.size = self.root_box.size

    def _build_ui(self):
        header = BoxLayout(size_hint_y=None, height=dp(62), spacing=dp(10))
        title_box = BoxLayout(orientation="vertical")
        title_box.add_widget(label("ExpenseIQ", 26, ACCENT, bold=True))
        title_box.add_widget(label("Personal finance, made clear.", 12, MUTED))
        header.add_widget(title_box)
        header.add_widget(btn("Set monthly budget", self.budget_popup, height=dp(46)))
        self.root_box.add_widget(header)

        self.summary = GridLayout(cols=4, spacing=dp(10), size_hint_y=None, height=dp(88))
        self.summary_labels = []
        for heading in ("TOTAL SPENDING", "EXPENSES", "HIGHEST EXPENSE", "MONTH BUDGET"):
            card = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(3))
            card.add_widget(label(heading, 10, MUTED))
            value = label("—", 17, TEXT, bold=True)
            card.add_widget(value); self.summary_labels.append(value)
            self.summary.add_widget(card)
        self.root_box.add_widget(self.summary)

        body = BoxLayout(spacing=dp(12))
        left = BoxLayout(orientation="vertical", size_hint_x=0.40, spacing=dp(8))
        left.add_widget(label("ADD / EDIT EXPENSE", 13, ACCENT, bold=True))
        self.amount = self._field("Amount (e.g. 125.50)")
        self.category = Spinner(text=CATEGORIES[0], values=CATEGORIES, size_hint_y=None,
                                height=dp(42), background_normal="", background_color=PANEL,
                                color=TEXT)
        self.date_input = self._field("Date YYYY-MM-DD")
        self.date_input.text = date.today().isoformat()
        self.description = self._field("Description (optional)", multiline=True, height=dp(78))
        left.add_widget(self.amount); left.add_widget(self.category)
        left.add_widget(self.date_input); left.add_widget(self.description)
        actions = GridLayout(cols=2, spacing=dp(7), size_hint_y=None, height=dp(88))
        actions.add_widget(btn("Save expense", self.save_expense))
        actions.add_widget(btn("Clear form", self.clear_form, color=(0.27,0.34,0.43,1), fg=TEXT))
        actions.add_widget(btn("Delete selected", self.delete_selected, color=DANGER, fg=TEXT))
        actions.add_widget(btn("Export CSV", self.export_csv, color=(0.27,0.34,0.43,1), fg=TEXT))
        left.add_widget(actions)
        left.add_widget(label("ANALYTICS", 13, ACCENT, bold=True))
        self.analytics_label = label("Category totals will appear here.", 12, TEXT)
        left.add_widget(self.analytics_label)
        body.add_widget(left)

        right = BoxLayout(orientation="vertical", spacing=dp(8))
        right.add_widget(label("EXPENSE HISTORY", 13, ACCENT, bold=True))
        filters = GridLayout(cols=2, spacing=dp(6), size_hint_y=None, height=dp(84))
        self.filter_category = Spinner(text="All", values=["All"] + CATEGORIES,
            size_hint_y=None, height=dp(38), background_normal="", background_color=PANEL, color=TEXT)
        self.start_filter = TextInput(hint_text="Start YYYY-MM-DD", multiline=False,
            size_hint_y=None, height=dp(38), background_color=PANEL, foreground_color=TEXT,
            hint_text_color=MUTED, padding=dp(8))
        self.end_filter = TextInput(hint_text="End YYYY-MM-DD", multiline=False,
            size_hint_y=None, height=dp(38), background_color=PANEL, foreground_color=TEXT,
            hint_text_color=MUTED, padding=dp(8))
        filters.add_widget(self.filter_category); filters.add_widget(self.start_filter)
        filters.add_widget(self.end_filter); filters.add_widget(btn("Apply filters", self.refresh, height=dp(38)))
        right.add_widget(filters)
        self.list_box = GridLayout(cols=1, spacing=dp(6), size_hint_y=None)
        self.list_box.bind(minimum_height=self.list_box.setter("height"))
        scroll = ScrollView()
        scroll.add_widget(self.list_box)
        right.add_widget(scroll)
        body.add_widget(right)
        self.root_box.add_widget(body)

        footer = label(f"Local database: {self.data_path}", 10, MUTED, size_hint_y=None, height=dp(18))
        self.root_box.add_widget(footer)

    def _field(self, hint, multiline=False, height=dp(42)):
        t = TextInput(hint_text=hint, multiline=multiline, size_hint_y=None, height=height,
                      background_color=PANEL, foreground_color=TEXT, hint_text_color=MUTED,
                      cursor_color=ACCENT, padding=dp(10))
        return t

    def message(self, title, message):
        content = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))
        content.add_widget(label(message, 13, TEXT))
        content.add_widget(btn("OK", lambda: popup.dismiss()))
        popup = Popup(title=title, content=content, size_hint=(0.78, 0.48), auto_dismiss=False)
        popup.open()

    def save_expense(self):
        try:
            if self.selected_id is None:
                self.service.add(self.amount.text, self.category.text, self.date_input.text, self.description.text)
                msg = "Expense saved."
            else:
                self.service.update(self.selected_id, self.amount.text, self.category.text,
                                    self.date_input.text, self.description.text)
                msg = "Expense updated."
            self.clear_form(); self.refresh()
            budget = self.service.monthly_budget()
            if budget is not None and self.service.current_month_total() > budget:
                self.message("Budget exceeded", f"{msg}\\nMonthly spending is ₹{self.service.current_month_total():,.2f}, above your ₹{budget:,.2f} budget.")
            else:
                self.status_message(msg)
        except (ValidationError, DatabaseError, OSError) as exc:
            self.message("Could not save", str(exc))

    def status_message(self, text):
        self.message("ExpenseIQ", text)

    def clear_form(self):
        self.selected_id = None
        self.amount.text = ""; self.category.text = CATEGORIES[0]
        self.date_input.text = date.today().isoformat(); self.description.text = ""

    def select_expense(self, expense):
        self.selected_id = expense.id
        self.amount.text = f"{expense.amount:.2f}"
        self.category.text = expense.category
        self.date_input.text = expense.spent_on.isoformat()
        self.description.text = expense.description
        self.status_message(f"Expense #{expense.id} loaded. Edit fields and press Save expense.")

    def delete_selected(self):
        if self.selected_id is None:
            self.message("Select an expense", "Click an expense row first, then choose Delete selected.")
            return
        content = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))
        content.add_widget(label("Delete this expense permanently?", 14, TEXT))
        buttons = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
        popup = Popup(title="Confirm deletion", content=content, size_hint=(0.7,0.3))
        buttons.add_widget(btn("Cancel", popup.dismiss, color=(0.27,0.34,0.43,1), fg=TEXT))
        def confirm():
            try:
                self.service.delete(self.selected_id)
                popup.dismiss(); self.clear_form(); self.refresh()
            except (DatabaseError, ValueError) as exc:
                popup.dismiss(); self.message("Delete failed", str(exc))
        buttons.add_widget(btn("Delete", confirm, color=DANGER, fg=TEXT))
        content.add_widget(buttons); popup.open()

    def refresh(self):
        try:
            expenses = self.service.expenses(
                category=self.filter_category.text,
                start_date=self.start_filter.text.strip() or None,
                end_date=self.end_filter.text.strip() or None)
            analytics = self.service.analytics(expenses)
        except (ValidationError, DatabaseError) as exc:
            self.message("Filter error", str(exc)); return
        self.list_box.clear_widgets()
        if not expenses:
            self.list_box.add_widget(label("No expenses match these filters.", 13, MUTED, size_hint_y=None, height=dp(60)))
        for expense in expenses:
            row = BoxLayout(size_hint_y=None, height=dp(70), spacing=dp(8), padding=(dp(8),dp(5)))
            details = BoxLayout(orientation="vertical")
            details.add_widget(label(f"₹{expense.amount:,.2f}  ·  {expense.category}", 14, TEXT, bold=True))
            desc = expense.description if expense.description else "No description"
            details.add_widget(label(f"{expense.spent_on.isoformat()}  ·  {desc}", 11, MUTED))
            row.add_widget(details)
            row.add_widget(btn("Edit", lambda e=expense: self.select_expense(e),
                               color=(0.27,0.34,0.43,1), fg=TEXT, height=dp(34)))
            self.list_box.add_widget(row)
        highest = f"₹{analytics.highest.amount:,.2f}" if analytics.highest else "—"
        self.summary_labels[0].text = f"₹{analytics.total:,.2f}"
        self.summary_labels[1].text = str(analytics.count)
        self.summary_labels[2].text = highest
        budget = self.service.monthly_budget()
        month_total = self.service.current_month_total()
        self.summary_labels[3].text = f"₹{month_total:,.0f} / ₹{budget:,.0f}" if budget is not None else f"₹{month_total:,.0f} / not set"
        lines = ["SPENDING BY CATEGORY"]
        for category, total in sorted(analytics.by_category.items(), key=lambda x: (-x[1], x[0])):
            lines.append(f"• {category}: ₹{total:,.2f}")
        lines.append("")
        lines.append("TOP 3 CATEGORIES")
        lines += [f"{i}. {name}: ₹{total:,.2f}" for i, (name,total) in enumerate(analytics.top_categories, 1)]
        if analytics.highest:
            lines += ["", f"Highest: ₹{analytics.highest.amount:,.2f} · {analytics.highest.category}"]
        self.analytics_label.text = "\\n".join(lines)
        if budget is not None and month_total > budget:
            self.summary_labels[3].color = DANGER
        else:
            self.summary_labels[3].color = ACCENT

    def budget_popup(self):
        content = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))
        current = self.service.monthly_budget()
        field = self._field("Monthly budget amount")
        field.text = f"{current:.2f}" if current is not None else ""
        content.add_widget(label("Set a monthly spending limit (₹).", 13, TEXT))
        content.add_widget(field)
        content.add_widget(label("You will be warned after an expense pushes this month over budget.", 11, MUTED))
        popup = Popup(title="Monthly budget", content=content, size_hint=(0.72,0.4))
        def save():
            try:
                self.service.set_monthly_budget(field.text)
                popup.dismiss(); self.refresh()
                total = self.service.current_month_total()
                budget = self.service.monthly_budget()
                if total > budget:
                    self.message("Budget exceeded", f"Current month spending ₹{total:,.2f} is above the budget ₹{budget:,.2f}.")
                else:
                    self.status_message("Monthly budget saved.")
            except ValidationError as exc:
                self.message("Invalid budget", str(exc))
        content.add_widget(btn("Save budget", save))
        popup.open()

    def export_csv(self):
        import csv
        from datetime import datetime
        try:
            expenses = self.service.expenses(
                category=self.filter_category.text,
                start_date=self.start_filter.text.strip() or None,
                end_date=self.end_filter.text.strip() or None)
            if not expenses:
                self.message("Nothing to export", "No expenses match the current filters."); return
            path = Path.home() / f"expenseiq_export_{datetime.now():%Y%m%d_%H%M%S}.csv"
            with path.open("w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["id", "amount", "category", "date", "description"])
                for e in expenses:
                    writer.writerow([e.id, f"{e.amount:.2f}", e.category, e.spent_on.isoformat(), e.description])
            self.message("Export complete", f"CSV exported to:\\n{path}")
        except (ValidationError, DatabaseError, OSError) as exc:
            self.message("Export failed", str(exc))
