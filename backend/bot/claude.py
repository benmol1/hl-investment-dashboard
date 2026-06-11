import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache

import anthropic

from .config import CLAUDE_MODEL, DB_PATH, SYSTEM_PROMPT_TEMPLATE
from .executors import execute_tool, pop_pending_charts, pop_pending_provenance
from .semantic import render_catalog
from .tools import TOOLS


@dataclass
class BotResponse:
    text: str
    charts: list[bytes] = field(default_factory=list)
    usage: dict = field(default_factory=dict)  # input_tokens, output_tokens (summed across all loop turns)


logger = logging.getLogger(__name__)


def _round_currency(text: str) -> str:
    """Round any £X.XX amounts ≥ £10 to the nearest pound."""

    def _replace(m: re.Match) -> str:
        amount = float(m.group(1).replace(",", ""))
        if amount >= 10:
            return f"£{round(amount):,}"
        return m.group(0)

    return re.sub(r"£([\d,]+\.\d+)", _replace, text)


@lru_cache(maxsize=1)
def _catalog() -> str:
    """Semantic layer catalogue, rendered once per process."""
    return render_catalog(DB_PATH)


def _provenance_footer(records: list[dict]) -> str:
    """Deterministic footer describing how each reply's data was obtained."""
    lines: list[str] = []
    for r in records:
        if r.get("source") == "semantic":
            parts = [r["model"], "metrics: " + ", ".join(r["metrics"])]
            if r.get("group_by"):
                parts.append("by: " + ", ".join(r["group_by"]))
            if r.get("filters"):
                parts.append("filters: " + "; ".join(r["filters"]))
            if r.get("time_range"):
                parts.append(r["time_range"])
            line = "📐 `semantic layer · " + " · ".join(parts) + "`"
        elif r.get("source") == "semantic_values":
            line = f"📐 `semantic layer · {r['model']} · values of {r['dimension']}`"
        elif r.get("source") == "sql_fallback":
            line = "🛠 `SQL fallback · tables: " + ", ".join(r["tables"]) + "`"
        else:
            continue
        if line not in lines:
            lines.append(line)
    return "\n".join(lines)


async def run_claude_loop(user_text: str, on_tool_call=None) -> BotResponse:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(today=date.today(), catalog=_catalog())
    messages: list[dict] = [{"role": "user", "content": user_text}]

    # Clear any state left over from a previous request that errored mid-loop.
    pop_pending_charts()
    pop_pending_provenance()

    tools_called: list[str] = []
    total_input_tokens = 0
    total_output_tokens = 0

    while True:
        response = await asyncio.to_thread(
            client.messages.create,
            model=CLAUDE_MODEL,
            max_tokens=4096,
            system=system_prompt,
            tools=TOOLS,
            messages=messages,
        )

        total_input_tokens += response.usage.input_tokens
        total_output_tokens += response.usage.output_tokens

        if response.stop_reason == "end_turn":
            body = _round_currency(
                "\n".join(b.text for b in response.content if hasattr(b, "text"))
            )
            footer = _provenance_footer(pop_pending_provenance())
            if footer:
                body = f"{body}\n\n{footer}"
            if tools_called:
                unique_tools = list(dict.fromkeys(tools_called))
                tool_label = ", ".join(unique_tools)
                text = f"🤖 `<tool: {tool_label}>`\n\n{body}"
            else:
                text = f"🤖 {body}"
            return BotResponse(
                text=text,
                charts=pop_pending_charts(),
                usage={"input_tokens": total_input_tokens, "output_tokens": total_output_tokens},
            )

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            round_tools = [b.name for b in response.content if b.type == "tool_use"]
            if on_tool_call and round_tools:
                await on_tool_call(round_tools)

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    logger.info("Tool call: %s %s", block.name, block.input)
                    tools_called.append(block.name)
                    result = await asyncio.to_thread(
                        execute_tool, block.name, block.input
                    )
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result, default=str),
                        }
                    )

            messages.append({"role": "user", "content": tool_results})
        else:
            logger.warning("Unexpected stop_reason: %s", response.stop_reason)
            return BotResponse(
                text="Sorry, I couldn't process that request.",
                usage={"input_tokens": total_input_tokens, "output_tokens": total_output_tokens},
            )
