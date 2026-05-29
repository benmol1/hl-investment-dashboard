TOOLS = [
    {
        "name": "get_model_schema",
        "description": (
            "Fetch the full column reference (names, types, descriptions) for a named dbt model. "
            "Call this before writing any SQL to confirm column names and understand the grain. "
            "The system prompt lists all available model names — use one of those as the 'name' parameter."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Exact model name, e.g. 'mart_holdings_latest'.",
                }
            },
            "required": ["name"],
        },
    },
    {
        "name": "query_database",
        "description": (
            "Run a read-only SQL SELECT against the DuckDB database. "
            "This is the primary way to answer data questions. "
            "Call get_model_schema first to verify column names for each model you plan to query. "
            "Only SELECT statements are permitted; mart_, dim_, and fct_ tables may be referenced. "
            "fct_ tables use surrogate keys — always JOIN to the relevant dim_ tables to get "
            "human-readable names (see example queries in get_model_schema output)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "A SELECT-only SQL query referencing only mart_ or dim_ tables.",
                },
            },
            "required": ["sql"],
        },
    },
    {
        "name": "generate_chart",
        "description": (
            "Render a chart as an image and send it to the user. Call this AFTER fetching data "
            "with query_database. Supported types: 'line' (time series, supports multiple series), "
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
                    "description": "Optional small subtitle shown below the chart.",
                },
                "data": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Flat array of data point objects from query_database rows, keyed by column name.",
                },
                "x_key": {
                    "type": "string",
                    "description": "(line, bar) Key in each data object to use as the x-axis.",
                },
                "series": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string"},
                            "y_key": {"type": "string"},
                        },
                        "required": ["label", "y_key"],
                    },
                    "description": "(line) One entry per line to draw.",
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
                    "description": "How to format y-axis tick labels. 'currency' adds £. Default: 'number'.",
                },
                "label_key": {
                    "type": "string",
                    "description": "(donut) Key to use as the slice label.",
                },
                "value_key": {
                    "type": "string",
                    "description": "(donut) Key to use as the slice value.",
                },
            },
            "required": ["chart_type", "data"],
        },
    },
]
