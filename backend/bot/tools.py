TOOLS = [
    {
        "name": "get_holdings",
        "description": (
            "Get current portfolio holdings: fund name, value, cost basis, unrealised gain/loss, "
            "and portfolio weight. Also includes cash balances. Use for questions about what is "
            "currently held, current values, gains or losses."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "account": {
                    "type": "string",
                    "enum": ["ISA", "SIPP"],
                    "description": "Filter to a single account. Omit for combined view across both accounts.",
                }
            },
        },
    },
    {
        "name": "get_portfolio_value",
        "description": (
            "Get total portfolio value over a date range. Returns monthly data points. "
            "Use for questions about what the portfolio was worth on a given date or over a period."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "from_date": {
                    "type": "string",
                    "description": "Start date YYYY-MM-DD. Defaults to 2017-01-01.",
                },
                "to_date": {
                    "type": "string",
                    "description": "End date YYYY-MM-DD. Defaults to today.",
                },
                "account": {
                    "type": "string",
                    "enum": ["ISA", "SIPP"],
                    "description": "Filter to a single account. Omit for combined view.",
                },
            },
        },
    },
    {
        "name": "get_contributions",
        "description": (
            "Get cumulative contributions vs portfolio value over time. Shows total invested, "
            "current value, and total growth (value minus contributions). Use for questions about "
            "how much has been invested, total growth, or money-weighted return."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "from_date": {
                    "type": "string",
                    "description": "Start date YYYY-MM-DD.",
                },
                "to_date": {
                    "type": "string",
                    "description": "End date YYYY-MM-DD. Defaults to today.",
                },
                "account": {
                    "type": "string",
                    "enum": ["ISA", "SIPP"],
                    "description": "Filter to a single account. Omit for combined view.",
                },
            },
        },
    },
    {
        "name": "get_portfolio_performance",
        "description": (
            "Get portfolio investment return (Modified Dietz, contribution-adjusted) indexed to 100 "
            "at the start date, plus FTSE100/S&P500/NASDAQ benchmarks indexed to the same start. "
            "Also returns trailing 12m and 36m Sharpe ratios. Use for questions about returns, "
            "performance vs benchmarks, or risk-adjusted performance. "
            "Set full_series=true when you intend to pass the data to generate_chart."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "from_date": {
                    "type": "string",
                    "description": "Start date YYYY-MM-DD.",
                },
                "to_date": {
                    "type": "string",
                    "description": "End date YYYY-MM-DD. Defaults to today.",
                },
                "account": {
                    "type": "string",
                    "enum": ["ISA", "SIPP"],
                    "description": "Filter to a single account. Omit for combined view.",
                },
                "full_series": {
                    "type": "boolean",
                    "description": "If true, return the full monthly series for all lines instead of just start/end summaries. Required when passing data to generate_chart.",
                },
            },
        },
    },
    {
        "name": "get_portfolio_allocation",
        "description": (
            "Get portfolio allocation by fund as of a given date, showing units held, price, "
            "value, and percentage weight. Use for questions about fund weights or current allocation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "as_of": {
                    "type": "string",
                    "description": "Date YYYY-MM-DD. Defaults to latest available price date.",
                },
                "account": {
                    "type": "string",
                    "enum": ["ISA", "SIPP"],
                    "description": "Filter to a single account. Omit for combined view.",
                },
            },
        },
    },
    {
        "name": "list_funds",
        "description": (
            "List all funds in the portfolio (including historical ones no longer held). "
            "Use to look up fund IDs before calling get_fund_performance."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "active_only": {
                    "type": "boolean",
                    "description": "If true, only return currently held funds. Default false.",
                }
            },
        },
    },
    {
        "name": "get_fund_performance",
        "description": (
            "Get NAV performance for a specific fund indexed to 100 at the start date, "
            "with FTSE100/S&P500/NASDAQ benchmark overlays. Use for questions about how a "
            "particular fund has performed. Call list_funds first if the fund ID is unknown."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "fund_id": {
                    "type": "string",
                    "description": "Fund ID from list_funds.",
                },
                "from_date": {
                    "type": "string",
                    "description": "Start date YYYY-MM-DD. Defaults to first investment date.",
                },
                "to_date": {
                    "type": "string",
                    "description": "End date YYYY-MM-DD. Defaults to today.",
                },
            },
            "required": ["fund_id"],
        },
    },
    {
        "name": "list_transactions",
        "description": (
            "List transactions with optional filters. Use for questions about buys, sells, "
            "contributions, fees, switches, or transaction history."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "account": {"type": "string", "enum": ["ISA", "SIPP"]},
                "fund_id": {"type": "string", "description": "Filter by fund ID."},
                "tx_type": {
                    "type": "string",
                    "enum": [
                        "BUY",
                        "SELL",
                        "SWITCH_IN",
                        "SWITCH_OUT",
                        "CONTRIBUTION",
                        "FEE",
                        "INTEREST",
                        "REBATE",
                        "TRANSFER",
                    ],
                },
                "from_date": {
                    "type": "string",
                    "description": "Start date YYYY-MM-DD.",
                },
                "to_date": {"type": "string", "description": "End date YYYY-MM-DD."},
                "page": {"type": "integer", "description": "Page number (default 1)."},
                "per_page": {
                    "type": "integer",
                    "description": "Results per page (default 50, max 200).",
                },
            },
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
            "LAST RESORT ONLY — run a read-only SQL SELECT against the database when none of the "
            "other tools can answer the question. Only SELECT statements are permitted. "
            "Only tables whose names start with 'mart_' or 'dim_' may be referenced."
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
                    "description": "Why none of the named API tools could answer this question.",
                },
            },
            "required": ["sql", "explanation"],
        },
    },
]
