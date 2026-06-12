import concurrent.futures
import io
import logging
import re
import uuid
from typing import Any

import duckdb
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

matplotlib.use(
    "Agg"
)  # non-interactive backend; must be set before any other pyplot import

from .config import DB_PATH
from .semantic import (
    SemanticQueryError,
    compile_dimension_values,
    compile_query,
    load_registry,
)

# Charts rendered during a request are stored here until the handler retrieves them.
# Safe for single-user sequential use; not thread-safe across concurrent requests.
_pending_charts: dict[str, bytes] = {}

# Provenance of data queries made during a request, used to build the footer
# on the reply. Same single-user lifecycle as _pending_charts.
_pending_provenance: list[dict] = []

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Read-only SQL execution (shared by semantic layer + fallback)
# ---------------------------------------------------------------------------


def _run_sql(sql: str) -> dict:
    def _run() -> dict:
        con = duckdb.connect(str(DB_PATH), read_only=True)
        try:
            rows = con.execute(sql).fetchall()
            cols = [desc[0] for desc in con.description]
            return {"columns": cols, "rows": rows[:200]}
        finally:
            con.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_run)
        try:
            return future.result(timeout=30)
        except concurrent.futures.TimeoutError:
            return {
                "error": "Query timed out after 30 seconds. Try a more targeted query."
            }
        except Exception as exc:
            return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Semantic layer executors
# ---------------------------------------------------------------------------


def _execute_semantic_layer(inputs: dict) -> Any:
    registry = load_registry()
    model = registry.model(inputs.get("model", ""))
    if model is None:
        return {
            "error": f"Unknown model '{inputs.get('model')}'. Available: {', '.join(registry.model_names)}"
        }
    try:
        compiled, provenance = compile_query(model, inputs)
    except SemanticQueryError as exc:
        return {"error": str(exc)}

    logger.info("Semantic SQL:\n%s", compiled.sql)
    result = _run_sql(compiled.sql)
    if "error" in result:
        return result

    _pending_provenance.append(provenance)
    return {"columns": result["columns"], "rows": result["rows"], "sql": compiled.sql}


def _execute_get_dimension_values(inputs: dict) -> Any:
    registry = load_registry()
    model = registry.model(inputs.get("model", ""))
    if model is None:
        return {
            "error": f"Unknown model '{inputs.get('model')}'. Available: {', '.join(registry.model_names)}"
        }
    dimension_name = inputs.get("dimension", "")
    try:
        sql = compile_dimension_values(model, dimension_name)
    except SemanticQueryError as exc:
        return {"error": str(exc)}
    result = _run_sql(sql)
    if "error" in result:
        return result
    values = [r[0] for r in result["rows"]]
    _pending_provenance.append(
        {"source": "semantic_values", "model": model.name, "dimension": dimension_name}
    )
    return {"model": model.name, "dimension": dimension_name, "values": values}


# ---------------------------------------------------------------------------
# Chart generation executor
# ---------------------------------------------------------------------------

_CHART_COLORS = [
    "#4C9BE8",
    "#E8824C",
    "#4CE87A",
    "#E84C4C",
    "#A04CE8",
    "#E8D44C",
    "#4CE8D4",
    "#E84CA0",
    "#8BE84C",
    "#4C4CE8",
]


def _y_formatter(y_format: str) -> mticker.FuncFormatter:
    if y_format == "currency":
        return mticker.FuncFormatter(lambda v, _: f"£{v:,.0f}")
    if y_format == "percent":
        return mticker.FuncFormatter(lambda v, _: f"{v:.1f}%")
    return mticker.FuncFormatter(lambda v, _: f"{v:,.1f}")


def _add_caption(fig: plt.Figure, caption: str) -> None:
    fig.text(
        0.5,
        0.01,
        caption,
        ha="center",
        va="bottom",
        fontsize=8.5,
        color="#888888",
        style="italic",
        transform=fig.transFigure,
    )


def _x_tick_positions(n: int, step: int) -> list[int]:
    return list(range(0, n, step))


