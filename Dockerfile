FROM astrocrpublic.azurecr.io/runtime:3.3-7-python-3.12

# dbt gets its own virtualenv so its pins never fight Airflow's.
# Python 3.12 image: dbt's dependencies do not support 3.14 yet.
RUN python -m venv dbt_venv && \
    dbt_venv/bin/pip install --no-cache-dir "dbt-core>=1.8,<1.10" "dbt-bigquery>=1.8,<1.10"
