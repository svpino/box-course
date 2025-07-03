import os
import json
import sqlite3
from dotenv import load_dotenv
from PyPDF2 import PdfReader
from box_sdk_gen import BoxClient, BoxDeveloperTokenAuth
import google.generativeai as genai

load_dotenv()

BOX_DEVELOPER_TOKEN = os.getenv("BOX_DEVELOPER_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = "gemini-2.5-flash"
BOX_FOLDER_ID = "329181520179"
LOCAL_INVOICE_FOLDER = "invoices"


def get_available_invoices_from_box(client: BoxClient):
    """
    Return a list of all available invoices in the Box folder.
    """
    files = []
    for item in client.folders.get_folder_items(BOX_FOLDER_ID).entries:
        files.append(item)

    print(f"Found {len(files)} invoices in Box folder {BOX_FOLDER_ID}.")

    return files


def download_invoices():
    """
    Download invoices from Box to a local folder.
    """
    auth: BoxDeveloperTokenAuth = BoxDeveloperTokenAuth(token=BOX_DEVELOPER_TOKEN)
    client: BoxClient = BoxClient(auth=auth)

    files = get_available_invoices_from_box(client)
    os.makedirs(LOCAL_INVOICE_FOLDER, exist_ok=True)

    for invoice in files:
        local_path = os.path.join(LOCAL_INVOICE_FOLDER, invoice.name)
        if not os.path.exists(local_path):
            print(f"Downloading {invoice.name}...")
            stream = client.downloads.download_file(invoice.id)
            with open(local_path, "wb") as f:
                for chunk in stream:
                    f.write(chunk)
        else:
            print(f"{invoice.name} already exists in the local folder.")


def extract_invoice_fields(text: str):
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(MODEL_NAME)

    prompt = (
        "Extract the following information from this invoice text: "
        "1. Client name "
        "2. Invoice amount "
        "3. Product name "
        "Return the result as a JSON object. Do not surround the result with ```json and ``` tags."
        "Use the the following keys: "
        "1. client_name (string) "
        "2. invoice_amount (float) "
        "3. product_name (string) "
        "If the information is not found, return 'null' for the corresponding key.\n"
        f"Invoice text:\n{text}"
    )

    try:
        response = model.generate_content(prompt)
        result = json.loads(response.text)
        return result
    except Exception as e:
        print(f"Failed to extract data using Gemini. Exception:{e}")


def invoice_already_exists_in_database(connection: sqlite3.Connection, file: str):
    """
    Check if the invoice file is already referenced in the database.
    """
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM invoices WHERE file = ?", (file,))
    count = cursor.fetchone()[0]
    return count > 0


def insert_invoice_data(connection: sqlite3.Connection, file: str, data: dict):
    """
    Insert the invoice data into the database.
    """
    print(f"Inserting invoice data for {file}...")
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO invoices (file, client, amount, product) VALUES (?, ?, ?, ?)
    """,
        (file, data["client_name"], data["invoice_amount"], data["product_name"]),
    )

    connection.commit()


def process_invoices(connection: sqlite3.Connection):
    """
    Process all invoices in the local folder and extract the appropriate fields.
    """
    for file in os.listdir(LOCAL_INVOICE_FOLDER):
        if file.endswith(".pdf"):
            if invoice_already_exists_in_database(connection, file):
                print(f"{file} already exists in the database.")
                continue

            print(f"Processing {file}...")
            try:
                reader = PdfReader(os.path.join(LOCAL_INVOICE_FOLDER, file))
                text = ""
                for page in reader.pages:
                    text += page.extract_text() or ""

                data = extract_invoice_fields(text)
                insert_invoice_data(connection, file, data)

            except Exception as e:
                print(f"Failed to extract text from {file}. Exception: {e}")


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


def setup_database():
    """
    Setup the database.
    """
    connection = sqlite3.connect("invoices.db")
    cursor = connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file TEXT,
            client TEXT,
            amount REAL,
            product TEXT
        )
    """)
    connection.commit()
    return connection


def main():
    connection = setup_database()
    download_invoices()
    process_invoices(connection)
    generate_report(connection)
    connection.close()


if __name__ == "__main__":
    main()
