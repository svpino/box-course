import os
import json
import sqlite3
import asyncio
from dotenv import load_dotenv
from google import genai
from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from database import setup_database, update_invoice_in_database, generate_report
from model import generate

load_dotenv(override=True)

BOX_CLIENT_ID = os.getenv("BOX_CLIENT_ID")
BOX_CLIENT_SECRET = os.getenv("BOX_CLIENT_SECRET")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
BOX_FOLDER_ID = os.getenv("BOX_FOLDER_ID")
BOX_MCP_SERVER_PATH = "/Users/svpino/dev/mcp-server-box"
BOX_MCP_TOOLS = [
    "box_who_am_i",
    "box_list_folder_content_by_folder_id",
    "box_ai_extract_tool",
]

PROMPT2 = """
You are a helpful assistant that can extract data from invoices.
You will be given a list of invoices and you will need to extract the data from each invoice.
You will need to extract the following data from the invoice:
- Client name
- Invoice amount
- Product name

Return the invoice_amount as a float.
"""


async def get_mcp_tools(session: ClientSession):
    """
    Set up the list of MCP tools that will be used to interact with Box.
    """
    mcp_tools = await session.list_tools()
    return [
        types.Tool(
            function_declarations=[
                {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {p: v for p, v in tool.inputSchema.items()},
                }
            ]
        )
        for tool in mcp_tools.tools
        if tool.name in BOX_MCP_TOOLS
    ]


async def get_list_of_invoices(
    client: genai.Client, session: ClientSession, tools: list
):
    """
    Get the list of invoices from the Box folder.
    """
    prompt = f"List the content of the folder with id {BOX_FOLDER_ID}"
    return await generate(prompt, client, session, tools)


async def extract_invoice_fields(
    invoice: dict, client: genai.Client, session: ClientSession, tools: list
):
    """
    Extract data from the supplied invoice.
    """
    print(f'Extracting data from invoice "{invoice["name"]}"...')
    prompt = (
        "Extract the following fields from the invoice "
        f"with file_id {invoice['id']}: "
        "client_name, invoice_amount, product_name. "
        "Return the invoice_amount as a float. "
    )
    response = await generate(prompt, client, session, tools)
    result = json.loads(response[0]["answer"])
    result["file"] = invoice["name"]
    return result


async def process_invoices(connection: sqlite3.Connection):
    """
    Process all invoices in the Box folder.
    """
    client = genai.Client(api_key=GEMINI_API_KEY)

    server_params = StdioServerParameters(
        command="uv",
        args=[
            "--directory",
            BOX_MCP_SERVER_PATH,
            "run",
            "src/mcp_server_box.py",
        ],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await get_mcp_tools(session)

            invoices = await get_list_of_invoices(client, session, tools)
            print(f"Found {len(invoices)} invoices")

            for invoice in invoices:
                invoice_data = await extract_invoice_fields(
                    invoice, client, session, tools
                )
                update_invoice_in_database(connection, invoice_data)


if __name__ == "__main__":
    connection = setup_database()
    asyncio.run(process_invoices(connection))
    generate_report(connection)
    connection.close()
