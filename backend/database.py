import sqlite3
from pathlib import Path


from importlib import import_module

from backend.invoice_schema import InvoiceData
from backend.invoice_validator import money

# Store the database in a local data folder
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATABASE_PATH = DATA_DIR / "atlas.db"


def initialize_database():
    """Create the Atlas database and invoices table."""

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vendor_name TEXT NOT NULL,
                invoice_number TEXT NOT NULL,
                invoice_date TEXT NOT NULL,
                due_date TEXT,
                bill_to TEXT,
                currency TEXT NOT NULL,
                subtotal TEXT NOT NULL,
                tax TEXT NOT NULL,
                total TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'needs_review',
                source_file TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(vendor_name, invoice_number)
            )
        """)

    
        connection.execute("""
            CREATE TABLE IF NOT EXISTS invoice_line_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL,
                description TEXT NOT NULL,
                quantity TEXT NOT NULL,
                unit_price TEXT NOT NULL,
                amount TEXT NOT NULL,
                FOREIGN KEY (invoice_id) REFERENCES invoices(id)
                    ON DELETE CASCADE
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS invoice_validation_issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL,
                issue_message TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (invoice_id) REFERENCES invoices(id)
                    ON DELETE CASCADE
            )
        """)
        connection.commit()

        from backend.invoice_schema import InvoiceData
from backend.invoice_validator import money


def save_invoice(
    invoice: InvoiceData,
    source_file: str,
    status: str = "needs_review",
    validation_issues: list[str] | None = None,
) -> int:
    """Save an extracted invoice and return its database ID."""

    initialize_database()

    with sqlite3.connect(DATABASE_PATH) as connection:
        cursor = connection.execute(
            """
            INSERT INTO invoices (
                vendor_name, invoice_number, invoice_date,
                due_date, bill_to, currency,
                subtotal, tax, total, status, source_file
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                invoice.vendor_name,
                invoice.invoice_number,
                invoice.invoice_date,
                invoice.due_date,
                invoice.bill_to,
                invoice.currency,
                str(money(invoice.subtotal)),
                str(money(invoice.tax)),
                str(money(invoice.total)),
                status,
                source_file,
            ),
        )

        invoice_id = cursor.lastrowid

        for item in invoice.line_items:
            connection.execute(
                """
                INSERT INTO invoice_line_items (
                    invoice_id, description, quantity,
                    unit_price, amount
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    invoice_id,
                    item.description,
                    str(item.quantity),
                    str(money(item.unit_price)),
                    str(money(item.amount)),
                ),
            )
        for issue in validation_issues or []:
            connection.execute(
                """
                INSERT INTO invoice_validation_issues (
                    invoice_id, issue_message
                )
                VALUES (?, ?)
                """,
                (invoice_id, issue),
            )
        connection.commit()

    excel_export = import_module("backend.excel_export")
    excel_export.create_excel_workbook()

    return invoice_id

def list_invoices():
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row

        rows = connection.execute(
    """
    SELECT
        invoices.*,
        (
            SELECT COUNT(*)
            FROM invoice_validation_issues
            WHERE invoice_validation_issues.invoice_id = invoices.id
        ) AS validation_issue_count
    FROM invoices
    ORDER BY invoices.id DESC
    """
).fetchall()

        return [dict(row) for row in rows]

def get_invoice(invoice_id: int):
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()



        if row is None:
            return None

        invoice = dict(row)

        issues = connection.execute(
            """
            SELECT issue_message
            FROM invoice_validation_issues
            WHERE invoice_id = ?
            ORDER BY id
            """,
            (invoice_id,),
        ).fetchall()

        invoice["validation_issues"] = [
            issue["issue_message"] for issue in issues
        ]

        return invoice


    
def update_invoice_status(invoice_id: int, status: str):
    with sqlite3.connect(DATABASE_PATH) as connection:
        cursor = connection.execute(
            "UPDATE invoices SET status = ? WHERE id = ?",
            (status, invoice_id)
        )
        connection.commit()
        return cursor.rowcount > 0