def _render_line_chart(
    title: str,
    data: list[dict],
    x_key: str,
    series: list[dict],
    y_label: str,
    y_format: str,
    caption: str,
) -> io.BytesIO:
    xs = [str(p[x_key]) for p in data]
    multi = len(series) > 1
    bottom_pad = 0.12 if caption else 0

    fig, ax = plt.subplots(figsize=(10, 5))

    for i, s in enumerate(series):
        ys = [float(p[s["y_key"]]) for p in data]
        color = _CHART_COLORS[i % len(_CHART_COLORS)]
        ax.plot(xs, ys, color=color, linewidth=2, label=s.get("label", ""))
        if not multi:
            ax.fill_between(range(len(xs)), ys, alpha=0.12, color=color)

    step = max(1, len(xs) // 6)
    ax.set_xticks(_x_tick_positions(len(xs), step))
    ax.set_xticklabels(
        [xs[i] for i in _x_tick_positions(len(xs), step)],
        rotation=30,
        ha="right",
        fontsize=9,
    )

    ax.yaxis.set_major_formatter(_y_formatter(y_format))
    if y_label:
        ax.set_ylabel(y_label, fontsize=10)
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    if multi:
        ax.legend(fontsize=9, frameon=False)

    fig.tight_layout(rect=[0, bottom_pad, 1, 1])
    if caption:
        _add_caption(fig, caption)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def _render_bar_chart(
    title: str,
    data: list[dict],
    x_key: str,
    y_key: str,
    y_label: str,
    y_format: str,
    caption: str,
) -> io.BytesIO:
    xs = [str(p[x_key]) for p in data]
    ys = [float(p[y_key]) for p in data]
    bottom_pad = 0.12 if caption else 0

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(range(len(xs)), ys, color=_CHART_COLORS[0], width=0.7)

    step = max(1, len(xs) // 8)
    ax.set_xticks(_x_tick_positions(len(xs), step))
    ax.set_xticklabels(
        [xs[i] for i in _x_tick_positions(len(xs), step)],
        rotation=30,
        ha="right",
        fontsize=9,
    )

    ax.yaxis.set_major_formatter(_y_formatter(y_format))
    if y_label:
        ax.set_ylabel(y_label, fontsize=10)
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout(rect=[0, bottom_pad, 1, 1])
    if caption:
        _add_caption(fig, caption)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def _render_donut_chart(
    title: str,
    data: list[dict],
    label_key: str,
    value_key: str,
    caption: str,
) -> io.BytesIO:
    labels = [str(p[label_key]) for p in data]
    values = [float(p[value_key]) for p in data]
    bottom_pad = 0.12 if caption else 0

    fig, ax = plt.subplots(figsize=(8, 7))
    wedges, texts, autotexts = ax.pie(
        values,
        labels=None,
        autopct=lambda pct: f"{pct:.1f}%" if pct >= 3 else "",
        startangle=90,
        pctdistance=0.78,
        wedgeprops={"width": 0.5, "edgecolor": "white", "linewidth": 1.5},
        colors=_CHART_COLORS[: len(values)],
    )
    for t in autotexts:
        t.set_fontsize(9)

    ax.legend(
        wedges,
        labels,
        loc="lower center",
        bbox_to_anchor=(0.5, -0.08),
        ncol=2,
        fontsize=9,
        frameon=False,
    )
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)

    fig.tight_layout(rect=[0, bottom_pad, 1, 1])
    if caption:
        _add_caption(fig, caption)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def _execute_generate_chart(inputs: dict) -> Any:
    chart_type = inputs.get("chart_type")
    title = inputs.get("title", "")
    data = inputs.get("data", [])
    caption = inputs.get("caption", "")
    y_format = inputs.get("y_format", "number")

    if not data:
        return {"error": "data array is empty — fetch data first with another tool."}

    try:
        if chart_type == "line":
            x_key = inputs.get("x_key")
            if not x_key:
                return {"error": "x_key is required for a line chart."}
            # Accept either series array or legacy single y_key
            raw_series = inputs.get("series")
            if not raw_series:
                y_key = inputs.get("y_key")
                if not y_key:
                    return {
                        "error": "Either 'series' or 'y_key' is required for a line chart."
                    }
                raw_series = [{"label": "", "y_key": y_key}]
            buf = _render_line_chart(
                title,
                data,
                x_key,
                raw_series,
                inputs.get("y_label", ""),
                y_format,
                caption,
            )
        elif chart_type == "bar":
            x_key = inputs.get("x_key")
            y_key = inputs.get("y_key")
            if not x_key or not y_key:
                return {"error": "x_key and y_key are required for a bar chart."}
            buf = _render_bar_chart(
                title, data, x_key, y_key, inputs.get("y_label", ""), y_format, caption
            )
        elif chart_type == "donut":
            label_key = inputs.get("label_key")
            value_key = inputs.get("value_key")
            if not label_key or not value_key:
                return {
                    "error": "label_key and value_key are required for a donut chart."
                }
            buf = _render_donut_chart(title, data, label_key, value_key, caption)
        else:
            return {
                "error": f"Unknown chart_type '{chart_type}'. Use 'line', 'bar', or 'donut'."
            }
    except (KeyError, ValueError, TypeError) as exc:
        return {"error": f"Chart rendering failed: {exc}"}

    chart_id = uuid.uuid4().hex[:8]
    _pending_charts[chart_id] = buf.read()
    return {
        "success": True,
        "chart_id": chart_id,
        "description": f"{chart_type} chart: {title}",
    }


def pop_pending_charts() -> list[bytes]:
    """Return and clear any charts rendered during the current request."""
    charts = list(_pending_charts.values())
    _pending_charts.clear()
    return charts


def pop_pending_provenance() -> list[dict]:
    """Return and clear the provenance records for the current request."""
    records = list(_pending_provenance)
    _pending_provenance.clear()
    return records


# ---------------------------------------------------------------------------
# DuckDB fallback executor
# ---------------------------------------------------------------------------

_ALLOWED_TABLE_PATTERN = re.compile(r"\b(mart_\w+|dim_\w+)\b", re.IGNORECASE)
_DISALLOWED_TABLE_PATTERN = re.compile(
    r"\b(fct_\w+|stg_\w+|int_\w+|raw_\w+|information_schema)\b", re.IGNORECASE
)


def _execute_query_database(inputs: dict) -> Any:
    sql = inputs["sql"].strip()

    if not re.match(r"^\s*SELECT\b", sql, re.IGNORECASE):
        return {"error": "Only SELECT statements are permitted."}

    if _DISALLOWED_TABLE_PATTERN.search(sql):
        return {
            "error": "Query references tables outside the allowed mart_/dim_ scope."
        }

    if not _ALLOWED_TABLE_PATTERN.search(sql):
        return {
            "error": "No mart_ or dim_ tables found in query. Only those tables may be queried."
        }

    result = _run_sql(sql)
    if "error" not in result:
        tables = sorted({m.lower() for m in _ALLOWED_TABLE_PATTERN.findall(sql)})
        _pending_provenance.append({"source": "sql_fallback", "tables": tables})
    return result


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_EXECUTORS = {
    "semantic_layer": _execute_semantic_layer,
    "get_dimension_values": _execute_get_dimension_values,
    "generate_chart": _execute_generate_chart,
    "query_database": _execute_query_database,
}


def execute_tool(name: str, tool_input: dict) -> Any:
    fn = _EXECUTORS.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        return fn(tool_input)
    except Exception as exc:
        return {"error": str(exc)}
