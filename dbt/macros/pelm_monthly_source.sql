{#
  Rows of the hand-maintained PELM valuations file, or an empty result with the same columns if
  the file does not exist (e.g. a fresh clone, or a deployment that doesn't track PELM).

  It is read straight from disk rather than loaded as a seed because the file is personal data
  that lives in the bind-mounted data/ folder: gitignored, and editable on the server without
  rebuilding the image. The path is relative to the dbt project directory, like profiles.yml.
  Override with --vars '{pelm_monthly_path: /some/file.csv}'.
#}
{% macro pelm_monthly_source() %}
    {%- set path = var('pelm_monthly_path', '../data/pelm/pelm_monthly.csv') -%}
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
                'month_end_date': 'DATE',
                'value_gbp': 'DOUBLE',
                'external_flow_gbp': 'DOUBLE'
            }
        )
    {%- else -%}
        select
            cast(null as date)   as month_end_date,
            cast(null as double) as value_gbp,
            cast(null as double) as external_flow_gbp
        where false
    {%- endif -%}
{% endmacro %}
