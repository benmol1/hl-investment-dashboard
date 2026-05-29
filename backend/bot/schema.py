"""
Utilities for surfacing dbt model schema context to Claude on demand.

build_schema_index() — compact one-liner per model for the system prompt.
get_model_schema(name) — full column reference for a named model, called as a tool.
"""

from pathlib import Path

import yaml

_DBT_MODELS_DIR = Path(__file__).parent.parent.parent / "dbt" / "models"
_SCANNED_LAYERS = ["marts", "core"]


def _parse_yml_files() -> dict:
    models: dict = {}
    for layer in _SCANNED_LAYERS:
        layer_dir = _DBT_MODELS_DIR / layer
        for yml_path in sorted(layer_dir.glob("*.yml")):
            try:
                with open(yml_path) as fh:
                    data = yaml.safe_load(fh)
                for model in data.get("models", []):
                    name = model.get("name")
                    if name:
                        models[name] = model
            except Exception:
                pass
    return models


# Parsed once at import time; YAML files don't change at runtime.
_MODELS: dict = _parse_yml_files()


def build_schema_index() -> str:
    """Return a compact bullet list of model names + one-line descriptions."""
    lines = []
    for name, model in sorted(_MODELS.items()):
        desc = (model.get("description") or "").replace("\n", " ").strip()
        # First sentence only (split on ". " to avoid over-capturing)
        parts = desc.split(". ")
        first = parts[0] + ("." if len(parts) > 1 else "")
        if len(first) > 120:
            first = first[:117] + "..."
        lines.append(f"- {name}: {first or '(no description)'}")
    return "\n".join(lines)


def get_model_schema(name: str) -> str:
    """Return a formatted column reference for *name*, or a helpful error."""
    model = _MODELS.get(name)
    if model is None:
        available = ", ".join(sorted(_MODELS.keys()))
        return f"Model '{name}' not found. Available models: {available}"

    desc = (model.get("description") or "").strip()
    columns = model.get("columns", [])

    lines = [f"## {name}", "", desc, "", "**Columns:**"]
    if columns:
        for col in columns:
            col_name = col.get("name", "")
            col_desc = (col.get("description") or "").replace("\n", " ").strip()
            lines.append(f"- `{col_name}`: {col_desc}")
    else:
        lines.append("(no column definitions in YAML)")

    return "\n".join(lines)
