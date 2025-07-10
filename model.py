import json
from google import genai
from mcp import ClientSession
from google.genai import types

MODEL_NAME = "gemini-2.5-flash"


def parse_json(content):
    # Try parsing as pure JSON first
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # If that fails, try to extract JSON from the text
    # Look for JSON-like content between curly braces
    import re

    json_match = re.search(r"\{.*\}", content, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    # If all else fails, return the original text
    return content


def _parse_content(content):
    """
    Parse the content of a model response.
    """
    try:
        return parse_json(content.text)
    except json.JSONDecodeError:
        return content.text


async def generate(
    prompt: str, client: genai.Client, session: ClientSession = None, tools: list = None
):
    """
    Generate content using the Gemini model using MCP tools if provided.
    """

    config = (
        types.GenerateContentConfig(temperature=0, tools=tools)
        if session is not None and tools is not None
        else None
    )

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=config,
    )

    if response.candidates[0].content.parts[0].function_call:
        print(
            f'[Calling MCP Tool: "{response.candidates[0].content.parts[0].function_call.name}"]'
        )
        function_call = response.candidates[0].content.parts[0].function_call
        response = await session.call_tool(
            function_call.name, arguments=dict(function_call.args)
        )

        return [_parse_content(content) for content in response.content]

    return response.candidates[0].content.parts[0].text
