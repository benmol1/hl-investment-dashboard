"""Render the semantic layer catalogue for the bot's system prompt.

The full catalogue is injected into the system prompt (rather than served via
a discovery tool) so the model has global awareness of what is answerable
without spending a tool round-trip. Dynamic enum values (fund names) are read
from the warehouse at startup, with a silent fallback when the database is
unavailable (tests, CI).
"""

import logging
from pathlib import Path

import duckdb

from .compiler import GRAINS
from .loader import Registry, SemanticModel, load_registry

logger = logging.getLogger(__name__)


def _dimension_values(db_path: Path | None, query: str) -> tuple[str, ...]:
    if db_path is None:
        return ()
    try:
        con = duckdb.connect(str(db_path), read_only=True)
        try:
            return tuple(str(r[0]) for r in con.execute(query).fetchall()[:50])
        finally:
            con.close()
    except Exception as exc:  # missing DB/table must never break the bot
        logger.warning("Could not load dimension values: %s", exc)
        return ()


def _render_model(model: SemanticModel, db_path: Path | None) -> str:
    lines = [f"### {model.name}", model.description.strip()]
    if model.time_dimension:
        lines.append(
            f"Time dimension: {model.time_dimension.name} "
            f"(grains: {', '.join(GRAINS)} via suffix, e.g. "
            f"{model.time_dimension.name}__month)"
        )
    lines.append("Dimensions:")
    for d in model.dimensions:
        if d.is_time:
            continue
        values = d.values
        if not values and d.values_query:
            values = _dimension_values(db_path, d.values_query)
        suffix = f" Values: {', '.join(values)}" if values else ""
        lines.append(f"- {d.name}: {d.description.strip()}{suffix}")
    lines.append("Metrics:")
    for m in model.measures:
        lines.append(f"- {m.name} ({m.agg}): {m.description.strip()}")
    for dm in model.metrics:
        lines.append(f"- {dm.name} (derived): {dm.description.strip()}")
    return "\n".join(lines)


def render_catalog(db_path: Path | None = None, registry: Registry | None = None) -> str:
    registry = registry or load_registry()
    return "\n\n".join(_render_model(m, db_path) for m in registry.models)
