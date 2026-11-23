{#
  Readers for the hand-maintained PELM Will Trust files in data/pelm/. Each returns the file's
  rows, or an empty result with the same columns if the file does not exist (e.g. a fresh clone,
  or a deployment that doesn't track PELM).

  They are read straight from disk rather than loaded as seeds because the files are personal
  data that live in the bind-mounted data/ folder: gitignored, and editable on the server without
  rebuilding the image. Paths are relative to the dbt project directory, like profiles.yml.
  Override with --vars '{pelm_monthly_path: /some/file.csv}' (or pelm_transactions_path).
#}

{% macro pelm_read_csv(path, columns) %}
    {%- set file_exists = false -%}
    {%- if execute -%}
        {%- set found = run_query("select count(*) from glob('" ~ path ~ "')") -%}
        {%- set file_exists = found.columns[0].values()[0] > 0 -%}
    {%- endif -%}

    {%- if file_exists -%}
        select * from read_csv(
            '{{ path }}',
            header = true,
            columns = {
                {%- for name, type in columns.items() %}
                '{{ name }}': '{{ type }}'{{ ',' if not loop.last }}
                {%- endfor %}
            }
        )
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
        {'month_end_date': 'DATE', 'value_gbp': 'DOUBLE', 'external_flow_gbp': 'DOUBLE'}
    ) }}
{% endmacro %}


{% macro pelm_transactions_source() %}
    {{ pelm_read_csv(
        var('pelm_transactions_path', '../data/pelm/pelm_transactions.csv'),
        {
            'tx_date': 'DATE', 'reference': 'VARCHAR', 'tx_type': 'VARCHAR',
            'security': 'VARCHAR', 'quantity': 'DOUBLE', 'amount_gbp': 'DOUBLE',
            'notes': 'VARCHAR'
        }
    ) }}
{% endmacro %}
