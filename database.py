import sqlite3


def setup_database():
    """
    Setup the database.
    """
    connection = sqlite3.connect("invoices.db")
    cursor = connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            file TEXT PRIMARY KEY UNIQUE,
            client TEXT,
            amount REAL,
            product TEXT
        )
    """)
    connection.commit()
    return connection


def update_invoice_in_database(connection: sqlite3.Connection, data: dict):
    """
    Insert or update the invoice data in the database.
    """
    print(f"Updating database with invoice {data['file']}...")
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO invoices (file, client, amount, product)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(file) DO UPDATE SET
            client=excluded.client,
            amount=excluded.amount,
            product=excluded.product
        """,
        (
            data["file"],
            data["client_name"],
            data["invoice_amount"],
            data["product_name"],
        ),
    )
    connection.commit()


def generate_report(connection: sqlite3.Connection):
    """
    Generate a report from the database.
    """
    print("\nInvoice Report")

    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*), SUM(amount) FROM invoices")
    total_invoices, total_amount = cursor.fetchone()

    print(f"* Total invoices: {total_invoices}")
    print(f"* Total amount: {total_amount}")

    print("\nBreakdown by client:")
    cursor.execute("SELECT client, COUNT(*), SUM(amount) FROM invoices GROUP BY client")
    for row in cursor.fetchall():
        client, count, amount = row
        print(f"* {client}: {count} invoices (${amount})")
