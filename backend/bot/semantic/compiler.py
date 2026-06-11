"""Compile structured semantic queries into DuckDB SQL.

The only strings that reach the generated SQL are (a) hand-curated
expressions from definitions.yml and (b) literal filter values, which are
validated and escaped here. Identifiers supplied by the caller (metrics,
dimensions, grains, order keys) must resolve against the semantic model or
the query is rejected.
"""

import re
from dataclasses import dataclass

from .loader import Dimension, DerivedMetric, Measure, SemanticModel, _MEASURE_REF

GRAINS = ("day", "month", "quarter", "year", "financial_year")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_OPS = {
    "eq": "=", "=": "=",
    "neq": "!=", "!=": "!=",
    "gt": ">", ">": ">",
    "gte": ">=", ">=": ">=",
    "lt": "<", "<": "<",
    "lte": "<=", "<=": "<=",
    "in": "IN",
    "contains": "ILIKE",
}

DEFAULT_LIMIT = 200
MAX_LIMIT = 500


class SemanticQueryError(Exception):
    """The requested query is invalid against the semantic model."""


@dataclass(frozen=True)
class CompiledQuery:
    sql: str
    columns: list[str]


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------


def _q(name: str) -> str:
    """Quote an output column alias."""
    return '"' + name.replace('"', "") + '"'


def _literal(value) -> str:
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    raise SemanticQueryError(f"Unsupported filter value type: {type(value).__name__}")


def _grain_expr(date_expr: str, grain: str) -> str:
    e = f"CAST({date_expr} AS DATE)"
    if grain == "day":
        return e
    if grain == "month":
        return f"strftime({e}, '%Y-%m')"
    if grain == "quarter":
        return f"CAST(year({e}) AS VARCHAR) || '-Q' || CAST(quarter({e}) AS VARCHAR)"
    if grain == "year":
        return f"year({e})"
    if grain == "financial_year":
        # UK tax year, labelled by its end year: FY26 = April 2025 - March 2026.
        return (
            f"'FY' || right('0' || CAST((year({e}) + CASE WHEN month({e}) >= 4 "
            f"THEN 1 ELSE 0 END) % 100 AS VARCHAR), 2)"
        )
    raise SemanticQueryError(f"Unknown time grain '{grain}'. Valid grains: {', '.join(GRAINS)}")


@dataclass(frozen=True)
class _FieldRef:
    """A reference to a dimension, optionally with a time grain (dunder syntax)."""

    ref: str  # as written, e.g. "trade_date__month"
    dimension: Dimension
    grain: str | None

    @property
    def expr(self) -> str:
        if self.grain:
            return _grain_expr(self.dimension.expr, self.grain)
        if self.dimension.is_time:
            return f"CAST({self.dimension.expr} AS DATE)"
        return self.dimension.expr


def _parse_field(model: SemanticModel, ref) -> _FieldRef:
    if not isinstance(ref, str):
        raise SemanticQueryError(f"Field reference must be a string, got {ref!r}")
    name, _, grain = ref.partition("__")
    dim = model.dimension(name)
    if dim is None:
        available = [d.name for d in model.dimensions]
        raise SemanticQueryError(
            f"Unknown dimension '{name}' on model '{model.name}'. Available: {', '.join(available)}"
        )
    if grain:
        if not dim.is_time:
            raise SemanticQueryError(f"'{name}' is not a time dimension; grain '__{grain}' is not allowed")
        if grain not in GRAINS:
            raise SemanticQueryError(f"Unknown grain '{grain}'. Valid grains: {', '.join(GRAINS)}")
        return _FieldRef(ref=ref, dimension=dim, grain=grain)
    return _FieldRef(ref=ref, dimension=dim, grain=None)


def _compile_filter(model: SemanticModel, raw) -> tuple[str, str]:
    """Returns (sql_condition, human_readable)."""
    if not isinstance(raw, dict) or not {"field", "op", "value"} <= set(raw):
        raise SemanticQueryError("Each filter needs 'field', 'op' and 'value' keys")
    field = _parse_field(model, raw["field"])
    op_key = str(raw["op"]).lower()
    if op_key not in _OPS:
        raise SemanticQueryError(f"Unknown filter op '{raw['op']}'. Valid: {', '.join(sorted(set(_OPS)))}")
    op = _OPS[op_key]
    value = raw["value"]

    lhs = field.expr
    if op == "IN":
        if not isinstance(value, list) or not value:
            raise SemanticQueryError("'in' filter requires a non-empty list value")
        rhs = "(" + ", ".join(_literal(v) for v in value) + ")"
        human = f"{field.ref} in [{', '.join(str(v) for v in value)}]"
        return f"{lhs} IN {rhs}", human
    if op == "ILIKE":
        if not isinstance(value, str):
            raise SemanticQueryError("'contains' filter requires a string value")
        return f"{lhs} ILIKE {_literal('%' + value + '%')}", f"{field.ref} contains '{value}'"

    if field.dimension.is_time and field.grain is None:
        if not isinstance(value, str) or not _DATE_RE.match(value):
            raise SemanticQueryError(
                f"Filter on time dimension '{field.ref}' requires a YYYY-MM-DD date string"
            )
        return f"{lhs} {op} DATE {_literal(value)}", f"{field.ref} {op} {value}"
    return f"{lhs} {op} {_literal(value)}", f"{field.ref} {op} {value}"


