from .semantic import GRAINS, load_registry

_REGISTRY = load_registry()

TOOLS = [
    {
        "name": "query_metrics",
        "description": (
            "PRIMARY TOOL — query the semantic layer. Pick a semantic model, the metrics to "
            "compute, and optionally dimensions to group by, filters, and a date range; the "
            "layer compiles this into SQL and returns the rows. The full catalogue of models, "
            "dimensions and metrics is in the system prompt. Time dimensions can be grouped or "
            "filtered at a grain using a double-underscore suffix, e.g. trade_date__month, "
            "valuation_date__financial_year. To compare across models (e.g. portfolio vs "
            "benchmark), call this tool once per model."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "model": {
                    "type": "string",
                    "enum": _REGISTRY.model_names,
                    "description": "Semantic model to query (see catalogue in system prompt).",
                },
                "metrics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "One or more metric names from the chosen model.",
                },
                "group_by": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Dimension names to group by. Time dimensions accept a grain suffix: "
                        "__" + ", __".join(GRAINS) + ". Omit for a single total row."
                    ),
                },
                "filters": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "field": {
                                "type": "string",
                                "description": "Dimension name, optionally with a time grain suffix (e.g. trade_date__year).",
                            },
                            "op": {
                                "type": "string",
                                "enum": ["eq", "neq", "gt", "gte", "lt", "lte", "in", "contains"],
                            },
                            "value": {
                                "description": (
                                    "Literal to compare against. Use a list for 'in'. Dates as "
                                    "YYYY-MM-DD strings. Filter values must match the dimension's "
                                    "exact values (see catalogue, or get_dimension_values)."
                                ),
                            },
                        },
                        "required": ["field", "op", "value"],
                    },
                },
                "time_range": {
                    "type": "object",
                    "properties": {
                        "start": {"type": "string", "description": "YYYY-MM-DD inclusive."},
                        "end": {"type": "string", "description": "YYYY-MM-DD inclusive."},
                    },
                    "description": (
                        "Date range on the model's time dimension. For point-in-time values of "
                        "balance metrics (portfolio value, units), set only 'end' — the latest "
                        "snapshot on or before that date is used. Omit entirely for current values."
                    ),
                },
                "order_by": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "field": {"type": "string", "description": "A selected metric or group_by field."},
                            "direction": {"type": "string", "enum": ["asc", "desc"]},
                        },
                        "required": ["field"],
                    },
                },
                "limit": {"type": "integer", "description": "Max rows (default 200)."},
            },
            "required": ["model", "metrics"],
        },
    },
    {
        "name": "get_dimension_values",
        "description": (
            "List the distinct values of a dimension (e.g. exact fund names) so filters can use "
            "exact matches. Only needed when the catalogue in the system prompt doesn't already "
            "list the values."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "model": {
                    "type": "string",
                    "enum": _REGISTRY.model_names,
                },
                "dimension": {
                    "type": "string",
                    "description": "Dimension name on that model.",
                },
            },
            "required": ["model", "dimension"],
        },
    },
    {
        "name": "generate_chart",
        "description": (
            "Render a chart as an image and send it to the user. Call this AFTER fetching data "
            "with another tool. Supported types: 'line' (time series, supports multiple series), "
            "'bar' (vertical bars, single series), 'donut' (allocation pie)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "chart_type": {
                    "type": "string",
                    "enum": ["line", "bar", "donut"],
                    "description": "'line' for time-series; 'bar' for vertical bar chart; 'donut' for allocation.",
                },
                "title": {
                    "type": "string",
                    "description": "Chart title shown at the top.",
                },
                "caption": {
                    "type": "string",
                    "description": "Optional small subtitle shown below the chart, e.g. 'Indexed to 100 at start date' or 'Source: Morningstar'.",
                },
                "data": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Flat array of data point objects already fetched from another tool.",
                },
                "x_key": {
                    "type": "string",
                    "description": "(line, bar) Key in each data object to use as the x-axis (usually a date string).",
                },
                "series": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {
                                "type": "string",
                                "description": "Legend label for this series.",
                            },
                            "y_key": {
                                "type": "string",
                                "description": "Key in each data object for this series' y values.",
                            },
                        },
                        "required": ["label", "y_key"],
                    },
                    "description": "(line) One entry per line to draw. Use multiple entries for a comparison chart, e.g. portfolio vs benchmarks.",
                },
                "y_key": {
                    "type": "string",
                    "description": "(bar, or line shorthand for a single unlabelled series) Key for y-axis values.",
                },
                "y_label": {
                    "type": "string",
                    "description": "(line, bar) Label for the y-axis.",
                },
                "y_format": {
                    "type": "string",
                    "enum": ["number", "currency", "percent"],
                    "description": "How to format y-axis tick labels. 'currency' adds £ and rounds to whole pounds. 'percent' appends %. Default: 'number'.",
                },
                "label_key": {
                    "type": "string",
                    "description": "(donut) Key in each data object to use as the slice label.",
                },
                "value_key": {
                    "type": "string",
                    "description": "(donut) Key in each data object to use as the slice value.",
                },
            },
            "required": ["chart_type", "data"],
        },
    },
    {
        "name": "query_database",
        "description": (
            "LAST RESORT ONLY — run a read-only SQL SELECT against the database when the "
            "semantic layer (query_metrics) cannot express the question. Only SELECT statements "
            "are permitted. Only tables whose names start with 'mart_' or 'dim_' may be "
            "referenced. Always try query_metrics first."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "A SELECT-only SQL query referencing only mart_ or dim_ tables.",
                },
                "explanation": {
                    "type": "string",
                    "description": "Why the semantic layer could not answer this question.",
                },
            },
            "required": ["sql", "explanation"],
        },
    },
]
