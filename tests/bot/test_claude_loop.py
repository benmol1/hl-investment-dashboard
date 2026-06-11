"""End-to-end test of run_claude_loop with a scripted Anthropic client:
tool call against the mini warehouse, then a final answer with the
provenance footer appended."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from bot import claude, executors
from bot.claude import run_claude_loop


def _tool_use_response():
    block = SimpleNamespace(
        type="tool_use",
        id="tu_1",
        name="query_metrics",
        input={
            "model": "holdings_latest",
            "metrics": ["value_gbp"],
            "group_by": ["account_name"],
        },
    )
    return SimpleNamespace(
        stop_reason="tool_use",
        content=[block],
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
    )


def _end_turn_response(text: str):
    return SimpleNamespace(
        stop_reason="end_turn",
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=20, output_tokens=8),
    )


@pytest.fixture
def scripted_client(mocker, warehouse_path):
    mocker.patch.object(executors, "DB_PATH", warehouse_path)
    claude._catalog.cache_clear()
    mocker.patch.object(claude, "render_catalog", return_value="(catalogue)")
    client = MagicMock()
    client.messages.create.side_effect = [
        _tool_use_response(),
        _end_turn_response("Your ISA is worth £1,080.00 and your SIPP £105.00."),
    ]
    mocker.patch.object(claude.anthropic, "Anthropic", return_value=client)
    yield client
    claude._catalog.cache_clear()


async def test_loop_executes_tool_and_appends_footer(scripted_client):
    result = await run_claude_loop("what is each account worth?")

    # Tool result was fed back to the model
    second_call_messages = scripted_client.messages.create.call_args.kwargs["messages"]
    tool_result = second_call_messages[-1]["content"][0]
    assert tool_result["type"] == "tool_result"
    assert "1080" in tool_result["content"]

    assert result.text.startswith("🤖 `<tool: query_metrics>`")
    assert "£1,080" in result.text
    footer_line = result.text.splitlines()[-1]
    assert footer_line == (
        "📐 `semantic layer · holdings_latest · metrics: value_gbp · by: account_name`"
    )
    assert result.usage == {"input_tokens": 30, "output_tokens": 13}
