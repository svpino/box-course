import os
import asyncio
import json
import sqlite3
from dotenv import load_dotenv
from PyPDF2 import PdfReader
from box_sdk_gen import BoxClient, BoxCCGAuth, CCGConfig
from google import genai
from database import setup_database, update_invoice_in_database, generate_report
from model import generate, parse_json

load_dotenv(override=True)

BOX_FOLDER_ID = os.getenv("BOX_FOLDER_ID")
BOX_CLIENT_ID = os.getenv("BOX_CLIENT_ID")
BOX_CLIENT_SECRET = os.getenv("BOX_CLIENT_SECRET")
BOX_SUBJECT_TYPE = os.getenv("BOX_SUBJECT_TYPE")
BOX_SUBJECT_ID = os.getenv("BOX_SUBJECT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
LOCAL_INVOICE_FOLDER = "invoices"


def get_box_client():
    """
    Create and return a Box client using the developer token.
    """
    ccg_config: CCGConfig = CCGConfig(
        client_id="l6lp8njqibhlw36lgfvy257i22r3uqfb",
        client_secret="fbWowQbz7pkjVvzTOPihCTkzrmXAGNMx",
        user_id="19498290761"
    )
    auth: BoxCCGAuth = BoxCCGAuth(config=ccg_config)
    
    return BoxClient(auth=auth)

def get_available_invoices_from_box(client: BoxClient):
    """
    Return a list of all available invoices in the Box folder.
    """
    files = []
    for item in client.folders.get_folder_items(BOX_FOLDER_ID).entries:
        files.append(item)

    print(f"Found {len(files)} invoices in Box folder {BOX_FOLDER_ID}.")

    return files


def download_invoices_from_box():
    """
    Download invoices from Box to a local folder.
    """
    
    client: BoxClient = get_box_client()

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


async def extract_invoice_fields(file: str, invoice: str):
    """
    Extract data from the supplied invoice text.
    """
    print(f"Extracting data from invoice {file}...")
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
        f"Invoice text:\n{invoice}"
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
    download_invoices_from_box()
    asyncio.run(process_invoices(connection))
    generate_report(connection)
    connection.close()
