import asyncio

from modkit.mcp_server import mcp


def test_tools_are_registered():
    tools = {t.name: t for t in asyncio.run(mcp.list_tools())}
    assert set(tools) == {"extract_data", "send_email", "ask_llm"}
    assert set(tools["extract_data"].input_schema["required"]) == {"source", "instructions"}


def test_extract_data_tool_calls_module(llm):
    llm.replies.append('{"vendor": "Acme"}')
    asyncio.run(mcp.call_tool("extract_data", {"source": "Acme invoice", "instructions": "vendor?", "fields": ["vendor"]}))
    assert "Acme invoice" in llm.calls[0]["messages"][-1]["content"]
