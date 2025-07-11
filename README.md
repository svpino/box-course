# Invoice Processing 

This repository contains two examples of how to process invoices stored in a Box account. 
The first script uses the Box API and the second uses the Box MCP Server.

## Setting up your environment

1. Install [`uv`](https://docs.astral.sh/uv/) in your environment.

2. Create an `.env` file in the project's root directory with the following environment variables:

* `BOX_FOLDER_ID`: The id of the folder containing the invoices in Box.
* `BOX_DEVELOPER_TOKEN`: The developer token to authenticate the script. This token will be used to access the Box API.
* `BOX_CLIENT_ID`: Client ID to authenticate the MCP Server.
* `BOX_CLIENT_SECRET`: Client Secret to authenticate the MCP Server.
* `GEMINI_API_KEY`: Gemini API Key.

3. Follow [these instructions](https://developer.box.com/guides/box-mcp/self-hosted/) to set up Box's MCP Server.

## Running the scripts

Use the following commands to run the scripts:

```
uv run python api-sample.py
uv run python mcp-sample.py
```

