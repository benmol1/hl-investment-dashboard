import asyncio
import json
import logging
import os
import re
from datetime import date

import anthropic

from .config import CLAUDE_MODEL, SYSTEM_PROMPT_TEMPLATE
from .executors import execute_tool
from .tools import TOOLS

logger = logging.getLogger(__name__)


def _round_currency(text: str) -> str:
    """Round any £X.XX amounts ≥ £10 to the nearest pound."""
    def _replace(m: re.Match) -> str:
        amount = float(m.group(1).replace(",", ""))
        if amount >= 10:
            return f"£{round(amount):,}"
        return m.group(0)
    return re.sub(r"£([\d,]+\.\d+)", _replace, text)


async def run_claude_loop(user_text: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(today=date.today())
    messages: list[dict] = [{"role": "user", "content": user_text}]

    tools_called: list[str] = []

    while True:
        response = await asyncio.to_thread(
            client.messages.create,
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=system_prompt,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            body = _round_currency("\n".join(b.text for b in response.content if hasattr(b, "text")))
            if tools_called:
                unique_tools = list(dict.fromkeys(tools_called))
                tool_label = ", ".join(unique_tools)
                return f"🤖 `tool: {tool_label}`\n{body}"
            return f"🤖 {body}"

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    logger.info("Tool call: %s %s", block.name, block.input)
                    tools_called.append(block.name)
                    result = await asyncio.to_thread(execute_tool, block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, default=str),
                    })

            messages.append({"role": "user", "content": tool_results})
        else:
            logger.warning("Unexpected stop_reason: %s", response.stop_reason)
            return "Sorry, I couldn't process that request."
