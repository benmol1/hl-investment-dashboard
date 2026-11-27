{#
  Readers for the PELM Will Trust files in data/pelm/. Each returns the file's rows, or an empty
  result with the same columns if the file does not exist (e.g. a fresh clone, or a deployment
  that doesn't track PELM).

  They are read straight from disk rather than loaded as seeds because the files are personal
  data that live in the bind-mounted data/ folder: gitignored, and editable on the server without
  rebuilding the image. Paths are relative to the dbt project directory, like profiles.yml.
  Override with --vars, e.g. '{pelm_monthly_path: /some/file.csv}'.

  Columns are matched by name. A declared column missing from the file comes back as null, and
  extra columns in the file are ignored, so a file written by an older version of the parser (or
  an older pelm_monthly.csv with its retired external_flow_gbp column) still builds.
#}

{% macro pelm_read_csv(path, columns) %}
    {%- set present = [] -%}
    {%- if execute -%}
        {%- set found = run_query("select count(*) from glob('" ~ path ~ "')") -%}
        {%- if found.columns[0].values()[0] > 0 -%}
            {%- set described = run_query(
                "select column_name from (describe select * from read_csv('" ~ path ~ "', header = true, all_varchar = true))"
            ) -%}
            {%- for name in described.columns[0].values() -%}
                {%- do present.append(name) -%}
            {%- endfor -%}
        {%- endif -%}
    {%- endif -%}

    {%- if present -%}
        select
            {%- for name, type in columns.items() %}
            {%- if name in present %}
            cast(nullif(trim("{{ name }}"), '') as {{ type }}) as {{ name }}{{ ',' if not loop.last }}
            {%- else %}
            cast(null as {{ type }}) as {{ name }}{{ ',' if not loop.last }}
            {%- endif %}
            {%- endfor %}
        from read_csv('{{ path }}', header = true, all_varchar = true)
    {%- else -%}
        select
            {%- for name, type in columns.items() %}
            cast(null as {{ type }}) as {{ name }}{{ ',' if not loop.last }}
            {%- endfor %}
        where false
    {%- endif -%}
{% endmacro %}


{% macro pelm_monthly_source() %}
    {{ pelm_read_csv(
        var('pelm_monthly_path', '../data/pelm/pelm_monthly.csv'),
        {'month_end_date': 'DATE', 'value_gbp': 'DOUBLE'}
    ) }}
{% endmacro %}


{% macro pelm_transactions_source() %}
    {{ pelm_read_csv(
        var('pelm_transactions_path', '../data/pelm/pelm_transactions.csv'),
        {
            'ledger': 'VARCHAR', 'tx_date': 'DATE', 'reference': 'VARCHAR', 'tx_type': 'VARCHAR',
            'security': 'VARCHAR', 'quantity': 'DOUBLE', 'amount_gbp': 'DOUBLE',
            'notes': 'VARCHAR'
        }
    ) }}
{% endmacro %}


{% macro pelm_ledger_coverage_source() %}
    {{ pelm_read_csv(
        var('pelm_ledger_coverage_path', '../data/pelm/pelm_ledger_coverage.csv'),
        {
            'ledger': 'VARCHAR', 'period_start': 'DATE', 'period_end': 'DATE',
            'opening_gbp': 'DOUBLE', 'closing_gbp': 'DOUBLE', 'source_file': 'VARCHAR'
        }
    ) }}
{% endmacro %}


{% macro pelm_reported_returns_source() %}
    {{ pelm_read_csv(
        var('pelm_reported_returns_path', '../data/pelm/pelm_reported_returns.csv'),
        {
            'period_start': 'DATE', 'period_end': 'DATE', 'return_pct': 'DOUBLE',
            'source': 'VARCHAR'
        }
    ) }}
{% endmacro %}