def _needed_joins(model: SemanticModel, fragments: list[str]) -> str:
    blob = "\n".join(fragments)
    sql = f"{model.table} AS base"
    for join in model.joins:
        if re.search(rf"\b{re.escape(join.alias)}\.", blob):
            sql += f"\nLEFT JOIN {join.table} AS {join.alias} ON {join.on}"
    return sql


def _agg_sql(measure: Measure) -> str:
    col = _q(f"_m_{measure.name}")
    if measure.agg == "count":
        core = f"COUNT({col})"
    elif measure.agg == "count_distinct":
        core = f"COUNT(DISTINCT {col})"
    elif measure.agg == "last":
        core = f'arg_max({col}, {_q("_t")})'
    else:
        core = f"{measure.agg.upper()}({col})"
    conditions = []
    if measure.filter:
        conditions.append(_q(f"_f_{measure.name}"))
    if measure.agg == "last":
        conditions.append(f"{col} IS NOT NULL")
    if conditions:
        core += " FILTER (WHERE " + " AND ".join(conditions) + ")"
    return f"{core} AS {_q(measure.name)}"


def compile_dimension_values(model: SemanticModel, dimension_name: str) -> str:
    """SELECT DISTINCT values of a categorical dimension."""
    dim = model.dimension(dimension_name)
    if dim is None or dim.is_time:
        available = [d.name for d in model.dimensions if not d.is_time]
        raise SemanticQueryError(
            f"Unknown dimension '{dimension_name}' on model '{model.name}'. "
            f"Available: {', '.join(available)}"
        )
    from_sql = _needed_joins(model, [dim.expr])
    return (
        f"SELECT DISTINCT {dim.expr} AS {_q(dim.name)} FROM {from_sql}\n"
        f"WHERE {dim.expr} IS NOT NULL ORDER BY 1 LIMIT 200"
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def compile_query(model: SemanticModel, params: dict) -> tuple[CompiledQuery, dict]:
    """Compile query params into SQL. Returns (compiled, provenance)."""

    # --- metrics ---------------------------------------------------------
    requested = params.get("metrics")
    if not isinstance(requested, list) or not requested:
        raise SemanticQueryError("'metrics' must be a non-empty list")
    measures: list[Measure] = []
    derived: list[DerivedMetric] = []
    for name in requested:
        m = model.measure(name) if isinstance(name, str) else None
        dm = model.metric(name) if isinstance(name, str) else None
        if m:
            measures.append(m)
        elif dm:
            derived.append(dm)
        else:
            raise SemanticQueryError(
                f"Unknown metric '{name}' on model '{model.name}'. Available: {', '.join(model.metric_names)}"
            )
    hidden = [
        model.measure(req)
        for dm in derived
        for req in dm.required_measures
        if model.measure(req) not in measures
    ]
    all_measures = list(dict.fromkeys(measures + hidden))

    # --- group by --------------------------------------------------------
    group_refs = [_parse_field(model, r) for r in params.get("group_by") or []]
    if len({g.ref for g in group_refs}) != len(group_refs):
        raise SemanticQueryError("Duplicate fields in group_by")

    # --- filters / time range --------------------------------------------
    where_parts: list[str] = []
    human_filters: list[str] = []
    for raw in params.get("filters") or []:
        cond, human = _compile_filter(model, raw)
        where_parts.append(cond)
        human_filters.append(human)

    time_dim = model.time_dimension
    time_range = params.get("time_range") or {}
    human_range = None
    if time_range:
        if time_dim is None:
            raise SemanticQueryError(f"Model '{model.name}' has no time dimension; time_range is not supported")
        start, end = time_range.get("start"), time_range.get("end")
        for label, v in (("start", start), ("end", end)):
            if v is not None and (not isinstance(v, str) or not _DATE_RE.match(v)):
                raise SemanticQueryError(f"time_range.{label} must be a YYYY-MM-DD date string")
        date_expr = f"CAST({time_dim.expr} AS DATE)"
        if start:
            where_parts.append(f"{date_expr} >= DATE {_literal(start)}")
        if end:
            where_parts.append(f"{date_expr} <= DATE {_literal(end)}")
        if start or end:
            human_range = f"{start or '…'} → {end or '…'}"

    # --- base CTE ---------------------------------------------------------
    needs_time_col = any(m.agg == "last" or m.additivity == "semi" for m in all_measures)
    select_items: list[str] = []
    group_cols: list[str] = []
    for ref in group_refs:
        select_items.append(f"{ref.expr} AS {_q(ref.ref)}")
        group_cols.append(_q(ref.ref))
    for m in all_measures:
        raw_expr = "1" if m.expr == "*" else m.expr
        select_items.append(f"{raw_expr} AS {_q('_m_' + m.name)}")
        if m.filter:
            select_items.append(f"({m.filter}) AS {_q('_f_' + m.name)}")
    if needs_time_col:
        select_items.append(f"CAST({time_dim.expr} AS DATE) AS {_q('_t')}")

    fragments = [i for i in select_items] + where_parts
    from_sql = _needed_joins(model, fragments)
    base_sql = "SELECT\n    " + ",\n    ".join(select_items) + f"\nFROM {from_sql}"
    if where_parts:
        base_sql += "\nWHERE " + "\n  AND ".join(where_parts)

    # --- aggregation (with semi-additive snapshotting) ---------------------
    semi = [m for m in all_measures if m.additivity == "semi"]
    additive = [m for m in all_measures if m.additivity != "semi"]
    group_list = ", ".join(group_cols)

    def agg_select(source: str, ms: list[Measure]) -> str:
        cols = group_cols + [_agg_sql(m) for m in ms]
        sql = "SELECT " + ", ".join(cols) + f" FROM {source}"
        if group_cols:
            sql += f" GROUP BY {group_list}"
        return sql

    ctes = [f"base AS (\n{base_sql}\n)"]
    if semi:
        partition = f"PARTITION BY {group_list}" if group_cols else ""
        ctes.append(
            "snap AS (\nSELECT * FROM base "
            f"QUALIFY {_q('_t')} = MAX({_q('_t')}) OVER ({partition})\n)"
        )

    if semi and additive:
        ctes.append(f"agg_add AS (\n{agg_select('base', additive)}\n)")
        ctes.append(f"agg_semi AS (\n{agg_select('snap', semi)}\n)")
        if group_cols:
            joined = f"agg_add FULL JOIN agg_semi USING ({group_list})"
        else:
            joined = "agg_add CROSS JOIN agg_semi"
        ctes.append(f"agg AS (\nSELECT * FROM {joined}\n)")
    elif semi:
        ctes.append(f"agg AS (\n{agg_select('snap', semi)}\n)")
    else:
        ctes.append(f"agg AS (\n{agg_select('base', additive)}\n)")

    # --- final select: requested fields + derived metrics ------------------
    out_cols = [g.ref for g in group_refs] + [str(n) for n in requested]
    item_by_name = {m.name: _q(m.name) for m in measures}
    for dm in derived:
        expr = _MEASURE_REF.sub(lambda match: _q(match.group(1)), dm.expr)
        item_by_name[dm.name] = f"{expr} AS {_q(dm.name)}"
    final_items = [_q(g.ref) for g in group_refs] + [item_by_name[n] for n in requested]

    sql = "WITH " + ",\n".join(ctes) + "\nSELECT " + ", ".join(final_items) + " FROM agg"

    # --- order / limit ------------------------------------------------------
    order_parts: list[str] = []
    for ob in params.get("order_by") or []:
        if not isinstance(ob, dict) or "field" not in ob:
            raise SemanticQueryError("Each order_by entry needs a 'field' key")
        f = ob["field"]
        if f not in out_cols:
            raise SemanticQueryError(
                f"order_by field '{f}' is not in the selected columns ({', '.join(out_cols)})"
            )
        direction = str(ob.get("direction", "asc")).lower()
        if direction not in ("asc", "desc"):
            raise SemanticQueryError("order_by direction must be 'asc' or 'desc'")
        order_parts.append(f"{_q(f)} {direction.upper()}")
    if not order_parts:
        time_groups = [g for g in group_refs if g.dimension.is_time]
        if time_groups:
            order_parts = [f"{_q(time_groups[0].ref)} ASC"]
    if order_parts:
        sql += "\nORDER BY " + ", ".join(order_parts)

    limit = params.get("limit") or DEFAULT_LIMIT
    if not isinstance(limit, int) or limit < 1:
        raise SemanticQueryError("'limit' must be a positive integer")
    sql += f"\nLIMIT {min(limit, MAX_LIMIT)}"

    provenance = {
        "source": "semantic",
        "model": model.name,
        "metrics": [str(n) for n in requested],
        "group_by": [g.ref for g in group_refs],
        "filters": human_filters,
        "time_range": human_range,
    }
    return CompiledQuery(sql=sql, columns=out_cols), provenance
