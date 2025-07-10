import os
import asyncio
import json
import sqlite3
from dotenv import load_dotenv
from PyPDF2 import PdfReader
from box_sdk_gen import BoxClient, BoxDeveloperTokenAuth
from google import genai
from database import setup_database, update_invoice_in_database, generate_report
from model import generate, parse_json

load_dotenv(override=True)

BOX_FOLDER_ID = os.getenv("BOX_FOLDER_ID")
BOX_DEVELOPER_TOKEN = os.getenv("BOX_DEVELOPER_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = "gemini-2.5-flash"
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


async def extract_invoice_fields(file: str, text: str):
    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt = (
        "Extract the following information from this invoice text: "
        "1. Client name "
        "2. Invoice amount "
        "3. Product name "
        "Return the result as a JSON object."
        "Use the the following keys: "
        "1. client_name (string) "
        "2. invoice_amount (float) "
        "3. product_name (string) "
        "If the information is not found, return 'null' for the corresponding key.\n"
        f"Invoice text:\n{text}"
    )

    try:
        response = await generate(prompt, client)
        result = parse_json(response)
        result["file"] = file
        print(json.dumps(result, indent=4))
        return result
    except Exception as e:
        print(f"Failed to extract data using Gemini. Exception:{e}")


async def process_invoices(connection: sqlite3.Connection):
    """
    Process all invoices in the local folder and extract the appropriate fields.
    """
    for file in os.listdir(LOCAL_INVOICE_FOLDER):
        if file.endswith(".pdf"):
            print(f"\nProcessing {file}...")
            try:
                reader = PdfReader(os.path.join(LOCAL_INVOICE_FOLDER, file))
                text = ""
                for page in reader.pages:
                    text += page.extract_text() or ""

                data = await extract_invoice_fields(file, text)
                update_invoice_in_database(connection, data)

            except Exception as e:
                print(f"Failed to extract text from {file}. Exception: {e}")


if __name__ == "__main__":
    connection = setup_database()
    download_invoices()
    asyncio.run(process_invoices(connection))
    generate_report(connection)
    connection.close()
